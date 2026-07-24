# Secret Key Management Setup Guide

## 🚀 Quick Start (5 minutes)

### 1. Install Dependencies

```bash
cd Backend
pip install python-dotenv
```

### 2. Create Local .env File

```bash
# Copy the example file
cp .env.example .env

# File should contain:
# SECRET_KEY=django-insecure-dev-only-...
# DEBUG=True
# ADMIN_REGISTRATION_KEY=dev-admin-key-local-only
```

### 3. Test Locally

```bash
python manage.py runserver
# Should start without errors
```

---

## 🔐 Production Setup

### Step 1: Generate Secure Keys

```bash
# Generate SECRET_KEY (run this in your terminal)
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Generate ADMIN_REGISTRATION_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Save these outputs - you'll need them for Step 2
```

**Example output:**
```
abc123xyz789... (SECRET_KEY - ~50 characters)
k9mL2pQ5wR8... (ADMIN_REGISTRATION_KEY - ~43 characters)
```

### Step 2: Set Environment Variables

**On Railway:**

1. Go to Railway Dashboard → Your Project
2. Click "Variables" tab
3. Add these variables:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | (paste generated value) |
| `ADMIN_REGISTRATION_KEY` | (paste generated value) |
| `DEBUG` | `False` |
| `EMAIL_HOST_USER` | (your Gmail) |
| `EMAIL_HOST_PASSWORD` | (Gmail app password) |
| `DATABASE_URL` | (Railway provides) |

**On Heroku:**

```bash
heroku config:set SECRET_KEY="<generated-value>" --app your-app-name
heroku config:set ADMIN_REGISTRATION_KEY="<generated-value>" --app your-app-name
heroku config:set DEBUG="False" --app your-app-name
heroku config:set EMAIL_HOST_USER="<email>" --app your-app-name
heroku config:set EMAIL_HOST_PASSWORD="<password>" --app your-app-name
```

**On AWS:**

Use AWS Secrets Manager or Parameter Store to store credentials.

### Step 3: Deploy

```bash
git add -A
git commit -m "Remove hardcoded secrets, add environment variable validation"
git push
```

---

## 📋 Environment Variables Reference

### Required in Production

```env
# Django Security - REQUIRED
SECRET_KEY=<generated-with-python-command>
DEBUG=False
ADMIN_REGISTRATION_KEY=<generated-with-python-command>

# Email - REQUIRED
EMAIL_HOST_USER=<production-email@gmail.com>
EMAIL_HOST_PASSWORD=<gmail-app-password>

# Database - REQUIRED (usually provided by platform)
DATABASE_URL=postgresql://user:pass@host:port/db
```

### Optional

```env
# Logging
LOG_LEVEL=INFO

# Railway (if using Railway)
RAILWAY_PUBLIC_DOMAIN=<domain>

# Email (defaults to EMAIL_HOST_USER if not set)
DEFAULT_FROM_EMAIL=<email>
```

### Development Only

```env
# These are safe to keep as defaults in local .env
SECRET_KEY=django-insecure-dev-only-local-testing-do-not-use-in-production
DEBUG=True
ADMIN_REGISTRATION_KEY=dev-admin-key-local-only
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

---

## ✅ Verification Checklist

### Before Deployment

- [ ] Generated SECRET_KEY with Python command
- [ ] Generated ADMIN_REGISTRATION_KEY with Python command
- [ ] Created .env file locally
- [ ] .env not committed to Git
- [ ] .env.example added to Git (without secrets)
- [ ] python-dotenv installed
- [ ] Local tests pass
- [ ] No hardcoded secrets in settings.py

### After Deployment

- [ ] Environment variables set in production platform
- [ ] Application starts without errors
- [ ] Login page works
- [ ] Password reset email sends
- [ ] No secrets in error logs
- [ ] No secrets in Git history

---

## 🔒 Git Security

### Add .env to .gitignore

```bash
# If not already there
echo ".env" >> Backend/.gitignore
echo ".env.local" >> Backend/.gitignore
echo ".env.*.local" >> Backend/.gitignore
```

### Check Git History

If you've committed secrets before:

```bash
# Search for exposed secrets
git log -p -S "SECRET_KEY" -- Backend/

# If found, you need to rewrite history (advanced - ask for help)
```

---

## 🐛 Troubleshooting

### Error: "SECRET_KEY environment variable is required in production"

**Cause:** SECRET_KEY not set in production and DEBUG=False

**Fix:**
```bash
# Generate and set SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Railway: Add to Variables
# Heroku: heroku config:set SECRET_KEY="value"
```

### Error: "EMAIL credentials are required in production"

**Cause:** EMAIL_HOST_USER or EMAIL_HOST_PASSWORD not set

**Fix:**
```bash
# Get Gmail app password:
# 1. Go to myaccount.google.com/apppasswords
# 2. Create new app password
# 3. Copy the password

# Set variables:
# Railway: Add to Variables
# Heroku: heroku config:set EMAIL_HOST_USER="email" EMAIL_HOST_PASSWORD="password"
```

### Error: "ADMIN_REGISTRATION_KEY environment variable is required"

**Cause:** ADMIN_REGISTRATION_KEY not set in production

**Fix:**
```bash
# Generate
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in production platform
```

### Local app won't start

**Solution:**

```bash
# 1. Check .env exists
ls -la Backend/.env

# 2. Check python-dotenv installed
pip list | grep dotenv

# 3. Test import
python -c "from fundi_backend import settings; print('OK')"

# 4. If still failing, delete and recreate:
rm Backend/.env
cp Backend/.env.example Backend/.env
```

---

## 📚 Reference

### Files Modified

- ✅ `Backend/fundi_backend/settings.py` - Removed hardcoded secrets, added validation
- ✅ `Backend/.env.example` - Added template
- ✅ `Backend/.gitignore` - Should contain `.env`

### Files NOT Modified (for reference)

- `Backend/api/views.py` - Password validation still uses Django's built-in
- `Backend/manage.py` - Standard Django file
- Frontend - No changes needed

### Related Documentation

- [SECURITY_AUDIT_SECRET_MANAGEMENT.md](../SECURITY_AUDIT_SECRET_MANAGEMENT.md) - Full audit report
- [Django Security Docs](https://docs.djangoproject.com/en/6.0/topics/security/)
- [python-dotenv Docs](https://python-dotenv.readthedocs.io/)

---

## 🎓 Best Practices Summary

### ✅ DO

1. Generate strong unique keys for each environment
2. Store keys in environment variables
3. Use .env for local development
4. Never commit .env files
5. Use .env.example as template
6. Rotate keys yearly
7. Use different keys per environment
8. Validate required keys on startup

### ❌ DON'T

1. Commit .env files
2. Use same key in dev/staging/production
3. Hardcode fallback values
4. Share secrets via Slack/email
5. Log secrets
6. Use weak keys
7. Reuse email passwords
8. Skip validation in production

---

## 📞 Support

If you encounter issues:

1. Check this guide first
2. Review SECURITY_AUDIT_SECRET_MANAGEMENT.md
3. Check environment variables are set correctly
4. Verify .env file syntax (no quotes needed for simple values)
5. Test with: `python -c "from fundi_backend import settings; print('OK')"`

---

**Status:** ✅ Ready to Deploy  
**Last Updated:** 2026-07-24  
**Next Steps:** Follow verification checklist before deploying to production
