import json

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from .models import Booking, Profile


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

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('Welcome' in message.subject for message in mail.outbox))
        self.assertTrue(any('welcome@example.com' in message.to for message in mail.outbox))

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

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('Password Reset' in message.subject for message in mail.outbox))
        self.assertTrue(any('forgot@example.com' in message.to for message in mail.outbox))

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
