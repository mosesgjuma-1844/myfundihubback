"""
Paystack Payment Integration Utilities

Handles all Paystack API interactions for payment processing.
"""

import requests
import logging
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from .models import Payment, Transaction

logger = logging.getLogger(__name__)

# Paystack API endpoints
PAYSTACK_BASE_URL = 'https://api.paystack.co'
PAYSTACK_INITIALIZE_URL = f'{PAYSTACK_BASE_URL}/transaction/initialize'
PAYSTACK_VERIFY_URL = f'{PAYSTACK_BASE_URL}/transaction/verify'
PAYSTACK_CHARGE_URL = f'{PAYSTACK_BASE_URL}/charge'


class PaystackError(Exception):
    """Custom exception for Paystack-related errors."""
    pass


class PaystackClient:
    """Paystack API client for handling payment operations."""

    def __init__(self):
        """Initialize Paystack client with API key."""
        self.api_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        
        if not self.api_key or not self.public_key:
            raise PaystackError('Paystack API keys not configured in settings')

    def _get_headers(self):
        """Get request headers with authorization."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def initialize_payment(self, payment_obj, request=None):
        """
        Initialize a payment transaction with Paystack.
        
        Args:
            payment_obj: Payment model instance
            request: Django request object for callback URL
            
        Returns:
            dict: Initialization response with authorization_url
            
        Raises:
            PaystackError: If initialization fails
        """
        try:
            user = payment_obj.user
            booking = payment_obj.booking

            # Prepare callback URL
            callback_url = f"{settings.FRONTEND_URL}/payment/verify/{payment_obj.id}"

            payload = {
                'email': user.email,
                'amount': int(float(payment_obj.amount) * 100),  # Convert to kobo
                'reference': f"FUNDI-{payment_obj.id}-{payment_obj.booking.id}",
                'callback_url': callback_url,
                'metadata': {
                    'user_id': user.id,
                    'user_name': user.username,
                    'booking_id': booking.id,
                    'service_type': booking.get_service_type_display(),
                    'payment_id': payment_obj.id,
                },
            }

            response = requests.post(
                PAYSTACK_INITIALIZE_URL,
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if not data.get('status'):
                logger.error(f"Paystack initialization failed: {data.get('message')}")
                raise PaystackError(data.get('message', 'Payment initialization failed'))

            result = data['data']

            # Save Paystack reference details
            payment_obj.paystack_reference = result.get('reference')
            payment_obj.paystack_access_code = result.get('access_code')
            payment_obj.paystack_authorization_url = result.get('authorization_url')
            payment_obj.status = 'processing'
            payment_obj.save(update_fields=[
                'paystack_reference', 'paystack_access_code', 
                'paystack_authorization_url', 'status'
            ])

            # Log transaction
            Transaction.objects.create(
                payment=payment_obj,
                transaction_type='payment',
                amount=payment_obj.amount,
                paystack_reference=result.get('reference'),
                status='pending',
                response=data,
                notes='Payment initialization'
            )

            logger.info(f"Payment {payment_obj.id} initialized successfully")

            return {
                'success': True,
                'authorization_url': result.get('authorization_url'),
                'access_code': result.get('access_code'),
                'reference': result.get('reference'),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during payment initialization: {str(e)}")
            payment_obj.status = 'failed'
            payment_obj.save(update_fields=['status'])
            raise PaystackError(f"Payment initialization failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during payment initialization: {str(e)}")
            payment_obj.status = 'failed'
            payment_obj.save(update_fields=['status'])
            raise PaystackError(f"Payment initialization error: {str(e)}")

    def verify_payment(self, reference):
        """
        Verify a payment transaction with Paystack.
        
        Args:
            reference: Paystack transaction reference
            
        Returns:
            dict: Verification response with transaction details
            
        Raises:
            PaystackError: If verification fails
        """
        try:
            url = f"{PAYSTACK_VERIFY_URL}/{reference}"

            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if not data.get('status'):
                logger.error(f"Paystack verification failed for {reference}: {data.get('message')}")
                raise PaystackError(data.get('message', 'Payment verification failed'))

            result = data['data']

            logger.info(f"Payment {reference} verified successfully")

            return {
                'success': True,
                'status': result.get('status'),
                'reference': result.get('reference'),
                'amount': result.get('amount'),
                'customer': result.get('customer'),
                'authorization': result.get('authorization'),
                'raw_response': data,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during payment verification: {str(e)}")
            raise PaystackError(f"Payment verification failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during payment verification: {str(e)}")
            raise PaystackError(f"Payment verification error: {str(e)}")

    def handle_successful_payment(self, payment_obj, verification_data):
        """
        Handle successful payment - update payment and booking status.
        
        Args:
            payment_obj: Payment model instance
            verification_data: Response from verify_payment
            
        Returns:
            bool: True if successful
        """
        try:
            # Update payment
            payment_obj.mark_as_completed()

            # Update booking status
            booking = payment_obj.booking
            booking.status = 'assigned'
            booking.save(update_fields=['status'])

            # Log transaction
            Transaction.objects.create(
                payment=payment_obj,
                transaction_type='payment',
                amount=payment_obj.amount,
                paystack_reference=verification_data.get('reference'),
                paystack_transaction_id=verification_data.get('raw_response', {}).get('data', {}).get('id'),
                status='success',
                response=verification_data.get('raw_response', {}),
                notes='Payment completed and verified'
            )

            logger.info(f"Payment {payment_obj.id} marked as completed")
            return True

        except Exception as e:
            logger.error(f"Error handling successful payment: {str(e)}")
            raise PaystackError(f"Error processing payment completion: {str(e)}")

    def handle_failed_payment(self, payment_obj, reason=''):
        """
        Handle failed payment.
        
        Args:
            payment_obj: Payment model instance
            reason: Reason for failure
            
        Returns:
            bool: True if successful
        """
        try:
            payment_obj.mark_as_failed()

            # Log transaction
            Transaction.objects.create(
                payment=payment_obj,
                transaction_type='payment',
                amount=payment_obj.amount,
                paystack_reference=payment_obj.paystack_reference,
                status='failed',
                response={},
                notes=f'Payment failed: {reason}'
            )

            logger.warning(f"Payment {payment_obj.id} marked as failed: {reason}")
            return True

        except Exception as e:
            logger.error(f"Error handling failed payment: {str(e)}")
            raise PaystackError(f"Error processing payment failure: {str(e)}")


def get_paystack_client():
    """Get Paystack client instance."""
    return PaystackClient()


def initialize_payment_for_booking(booking, request=None):
    """
    Create and initialize a payment for a booking.
    
    Args:
        booking: Booking model instance
        request: Django request object
        
    Returns:
        tuple: (Payment object, initialization response dict)
        
    Raises:
        PaystackError: If payment creation or initialization fails
    """
    try:
        # Create payment record for callout fee
        payment = Payment.objects.create(
            booking=booking,
            user=booking.customer,
            amount=booking.callout_fee,
            payment_method='paystack',
            payment_type='callout_fee',
            description=f"Callout fee for {booking.get_service_type_display()} service at {booking.location}",
        )

        # Initialize payment
        client = get_paystack_client()
        init_response = client.initialize_payment(payment, request)

        return payment, init_response

    except PaystackError:
        raise
    except Exception as e:
        logger.error(f"Error creating payment for booking {booking.id}: {str(e)}")
        raise PaystackError(f"Error creating payment: {str(e)}")


def verify_and_process_payment(reference):
    """
    Verify payment with Paystack and process if successful.
    
    Args:
        reference: Paystack transaction reference
        
    Returns:
        tuple: (Payment object, success bool, message str)
    """
    try:
        # Get payment by reference
        payment = Payment.objects.get(paystack_reference=reference)

        # Verify with Paystack
        client = get_paystack_client()
        verification_data = client.verify_payment(reference)

        if verification_data['status'] == 'success':
            # Payment successful
            client.handle_successful_payment(payment, verification_data)
            return payment, True, 'Payment successful'
        else:
            # Payment failed
            client.handle_failed_payment(payment, f"Status: {verification_data['status']}")
            return payment, False, f"Payment {verification_data['status']}"

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for reference: {reference}")
        raise PaystackError(f"Payment record not found")
    except PaystackError:
        raise
    except Exception as e:
        logger.error(f"Error processing payment verification: {str(e)}")
        raise PaystackError(f"Error processing payment: {str(e)}")
