"""
Payment API Views for Paystack Integration

Handles payment initialization, verification, and webhooks.
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import JWTAuthentication
from django.core.cache import cache
import hmac
import hashlib

from .models import Payment, Booking
from .utils.paystack_utils import (
    initialize_payment_for_booking,
    verify_and_process_payment,
    PaystackError,
)
from .utils.rate_limiting import rate_limit
from .utils.security_logging import log_security_event, get_client_ip

logger = logging.getLogger(__name__)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
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
        user = request.user
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


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
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
        user = request.user

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


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
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
        user = request.user

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


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
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
