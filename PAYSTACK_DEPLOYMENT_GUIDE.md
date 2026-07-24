# Paystack Integration - Deployment & Migration Guide

**Status:** Ready for Deployment  
**Date:** 2026-07-24  

---

## 🚀 Quick Deployment (10 minutes)

### Step 1: Install Dependencies

```bash
cd Backend
pip install -r requirements.txt
```

**What gets installed:**
- `requests` - HTTP library for Paystack API calls
- `python-dotenv` - Environment variable management
- All other existing dependencies

---

### Step 2: Configure Environment Variables

#### Local Development

```bash
# Create .env file
cd Backend
cat > .env << 'EOF'
SECRET_KEY=django-insecure-dev-only-local-testing-do-not-use-in-production
DEBUG=True
ADMIN_REGISTRATION_KEY=dev-admin-key-local-only
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key_here
PAYSTACK_SECRET_KEY=sk_test_your_secret_key_here
FRONTEND_URL=http://localhost:5173
LOG_LEVEL=DEBUG
EOF
```

#### Production (Railway)

1. Go to Railway Dashboard
2. Select Project → Variables
3. Add these variables:

```
PAYSTACK_PUBLIC_KEY = pk_live_your_production_public_key
PAYSTACK_SECRET_KEY = sk_live_your_production_secret_key
FRONTEND_URL = https://yourdomain.com
SECRET_KEY = (already set)
DEBUG = False
```

---

### Step 3: Run Database Migrations

```bash
# Create migrations for new Payment & Transaction models
python manage.py makemigrations

# Expected output:
# Migrations for 'api':
#   api/migrations/XXXX_initial.py
#     - Create model Payment
#     - Create model Transaction

# Apply migrations
python manage.py migrate

# Expected output:
# Running migrations:
#   Applying api.XXXX_initial... OK
```

---

### Step 4: Verify Models Created

```bash
# Start Django shell
python manage.py shell

# List all models
>>> from django.apps import apps
>>> apps.get_app_config('api').get_models()

# Should include:
# - Payment
# - Transaction
# - Booking
# - Profile
# - PasswordResetCode
```

---

### Step 5: Test Endpoints

```bash
# Start development server
python manage.py runserver

# In another terminal, test the API
curl -X POST http://localhost:8000/api/payments/webhook/paystack/ \
  -H "Content-Type: application/json" \
  -H "X-Paystack-Signature: test" \
  -d '{"event": "charge.success"}'

# Should return error (invalid signature is expected without proper Paystack webhook)
```

---

## 📋 Migration Commands Reference

### Create Migrations

```bash
# Detect changes in models
python manage.py makemigrations

# Create migration for specific app
python manage.py makemigrations api

# Show what will be migrated (dry-run)
python manage.py makemigrations --dry-run --verbosity 3
```

### Apply Migrations

```bash
# Apply all pending migrations
python manage.py migrate

# Apply migrations for specific app
python manage.py migrate api

# See migration status
python manage.py showmigrations

# Migrate to specific point (rollback)
python manage.py migrate api 0001_initial
```

### Check Migration Status

```bash
# Show all migrations and their status
python manage.py showmigrations api

# Example output:
# api
#  [X] 0001_initial
#  [X] 0002_booking
#  [ ] 0003_payment  (not applied yet)
```

---

## 🔍 Verification Checklist

After deployment, verify everything works:

### Database Verification

```bash
python manage.py shell
```

```python
# Check models exist
from api.models import Payment, Transaction, Booking
print("✓ Models imported successfully")

# Check Payment table is empty (first run)
print(f"Payments: {Payment.objects.count()}")
print(f"Transactions: {Transaction.objects.count()}")

# Check fields exist
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='api_payment'")
print("Payment table columns:", [row[0] for row in cursor.fetchall()])
```

### Settings Verification

```bash
python manage.py shell
```

```python
from django.conf import settings

# Check Paystack keys are configured
print(f"✓ PAYSTACK_PUBLIC_KEY set: {bool(settings.PAYSTACK_PUBLIC_KEY)}")
print(f"✓ PAYSTACK_SECRET_KEY set: {bool(settings.PAYSTACK_SECRET_KEY)}")
print(f"✓ FRONTEND_URL: {settings.FRONTEND_URL}")
```

### API Endpoint Verification

```bash
# Check payment endpoints are registered
python manage.py show_urls | grep payment

# Should show:
# /api/payments/initialize/
# /api/payments/verify/<str:reference>/
# /api/payments/<int:payment_id>/status/
# /api/payments/list/
# /api/payments/webhook/paystack/
```

---

## 🐛 Troubleshooting

### Error: "No module named 'requests'"

**Solution:**
```bash
pip install requests
```

### Error: "No module named 'paystack_utils'"

**Solution:**
This file should be at `Backend/api/utils/paystack_utils.py`

Verify it exists:
```bash
ls -la Backend/api/utils/paystack_utils.py
```

### Error: Migration conflicts

**Solution:**
```bash
# Show migration history
python manage.py showmigrations

# Reset to specific state if needed
python manage.py migrate api zero_name_of_migration
```

### Error: "PAYSTACK_SECRET_KEY not configured"

