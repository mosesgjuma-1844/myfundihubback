# Callout Fee Implementation - Quick Migration Guide

**Status:** ✅ Ready to Apply  
**Date:** 2026-07-24  
**Time Required:** 5 minutes  

---

## 🚀 Quick Start (3 Commands)

```bash
cd Backend

# Step 1: Create migrations
python manage.py makemigrations

# Step 2: Apply migrations
python manage.py migrate

# Step 3: Verify
python manage.py shell
```

Then in the Python shell:

```python
from api.models import Booking, Payment
# Check models exist
print(f"Booking fields: {Booking._meta.get_fields()}")
print(f"Payment fields: {Payment._meta.get_fields()}")
# Should include: callout_fee (Booking), payment_type (Payment)
```

---

## 📋 What Changed

### Booking Model
- **Added:** `callout_fee` field (DecimalField, default=1000)
- **Updated:** `STATUS_CHOICES` - Added `pending_payment` status

### Payment Model  
- **Added:** `payment_type` field (CharField, choices: callout_fee/service_cost)
- **Default:** `payment_type='callout_fee'`

### API Changes
- Payment initialization now uses `booking.callout_fee` instead of `booking.estimated_cost`
- Booking status set to `pending_payment` when payment initialized
- Booking status set to `assigned` when payment succeeds

---

## 🔄 Migration Process

### 1. Create Migrations

```bash
python manage.py makemigrations
```

**Expected output:**
```
Migrations for 'api':
  api/migrations/XXXX_auto_YYYYMMDD_HHMM.py
    - Add field callout_fee to booking
    - Add field pending_payment to booking status
    - Add field payment_type to payment
```

### 2. Review Migration (Optional)

```bash
# View the migration file
cat api/migrations/XXXX_auto_YYYYMMDD_HHMM.py

# Or see what it will do
python manage.py sqlmigrate api XXXX
```

### 3. Apply Migration

```bash
python manage.py migrate
```

**Expected output:**
```
Running migrations:
  Applying api.XXXX_auto_YYYYMMDD_HHMM... OK
```

### 4. Verify Migration

```bash
python manage.py showmigrations api

# Should show [X] next to your new migration, indicating it's applied
```

---

## ✅ Verification Steps

### Check Database Schema

```bash
python manage.py shell
```

```python
# Check Booking model
from api.models import Booking
print(Booking._meta.get_field('callout_fee'))
# Output: <django.db.models.fields.DecimalField: callout_fee>

# Check Payment model
from api.models import Payment
print(Payment._meta.get_field('payment_type'))
# Output: <django.db.models.fields.CharField: payment_type>

# Test creating a booking
from django.contrib.auth.models import User
user = User.objects.first()
booking = Booking.objects.create(
    customer=user,
    service_type='electrical',
    location='Test',
    callout_fee=1000
)
print(f"Created booking {booking.id} with callout_fee: {booking.callout_fee}")
```

### Check Status Choices

```python
from api.models import Booking
print(dict(Booking.STATUS_CHOICES))
# Should include: 'pending_payment'
```

---

## 🔙 Rollback (If Needed)

### Rollback to Previous Migration

```bash
# See all migrations
python manage.py showmigrations api

# Rollback to specific migration
python manage.py migrate api [migration_name_before_latest]

# Example:
python manage.py migrate api 0003_booking_extended_fields
```

### Delete Latest Migration Files

```bash
# First rollback the database
python manage.py migrate api [previous_migration]

# Then delete the migration files
rm api/migrations/XXXX_*.py
```

---

## 🐛 Troubleshooting

### Error: "No changes detected in app 'api'"

**Cause:** Models already have the changes  
**Solution:** Check if migration already applied

```bash
python manage.py showmigrations api
# If migration is [X], already applied - OK
```

### Error: "The field was supposed to be immutable"

**Cause:** Migration issue from previous attempt  
**Solution:**
```bash
# Rollback
python manage.py migrate api [previous_migration]

# Delete migration files
rm api/migrations/XXXX_*.py

# Try again
python manage.py makemigrations
python manage.py migrate
```

### Error: "IntegrityError: duplicate key value"

**Cause:** Migration trying to add field without default to existing records  
**Solution:** This shouldn't happen since `callout_fee` has default=1000
- Safe to ignore if it completes anyway
- Run migration again if it fails

---

## 📊 Database Changes Detailed

### What `python manage.py migrate` Will Do

1. **Add column to `api_booking`:**
   ```sql
   ALTER TABLE api_booking ADD COLUMN callout_fee DECIMAL(8,2) DEFAULT 1000;
   ```

2. **Update `api_booking` status choices:**
   - Old: ('pending', 'assigned', 'completed', 'cancelled')
   - New: ('pending', 'pending_payment', 'assigned', 'completed', 'cancelled')

3. **Add column to `api_payment`:**
   ```sql
   ALTER TABLE api_payment ADD COLUMN payment_type VARCHAR(20) DEFAULT 'callout_fee';
   ```

### Existing Data

- ✅ All existing bookings get `callout_fee=1000`
- ✅ All existing payments get `payment_type='callout_fee'`
- ✅ No data lost
- ✅ Backward compatible

---

## 📝 Production Deployment

### Pre-Migration Checklist

- [ ] Backup production database
- [ ] Pull latest code with changes
- [ ] Test migrations on staging environment
- [ ] Inform stakeholders of deployment
- [ ] Schedule during low-traffic period (if possible)

### Migration Commands

```bash
# SSH into production server
ssh user@your-server.com

# Navigate to backend
cd /path/to/Backend

# Pull latest code
git pull

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Restart application
systemctl restart gunicorn

# OR if using Railway:
railway link
railway run python manage.py migrate
```

### Post-Migration Verification

```bash
# Check migrations applied
python manage.py showmigrations api

# Check new bookings created after migration
python manage.py shell
>>> from api.models import Booking
>>> Booking.objects.latest('id').callout_fee
# Should print: 1000
```

---

## 🔑 Important Notes

1. **callout_fee Default = 1000 (KES)**
   - All existing bookings get this value
   - Can be overridden per booking if needed
   - Update admin interface to allow changes

2. **payment_type Default = 'callout_fee'**
   - All existing payments categorized as callout fee
   - Future payments for final service will use 'service_cost'

3. **Backward Compatibility**
   - No breaking changes
   - Existing payment logic still works
   - New logic only affects payment initialization

4. **Database Flexibility**
   - callout_fee per booking allows future variation
   - Not hardcoded to database
   - Can be adjusted in admin

---

## ✨ Success Indicators

After migration, confirm:

- [ ] `python manage.py migrate` completed without errors
- [ ] `python manage.py showmigrations api` shows all [X]
- [ ] Can create new bookings with `callout_fee=1000`
- [ ] Can create payments with `payment_type='callout_fee'`
- [ ] Old bookings/payments still accessible
- [ ] No 500 errors in application logs

---

## 📞 Support

If you encounter issues:

1. Check migration status: `python manage.py showmigrations`
2. Review error messages in detail
3. Check database directly: `python manage.py dbshell`
4. Rollback if necessary: `python manage.py migrate api [previous]`
5. Try again from the beginning

---

**Status:** ✅ Ready to Deploy  
**Estimated Time:** 5-10 minutes including verification  
**Next Step:** Run the 3 commands above!
