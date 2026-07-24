import json
import logging
import secrets
from datetime import datetime, timedelta

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import Booking, Profile, PasswordResetCode
from .utils.email_utils import (
    send_admin_alert,
    send_booking_created,
    send_booking_assigned,
    send_booking_status_changed,
    send_password_reset_code,
    send_welcome_email,
)
from .utils.auth_utils import (
    rate_limit,
    get_tokens_for_user,
    is_valid_admin_key,
    get_client_ip,
    log_security_event,
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
@rate_limit('login')
def login_view(request):
    """
    Login endpoint with rate limiting and security hardening.
    Uses generic error messages to prevent user enumeration.
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Invalid JSON payload.'}, status=400)

    email = payload.get('email', '').strip()
    password = payload.get('password', '').strip()
    role = payload.get('role', 'customer')

    if not email or not password:
        return JsonResponse({'ok': False, 'message': 'Invalid credentials.'}, status=401)

    user = User.objects.filter(email__iexact=email).first() or User.objects.filter(username=email).first()
    
    if not user or not user.check_password(password):
        ip = get_client_ip(request)
        log_security_event('failed_login', email=email, ip=ip)
        return JsonResponse({'ok': False, 'message': 'Invalid credentials.'}, status=401)

    profile = getattr(user, 'profile', None)
    actual_role = role
    if profile:
        actual_role = profile.role

    redirect_path = '/customer-dashboard'
    if actual_role == 'admin':
        redirect_path = '/admin-dashboard'
    elif actual_role == 'technician':
        redirect_path = '/technician-dashboard'

    login(request, user)
    log_security_event('successful_login', user=user, ip=get_client_ip(request))

    tokens = get_tokens_for_user(user)

    return JsonResponse({
        'ok': True,
        'message': f'{actual_role.title()} login accepted.',
        'role': actual_role,
        'redirect': redirect_path,
        'tokens': tokens,
        'user': {
            'id': user.id,
            'username': user.username,
            'firstName': user.first_name,
            'lastName': user.last_name,
            'email': user.email,
            'role': actual_role,
        },
    })


@csrf_exempt
@require_POST
@rate_limit('forgot_password')
def forgot_password_view(request):
    """
    Password reset request with rate limiting.
    Uses database-based reset codes with expiration.
    Generic response prevents user enumeration.
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Invalid JSON payload.'}, status=400)

    email = (payload.get('email') or '').strip().lower()
    if not email:
        return JsonResponse({'ok': False, 'message': 'Email is required.'}, status=400)

    user = User.objects.filter(email__iexact=email).first()
    
    # Generic response for security
    generic_response = JsonResponse({
        'ok': True,
        'message': 'If an account exists for that email, a reset code has been sent.'
    })

    if not user:
        log_security_event('password_reset_nonexistent_user', email=email, ip=get_client_ip(request))
        return generic_response

    # Create database-based reset code with expiration
    reset_obj = PasswordResetCode.create_code(user, email, expiry_minutes=15)
    
    try:
        send_password_reset_code(user, reset_obj.code, [user.email])
        log_security_event('password_reset_requested', user=user, ip=get_client_ip(request))
    except Exception:
        logger.exception('Failed to send password reset email')

    return generic_response


@csrf_exempt
@require_POST
def verify_reset_code_view(request):
    """Verify password reset code."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Invalid JSON payload.'}, status=400)

    email = (payload.get('email') or '').strip().lower()
    code = (payload.get('code') or '').strip()
    
    if not email or not code:
        return JsonResponse({'ok': False, 'message': 'Email and code are required.'}, status=400)

    reset_obj = PasswordResetCode.objects.filter(email=email, code=code).first()
    
    if not reset_obj or not reset_obj.is_valid():
        ip = get_client_ip(request)
        log_security_event('invalid_reset_code_attempt', email=email, ip=ip)
        return JsonResponse({'ok': False, 'message': 'Invalid or expired reset code.'}, status=400)

    return JsonResponse({'ok': True, 'message': 'Reset code verified successfully.'})


@csrf_exempt
@require_POST
@rate_limit('reset_password')
def reset_password_view(request):
    """
    Reset password using valid reset code.
    Uses database-based codes with validation and expiration checks.
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Invalid JSON payload.'}, status=400)

    email = (payload.get('email') or '').strip().lower()
    code = (payload.get('code') or '').strip()
    password = (payload.get('password') or '').strip()
    confirm_password = (payload.get('confirmPassword') or '').strip()
    
    if not email or not code or not password or not confirm_password:
        return JsonResponse({'ok': False, 'message': 'Email, code, and password are required.'}, status=400)

    if password != confirm_password:
        return JsonResponse({'ok': False, 'message': 'Passwords do not match.'}, status=400)

    reset_obj = PasswordResetCode.objects.filter(email=email, code=code).first()
    
    if not reset_obj or not reset_obj.is_valid():
        ip = get_client_ip(request)
        log_security_event('invalid_password_reset_attempt', email=email, ip=ip)
        return JsonResponse({'ok': False, 'message': 'Invalid or expired reset code.'}, status=400)

    user = reset_obj.user
    
    # Validate password strength
    try:
        validate_password(password, user=user)
    except ValidationError as e:
        return JsonResponse({'ok': False, 'message': 'Password does not meet requirements: ' + ', '.join(e.messages)}, status=400)

    user.set_password(password)
    user.save(update_fields=['password'])
    reset_obj.mark_as_used()
    
    log_security_event('password_reset_successful', user=user, ip=get_client_ip(request))

    return JsonResponse({'ok': True, 'message': 'Password reset successfully.'})


@csrf_exempt
@rate_limit('register')
def register_view(request):
    """
    User registration with enhanced security:
    - Rate limiting
    - Input validation
    - Admin key validation
    - Email verification
    - Proper password validation
    """
    origin = request.META.get('HTTP_ORIGIN', '')
    allowed_origins = {
        'https://myfundihubfront.up.railway.app',
        'https://myfundihubfront-production.up.railway.app',
        'https://myfundihubback.up.railway.app',
        'https://myfundihubback-production.up.railway.app',
    }
    if request.method == 'OPTIONS':
        response = HttpResponse(status=204)
        if origin in allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Vary'] = 'Origin'
        return response

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Invalid JSON payload.'}, status=400)

    required_fields = ['firstName', 'lastName', 'email', 'phoneNumber', 'username', 'password']
    missing = [field for field in required_fields if not str(payload.get(field, '')).strip()]

    if missing:
        return JsonResponse({'ok': False, 'message': f'Missing required fields: {", ".join(missing)}.'}, status=400)

    email = payload.get('email', '').strip().lower()
    username = payload.get('username', '').strip()
    password = payload.get('password', '').strip()
    confirm_password = payload.get('confirmPassword', '').strip()
    confirm_email = payload.get('confirmEmail', '').strip().lower()
    phone_number = payload.get('phoneNumber', '').strip()
    role = payload.get('role', 'customer').lower()
    admin_key = payload.get('adminKey', '').strip()

    # Validate email format
    if '@' not in email or '.' not in email.split('@')[1]:
        return JsonResponse({'ok': False, 'message': 'Invalid email format.'}, status=400)

    # Validate passwords match
    if password != confirm_password:
        return JsonResponse({'ok': False, 'message': 'Passwords do not match.'}, status=400)

    # Validate emails match
    if email != confirm_email:
        return JsonResponse({'ok': False, 'message': 'Emails do not match.'}, status=400)

    # Check if username exists
    if User.objects.filter(username=username).exists():
        ip = get_client_ip(request)
        log_security_event('registration_duplicate_username', username=username, ip=ip)
        return JsonResponse({'ok': False, 'message': 'Username already exists.'}, status=400)

    # Check if email exists
    if User.objects.filter(email__iexact=email).exists():
        ip = get_client_ip(request)
        log_security_event('registration_duplicate_email', email=email, ip=ip)
        return JsonResponse({'ok': False, 'message': 'Email already exists.'}, status=400)

    # Validate role
    if role not in dict(Profile.ROLE_CHOICES):
        role = 'customer'

    # Validate admin key if registering as admin
    if role == 'admin' and not is_valid_admin_key(admin_key):
        ip = get_client_ip(request)
        log_security_event('invalid_admin_key_attempt', email=email, ip=ip)
        return JsonResponse({'ok': False, 'message': 'Invalid admin key.'}, status=403)

    # Create temporary user object for password validation
    temp_user = User(username=username, email=email)

    # Validate password strength using Django's validators
    try:
        validate_password(password, user=temp_user)
    except ValidationError as e:
        return JsonResponse({'ok': False, 'message': 'Password does not meet requirements: ' + ', '.join(e.messages)}, status=400)

    # Create user
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=payload.get('firstName', '').strip(),
            last_name=payload.get('lastName', '').strip(),
        )
    except Exception as e:
        logger.exception('Failed to create user')
        return JsonResponse({'ok': False, 'message': 'Failed to create user account.'}, status=500)

    # Create profile
    try:
        Profile.objects.create(
            user=user,
            role=role,
            phone_number=phone_number,
            specialization=payload.get('specialization', '').strip(),
            years_of_experience=int(payload.get('yearsOfExperience', 0) or 0),
            admin_key='' if role != 'admin' else 'verified',
        )
    except Exception as e:
        logger.exception('Failed to create profile')
        user.delete()
        return JsonResponse({'ok': False, 'message': 'Failed to create user profile.'}, status=500)

    # Send notifications
    try:
        if user.email:
            send_welcome_email(user, [user.email])

        admin_emails = list(
            User.objects.filter(profile__role='admin')
            .values_list('email', flat=True)
            .distinct()
            .exclude(email='')
        )
        if admin_emails:
            send_admin_alert(
                'New user registration',
                f"A new {role} account was created for {user.get_full_name() or user.username} ({user.email}).",
                admin_emails,
            )
    except Exception:
        logger.exception('Failed to send registration notification emails')

    log_security_event('user_registered', user=user, ip=get_client_ip(request))

    return JsonResponse({
        'ok': True,
        'message': 'Account created successfully.',
        'role': role,
    })


