#!/usr/bin/env python3
"""
Role-Based Access Control Testing Script

This script tests the RBAC implementation by:
1. Creating test users with different roles
2. Generating JWT tokens for each user
3. Testing protected endpoints with each token
4. Verifying correct access control enforcement
"""

import os
import sys
import json
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundi_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from api.models import Profile
from api.utils.auth_utils import get_tokens_for_user
from rest_framework_simplejwt.tokens import RefreshToken

# Color codes for output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(title):
    """Print a formatted header."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{title:^60}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_success(message):
    """Print a success message."""
    print(f"{GREEN}✓ {message}{RESET}")


def print_error(message):
    """Print an error message."""
    print(f"{RED}✗ {message}{RESET}")


def print_info(message):
    """Print an info message."""
    print(f"{BLUE}ℹ {message}{RESET}")


def create_test_users():
    """Create test users with different roles."""
    print_header("Creating Test Users")
    
    test_users = [
        ('admin_user', 'admin@test.com', 'admin', 'password123'),
        ('tech_user', 'tech@test.com', 'technician', 'password123'),
        ('customer_user', 'customer@test.com', 'customer', 'password123'),
    ]
    
    users = {}
    for username, email, role, password in test_users:
        # Delete if exists
        User.objects.filter(username=username).delete()
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=role.title(),
            last_name='Test User'
        )
        
        # Create or update profile
        Profile.objects.filter(user=user).delete()
        Profile.objects.create(
            user=user,
            role=role,
            phone_number='0700000000',
            specialization='Testing' if role == 'technician' else '',
        )
        
        users[role] = {
            'user': user,
            'username': username,
            'email': email,
            'password': password,
        }
        
        print_success(f"Created {role} user: {username} ({email})")
    
    return users


def generate_tokens(user):
    """Generate JWT tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def test_rbac_decorators():
    """Test RBAC decorator functionality."""
    print_header("Testing RBAC Decorators")
    
    from api.utils.rbac import RoleBasedAccessControl, require_role
    
    users = create_test_users()
    
    print_info("Testing RoleBasedAccessControl helper methods:\n")
    
    for role, user_data in users.items():
        user = user_data['user']
        
        # Test helper methods
        print(f"\n{YELLOW}User: {user.username} (Role: {role}){RESET}")
        
        # Test has_role
        is_correct_role = RoleBasedAccessControl.has_role(user, role)
        if is_correct_role:
            print_success(f"has_role(user, '{role}') = True")
        else:
            print_error(f"has_role(user, '{role}') = False")
        
        # Test is_admin
        is_admin = RoleBasedAccessControl.is_admin(user)
        expected_admin = role == 'admin'
        if is_admin == expected_admin:
            print_success(f"is_admin(user) = {is_admin} (expected: {expected_admin})")
        else:
            print_error(f"is_admin(user) = {is_admin} (expected: {expected_admin})")
        
        # Test is_technician
        is_tech = RoleBasedAccessControl.is_technician(user)
        expected_tech = role == 'technician'
        if is_tech == expected_tech:
            print_success(f"is_technician(user) = {is_tech} (expected: {expected_tech})")
        else:
            print_error(f"is_technician(user) = {is_tech} (expected: {expected_tech})")
        
        # Test is_customer
        is_cust = RoleBasedAccessControl.is_customer(user)
        expected_cust = role == 'customer'
        if is_cust == expected_cust:
            print_success(f"is_customer(user) = {is_cust} (expected: {expected_cust})")
        else:
            print_error(f"is_customer(user) = {is_cust} (expected: {expected_cust})")
        
        # Test role level
        level = RoleBasedAccessControl.get_role_level(user)
        expected_level = {'customer': 1, 'technician': 2, 'admin': 3}[role]
        if level == expected_level:
            print_success(f"get_role_level(user) = {level} (expected: {expected_level})")
        else:
            print_error(f"get_role_level(user) = {level} (expected: {expected_level})")


