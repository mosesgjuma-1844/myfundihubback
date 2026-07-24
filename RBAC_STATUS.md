# Role-Based Access Control (RBAC) - Status & Implementation

## 📊 Current Status

### ✅ What's Already Implemented

1. **Role Model**
   - Defined in `api/models.py` Profile model
   - Three roles: customer, technician, admin
   - Assigned during registration

2. **Role-Based Routing**
   - Login returns different redirect URLs based on role
   - Menu endpoint returns different items per role

3. **JWT Tokens**
   - Tokens include user ID (which resolves to role via profile)
   - Tokens enable API-based access control

4. **Partial Role Filtering**
   - Bookings view filters by role (if authenticated)
   - Dashboard views query based on role

### ⚠️ What's Missing (CRITICAL SECURITY GAP)

1. **No Access Control Enforcement**
   - Endpoints don't verify user has required role
   - No decorators protecting admin/technician endpoints
   - Users could potentially access wrong dashboard endpoints

2. **No Authentication Required**
   - Many endpoints use `@csrf_exempt` without auth check
   - `request.user` relies on Django session, not JWT token from header
   - API clients can't be properly authenticated

3. **No Authorization Checks**
   - No validation that user owns resource they're accessing
   - No checks for role before sensitive operations

---

## 🚀 Implementation Plan

### Phase 1: Create RBAC Infrastructure (DONE ✅)

Files created:
- **`api/utils/rbac.py`** - RBAC decorators and utilities
  - `@require_role('admin')` decorator
  - `@require_authenticated()` decorator
  - `RoleBasedAccessControl` helper class
  - Role hierarchy checks

- **`ROLE_BASED_ACCESS_CONTROL.md`** - Complete documentation
  - How to use decorators
  - Error responses
  - Testing guide
  - Best practices

- **`test_rbac.py`** - Automated test script
  - Creates test users
  - Tests decorators
  - Tests role hierarchy
  - Tests ownership verification

### Phase 2: Apply RBAC to Views (TODO)

**High Priority - Admin Endpoints:**
```python
# api/views.py
from api.utils.rbac import require_role

@require_role('admin')
def admin_dashboard_view(request):
    # Only admins can access
    pass

@require_role('admin')
def assign_booking_view(request):
    # Only admins can assign bookings
    pass

@require_role('admin')
def user_management_view(request):
    # Only admins can manage users
    pass
```

**High Priority - Technician Endpoints:**
```python
@require_role('technician')
def technician_dashboard_view(request):
    # Only technicians
    pass

@require_role('technician')
def technician_jobs_view(request):
    # Only technicians
    pass
```

**High Priority - Customer Endpoints:**
```python
@require_role('customer')
def customer_dashboard_view(request):
    # Only customers
    pass
```

**Medium Priority - Mixed Role Endpoints:**
```python
from api.utils.rbac import require_role, RoleBasedAccessControl

@require_role('admin', 'technician', 'customer')
def bookings_view(request):
    # All authenticated users, but filter by role
    profile = request.user.profile
    if profile.role == 'admin':
        # See all bookings
        pass
    elif profile.role == 'technician':
        # See assigned jobs
        pass
    else:
        # See own bookings
        pass
```

### Phase 3: Update Frontend (TODO)

**Handle 403 Errors:**
```typescript
try {
  const data = await apiGet('/api/admin-dashboard/');
} catch (error) {
  if (error instanceof APIError) {
    if (error.statusCode === 403) {
      showError('You do not have permission to access this resource');
      // Redirect to appropriate dashboard
      if (userRole === 'customer') {
        navigate('/customer-dashboard');
      }
    }
  }
}
```

**Hide Unauthorized Features:**
```typescript
const canManageUsers = userRole === 'admin';
const canAssignJobs = userRole === 'admin';

{canManageUsers && <ManageUsersButton />}
{canAssignJobs && <AssignJobButton />}
```

### Phase 4: Test Comprehensively (TODO)

**Run Automated Tests:**
```bash
cd Backend
python manage.py shell < test_rbac.py
```

**Manual Testing:**
1. Login as customer → should only see customer dashboard
2. Login as technician → should only see technician dashboard
3. Login as admin → should see admin dashboard
4. Try to access wrong dashboard → should get 403 error

---

## 📋 Checklist

### Setup (✅ DONE)
- [x] Create `api/utils/rbac.py` with decorators
- [x] Document RBAC system
- [x] Create test script
- [x] Add helper methods

### Implementation (TODO)
- [ ] Apply `@require_role` to admin endpoints
- [ ] Apply `@require_role` to technician endpoints
- [ ] Apply `@require_role` to customer endpoints
- [ ] Apply ownership checks where needed
- [ ] Update error handling

### Testing (TODO)
- [ ] Run automated test script
- [ ] Test each endpoint with all role combinations
- [ ] Test unauthenticated access
- [ ] Test role escalation attempts
- [ ] Test resource ownership

### Frontend (TODO)
- [ ] Handle 403 errors properly
- [ ] Hide unauthorized features
- [ ] Show user-friendly error messages
- [ ] Test role-based UI
- [ ] Test redirect logic

---

## 🔒 Security Enforcement

### Critical Endpoints to Protect