def _serialize_user(user):
    profile = getattr(user, 'profile', None)
    return {
        'id': user.id,
        'username': user.username,
        'firstName': user.first_name,
        'lastName': user.last_name,
        'email': user.email,
        'role': profile.role if profile else 'customer',
        'phoneNumber': profile.phone_number if profile else '',
        'specialization': profile.specialization if profile else '',
        'yearsOfExperience': profile.years_of_experience if profile else 0,
    }


def _serialize_booking(booking):
    def _format_date(value):
        if not value:
            return None
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return str(value)

    def _format_time(value):
        if not value:
            return None
        if hasattr(value, 'strftime'):
            return value.strftime('%H:%M')
        return str(value)

    return {
        'id': booking.id,
        'serviceType': booking.get_service_type_display(),
        'location': booking.location,
        'county': booking.county,
        'townOrEstate': booking.town_or_estate,
        'landmark': booking.landmark,
        'latitude': float(booking.latitude) if booking.latitude is not None else None,
        'longitude': float(booking.longitude) if booking.longitude is not None else None,
        'description': booking.description,
        'scheduledDate': _format_date(booking.scheduled_date),
        'scheduledTime': _format_time(booking.scheduled_time),
        'serviceWindow': booking.service_window,
        'status': booking.status,
        'estimatedCost': float(booking.estimated_cost),
        'customer': {
            'id': booking.customer.id,
            'name': f"{booking.customer.first_name} {booking.customer.last_name}".strip() or booking.customer.username,
        } if booking.customer else None,
        'assignedTechnician': {
            'id': booking.assigned_technician.id,
            'name': f"{booking.assigned_technician.first_name} {booking.assigned_technician.last_name}".strip() or booking.assigned_technician.username,
        } if booking.assigned_technician else None,
    }


