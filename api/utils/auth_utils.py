import logging
from functools import wraps
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import condition
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    'login': {'attempts': 5, 'period': 900},  # 5 attempts per 15 minutes
    'forgot_password': {'attempts': 3, 'period': 3600},  # 3 attempts per hour
    'register': {'attempts': 10, 'period': 3600},  # 10 per hour per IP
    'reset_password': {'attempts': 5, 'period': 3600},  # 5 attempts per hour
}


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def check_rate_limit(request, action):
    """Check if client has exceeded rate limit for action."""
    if action not in RATE_LIMIT_CONFIG:
        return True

    ip = get_client_ip(request)
    cache_key = f'rate_limit:{action}:{ip}'
    
    config = RATE_LIMIT_CONFIG[action]
    current_count = cache.get(cache_key, 0)
    
    if current_count >= config['attempts']:
        return False
    
    cache.set(cache_key, current_count + 1, config['period'])
    return True


def rate_limit(action):
    """Decorator for rate limiting endpoints."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not check_rate_limit(request, action):
                return JsonResponse(
                    {'ok': False, 'message': 'Too many attempts. Please try again later.'},
                    status=429
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_tokens_for_user(user):
    """Generate JWT tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def is_valid_admin_key(admin_key, user=None):
    """Validate admin key for registration."""
    if not admin_key:
        return False
    
    # Store admin keys in environment or database
    # For now, use a hardcoded value (change in production)
    ADMIN_KEY_HASH = 'admin_key_hash_value'
    
    # In production, use proper hashing
    # return check_password(admin_key, ADMIN_KEY_HASH)
    
    # Placeholder: validate against environment variable
    import os
    expected_key = os.getenv('ADMIN_REGISTRATION_KEY', '')
    return admin_key == expected_key and expected_key


def mask_email(email):
    """Mask email for security (show only part of it)."""
    parts = email.split('@')
    if len(parts[0]) > 2:
        masked = parts[0][0] + '*' * (len(parts[0]) - 2) + parts[0][-1]
        return f"{masked}@{parts[1]}"
    return email


def log_security_event(event_type, user=None, email=None, username=None, ip=None, details=None):
    """Log security-related events."""
    message = f"Security Event: {event_type}"
    if user:
        message += f" | User: {user.username}"
    if email:
        message += f" | Email: {email}"
    if username:
        message += f" | Username: {username}"
    if ip:
        message += f" | IP: {ip}"
    if details:
        message += f" | Details: {details}"
    
    logger.warning(message)
