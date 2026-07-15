import logging
from typing import List
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_email(subject: str, template_name: str, context: dict, to: List[str]):
    if not to:
        return False

    body = render_to_string(template_name, context)
    email = EmailMessage(subject=subject, body=body, from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None), to=to)
    email.content_subtype = 'html'
    try:
        email.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.exception('Email delivery failed for %s', to)
        raise exc


def send_welcome_email(user, to_emails: List[str]):
    subject = 'Welcome to FUNDI'
    template = 'emails/welcome.html'
    context = {'user': user}
    return send_email(subject, template, context, to_emails)


def send_admin_alert(subject: str, message: str, to_emails: List[str]):
    template = 'emails/admin_alert.html'
    context = {'subject': subject, 'message': message}
    return send_email(subject, template, context, to_emails)


def send_password_reset_code(user, reset_code: str, to_emails: List[str]):
    subject = 'Password Reset'
    template = 'emails/password_reset.html'
    context = {'user': user, 'reset_code': reset_code}
    return send_email(subject, template, context, to_emails)


def send_booking_created(booking, to_emails: List[str]):
    subject = f"Booking Received - {booking.get_service_type_display()}"
    template = 'emails/booking_created.html'
    context = {'booking': booking}
    return send_email(subject, template, context, to_emails)


def send_booking_assigned(booking, technician, to_emails: List[str]):
    subject = f"Booking Assigned - {booking.get_service_type_display()}"
    template = 'emails/booking_assigned.html'
    context = {'booking': booking, 'technician': technician}
    return send_email(subject, template, context, to_emails)


def send_booking_status_changed(booking, to_emails: List[str]):
    subject = f"Booking Status Updated - {booking.get_service_type_display()}"
    template = 'emails/booking_status.html'
    context = {'booking': booking}
    return send_email(subject, template, context, to_emails)
