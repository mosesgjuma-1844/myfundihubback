import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundi_backend.settings')
django.setup()

from django.test import Client

client = Client()
email = 'chenhawi12@gmail.com'
password = 'Chen@1234'

response = client.post(
    '/api/auth/login/',
    data=json.dumps({'email': email, 'password': password}),
    content_type='application/json',
)
print('LOGIN_STATUS', response.status_code)
print('LOGIN_CONTENT', response.content.decode('utf-8'))

if response.status_code != 200:
    raise SystemExit('Login failed')

access = response.json().get('tokens', {}).get('access')
print('ACCESS_PRESENT', bool(access))
if not access:
    raise SystemExit('No access token')

headers = {'HTTP_AUTHORIZATION': f'Bearer {access}'}

booking_payload = {
    'serviceType': 'electrical',
    'location': 'Test Location',
    'county': 'Nairobi',
    'townOrEstate': 'Test Estate',
    'landmark': 'Test Landmark',
    'latitude': 1.0,
    'longitude': 1.0,
    'description': 'Test booking',
    'scheduledDate': '2026-08-01',
    'scheduledTime': '10:00',
    'serviceWindow': 'scheduled',
    'estimatedCost': 2500,
}

response = client.post(
    '/api/bookings/',
    data=json.dumps(booking_payload),
    content_type='application/json',
    **headers,
)
print('BOOKING_STATUS', response.status_code)
print('BOOKING_CONTENT', response.content.decode('utf-8'))

if response.status_code != 200:
    raise SystemExit('Booking creation failed')

booking_data = response.json()
booking_id = booking_data.get('booking', {}).get('id')
print('BOOKING_ID', booking_id)

response = client.post(
    '/api/payments/initialize/',
    data=json.dumps({'booking_id': booking_id}),
    content_type='application/json',
    **headers,
)
print('PAYMENT_INIT_STATUS', response.status_code)
print('PAYMENT_INIT_CONTENT', response.content.decode('utf-8'))
