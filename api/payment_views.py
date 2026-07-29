"""
Payment API Views for Paystack Integration

Handles payment initialization, verification, and webhooks.
"""

import json
import logging
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.cache import cache
import hmac
import hashlib

from .models import Payment, Booking
from .utils.paystack_utils import (
    initialize_payment_for_booking,
    verify_and_process_payment,
    PaystackError,
)
from .utils.auth_utils import rate_limit, log_security_event, get_client_ip

logger = logging.getLogger(__name__)


class FlexibleJWTAuthentication(BaseAuthentication):
    """Accept JWTs from the standard Authorization header or common alternate headers."""

    def __init__(self):
        self.jwt_auth = JWTAuthentication()

    def authenticate(self, request):
        django_request = getattr(request, '_request', None)
        if django_request is not None:
            django_user = getattr(django_request, 'user', None)
            if django_user is not None and getattr(django_user, 'is_authenticated', False):
                return django_user, None

        token = None
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(None, 1)[1].strip()
        elif auth_header:
            token = auth_header.strip()
        else:
            for header_name in ('HTTP_X_ACCESS_TOKEN', 'HTTP_X_AUTH_TOKEN', 'HTTP_ACCESS_TOKEN', 'HTTP_AUTH_TOKEN'):
                value = request.META.get(header_name, '')
                if value:
                    token = value.strip()
                    break

        if not token:
            for key in ('token', 'access_token', 'accessToken', 'jwt'):
                value = request.GET.get(key)
                if value:
                    token = value.strip()
                    break
            if not token:
                payload = request.data if hasattr(request, 'data') else {}
                if hasattr(payload, 'get'):
                    value = payload.get('token') or payload.get('access_token') or payload.get('accessToken')
                    if value:
                        token = str(value).strip()

        if not token:
            return None

        try:
            validated_token = self.jwt_auth.get_validated_token(token)
            user = self.jwt_auth.get_user(validated_token)
            return (user, validated_token)
        except Exception:
            return None


def get_authenticated_user(request):
    if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False):
        return request.user

    django_user = getattr(request._request, 'user', None) if hasattr(request, '_request') else None
    if django_user and getattr(django_user, 'is_authenticated', False):
        request.user = django_user
        return django_user

    for auth in (FlexibleJWTAuthentication(), SessionAuthentication()):
        try:
            user_auth_tuple = auth.authenticate(request)
            if user_auth_tuple is not None:
                user = user_auth_tuple[0]
                if user and getattr(user, 'is_authenticated', False):
                    request.user = user
                    return user
        except Exception:
            continue

    return None


@csrf_exempt
@api_view(['POST'])
@authentication_classes([FlexibleJWTAuthentication, SessionAuthentication])
@permission_classes([])
@rate_limit('payment_initialization')
def initialize_payment_view(request):
    """
    Initialize a payment for a booking.
    
    Request body:
    {
        "booking_id": 1,
        "amount": 5000.00  # Optional: use booking's estimated_cost if not provided
    }
    
    Response:
    {
        "ok": true,
        "payment_id": 1,
        "authorization_url": "https://checkout.paystack.com/...",
        "access_code": "...",
        "reference": "FUNDI-1-1",
        "message": "Payment initialized successfully"
    }
    """
    try:
        user = get_authenticated_user(request)
        if not user or not getattr(user, 'is_authenticated', False):
            return JsonResponse({'ok': False, 'message': 'Authentication required.'}, status=401)
        payload = request.data

        # Validate input
        booking_id = payload.get('booking_id')
        if not booking_id:
            return JsonResponse(
                {'ok': False, 'message': 'booking_id is required'},
                status=400
            )

        # Get booking
        try:
            booking = Booking.objects.get(id=booking_id, customer=user)
        except Booking.DoesNotExist:
            log_security_event(
                'payment_booking_not_found',
                user=user,
                ip=get_client_ip(request),
                booking_id=booking_id
            )
            return JsonResponse(
                {'ok': False, 'message': 'Booking not found'},
                status=404
            )

        # Check if payment already exists
        if hasattr(booking, 'payment'):
            if booking.payment.status in ['pending', 'processing']:
                return JsonResponse({
                    'ok': False,
                    'message': 'Payment already in progress for this booking',
                    'payment_id': booking.payment.id,
                }, status=400)

        # Validate booking status - can only pay if pending
        if booking.status != 'pending':
            return JsonResponse(
                {'ok': False, 'message': f'Booking must be in pending status to pay. Current status: {booking.status}'},
                status=400
            )

        # Validate callout fee
        if not booking.callout_fee or booking.callout_fee <= 0:
            return JsonResponse(
                {'ok': False, 'message': 'Booking callout fee must be greater than 0'},
                status=400
            )

        # Create and initialize payment with callout fee
        payment, init_response = initialize_payment_for_booking(booking, request)

        # Update booking status to pending_payment
        booking.status = 'pending_payment'
        booking.save(update_fields=['status'])

        log_security_event(
            'payment_initialized',
            user=user,
            ip=get_client_ip(request),
            booking_id=booking_id,
            payment_id=payment.id,
            amount=str(booking.callout_fee),
            payment_type='callout_fee'
        )

        return JsonResponse({
            'ok': True,
            'payment_id': payment.id,
            'authorization_url': init_response['authorization_url'],
            'access_code': init_response['access_code'],
            'reference': init_response['reference'],
            'message': 'Payment initialized successfully',
        }, status=201)

    except PaystackError as e:
        logger.error(f"Paystack error during payment initialization: {str(e)}")
        log_security_event(
            'payment_initialization_error',
            user=request.user,
            ip=get_client_ip(request),
            error=str(e)
        )
        return JsonResponse(
            {'ok': False, 'message': str(e)},
            status=400
        )
    except Exception as e:
        logger.error(f"Unexpected error during payment initialization: {str(e)}")
        log_security_event(
            'payment_initialization_exception',
            user=request.user,
            ip=get_client_ip(request),
            error=str(e)
        )
        return JsonResponse(
            {'ok': False, 'message': 'Payment initialization failed'},
            status=500
        )


