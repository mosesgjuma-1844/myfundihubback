# Role-Based Access Control Implementation Guide

## Overview

This document explains how to implement and verify role-based access control (RBAC) in the FUNDI application.

## Current System

### Roles Defined

```python
# From api/models.py Profile model
ROLE_CHOICES = [
    ('customer', 'Customer'),
    ('technician', 'Technician'),
    ('admin', 'Admin'),
]
```

### Role Hierarchy

```
Level 3: Admin (all permissions)
  ↓
Level 2: Technician (assigned jobs, personal data)
  ↓
Level 1: Customer (own bookings, personal data)
  ↓
Level 0: Unauthenticated (public endpoints only)
```

---

## Implementation

### 1. RBAC Utilities (`api/utils/rbac.py`)

New decorators and helper functions for role-based access control:

```python
from api.utils.rbac import (
    require_role,           # Enforce specific role(s)
    require_authenticated,  # Enforce authentication only
    check_ownership,        # Verify resource ownership
    RoleBasedAccessControl, # Utility class with helper methods
)
```

### 2. Decorator Usage

#### Protect Admin Endpoints

```python
from api.utils.rbac import require_role
from django.views.decorators.http import require_POST

@require_POST
@require_role('admin')
def admin_action_view(request):
    """Only admins can access this endpoint."""
    return JsonResponse({'ok': True, 'message': 'Admin action performed'})
```

#### Protect Technician Endpoints

```python
@require_role('technician')
def technician_jobs_view(request):
    """Only technicians can view this endpoint."""
    # request.user is guaranteed to be a technician
    return JsonResponse({'ok': True, 'jobs': []})
```

#### Protect Multi-Role Endpoints

```python
@require_role('admin', 'technician')
def manage_jobs_view(request):
    """Admin or technician can access."""
    profile = request.user.profile
    if profile.role == 'admin':
        # Admin logic
    elif profile.role == 'technician':
        # Technician logic
    return JsonResponse({'ok': True})
```

#### Require Any Authentication

```python
from api.utils.rbac import require_authenticated

@require_authenticated()
def my_profile_view(request):
    """Any authenticated user can access."""
    return JsonResponse({'ok': True, 'user': {...}})
```

### 3. Helper Methods

```python
from api.utils.rbac import RoleBasedAccessControl

# Check user role
if RoleBasedAccessControl.is_admin(request.user):
    # Admin-specific logic

if RoleBasedAccessControl.is_technician(request.user):
    # Technician-specific logic

if RoleBasedAccessControl.is_customer(request.user):
    # Customer-specific logic

# Check if user has any of multiple roles
if RoleBasedAccessControl.has_any_role(request.user, ['admin', 'technician']):
    # Admin or technician logic

# Check resource ownership
if RoleBasedAccessControl.owns_resource(request.user, booking.customer.id):
    # User owns this booking

# Check role hierarchy
if RoleBasedAccessControl.has_higher_or_equal_role(request.user, 'technician'):
    # User is technician or admin
```

---

## Protected Endpoints

### Recommended Protected Endpoints

```
Admin Only:
  POST   /api/auth/register/         (admin_key required)
  GET    /api/admin-dashboard/       
  GET    /api/users/                 
  POST   /api/assign-booking/        
  DELETE /api/user/<id>/             

Technician Only:
  GET    /api/technician-dashboard/  
  GET    /api/assigned-jobs/         

Customer Only:
  GET    /api/customer-dashboard/    
  GET    /api/my-bookings/           

Authenticated (Any Role):
  GET    /api/auth/user/
  POST   /api/bookings/              
  POST   /api/logout/                
```

### How to Apply Protection

Before (Unprotected):
```python
@csrf_exempt
def admin_dashboard_view(request):
    # No authentication check
    # Any user can access
    total_users = User.objects.count()
    return JsonResponse({'ok': True, 'total_users': total_users})
```

After (Protected):
```python
from api.utils.rbac import require_role

@csrf_exempt
@require_role('admin')
def admin_dashboard_view(request):
    # Only admins can access
    # Unauthenticated users get 401
    # Other roles get 403
    total_users = User.objects.count()
    return JsonResponse({'ok': True, 'total_users': total_users})
```