@csrf_exempt
def user_view(request):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    user_id = request.GET.get('id')
    if not user_id:
        return JsonResponse({'ok': False, 'message': 'User id is required.'}, status=400)

    user = User.objects.filter(id=user_id).first()
    if not user:
        return JsonResponse({'ok': False, 'message': 'User not found.'}, status=404)

    return JsonResponse({'ok': True, 'user': _serialize_user(user)})

@csrf_exempt
def technicians_view(request):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    technicians = Profile.objects.filter(role='technician').select_related('user')
    payload = [
        {
            'id': profile.user.id,
            'name': f"{profile.user.first_name} {profile.user.last_name}".strip() or profile.user.username,
            'specialization': profile.specialization,
        }
        for profile in technicians
    ]
    return JsonResponse({'ok': True, 'technicians': payload})


@csrf_exempt
def menu_view(request):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    role = request.GET.get('role', 'customer').lower()
    menu_items = []

    if role == 'admin':
        menu_items = [
            {'id': 'dashboard', 'label': 'Dashboard', 'link': '', 'icon': 'dashboard'},
            {'id': 'users', 'label': 'Users', 'link': 'users', 'icon': 'user'},
            {'id': 'fundis', 'label': 'Fundis', 'link': 'fundis', 'icon': 'tool'},
            {'id': 'bookings', 'label': 'Bookings', 'link': 'bookings', 'icon': 'book'},
            {'id': 'payments', 'label': 'Payments', 'link': 'payments', 'icon': 'wallet'},
            {'id': 'reports', 'label': 'Reports', 'link': 'reports', 'icon': 'file-text'},
            {'id': 'settings', 'label': 'Settings', 'link': 'settings', 'icon': 'setting'},
        ]
    elif role == 'technician':
        menu_items = [
            {'id': 'techdashboard', 'label': 'Dashboard', 'link': '', 'icon': 'dashboard'},
            {'id': 'techavailablejobs', 'label': 'Available Jobs', 'link': 'techavailablejobs', 'icon': 'search'},
            {'id': 'techmyjobs', 'label': 'My Jobs', 'link': 'techmyjobs', 'icon': 'book'},
            {'id': 'techearnings', 'label': 'Earnings', 'link': 'techearnings', 'icon': 'wallet'},
            {'id': 'technotifications', 'label': 'Notifications', 'link': 'technotifications', 'icon': 'bell'},
            {'id': 'techsettings', 'label': 'Settings', 'link': 'techsettings', 'icon': 'setting'},
        ]
    else:
        menu_items = [
            {'id': 'dashboard', 'label': 'Dashboard', 'link': '', 'icon': 'dashboard'},
            {'id': 'book-service', 'label': 'Book Service', 'link': 'book-service', 'icon': 'calendar'},
            {'id': 'my-bookings', 'label': 'My Bookings', 'link': 'my-bookings', 'icon': 'book'},
            {'id': 'nearby-techs', 'label': 'Nearby Techs', 'link': 'nearby-techs', 'icon': 'environment'},
            {'id': 'payments', 'label': 'Payments', 'link': 'payments', 'icon': 'wallet'},
            {'id': 'notifications', 'label': 'Notifications', 'link': 'notifications', 'icon': 'bell'},
            {'id': 'settings', 'label': 'Settings', 'link': 'settings', 'icon': 'setting'},
        ]

    return JsonResponse({'ok': True, 'menuItems': menu_items})