@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([FlexibleJWTAuthentication, SessionAuthentication])
@permission_classes([])
def verify_payment_view(request, reference):
    """
    Verify a payment transaction.
    
    Response:
    {
        "ok": true,
        "payment_id": 1,
        "status": "success",
        "reference": "FUNDI-1-1",
        "message": "Payment verified successfully"
    }
    """
    try:
        user = get_authenticated_user(request)
        if not user or not getattr(user, 'is_authenticated', False):
            return JsonResponse({'ok': False, 'message': 'Authentication required.'}, status=401)

        # Verify payment
        payment, success, message = verify_and_process_payment(reference)

        # Check authorization
        if payment.user != user:
            log_security_event(
                'payment_verification_unauthorized',
                user=user,
                ip=get_client_ip(request),
                payment_id=payment.id
            )
            return JsonResponse(
                {'ok': False, 'message': 'Unauthorized'},
                status=403
            )

        log_security_event(
            'payment_verified',
            user=user,
            ip=get_client_ip(request),
            payment_id=payment.id,
            reference=reference,
            success=success
        )

        return JsonResponse({
            'ok': success,
            'payment_id': payment.id,
            'status': payment.status,
            'reference': reference,
            'message': message,
        }, status=200)

    except PaystackError as e:
        logger.error(f"Paystack error during payment verification: {str(e)}")
        log_security_event(
            'payment_verification_error',
            user=request.user,
            ip=get_client_ip(request),
            reference=reference,
            error=str(e)
        )
        return JsonResponse(
            {'ok': False, 'message': str(e)},
            status=400
        )
    except Exception as e:
        logger.error(f"Unexpected error during payment verification: {str(e)}")
        log_security_event(
            'payment_verification_exception',
            user=request.user,
            ip=get_client_ip(request),
            reference=reference,
            error=str(e)
        )
        return JsonResponse(
            {'ok': False, 'message': 'Payment verification failed'},
            status=500
        )


@csrf_exempt
@api_view(['GET'])
@permission_classes([])
def paystack_callback_view(request, reference):
    """
    Public callback endpoint for Paystack redirects.

    This endpoint verifies the payment using the reference and then redirects
    the user back to the frontend with the original query string preserved.
    """
    try:
        # Attempt to verify and process the payment
        payment, success, message = verify_and_process_payment(reference)
    except Exception as e:
        qs = request.META.get('QUERY_STRING', '')
        redirect_url = f"{settings.FRONTEND_URL}/payment/verify/0"
        if qs:
            redirect_url = f"{redirect_url}?{qs}"
        return redirect(redirect_url)

    qs = request.META.get('QUERY_STRING', '')
    redirect_url = f"{settings.FRONTEND_URL}/payment/verify/{payment.id}"
    if qs:
        redirect_url = f"{redirect_url}?{qs}"
    return redirect(redirect_url)