```
ADMIN ONLY (Level 3):
├─ GET    /api/admin-dashboard/
├─ POST   /api/assign-booking/
├─ POST   /api/user/delete/
├─ GET    /api/users/
└─ GET    /api/admin-reports/

TECHNICIAN (Level 2):
├─ GET    /api/technician-dashboard/
├─ GET    /api/assigned-jobs/
└─ POST   /api/job-accept/

CUSTOMER (Level 1):
├─ GET    /api/customer-dashboard/
├─ GET    /api/my-bookings/
└─ POST   /api/bookings/

AUTHENTICATED (Any Level):
├─ GET    /api/auth/user/
├─ POST   /api/auth/logout/
└─ GET    /api/menu/
```

### Error Responses

| Scenario | Status | Response |
|----------|--------|----------|
| Not logged in | 401 | "Authentication required." |
| Wrong role | 403 | "Access denied. This endpoint requires: admin." |
| No permission | 403 | "You do not have permission to access this resource." |
| Success | 200 | Normal response |

---

## 🧪 Testing Guide

### Quick Test (5 minutes)

```bash
# 1. Start Django shell
python manage.py shell

# 2. Test RBAC utilities
from api.utils.rbac import RoleBasedAccessControl
from django.contrib.auth.models import User

admin = User.objects.filter(profile__role='admin').first()
print(RoleBasedAccessControl.is_admin(admin))  # Should print True
print(RoleBasedAccessControl.has_role(admin, 'technician'))  # Should print False
```

### Comprehensive Test (15 minutes)

```bash
# 1. Run test script
python test_rbac.py

# 2. Check output for:
#    ✓ All user creation succeeds
#    ✓ All role checks pass
#    ✓ Token generation works
#    ✓ Hierarchy is correct
```

### Full Test (30 minutes)

```bash
# 1. Start servers
npm run dev              # Frontend on 5173
python manage.py runserver  # Backend on 8000

# 2. Test in browser
# - Login as customer → see customer dashboard
# - Try to access /admin-dashboard → get 403 error
# - Login as admin → see admin dashboard
# - Verify tokens in localStorage

# 3. Test with curl
curl -H "Authorization: Bearer <admin-token>" \
  http://localhost:8000/api/admin-dashboard/  # Should work

curl -H "Authorization: Bearer <customer-token>" \
  http://localhost:8000/api/admin-dashboard/  # Should fail with 403
```

---

## 📚 Documentation

### Main Files
- **`ROLE_BASED_ACCESS_CONTROL.md`** - Complete implementation guide
- **`api/utils/rbac.py`** - Source code with detailed docstrings
- **`test_rbac.py`** - Test script and examples

### Key Classes & Functions

```python
# Decorators
@require_role('admin')              # Enforce admin role
@require_role('admin', 'technician') # Enforce multiple roles
@require_authenticated()             # Enforce any authentication

# Utilities
RoleBasedAccessControl.is_admin(user)
RoleBasedAccessControl.is_technician(user)
RoleBasedAccessControl.is_customer(user)
RoleBasedAccessControl.has_role(user, 'admin')
RoleBasedAccessControl.owns_resource(user, owner_id)
RoleBasedAccessControl.get_role_level(user)
RoleBasedAccessControl.has_higher_or_equal_role(user, 'technician')
```

---

## 🎯 Next Steps

### Immediate (Today)
1. Review `ROLE_BASED_ACCESS_CONTROL.md`
2. Understand the decorators in `api/utils/rbac.py`
3. Run `python test_rbac.py` to verify setup

### Short Term (This Week)
1. Apply decorators to critical admin endpoints
2. Update frontend to handle 403 errors
3. Test role-based access

### Medium Term (Next Week)
1. Apply decorators to all endpoints
2. Comprehensive security testing
3. Update documentation
4. Deploy to staging

---

## 📈 Security Impact

### Before RBAC
- ❌ Any customer could access admin dashboard URL
- ❌ Technicians could view all users
- ❌ Users could modify others' bookings
- ❌ No enforcement of role-based features

### After RBAC
- ✅ Admin endpoints return 403 for non-admins
- ✅ JWT tokens validated before endpoint access
- ✅ Ownership verified for resource access
- ✅ Role hierarchy enforced automatically
- ✅ Logging of unauthorized access attempts

---

## 📞 Support

### Questions About Implementation?

1. **How to use decorators?**
   → See `ROLE_BASED_ACCESS_CONTROL.md` → "Decorator Usage"

2. **How to test RBAC?**
   → Run `python test_rbac.py`

3. **How to handle errors in frontend?**
   → See section → "Frontend Error Handling"

4. **How to check role in code?**
   → Use `RoleBasedAccessControl` helper methods

### Common Issues

**Issue:** Decorator not working
- Make sure it's imported: `from api.utils.rbac import require_role`
- Make sure it's applied above the function definition
- Make sure views.py has the import

**Issue:** 401 errors everywhere
- Check JWT token is being sent in Authorization header
- Verify token is valid and not expired
- Check `get_user_from_jwt()` is extracting user correctly

**Issue:** 403 errors when shouldn't
- Verify user's role in database: `user.profile.role`
- Check decorator has correct role: `@require_role('admin')`
- Check test user was created with correct role

---

## ✨ Summary

The RBAC infrastructure is ready to use! You now have:

✅ **Complete Decorator System** - Apply `@require_role` to any endpoint
✅ **Helper Methods** - Query role permissions in code
✅ **Test Suite** - Verify RBAC works as expected
✅ **Documentation** - Comprehensive guides and examples

**Next:** Apply decorators to views.py and test end-to-end.

---

**Status:** Ready for Implementation 🚀  
**Estimated Implementation Time:** 2-3 hours  
**Estimated Testing Time:** 1-2 hours  
**Last Updated:** 2026-07-24