@csrf_exempt
def customer_dashboard_view(request):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    customer_bookings = Booking.objects.all()
    if request.user.is_authenticated:
        customer_bookings = customer_bookings.filter(customer=request.user)

    total_bookings = customer_bookings.count()
    active_bookings = customer_bookings.filter(~Q(status='completed'), ~Q(status='cancelled')).count()
    completed_bookings = customer_bookings.filter(status='completed').count()
    service_categories = [
        {'key': key, 'label': label, 'description': 'Book a reliable professional for ' + label.lower(), 'icon': key}
        for key, label in Booking.SERVICE_CHOICES
    ]

    stats = [
        {'label': 'Total Bookings', 'value': str(total_bookings)},
        {'label': 'Active Now', 'value': str(active_bookings)},
        {'label': 'Completed', 'value': str(completed_bookings)},
    ]

    return JsonResponse({'ok': True, 'stats': stats, 'serviceCategories': service_categories})

@csrf_exempt
def admin_dashboard_view(request):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    total_users = User.objects.count()
    total_fundis = Profile.objects.filter(role='technician').count()
    total_bookings = Booking.objects.count()
    active_jobs = Booking.objects.filter(~Q(status='completed'), ~Q(status='cancelled')).count()
    pending_bookings = Booking.objects.filter(status='pending').count()
    revenue = Booking.objects.aggregate(total=Sum('estimated_cost'))['total'] or 0

    stats = [
        {'label': 'Total Users', 'value': str(total_users)},
        {'label': 'Total Fundis', 'value': str(total_fundis)},
        {'label': 'Total Bookings', 'value': str(total_bookings)},
        {'label': 'Revenue', 'value': f'KSh {revenue:.2f}'},
        {'label': 'Pending Bookings', 'value': str(pending_bookings)},
        {'label': 'Active Jobs', 'value': str(active_jobs)},
    ]

    recent_activities = [
        {
            'id': booking.id,
            'action': f'{booking.get_service_type_display()} booking {booking.status}',
            'time': booking.created_at.strftime('%b %d %H:%M'),
            'status': booking.status,
        }
        for booking in Booking.objects.order_by('-created_at')[:5]
    ]

    quick_actions = [
        {'name': 'Manage Users'},
        {'name': 'Verify Fundis'},
        {'name': 'View Bookings'},
        {'name': 'Payment Reports'},
    ]

    return JsonResponse({'ok': True, 'stats': stats, 'recentActivities': recent_activities, 'quickActions': quick_actions})

