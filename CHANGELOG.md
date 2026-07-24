# CHANGELOG - Security Improvements

## Version 2.0.0 - Security Hardening Release (2026-07-24)

### 🔐 Security Enhancements

#### New Features
- ✅ **Rate Limiting**: IP-based rate limiting on all authentication endpoints
- ✅ **JWT Authentication**: OAuth 2.0 token-based authentication
- ✅ **Database-based Password Reset**: Secure reset codes with expiration
- ✅ **Security Event Logging**: Comprehensive audit logging
- ✅ **User Enumeration Prevention**: Generic error messages
- ✅ **Enhanced Password Validation**: Django validators + custom checks
- ✅ **Admin Key Validation**: Secure admin account creation

#### Dependencies Added
- `djangorestframework-simplejwt>=5.3` - JWT token authentication
- `django-ratelimit>=4.1` - Rate limiting functionality

#### Files Modified
- `api/models.py` - Added PasswordResetCode model
- `api/views.py` - Refactored all auth endpoints with security hardening
- `api/utils/auth_utils.py` - New utility file for security functions
- `fundi_backend/settings.py` - JWT and cache configuration
- `requirements.txt` - Added new security packages

#### Files Created
- `SECURITY_IMPROVEMENTS.md` - Complete security documentation
- `setup_security.sh` - Linux/Mac setup script
- `setup_security.bat` - Windows setup script
- `CHANGELOG.md` - This file

### 📋 Detailed Changes

#### 1. Authentication & Authorization

**Before:**
- In-memory password reset codes (lost on server restart)
- 6-digit reset codes (1M combinations, easily brute-forced)
- No expiration mechanism for reset codes
- User enumeration vulnerabilities
- No rate limiting
- Session-based authentication only

**After:**
- Database-backed secure reset codes (32-char, 2^192 combinations)
- 15-minute auto-expiration for reset codes
- One-time use reset codes
- Generic error messages prevent user enumeration
- Rate limiting on all auth endpoints
- JWT token-based stateless authentication
- Comprehensive security event logging

#### 2. Password Security

**Before:**
```python
if len(password) < 8:
    return error
```

**After:**
```python
from django.contrib.auth.password_validation import validate_password
# Validates against:
# - UserAttributeSimilarityValidator (not similar to username)
# - MinimumLengthValidator (8+ chars)
# - CommonPasswordValidator (against common passwords)
# - NumericPasswordValidator (not all numbers)
# Plus email format validation
```

#### 3. Rate Limiting

**New Configuration:**
```python
RATE_LIMIT_CONFIG = {
    'login': {'attempts': 5, 'period': 900},           # 5 per 15 min
    'forgot_password': {'attempts': 3, 'period': 3600}, # 3 per hour
    'register': {'attempts': 10, 'period': 3600},      # 10 per hour
    'reset_password': {'attempts': 5, 'period': 3600}, # 5 per hour
}
```

**Response on Rate Limit Hit:**
```json
{
    "ok": false,
    "message": "Too many attempts. Please try again later."
}
HTTP 429 Too Many Requests
```

#### 4. Reset Code Generation

**Before:**
```python
reset_code = ''.join(random.choices(string.digits, k=6))
_RESET_CODE_STORE[email] = {'code': reset_code, 'user_id': user.id}
```

**After:**
```python
reset_obj = PasswordResetCode.create_code(user, email, expiry_minutes=15)
# Generates: secrets.token_urlsafe(24) = 32-char code
# Stores in DB with expiration timestamp
# Auto-deletes old codes
```

#### 5. User Enumeration Fix

**Before:**
```
Login endpoint:
❌ "No account found for that email or username"  <- reveals user exists
❌ "Incorrect password"                            <- reveals user exists

Password reset:
❌ Specific user not found error
```

**After:**
```
Login endpoint:
✅ "Invalid credentials"                           <- same for both
✅ "Invalid credentials"                           <- no difference

Password reset:
✅ Generic response regardless of user existence
```

