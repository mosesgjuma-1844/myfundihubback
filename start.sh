#!/usr/bin/env bash
set -e
python manage.py collectstatic --noinput
python manage.py migrate --noinput
exec gunicorn fundi_backend.wsgi:application --bind 0.0.0.0:${PORT:-8000}