@csrf_exempt
def technician_dashboard_view(request):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    total_jobs = Booking.objects.count()
    active_jobs = Booking.objects.filter(~Q(status='completed'), ~Q(status='cancelled')).count()
    completed_jobs = Booking.objects.filter(status='completed').count()
    earnings = Booking.objects.filter(status='completed').aggregate(total=Sum('estimated_cost'))['total'] or 0

    stats = [
        {'label': 'Total Jobs', 'value': str(total_jobs)},
        {'label': 'Active Jobs', 'value': str(active_jobs)},
        {'label': 'Completed', 'value': str(completed_jobs)},
        {'label': 'Earnings', 'value': f'KSh {earnings:.2f}'},
    ]

    quick_actions = [
        {'name': 'Find Jobs'},
        {'name': 'My Schedule'},
        {'name': 'Earnings'},
    ]

    return JsonResponse({'ok': True, 'stats': stats, 'quickActions': quick_actions})

@csrf_exempt
def bookings_view(request):
    if request.method == 'GET':
        bookings = Booking.objects.order_by('-created_at').all()
        status = request.GET.get('status')
        service_type = request.GET.get('serviceType')
        technician_id = request.GET.get('technicianId')
        search = request.GET.get('search')
        customer_id = request.GET.get('customer_id') or request.GET.get('customerId')

        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile and profile.role == 'technician':
                bookings = bookings.filter(assigned_technician=request.user)
            elif profile and profile.role == 'customer':
                bookings = bookings.filter(customer=request.user)

        if customer_id:
            bookings = bookings.filter(customer__id=customer_id)
        if status:
            bookings = bookings.filter(status__iexact=status)
        if service_type:
            bookings = bookings.filter(service_type__iexact=service_type)
        if technician_id:
            bookings = bookings.filter(assigned_technician__id=technician_id)
        if search:
            bookings = bookings.filter(
                Q(location__icontains=search) |
                Q(description__icontains=search) |
                Q(customer__username__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search)
            )

        payload = [_serialize_booking(booking) for booking in bookings]
        return JsonResponse({'ok': True, 'bookings': payload})

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Invalid JSON payload.'}, status=400)

    service_type = payload.get('serviceType', '').strip()
    location = payload.get('location', '').strip()
    description = payload.get('description', '').strip()
    customer_id = payload.get('customerId')

    if not service_type or not location:
        return JsonResponse({'ok': False, 'message': 'Service type and location are required.'}, status=400)

    customer = None
    if customer_id:
        customer = User.objects.filter(id=customer_id).first()
    if customer is None and request.user.is_authenticated:
        customer = request.user

    scheduled_date_value = None
    if payload.get('scheduledDate'):
        try:
            scheduled_date_value = datetime.strptime(payload.get('scheduledDate'), '%Y-%m-%d').date()
        except ValueError:
            scheduled_date_value = None

    scheduled_time_value = None
    if payload.get('scheduledTime'):
        try:
            scheduled_time_value = datetime.strptime(payload.get('scheduledTime'), '%H:%M').time()
        except ValueError:
            scheduled_time_value = None

    if customer is not None:
        duplicate_window = timezone.now() - timedelta(minutes=5)
        duplicate_exists = Booking.objects.filter(
            customer=customer,
            service_type__iexact=service_type,
            location__iexact=location,
            county__iexact=(payload.get('county', '') or '').strip(),
            town_or_estate__iexact=(payload.get('townOrEstate', '') or '').strip(),
            landmark__iexact=(payload.get('landmark', '') or '').strip(),
            description__iexact=description,
            scheduled_date=scheduled_date_value,
            scheduled_time=scheduled_time_value,
            created_at__gte=duplicate_window,
        ).exclude(status='completed').exclude(status='cancelled').exists()
        if duplicate_exists:
            return JsonResponse(
                {'ok': False, 'message': 'A similar booking already exists. Please check your bookings before submitting again.'},
                status=409,
            )

    booking = Booking.objects.create(
        customer=customer,
        service_type=service_type,
        location=location,
        county=payload.get('county', '').strip(),
        town_or_estate=payload.get('townOrEstate', '').strip(),
        landmark=payload.get('landmark', '').strip(),
        latitude=payload.get('latitude') or None,
        longitude=payload.get('longitude') or None,
        description=description,
        scheduled_date=scheduled_date_value,
        scheduled_time=scheduled_time_value,
        service_window=payload.get('serviceWindow', 'scheduled'),
        estimated_cost=payload.get('estimatedCost', 0) or 0,
    )
    try:
        if booking.customer and booking.customer.email:
            send_booking_created(booking, [booking.customer.email])

        admin_emails = list(User.objects.filter(profile__role='admin').values_list('email', flat=True).distinct().exclude(email=''))
        if admin_emails:
            send_admin_alert(
                'New booking created',
                f"A new {booking.get_service_type_display()} booking was created for {booking.location}.",
                admin_emails,
            )
    except Exception:
        logger.exception('Failed to send booking notification emails')

    return JsonResponse({
        'ok': True,
        'message': 'Booking created successfully.',
        'booking': _serialize_booking(booking),
    })


@csrf_exempt
@require_POST
def assign_booking_view(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Invalid JSON payload.'}, status=400)

    booking_id = payload.get('bookingId')
    technician_id = payload.get('technicianId')

    if not booking_id or not technician_id:
        return JsonResponse({'ok': False, 'message': 'Booking ID and technician ID are required.'}, status=400)

    booking = Booking.objects.filter(id=booking_id).first()
    if not booking:
        return JsonResponse({'ok': False, 'message': 'Booking not found.'}, status=404)

    technician = User.objects.filter(id=technician_id).first()
    if not technician or getattr(getattr(technician, 'profile', None), 'role', '') != 'technician':
        return JsonResponse({'ok': False, 'message': 'Technician not found.'}, status=404)

    booking.assigned_technician = technician
    booking.status = 'assigned'
    booking.save()
    # notify customer and technician about assignment
    try:
        recipients = []
        if booking.customer and booking.customer.email:
            recipients.append(booking.customer.email)
        if technician and technician.email:
            recipients.append(technician.email)
        if recipients:
            send_booking_assigned(booking, technician, recipients)
    except Exception:
        pass
    return JsonResponse({
        'ok': True,
        'message': 'Booking assigned to technician successfully.',
        'booking': _serialize_booking(booking),
    })
