import json
import os
import time
from unittest.mock import patch

from datetime import datetime

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Booking, Payment, Profile
from .utils.auth_utils import get_tokens_for_user
from .utils.paystack_utils import PaystackClient


def wait_for_mail(timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mail.outbox:
            return
        time.sleep(0.05)


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='jane_wanjiku',
            email='jane@example.com',
            password='Secret123!',
            first_name='Jane',
            last_name='Wanjiku',
        )
        Profile.objects.create(user=self.user, role='customer')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_register_sends_welcome_email(self):
        mail.outbox = []
        response = self.client.post(
            '/api/auth/register/',
            data=json.dumps({
                'firstName': 'New',
                'lastName': 'User',
                'email': 'welcome@example.com',
                'confirmEmail': 'welcome@example.com',
                'phoneNumber': '0712345678',
                'username': 'new_user',
                'password': 'Secret123!',
                'confirmPassword': 'Secret123!',
                'role': 'customer',
            }),
            content_type='application/json',
        )

        wait_for_mail()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='welcome@example.com').exists())
        self.assertTrue(response.json()['ok'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @patch('django.core.mail.EmailMessage.send', side_effect=Exception('SMTP unavailable'))
    def test_register_still_succeeds_when_email_delivery_fails(self, mock_send):
        response = self.client.post(
            '/api/auth/register/',
            data=json.dumps({
                'firstName': 'Email',
                'lastName': 'Fallback',
                'email': 'fallback@example.com',
                'confirmEmail': 'fallback@example.com',
                'phoneNumber': '0712345678',
                'username': 'email_fallback',
                'password': 'Secret123!',
                'confirmPassword': 'Secret123!',
                'role': 'customer',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='fallback@example.com').exists())
        self.assertTrue(response.json()['ok'])

    def test_register_defers_notification_emails_until_commit(self):
        with patch('api.views._dispatch_post_commit') as mock_on_commit:
            response = self.client.post(
                '/api/auth/register/',
                data=json.dumps({
                    'firstName': 'Deferred',
                    'lastName': 'Mail',
                    'email': 'deferred@example.com',
                    'confirmEmail': 'deferred@example.com',
                    'phoneNumber': '0712345678',
                    'username': 'deferred_mail',
                    'password': 'Secret123!',
                    'confirmPassword': 'Secret123!',
                    'role': 'customer',
                }),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_on_commit.called)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_forgot_password_sends_reset_code_email(self):
        mail.outbox = []
        User.objects.create_user(
            username='forgot_user',
            email='forgot@example.com',
            password='Secret123!',
            first_name='Forgot',
            last_name='User',
        )

        response = self.client.post(
            '/api/auth/forgot-password/',
            data=json.dumps({'email': 'forgot@example.com'}),
            content_type='application/json',
        )

        wait_for_mail()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('Password Reset' in message.subject for message in mail.outbox))
        self.assertTrue(any('forgot@example.com' in message.to for message in mail.outbox))

    def test_register_options_returns_cors_headers_for_allowed_origin(self):
        response = self.client.options(
            '/api/auth/register/',
            HTTP_ORIGIN='https://myfundihubfront-production.up.railway.app',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://myfundihubfront-production.up.railway.app')
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')
        self.assertIn('OPTIONS', response['Access-Control-Allow-Methods'])

    def test_public_register_rejects_admin_role(self):
        response = self.client.post(
            '/api/auth/register/',
            data=json.dumps({
                'firstName': 'Hidden',
                'lastName': 'Admin',
                'email': 'hiddenadmin@example.com',
                'confirmEmail': 'hiddenadmin@example.com',
                'phoneNumber': '0712345678',
                'username': 'hidden_admin',
                'password': 'Secret123!',
                'confirmPassword': 'Secret123!',
                'role': 'admin',
                'adminKey': 'secret-key',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertFalse(body['ok'])
        self.assertIn('Admin registration is not allowed here', body['message'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @patch.dict(os.environ, {'ADMIN_REGISTRATION_KEY': 'secret-admin-key'})
    def test_admin_register_with_valid_admin_key(self):
        mail.outbox = []
        response = self.client.post(
            '/api/auth/admin-register/',
            data=json.dumps({
                'firstName': 'Hidden',
                'lastName': 'Admin',
                'email': 'hiddenadmin@example.com',
                'confirmEmail': 'hiddenadmin@example.com',
                'phoneNumber': '0712345678',
                'username': 'hidden_admin',
                'password': 'Secret123!',
                'confirmPassword': 'Secret123!',
                'adminKey': 'secret-admin-key',
            }),
            content_type='application/json',
        )

        wait_for_mail()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['role'], 'admin')
        self.assertTrue(User.objects.filter(username='hidden_admin', email='hiddenadmin@example.com').exists())
        self.assertTrue(any('Welcome' in message.subject for message in mail.outbox))

    def test_admin_register_options_returns_cors_headers_for_allowed_origin(self):
        response = self.client.options(
            '/api/auth/admin-register/',
            HTTP_ORIGIN='https://myfundihubfront-production.up.railway.app',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://myfundihubfront-production.up.railway.app')
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')
        self.assertIn('POST', response['Access-Control-Allow-Methods'])

    def test_login_returns_user_profile_details(self):
        response = self.client.post(
            '/api/auth/login/',
            data=json.dumps({
                'email': 'jane@example.com',
                'password': 'Secret123!',
                'role': 'customer',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['user']['firstName'], 'Jane')
        self.assertEqual(body['user']['lastName'], 'Wanjiku')
        self.assertEqual(body['user']['username'], 'jane_wanjiku')

    def test_login_accepts_username_field(self):
        response = self.client.post(
            '/api/auth/login/',
            data=json.dumps({
                'username': 'jane_wanjiku',
                'password': 'Secret123!',
                'role': 'customer',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['user']['email'], 'jane@example.com')


class PaystackClientTests(TestCase):
    @override_settings(
        PAYSTACK_PUBLIC_KEY='pk_test_dummy',
        PAYSTACK_SECRET_KEY='sk_test_dummy',
        PAYSTACK_USE_MOCK=True,
        DEBUG=True,
    )
    def test_placeholder_keys_enable_mock_payment_initialization(self):
        user = User.objects.create_user(
            username='mock_paystack_user',
            email='mockpaystack@example.com',
            password='Secret123!',
            first_name='Mock',
            last_name='Paystack',
        )
        Profile.objects.create(user=user, role='customer')
        booking = Booking.objects.create(
            customer=user,
            service_type='plumbing',
            location='Test location',
            description='Need help',
            estimated_cost=1000,
            callout_fee=1000,
        )
        payment = Payment.objects.create(
            booking=booking,
            user=user,
            amount=1000,
            payment_method='paystack',
            payment_type='callout_fee',
        )

        client = PaystackClient()
        self.assertTrue(client.use_mock)

        result = client.initialize_payment(payment)
        self.assertTrue(result['success'])
        self.assertIn('mock-paystack', result['authorization_url'])
        self.assertEqual(payment.status, 'processing')


class BookingViewTests(TestCase):
    def test_admin_dashboard_uses_database_metrics(self):
        admin = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='Secret123!',
            first_name='Admin',
            last_name='User',
        )
        Profile.objects.create(user=admin, role='admin')

        customer = User.objects.create_user(
            username='customer_four',
            email='customer4@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Four',
        )
        Profile.objects.create(user=customer, role='customer')

        Booking.objects.create(customer=customer, service_type='plumbing', location='A', estimated_cost=1200)
        Booking.objects.create(customer=customer, service_type='electrical', location='B', status='assigned', estimated_cost=1800)
        Booking.objects.create(customer=customer, service_type='carpentry', location='C', status='completed', estimated_cost=2500)
        Booking.objects.create(customer=customer, service_type='installation', location='D', status='cancelled', estimated_cost=900)

        response = self.client.get('/api/dashboard/admin/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        stats = {item['label']: item['value'] for item in payload['stats']}
        self.assertEqual(stats['Total Users'], '2')
        self.assertEqual(stats['Total Bookings'], '4')
        self.assertEqual(stats['Pending Bookings'], '1')
        self.assertEqual(stats['Active Jobs'], '2')
        self.assertEqual(stats['Revenue'], 'KSh 6400.00')

    def test_booking_options_returns_cors_headers_for_allowed_origin(self):
        response = self.client.options(
            '/api/bookings/',
            HTTP_ORIGIN='https://myfundihubfront-production.up.railway.app',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://myfundihubfront-production.up.railway.app')
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')
        self.assertIn('OPTIONS', response['Access-Control-Allow-Methods'])

    @patch('api.views.Booking.objects.create', side_effect=RuntimeError('boom'))
    def test_booking_creation_returns_cors_headers_when_internal_error_occurs(self, _mock_create):
        response = self.client.post(
            '/api/bookings/',
            data=json.dumps({
                'serviceType': 'installation',
                'location': 'Test location',
                'description': 'Need help',
            }),
            content_type='application/json',
            HTTP_ORIGIN='https://myfundihub.com',
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://myfundihub.com')
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')

    def test_duplicate_booking_returns_existing_booking_instead_of_conflict(self):
        user = User.objects.create_user(
            username='customer_duplicate',
            email='customerduplicate@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Duplicate',
        )
        Profile.objects.create(user=user, role='customer')
        self.client.force_login(user)

        first_response = self.client.post(
            '/api/bookings/',
            data=json.dumps({
                'serviceType': 'installation',
                'location': 'Test location',
                'description': 'Need help',
                'scheduledDate': '2026-07-15',
                'scheduledTime': '10:00',
            }),
            content_type='application/json',
        )
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post(
            '/api/bookings/',
            data=json.dumps({
                'serviceType': 'installation',
                'location': 'Test location',
                'description': 'Need help',
                'scheduledDate': '2026-07-15',
                'scheduledTime': '10:00',
            }),
            content_type='application/json',
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.json()['duplicate'])
        self.assertEqual(Booking.objects.count(), 1)

    def test_booking_creation_accepts_string_dates_and_times(self):
        response = self.client.post(
            '/api/bookings/',
            data=json.dumps({
                'serviceType': 'installation',
                'location': 'Test location',
                'description': 'Need help',
                'county': 'Nairobi',
                'townOrEstate': 'Westlands',
                'landmark': 'Near the mall',
                'latitude': None,
                'longitude': None,
                'scheduledDate': '2026-07-15',
                'scheduledTime': '10:00',
                'serviceWindow': 'scheduled',
                'estimatedCost': 1000,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['booking']['scheduledDate'], '2026-07-15')
        self.assertEqual(body['booking']['scheduledTime'], '10:00')

    def test_booking_creation_defers_notification_emails_until_commit(self):
        with patch('api.views._dispatch_post_commit') as mock_on_commit:
            response = self.client.post(
                '/api/bookings/',
                data=json.dumps({
                    'serviceType': 'plumbing',
                    'location': 'Deferred email location',
                    'description': 'Need help quickly',
                    'estimatedCost': 1500,
                }),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_on_commit.called)

    def test_logged_in_users_booking_is_linked_to_their_account(self):
        user = User.objects.create_user(
            username='customer_one',
            email='customer@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='One',
        )
        Profile.objects.create(user=user, role='customer')

        login_response = self.client.post(
            '/api/auth/login/',
            data=json.dumps({
                'email': 'customer@example.com',
                'password': 'Secret123!',
                'role': 'customer',
            }),
            content_type='application/json',
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(self.client.session.get('_auth_user_id'))

        booking_response = self.client.post(
            '/api/bookings/',
            data=json.dumps({
                'serviceType': 'plumbing',
                'location': 'Test location',
                'description': 'Need help',
                'scheduledDate': '2026-07-15',
                'scheduledTime': '10:00',
            }),
            content_type='application/json',
        )

        self.assertEqual(booking_response.status_code, 200)
        booking = Booking.objects.latest('id')
        self.assertEqual(booking.customer, user)
        self.assertEqual(booking_response.json()['booking']['customer']['name'], 'Customer One')

    def test_booking_creation_uses_explicit_customer_id(self):
        customer = User.objects.create_user(
            username='customer_two',
            email='customer2@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Two',
        )
        Profile.objects.create(user=customer, role='customer')

        response = self.client.post(
            '/api/bookings/',
            data=json.dumps({
                'customerId': customer.id,
                'serviceType': 'plumbing',
                'location': 'Test location',
                'description': 'Need help',
                'scheduledDate': '2026-07-15',
                'scheduledTime': '10:00',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.latest('id')
        self.assertEqual(booking.customer, customer)
        self.assertEqual(response.json()['booking']['customer']['name'], 'Customer Two')

    def test_logged_in_booking_can_be_found_for_payment_initialization(self):
        user = User.objects.create_user(
            username='customer_payment',
            email='customerpayment@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Payment',
        )
        Profile.objects.create(user=user, role='customer')

        access_token = get_tokens_for_user(user)['access']

        create_response = self.client.post(
            '/api/bookings/',
            data=json.dumps({
                'serviceType': 'plumbing',
                'location': 'Test location',
                'description': 'Need help',
            }),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}',
        )

        self.assertEqual(create_response.status_code, 200)
        booking = Booking.objects.latest('id')
        self.assertEqual(booking.customer, user)

        payment_response = self.client.post(
            '/api/payments/initialize/',
            data=json.dumps({'booking_id': booking.id}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}',
        )

        self.assertNotEqual(payment_response.status_code, 404)

    def test_assign_booking_accepts_snake_case_payload(self):
        customer = User.objects.create_user(
            username='customer_assign',
            email='customerassign@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Assign',
        )
        technician = User.objects.create_user(
            username='tech_assign',
            email='techassign@example.com',
            password='Secret123!',
            first_name='Tech',
            last_name='Assign',
        )
        Profile.objects.create(user=customer, role='customer')
        Profile.objects.create(user=technician, role='technician')

        booking = Booking.objects.create(
            customer=customer,
            service_type='plumbing',
            location='Assign target',
            description='Need technician',
        )

        response = self.client.post(
            '/api/bookings/assign/',
            data=json.dumps({
                'booking_id': booking.id,
                'technician_id': technician.id,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.assigned_technician, technician)
        self.assertEqual(booking.status, 'assigned')
        self.assertEqual(response.json()['booking']['assignedTechnician']['id'], technician.id)

    def test_booking_list_includes_customer_details_and_assignment_metadata(self):
        customer = User.objects.create_user(
            username='customer_details',
            email='customerdetails@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Details',
        )
        Profile.objects.create(user=customer, role='customer', phone_number='0712345678')

        booking = Booking.objects.create(
            customer=customer,
            service_type='plumbing',
            location='Test location',
            town_or_estate='Westlands',
            landmark='Near the mall',
            description='Need help',
            status='pending',
        )

        response = self.client.get('/api/bookings/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['bookings'][0]['customerName'], 'Customer Details')
        self.assertEqual(payload['bookings'][0]['customerPhoneNumber'], '0712345678')
        self.assertEqual(payload['bookings'][0]['serviceType'], 'Plumbing')
        self.assertEqual(payload['bookings'][0]['townOrEstate'], 'Westlands')
        self.assertEqual(payload['bookings'][0]['landmark'], 'Near the mall')
        self.assertTrue(payload['bookings'][0]['canAssignTechnician'])

    def test_booking_list_can_filter_by_application_date(self):
        customer = User.objects.create_user(
            username='customer_date_filter',
            email='customerdatefilter@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Date',
        )
        Profile.objects.create(user=customer, role='customer')

        matching_booking = Booking.objects.create(
            customer=customer,
            service_type='plumbing',
            location='Match location',
            description='Need help',
        )
        matching_booking.created_at = timezone.make_aware(datetime(2026, 7, 10, 9, 30, 0))
        matching_booking.save(update_fields=['created_at'])

        other_booking = Booking.objects.create(
            customer=customer,
            service_type='electrical',
            location='Other location',
            description='Need help later',
        )
        other_booking.created_at = timezone.make_aware(datetime(2026, 7, 11, 9, 30, 0))
        other_booking.save(update_fields=['created_at'])

        response = self.client.get('/api/bookings/?date=2026-07-10')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['bookings'][0]['id'], matching_booking.id)
        self.assertEqual(payload['bookings'][0]['createdAtDate'], '2026-07-10')

    @patch('api.views._dispatch_post_commit')
    @patch('api.views.send_booking_assigned')
    def test_assign_booking_defers_assignment_email(self, mock_send_assignment, mock_dispatch):
        customer = User.objects.create_user(
            username='customer_assign_email',
            email='customerassignemail@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='AssignEmail',
        )
        technician = User.objects.create_user(
            username='tech_assign_email',
            email='techassignemail@example.com',
            password='Secret123!',
            first_name='Tech',
            last_name='AssignEmail',
        )
        Profile.objects.create(user=customer, role='customer')
        Profile.objects.create(user=technician, role='technician')

        booking = Booking.objects.create(
            customer=customer,
            service_type='plumbing',
            location='Email target',
            description='Need technician',
        )

        response = self.client.post(
            '/api/bookings/assign/',
            data=json.dumps({
                'booking_id': booking.id,
                'technician_id': technician.id,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        mock_dispatch.assert_called_once()
        mock_send_assignment.assert_not_called()

    def test_technician_only_sees_their_assigned_bookings(self):
        customer = User.objects.create_user(
            username='customer_three',
            email='customer3@example.com',
            password='Secret123!',
            first_name='Customer',
            last_name='Three',
        )
        technician = User.objects.create_user(
            username='tech_two',
            email='tech2@example.com',
            password='Secret123!',
            first_name='Tech',
            last_name='Two',
        )
        Profile.objects.create(user=customer, role='customer')
        Profile.objects.create(user=technician, role='technician')

        other_booking = Booking.objects.create(
            customer=customer,
            service_type='plumbing',
            location='Other location',
            description='Unassigned',
        )
        assigned_booking = Booking.objects.create(
            customer=customer,
            assigned_technician=technician,
            service_type='plumbing',
            location='Assigned location',
            description='Assigned',
        )

        self.client.force_login(technician)
        response = self.client.get('/api/bookings/')

        self.assertEqual(response.status_code, 200)
        booking_ids = [booking['id'] for booking in response.json()['bookings']]
        self.assertIn(assigned_booking.id, booking_ids)
        self.assertNotIn(other_booking.id, booking_ids)
