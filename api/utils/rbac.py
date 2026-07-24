"""
Role-Based Access Control (RBAC) Utilities

Provides decorators and helpers for enforcing role-based access control
across API endpoints. Prevents unauthorized users from accessing role-specific features.
"""

from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.models import User
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


def get_user_role(request):
    """Extract user's role from the request."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return None
    
    profile = getattr(request.user, 'profile', None)
    if profile:
        return profile.role.lower()
    
    return 'customer'  # Default role


def get_user_from_jwt(request):
    """Extract user from JWT token if present."""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    
    if not auth_header.startswith('Bearer '):
        return None
    
    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(auth_header.split(' ')[1])
        user = jwt_auth.get_user(validated_token)
        return user
    except (InvalidToken, AuthenticationFailed):
        return None


def require_role(*allowed_roles):
    """
    Decorator to enforce role-based access control.
    
    Usage:
        @require_role('admin')
        def admin_only_view(request):
            pass
        
        @require_role('admin', 'technician')
        def admin_or_tech_view(request):
            pass
    """
    allowed_roles_lower = [role.lower() for role in allowed_roles]
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Try to get user from JWT first (for API calls)
            user = get_user_from_jwt(request)
            
            # Fall back to session-authenticated user
            if not user:
                user = request.user if hasattr(request, 'user') else None
            
            # Check if user is authenticated
            if not user or not user.is_authenticated:
                return JsonResponse(
                    {
                        'ok': False,
                        'message': 'Authentication required.',
                    },
                    status=401,
                )
            
            # Get user role
            profile = getattr(user, 'profile', None)
            user_role = profile.role.lower() if profile else 'customer'
            
            # Check if user has required role
            if user_role not in allowed_roles_lower:
                return JsonResponse(
                    {
                        'ok': False,
                        'message': f'Access denied. This endpoint requires one of the following roles: {", ".join(allowed_roles)}.',
                    },
                    status=403,
                )
            
            # Inject authenticated user into request
            request.user = user
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_authenticated():
    """Decorator to require any authenticated user."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Try JWT first
            user = get_user_from_jwt(request)
            
            # Fall back to session
            if not user:
                user = request.user if hasattr(request, 'user') else None
            
            if not user or not user.is_authenticated:
                return JsonResponse(
                    {
                        'ok': False,
                        'message': 'Authentication required.',
                    },
                    status=401,
                )
            
            request.user = user
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def check_ownership(owner_field='customer'):
    """
    Decorator to check if authenticated user owns the requested resource.
    
    Usage:
        @check_ownership('customer')
        def booking_detail_view(request):
            pass
    
    Args:
        owner_field: The field name that contains the owner (e.g., 'customer', 'technician')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Authenticate user
            user = get_user_from_jwt(request)
            if not user:
                user = request.user if hasattr(request, 'user') else None
            
            if not user or not user.is_authenticated:
                return JsonResponse(
                    {
                        'ok': False,
                        'message': 'Authentication required.',
                    },
                    status=401,
                )
            
            # Get resource ID from kwargs or query params
            resource_id = kwargs.get('id') or request.GET.get('id')
            
            if not resource_id:
                return JsonResponse(
                    {
                        'ok': False,
                        'message': 'Resource ID is required.',
                    },
                    status=400,
                )
            
            # Store auth info in request for view to use
            request.user = user
            request.owner_field = owner_field
            request.resource_id = resource_id
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


class RoleBasedAccessControl:
    """
    Utility class for role-based access control checks.
    """
    
    ROLES = {
        'customer': {'level': 1, 'description': 'Customer'},
        'technician': {'level': 2, 'description': 'Service Provider (Technician)'},
        'admin': {'level': 3, 'description': 'Administrator'},
    }
    
    @staticmethod
    def has_role(user, required_role):
        """Check if user has a specific role."""
        if not user or not user.is_authenticated:
            return False
        
        profile = getattr(user, 'profile', None)
        if not profile:
            return required_role.lower() == 'customer'
        
        return profile.role.lower() == required_role.lower()
    
    @staticmethod
    def has_any_role(user, roles):
        """Check if user has any of the specified roles."""
        return any(RoleBasedAccessControl.has_role(user, role) for role in roles)
    
    @staticmethod
    def is_admin(user):
        """Check if user is an admin."""
        return RoleBasedAccessControl.has_role(user, 'admin')
    
    @staticmethod
    def is_technician(user):
        """Check if user is a technician."""
        return RoleBasedAccessControl.has_role(user, 'technician')
    
    @staticmethod
    def is_customer(user):
        """Check if user is a customer."""
        return RoleBasedAccessControl.has_role(user, 'customer')
    
    @staticmethod
    def owns_resource(user, resource_owner_id):
        """Check if user owns a resource."""
        if not user or not user.is_authenticated:
            return False
        return user.id == resource_owner_id
    
    @staticmethod
    def get_role_level(user):
        """Get the numeric level of user's role (higher = more privileged)."""
        if not user or not user.is_authenticated:
            return 0
        
        profile = getattr(user, 'profile', None)
        role = profile.role.lower() if profile else 'customer'
        return RoleBasedAccessControl.ROLES.get(role, {}).get('level', 0)
    
    @staticmethod
    def has_higher_or_equal_role(user, required_role):
        """Check if user's role level is >= required role level."""
        user_level = RoleBasedAccessControl.get_role_level(user)
        required_level = RoleBasedAccessControl.ROLES.get(required_role.lower(), {}).get('level', 0)
        return user_level >= required_level