@csrf_exempt
@api_view(['GET'])
@authentication_classes([FlexibleJWTAuthentication, SessionAuthentication])
@permission_classes([])
def payment_status_view(request, payment_id):
    """
    Get payment status.
    
    Response:
    {
        "ok": true,
        "payment_id": 1,
        "status": "completed",
        "amount": 5000.00,
        "booking_id": 1,
        "created_at": "2024-07-24T10:00:00Z",
        "completed_at": "2024-07-24T10:05:00Z"
    }
    """
    try:
        user = get_authenticated_user(request)
        if not user or not getattr(user, 'is_authenticated', False):
            return JsonResponse({'ok': False, 'message': 'Authentication required.'}, status=401)

        # Get payment
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return JsonResponse(
                {'ok': False, 'message': 'Payment not found'},
                status=404
            )

        # Check authorization
        if payment.user != user:
            log_security_event(
                'payment_status_unauthorized',
                user=user,
                ip=get_client_ip(request),
                payment_id=payment_id
            )
            return JsonResponse(
                {'ok': False, 'message': 'Unauthorized'},
                status=403
            )

        return JsonResponse({
            'ok': True,
            'payment_id': payment.id,
            'status': payment.status,
            'amount': str(payment.amount),
            'booking_id': payment.booking.id,
            'payment_method': payment.payment_method,
            'created_at': payment.created_at.isoformat(),
            'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
        }, status=200)

    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        return JsonResponse(
            {'ok': False, 'message': 'Error retrieving payment status'},
            status=500
        )


@csrf_exempt
@require_http_methods(['POST'])
def paystack_webhook_view(request):
    """
    Paystack webhook for payment notifications.
    
    Paystack sends POST requests to this endpoint when payment status changes.
    """
    try:
        # Verify webhook signature
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        body = request.body.decode('utf-8')

        hash_object = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode(),
            body.encode(),
            hashlib.sha512
        )
        computed_signature = hash_object.hexdigest()

        if signature != computed_signature:
            logger.warning(f"Invalid webhook signature")
            return JsonResponse({'status': 'invalid_signature'}, status=401)

        # Parse webhook data
        data = json.loads(body)

        if data.get('event') == 'charge.success':
            event_data = data.get('data', {})
            reference = event_data.get('reference')
            status = event_data.get('status')

            logger.info(f"Webhook received for payment {reference}: {status}")

            # Verify and process payment
            try:
                payment, success, message = verify_and_process_payment(reference)

                if success:
                    log_security_event(
                        'payment_webhook_success',
                        payment_id=payment.id,
                        reference=reference
                    )
                else:
                    log_security_event(
                        'payment_webhook_failed',
                        payment_id=payment.id,
                        reference=reference,
                        message=message
                    )

                return JsonResponse({'status': 'success'}, status=200)

            except Exception as e:
                logger.error(f"Error processing webhook for {reference}: {str(e)}")
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

        return JsonResponse({'status': 'ok'}, status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@api_view(['GET'])
@authentication_classes([FlexibleJWTAuthentication, SessionAuthentication])
@permission_classes([])
def user_payments_view(request):
    """
    Get all payments for the current user.
    
    Query parameters:
    - status: Filter by status (pending, completed, failed, etc)
    - page: Page number (default: 1)
    
    Response:
    {
        "ok": true,
        "count": 5,
        "payments": [...]
    }
    """
    try:
        user = request.user
        status = request.query_params.get('status')

        # Get user payments
        payments = Payment.objects.filter(user=user)

        if status:
            payments = payments.filter(status=status)

        payments = payments.order_by('-created_at')

        # Paginate
        page = int(request.query_params.get('page', 1))
        page_size = 10
        start = (page - 1) * page_size
        end = start + page_size

        payments_list = []
        for payment in payments[start:end]:
            payments_list.append({
                'id': payment.id,
                'booking_id': payment.booking.id,
                'amount': str(payment.amount),
                'status': payment.status,
                'payment_method': payment.payment_method,
                'created_at': payment.created_at.isoformat(),
                'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
            })

        return JsonResponse({
            'ok': True,
            'count': payments.count(),
            'page': page,
            'page_size': page_size,
            'payments': payments_list,
        }, status=200)

    except Exception as e:
        logger.error(f"Error retrieving user payments: {str(e)}")
        return JsonResponse(
            {'ok': False, 'message': 'Error retrieving payments'},
            status=500
        )