#### 6. Security Logging

**New Logging Feature:**
```python
log_security_event('failed_login', email='user@example.com', ip='192.168.1.1')
log_security_event('password_reset_requested', user=user_obj, ip=ip)
log_security_event('invalid_admin_key_attempt', email='admin@example.com', ip=ip)
```

**Log Output:**
```
WARNING Security Event: failed_login | Email: user@example.com | IP: 192.168.1.1
```

#### 7. Admin Key Validation

**Before:**
```python
admin_key=payload.get('adminKey', '')  # No validation
```

**After:**
```python
if role == 'admin' and not is_valid_admin_key(admin_key):
    log_security_event('invalid_admin_key_attempt', email=email, ip=ip)
    return JsonResponse({'ok': False, 'message': 'Invalid admin key.'}, status=403)
```

#### 8. Cookie Security

**New Configuration:**
```python
CSRF_COOKIE_SECURE = not DEBUG      # HTTPS only in production
SESSION_COOKIE_SECURE = not DEBUG   # HTTPS only in production
CSRF_COOKIE_HTTPONLY = True         # JavaScript cannot access
SESSION_COOKIE_HTTPONLY = True      # JavaScript cannot access
```

#### 9. Cache Configuration

**Added In-Memory Cache:**
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {'MAX_ENTRIES': 10000}
    }
}
```

### 📊 Database Schema

#### New Table: `api_passwordresetcode`
```sql
- id (BigAutoField)
- user_id (ForeignKey to User)
- code (CharField, 32, unique)
- email (EmailField)
- created_at (DateTimeField, auto_now_add)
- expires_at (DateTimeField)
- is_used (BooleanField, default=False)
```

### 🚀 Migration Steps

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create Migrations:**
   ```bash
   python manage.py makemigrations api
   ```

3. **Apply Migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Set Environment Variables:**
   ```bash
   export ADMIN_REGISTRATION_KEY='your-secure-key'
   export DEBUG='False'
   ```

5. **Test:**
   ```bash
   python manage.py test
   ```

### 🧪 Breaking Changes

None - All changes are backward compatible. API response format extended to include JWT tokens.

### ⚠️ Important Notes for Deployment

1. **Set ADMIN_REGISTRATION_KEY** before deploying:
   - Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Set in environment before server starts

2. **Update Frontend** to handle new token response:
   ```json
   {
       "tokens": {
           "access": "...",
           "refresh": "..."
       }
   }
   ```

3. **Cache Backend** - For multi-server deployments:
   - Replace LocMemCache with Redis
   - Update `CACHES` setting in settings.py

4. **Database** - Run migration on production:
   ```bash
   python manage.py migrate --database=production
   ```

5. **Email Settings** - Ensure configured for password reset emails

### 📈 Performance Impact

- **Rate Limiting**: Minimal overhead (in-memory cache lookups)
- **JWT Tokens**: Stateless, reduces session storage
- **Password Reset Codes**: Database queries (negligible for typical usage)
- **Security Logging**: Async logging recommended for production

### 🔍 Testing

Test all security features:
```bash
# Rate limiting
for i in {1..6}; do
    curl -X POST http://localhost:8000/api/login \
      -H "Content-Type: application/json" \
      -d '{"email":"test@test.com","password":"wrong"}'
done

# Password reset expiration
curl -X POST http://localhost:8000/api/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com"}'
# Wait 15 minutes, verify code expires

# JWT token
curl -H "Authorization: Bearer {access_token}" \
  http://localhost:8000/api/user?id=1
```

### 📚 Documentation

- See `SECURITY_IMPROVEMENTS.md` for complete documentation
- See `api/utils/auth_utils.py` for security utility functions
- See `api/models.py` for PasswordResetCode model

### 🙏 Contributors

Security implementation completed on 2026-07-24

---

**Next Steps:**
1. Deploy to staging environment
2. Run full test suite
3. Monitor security logs
4. Deploy to production
5. Notify users of enhanced security features
