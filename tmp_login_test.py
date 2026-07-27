import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundi_backend.settings')
django.setup()

from django.test import Client

client = Client()
client.defaults['HTTP_HOST'] = 'localhost'
email = 'chenhawi12@gmail.com'
password = 'Chen@1234'
response = client.post(
    '/api/auth/login/',
    data=json.dumps({'email': email, 'password': password}),
    content_type='application/json',
)
print('STATUS', response.status_code)
print('CONTENT_START', repr(response.content.decode('utf-8', errors='replace'))[:1200])
print('CONTENT_END', repr(response.content.decode('utf-8', errors='replace'))[-1200:])
