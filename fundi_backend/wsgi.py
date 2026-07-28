"""
WSGI config for fundi_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
# existing imports...

if os.environ.get("RUN_CREATE_USERS") == "1":
    try:
        from create_railway_users import main as create_users_main
        create_users_main()
    except Exception:
        pass

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundi_backend.settings')

application = get_wsgi_application()