---

## Error Responses

### 401 Unauthorized (Not Authenticated)

**When:** User is not logged in and tries to access protected endpoint

```json
HTTP 401 Unauthorized
{
  "ok": false,
  "message": "Authentication required."
}
```

**How to fix:** User needs to login first

```typescript
// Frontend
try {
  const data = await apiGet('/api/admin-dashboard/');
} catch (error) {
  if (error.statusCode === 401) {
    // Redirect to login
    navigate('/login');
  }
}
```

### 403 Forbidden (Wrong Role)

**When:** User is authenticated but doesn't have required role

```json
HTTP 403 Forbidden
{
  "ok": false,
  "message": "Access denied. This endpoint requires one of the following roles: admin."
}
```

**How to fix:** Ensure user is logged in with correct role

### 400 Bad Request (Missing Parameters)

**When:** Required parameters are missing

```json
HTTP 400 Bad Request
{
  "ok": false,
  "message": "Resource ID is required."
}
```

---

## Testing Role-Based Access

### Test Admin-Only Endpoint

```bash
# Without token (should get 401)
curl -X GET http://localhost:8000/api/admin-dashboard/

# With customer token (should get 403)
curl -X GET http://localhost:8000/api/admin-dashboard/ \
  -H "Authorization: Bearer <customer-token>"

# With admin token (should get 200)
curl -X GET http://localhost:8000/api/admin-dashboard/ \
  -H "Authorization: Bearer <admin-token>"
```

### Test Role Escalation Prevention

```javascript
// Frontend
// Try to access admin endpoint as customer
const adminData = await apiGet('/api/admin-dashboard/');
// Expected: 403 Forbidden error

// Try to access technician endpoint as customer
const techData = await apiGet('/api/technician-dashboard/');
// Expected: 403 Forbidden error
```

### Test Multi-Role Endpoint

```bash
# Admin can access
curl -X GET http://localhost:8000/api/manage-jobs/ \
  -H "Authorization: Bearer <admin-token>"
# Expected: 200

# Technician can access
curl -X GET http://localhost:8000/api/manage-jobs/ \
  -H "Authorization: Bearer <technician-token>"
# Expected: 200

# Customer cannot access
curl -X GET http://localhost:8000/api/manage-jobs/ \
  -H "Authorization: Bearer <customer-token>"
# Expected: 403
```

---

## Implementation Checklist

### Phase 1: Apply RBAC to Critical Endpoints

- [ ] Admin dashboard - `@require_role('admin')`
- [ ] User management - `@require_role('admin')`
- [ ] Booking assignment - `@require_role('admin')`
- [ ] Technician dashboard - `@require_role('technician')`
- [ ] Customer dashboard - `@require_role('customer')`

### Phase 2: Test All Endpoints

- [ ] Test unauthenticated access → 401
- [ ] Test wrong role access → 403
- [ ] Test correct role access → 200
- [ ] Test multi-role endpoints
- [ ] Test role hierarchy

### Phase 3: Update Frontend

- [ ] Catch 403 errors in API error handler
- [ ] Show user-friendly error message
- [ ] Redirect to appropriate dashboard based on role
- [ ] Hide unauthorized features from UI

### Phase 4: Documentation

- [ ] Document protected endpoints
- [ ] Document error responses
- [ ] Create troubleshooting guide
- [ ] Update API documentation

---

## Common Patterns

### Pattern 1: Admin-Only Actions

```python
from api.utils.rbac import require_role

@require_role('admin')
def delete_user_view(request):
    user_id = request.GET.get('id')
    user = User.objects.get(id=user_id)
    user.delete()
    return JsonResponse({'ok': True, 'message': 'User deleted'})
```

### Pattern 2: User-Specific Data