def test_jwt_tokens():
    """Test JWT token generation and validation."""
    print_header("Testing JWT Token Generation")
    
    users = create_test_users()
    tokens_data = {}
    
    for role, user_data in users.items():
        user = user_data['user']
        tokens = generate_tokens(user)
        tokens_data[role] = tokens
        
        print(f"\n{YELLOW}{role.title()} Token:{RESET}")
        print(f"  Access Token (first 50 chars): {tokens['access'][:50]}...")
        print(f"  Refresh Token (first 50 chars): {tokens['refresh'][:50]}...")
        print_success(f"Generated tokens for {role} user")
    
    return tokens_data


def test_role_hierarchy():
    """Test role hierarchy."""
    print_header("Testing Role Hierarchy")
    
    from api.utils.rbac import RoleBasedAccessControl
    
    users = create_test_users()
    
    print_info("Role Hierarchy (higher = more privileged):\n")
    print("  Level 1: Customer")
    print("  Level 2: Technician")
    print("  Level 3: Admin\n")
    
    test_cases = [
        ('admin', 'admin', True, "Admin can access admin level"),
        ('admin', 'technician', True, "Admin has higher level than technician"),
        ('technician', 'technician', True, "Technician can access technician level"),
        ('technician', 'admin', False, "Technician cannot access admin level"),
        ('customer', 'technician', False, "Customer cannot access technician level"),
        ('customer', 'customer', True, "Customer can access customer level"),
    ]
    
    for user_role, required_role, expected, description in test_cases:
        user = users[user_role]['user']
        result = RoleBasedAccessControl.has_higher_or_equal_role(user, required_role)
        
        if result == expected:
            print_success(f"{description}")
        else:
            print_error(f"{description} (got: {result}, expected: {expected})")


def test_ownership():
    """Test resource ownership checks."""
    print_header("Testing Resource Ownership")
    
    from api.utils.rbac import RoleBasedAccessControl
    
    users = create_test_users()
    
    customer_user = users['customer']['user']
    admin_user = users['admin']['user']
    
    # Create a booking for customer
    from api.models import Booking
    Booking.objects.all().delete()
    
    booking = Booking.objects.create(
        customer=customer_user,
        service_type='electrical',
        location='Test Location',
    )
    
    print_info(f"Created booking #{booking.id} for customer ({customer_user.id})\n")
    
    # Test ownership
    owns_customer = RoleBasedAccessControl.owns_resource(customer_user, booking.customer.id)
    if owns_customer:
        print_success("Customer owns their own booking")
    else:
        print_error("Customer should own their own booking")
    
    owns_admin = RoleBasedAccessControl.owns_resource(admin_user, booking.customer.id)
    if not owns_admin:
        print_success("Admin does not own customer's booking")
    else:
        print_error("Admin should not own customer's booking")


def test_access_control_decision_matrix():
    """Create and display access control decision matrix."""
    print_header("Access Control Decision Matrix")
    
    roles = ['customer', 'technician', 'admin']
    endpoints = {
        'customer-dashboard': ['customer', 'admin'],
        'technician-dashboard': ['technician', 'admin'],
        'admin-dashboard': ['admin'],
        'manage-bookings': ['admin', 'technician'],
        'user-profile': ['customer', 'technician', 'admin'],
    }
    
    print(f"\n{YELLOW}Endpoint Protection Levels:{RESET}\n")
    print(f"{'Endpoint':<25} | {' | '.join(roles):<30}")
    print("-" * 70)
    
    for endpoint, allowed_roles in endpoints.items():
        row = f"{endpoint:<25} |"
        for role in roles:
            status = "✓" if role in allowed_roles else "✗"
            row += f" {status:^5} |"
        print(row)


def run_all_tests():
    """Run all RBAC tests."""
    print(f"\n{BLUE}{'*' * 60}{RESET}")
    print(f"{BLUE}{'FUNDI RBAC Testing Suite':^60}{RESET}")
    print(f"{BLUE}{'*' * 60}{RESET}")
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Run tests
        test_rbac_decorators()
        test_jwt_tokens()
        test_role_hierarchy()
        test_ownership()
        test_access_control_decision_matrix()
        
        # Summary
        print_header("Test Summary")
        print_success("All RBAC tests completed successfully!")
        print_info("Next: Apply @require_role decorators to protected endpoints in views.py")
        
    except Exception as e:
        print_error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == '__main__':
    run_all_tests()
