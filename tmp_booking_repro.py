import os
import json
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundi_backend.settings')
os.environ['PAYSTACK_PUBLIC_KEY'] = 'pk_test_dummy'
os.environ['PAYSTACK_SECRET_KEY'] = 'sk_test_dummy'

import django

django.setup()

from django.test import Client

client = Client()
client.defaults['HTTP_HOST'] = 'myfundihub.com'
client.defaults['HTTP_ORIGIN'] = 'https://myfundihub.com'

try:
    response = client.post(
        '/api/bookings/',
        data=json.dumps({'serviceType': 'plumbing', 'location': 'Test', 'description': 'Test', 'customerId': 1}),
        content_type='application/json',
    )
    print('STATUS', response.status_code)
    print(response.content.decode('utf-8', 'replace'))
except Exception as exc:
    print(type(exc).__name__, exc)
    traceback.print_exc()