```python
from api.utils.rbac import require_authenticated

@require_authenticated()
def my_bookings_view(request):
    profile = request.user.profile
    
    if profile.role == 'customer':
        bookings = Booking.objects.filter(customer=request.user)
    elif profile.role == 'technician':
        bookings = Booking.objects.filter(assigned_technician=request.user)
    else:
        bookings = Booking.objects.all()
    
    return JsonResponse({
        'ok': True,
        'bookings': [serialize_booking(b) for b in bookings]
    })
```

### Pattern 3: Ownership Verification

```python
from api.utils.rbac import RoleBasedAccessControl, require_authenticated

@require_authenticated()
def update_booking_view(request):
    booking_id = request.GET.get('id')
    booking = Booking.objects.get(id=booking_id)
    
    # Allow admin or booking owner
    is_owner = RoleBasedAccessControl.owns_resource(request.user, booking.customer.id)
    is_admin = RoleBasedAccessControl.is_admin(request.user)
    
    if not (is_owner or is_admin):
        return JsonResponse({'ok': False, 'message': 'Access denied'}, status=403)
    
    # Update logic
    return JsonResponse({'ok': True})
```

---

## Security Best Practices

### ✅ DO

- Always check authentication before accessing user data
- Always check role before allowing sensitive operations
- Return 401 for unauthenticated, 403 for unauthorized
- Use decorators on all protected endpoints
- Log unauthorized access attempts
- Validate role on backend (never trust frontend)

### ❌ DON'T

- Use role from URL parameter as sole authorization check
- Skip role checks because "frontend validates"
- Return same error for auth vs authorization failures
- Store role in JWT without backend verification
- Allow role field to be edited by users
- Trust browser-stored role information

---

## Migration Guide

### Step 1: Update imports in views.py

```python
from api.utils.rbac import require_role, require_authenticated, RoleBasedAccessControl
```

### Step 2: Apply decorators

```python
# Before
@csrf_exempt
def admin_dashboard_view(request):

# After
@csrf_exempt
@require_role('admin')
def admin_dashboard_view(request):
```

### Step 3: Update frontend error handling

```typescript
try {
  const data = await apiGet('/api/admin-dashboard/');
} catch (error) {
  if (error instanceof APIError) {
    if (error.statusCode === 401) {
      showError('Please log in to continue');
      navigate('/login');
    } else if (error.statusCode === 403) {
      showError('You do not have permission to access this resource');
      navigate('/customer-dashboard');
    }
  }
}
```

### Step 4: Test thoroughly

```bash
# Test with different roles
npm run dev              # Frontend
python manage.py runserver  # Backend

# Test all endpoints
# 1. As unauthenticated user
# 2. As customer
# 3. As technician
# 4. As admin
```

---

## Troubleshooting

### Issue: "Authentication required" on all endpoints

**Cause:** JWT token not being sent properly

**Solution:** Check Authorization header:
```javascript
// In browser console
const tokens = JSON.parse(localStorage.getItem('fundiTokens'));
console.log(tokens.access);  // Should have value
```

### Issue: "Access denied" on correct endpoint

**Cause:** User doesn't have required role

**Solution:** Check user's actual role:
```python
# In Django shell
from django.contrib.auth.models import User
user = User.objects.get(id=1)
print(user.profile.role)  # Should be 'admin', 'technician', or 'customer'
```

### Issue: All users can access admin endpoints

**Cause:** RBAC decorator not applied

**Solution:** Check views.py has decorator:
```python
# Should have @require_role
@require_role('admin')
def admin_view(request):
    pass
```

---

## Next Steps

1. **Apply RBAC Decorators**
   - Start with admin endpoints
   - Then technician endpoints
   - Finally customer endpoints

2. **Test Comprehensive**
   - Each endpoint with all role combinations
   - Invalid tokens
   - Expired tokens
   - Missing Authorization header

3. **Monitor & Log**
   - Log failed authorization attempts
   - Monitor 403 errors in production
   - Alert on repeated 403 attempts

4. **Document API**
   - Mark protected endpoints in API docs
   - Specify required roles
   - Document error responses

---

**Version:** 2.0.0  
**Status:** Ready for Implementation ✅  
**Last Updated:** 2026-07-24