**Solution:**
Check .env file has Paystack keys:
```bash
cat Backend/.env | grep PAYSTACK
```

Should show:
```
PAYSTACK_PUBLIC_KEY=pk_test_...
PAYSTACK_SECRET_KEY=sk_test_...
```

### Error: "Database is locked"

**Solution:**
```bash
# Stop any running Django processes
pkill -f "python manage.py"

# Try migration again
python manage.py migrate
```

---

## 📊 Database Schema

### New Tables Created

#### `api_payment` table
```sql
CREATE TABLE api_payment (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL REFERENCES api_booking(id),
    user_id INTEGER NOT NULL REFERENCES auth_user(id),
    amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(20) DEFAULT 'paystack',
    status VARCHAR(20) DEFAULT 'pending',
    paystack_reference VARCHAR(255) UNIQUE,
    paystack_authorization_url VARCHAR(200),
    paystack_access_code VARCHAR(255),
    description TEXT,
    receipt_url VARCHAR(200),
    created_at TIMESTAMP AUTO_NOW_ADD,
    updated_at TIMESTAMP AUTO_NOW,
    completed_at TIMESTAMP NULL
);
```

#### `api_transaction` table
```sql
CREATE TABLE api_transaction (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL REFERENCES api_payment(id),
    transaction_type VARCHAR(20) DEFAULT 'payment',
    amount DECIMAL(10,2) NOT NULL,
    paystack_reference VARCHAR(255),
    paystack_transaction_id INTEGER,
    status VARCHAR(20),
    response JSON DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMP AUTO_NOW_ADD
);
```

---

## 🔄 Rollback Plan

If something goes wrong:

### Rollback Migrations

```bash
# See current migration state
python manage.py showmigrations api

# Rollback to previous migration
python manage.py migrate api [previous_migration_name]

# Example: rollback to before Payment model
python manage.py migrate api 0002_booking
```

### Restore from Backup

```bash
# If using PostgreSQL
pg_restore -d database_name backup_file.dump

# If using SQLite
cp db.sqlite3.backup db.sqlite3
```

---

## ✅ Post-Deployment Steps

### 1. Create First Payment

```bash
# Create a test booking and payment
python manage.py shell
```

```python
from django.contrib.auth.models import User
from api.models import Booking, Payment

# Get user
user = User.objects.first()

# Create booking
booking = Booking.objects.create(
    customer=user,
    service_type='electrical',
    location='123 Main St',
    estimated_cost=5000.00
)

# Create payment
payment = Payment.objects.create(
    booking=booking,
    user=user,
    amount=booking.estimated_cost,
    payment_method='paystack'
)

print(f"✓ Created payment: {payment.id}")
print(f"✓ Booking: {booking.id}")
```

### 2. Test Paystack Client

```python
from api.utils.paystack_utils import PaystackClient

client = PaystackClient()
print("✓ Paystack client initialized successfully")
```

### 3. Setup Monitoring

```bash
# Watch logs in real-time
tail -f logs/django.log

# Or in Django shell
python manage.py shell
```

```python
from api.models import Transaction
import json

# View recent transactions
for t in Transaction.objects.order_by('-created_at')[:5]:
    print(f"{t.id}: {t.status} ({t.amount})")
    print(f"  Response: {json.dumps(t.response, indent=2)[:100]}...")
```

---

## 📈 Monitoring After Deployment

### Check Payment Status

```python
from api.models import Payment

# Pending payments
pending = Payment.objects.filter(status='pending')
print(f"Pending payments: {pending.count()}")

# Completed payments
completed = Payment.objects.filter(status='completed')
print(f"Completed payments: {completed.count()}")

# Revenue tracking
total_revenue = sum(p.amount for p in Payment.objects.filter(status='completed'))
print(f"Total revenue: ${total_revenue}")
```

### Check Error Logs

```python
from api.models import Transaction

# Failed transactions
failed = Transaction.objects.filter(status='failed')
for t in failed:
    print(f"Failed: {t.id}")
    print(f"  Payment: {t.payment_id}")
    print(f"  Error: {t.notes}")
```

---

## 🔐 Security Verification

After deployment, verify security:

### Verify Webhook Signature Validation

```bash
# Test invalid signature is rejected
curl -X POST http://localhost:8000/api/payments/webhook/paystack/ \
  -H "Content-Type: application/json" \
  -H "X-Paystack-Signature: invalid_signature" \
  -d '{"event": "charge.success"}'

# Should return 401 Unauthorized
```

### Verify User Authorization

```bash
# Get a user's payment token
# Try accessing another user's payment - should fail with 403
```

### Verify Rate Limiting

```bash
# Make multiple requests quickly - should be rate limited after 10
```

---

## 📞 Support

If you encounter issues:

1. Check logs: `tail -f logs/django.log`
2. Verify environment variables: `python -c "import os; print(os.getenv('PAYSTACK_SECRET_KEY'))"`
3. Check database: `python manage.py shell` → `from api.models import Payment; Payment.objects.all()`
4. Review documentation: See PAYSTACK_INTEGRATION_GUIDE.md

---

**Status:** ✅ Ready for Deployment  
**Next Steps:** Follow deployment steps above, then test payment flow  
**Estimated Time:** 15-30 minutes for complete setup
