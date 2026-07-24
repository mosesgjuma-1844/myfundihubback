# Paystack Payment Integration Guide

**Status:** ✅ Complete  
**Date:** 2026-07-24  
**Estimated Setup Time:** 30 minutes  

---

## 📋 Overview

This guide covers the complete Paystack payment integration for the FUNDI platform. Users can pay for service bookings using Paystack's secure payment gateway.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd Backend
pip install -r requirements.txt
```

### 2. Get Paystack API Keys

1. Go to [paystack.com](https://paystack.com)
2. Sign up for an account
3. Navigate to Settings → API Keys & Webhooks
4. Copy **Public Key** and **Secret Key**

### 3. Set Environment Variables

Create/update `Backend/.env`:

```env
# Paystack Configuration
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key_here
PAYSTACK_SECRET_KEY=sk_test_your_secret_key_here
FRONTEND_URL=http://localhost:5173
```

### 4. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Test Locally

```bash
python manage.py runserver
```

---

## 💳 Payment Flow

### Step 1: Customer Initiates Payment

```
Customer Book Service
    ↓
Booking Created with estimated_cost
    ↓
Customer clicks "Pay Now"
    ↓
Frontend calls POST /api/payments/initialize/
```

### Step 2: Backend Initializes Payment

```python
# Frontend request
POST /api/payments/initialize/
{
    "booking_id": 1
}

# Backend response
{
    "ok": true,
    "payment_id": 5,
    "authorization_url": "https://checkout.paystack.com/...",
    "reference": "FUNDI-5-1"
}
```

### Step 3: Customer Pays

```
Frontend redirects to Paystack
    ↓
Customer enters payment details
    ↓
Paystack processes payment
    ↓
Paystack redirects to success/failure page
```

### Step 4: Payment Verification

```python
# Frontend calls after payment
POST /api/payments/verify/FUNDI-5-1/

# Backend verifies with Paystack
# Updates Payment status
# Updates Booking status to 'assigned'
```

### Step 5: Webhook Notification

```
Paystack sends webhook to /api/payments/webhook/paystack/
    ↓
Backend verifies webhook signature
    ↓
Backend processes payment
    ↓
Database updated
```

---

## 🔌 API Endpoints

### 1. Initialize Payment

**Endpoint:** `POST /api/payments/initialize/`

**Authentication:** Required (JWT)

**Request:**
```json
{
    "booking_id": 1
}
```

**Response (201 Created):**
```json
{
    "ok": true,
    "payment_id": 5,
    "authorization_url": "https://checkout.paystack.com/...",
    "access_code": "0pepo1p7tr",
    "reference": "FUNDI-5-1",
    "message": "Payment initialized successfully"
}
```

**Errors:**
- `400`: Booking not found / already has payment
- `400`: Invalid booking status
- `400`: Estimated cost not set

---

### 2. Verify Payment

**Endpoint:** `GET/POST /api/payments/verify/{reference}/`

**Authentication:** Required (JWT)

**Response (200 OK):**
```json
{
    "ok": true,
    "payment_id": 5,
    "status": "completed",
    "reference": "FUNDI-5-1",
    "message": "Payment verified successfully"
}
```

**Errors:**
- `404`: Payment not found
- `403`: Unauthorized

---

### 3. Get Payment Status

**Endpoint:** `GET /api/payments/{payment_id}/status/`

**Authentication:** Required (JWT)

**Response (200 OK):**
```json
{
    "ok": true,
    "payment_id": 5,
    "status": "completed",
    "amount": "5000.00",
    "booking_id": 1,
    "payment_method": "paystack",
    "created_at": "2024-07-24T10:00:00Z",
    "completed_at": "2024-07-24T10:05:00Z"
}
```

---

### 4. List User Payments

**Endpoint:** `GET /api/payments/list/`

**Authentication:** Required (JWT)

**Query Parameters:**
- `status`: Filter by status (pending, completed, failed)
- `page`: Page number (default: 1)

**Response (200 OK):**
```json
{
    "ok": true,
    "count": 5,
    "page": 1,
    "page_size": 10,
    "payments": [
        {
            "id": 5,
            "booking_id": 1,
            "amount": "5000.00",
            "status": "completed",
            "payment_method": "paystack",
            "created_at": "2024-07-24T10:00:00Z",
            "completed_at": "2024-07-24T10:05:00Z"
        }
    ]
}
```

---

### 5. Paystack Webhook

**Endpoint:** `POST /api/payments/webhook/paystack/`

**Authentication:** Not required (webhook signature verified)

**Paystack sends:**
```json
{
    "event": "charge.success",
    "data": {
        "id": 123456,
        "reference": "FUNDI-5-1",
        "status": "success",
        "customer": {
            "id": 789,
            "email": "user@example.com"
        }
    }
}
```

**Response (200 OK):**
```json
{
    "status": "success"
}
```

---

## 📁 File Structure

```
Backend/
├── api/
│   ├── models.py                 # Payment & Transaction models
│   ├── payment_views.py          # Payment API endpoints
│   ├── urls.py                   # Updated with payment routes
│   └── utils/
│       └── paystack_utils.py     # Paystack API client
├── fundi_backend/
│   └── settings.py               # Updated with Paystack config
├── requirements.txt              # Updated with requests package
└── .env                          # Paystack keys
```

---

## 💾 Models

### Payment Model

```python
class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='paystack')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Paystack details
    paystack_reference = models.CharField(max_length=255, unique=True, blank=True)
    paystack_authorization_url = models.URLField(blank=True)
    paystack_access_code = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

### Transaction Model

```python
class Transaction(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20)  # payment, refund, adjustment
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    paystack_reference = models.CharField(max_length=255, blank=True)
    paystack_transaction_id = models.PositiveIntegerField(null=True, blank=True)
    
    status = models.CharField(max_length=20)  # pending, success, failed
    response = models.JSONField(default=dict)  # Full Paystack response
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 🔧 Configuration

### Environment Variables (Production)

```env
# Paystack Keys (from paystack.com)
PAYSTACK_PUBLIC_KEY=pk_live_your_production_public_key
PAYSTACK_SECRET_KEY=sk_live_your_production_secret_key

# Frontend URL for payment callbacks
FRONTEND_URL=https://yourdomain.com

# Other required variables
SECRET_KEY=<generated>
DEBUG=False
```

### Settings Configuration

```python
# In settings.py
PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY')
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')
```

---

## 🧪 Testing

### Test with Paystack Test Keys

Use these test credentials (valid during development):

**Test Card 1 (Success):**
```
Card Number: 4084084084084081
Expiry: Any future date (MM/YY)
CVV: Any 3 digits
OTP: 123456
```

**Test Card 2 (Failed):**
```
Card Number: 4111111111111111
Expiry: Any future date (MM/YY)
CVV: Any 3 digits
```

### Test Payment Flow

1. **Local Setup:**
   ```bash
   cd Backend
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver
   ```

2. **Create Booking (via API):**
   ```bash
   POST /api/bookings/
   {
       "service_type": "electrical",
       "location": "123 Main St",
       "estimated_cost": "5000.00"
   }
   ```

3. **Initialize Payment:**
   ```bash
   POST /api/payments/initialize/
   {
       "booking_id": 1
   }
   ```

4. **Verify Payment:**
   ```bash
   GET /api/payments/verify/FUNDI-1-1/
   ```

---

## 🔐 Security Features

### 1. Webhook Signature Verification

```python
# Paystack sends X-Paystack-Signature header
# Backend verifies with HMAC-SHA512
import hmac
import hashlib

signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
hash_object = hmac.new(
    SECRET_KEY.encode(),
    body.encode(),
    hashlib.sha512
)
computed = hash_object.hexdigest()
assert signature == computed
```

### 2. CSRF Protection

- Webhook endpoint excluded from CSRF (necessary for Paystack)
- All other endpoints protected

### 3. Rate Limiting

- Payment initialization: 10 per hour per user
- Applied via `@rate_limit` decorator

### 4. Security Logging

- All payment operations logged
- Unauthorized access attempts logged
- Failed payments logged with reasons

### 5. Transaction Auditing

- All payments tracked in Transaction model
- Full Paystack response stored
- Refund history maintained

---

## 🚨 Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `PAYSTACK_SECRET_KEY not configured` | Missing env variable | Set PAYSTACK_SECRET_KEY in .env |
| `Payment already in progress` | Duplicate payment attempt | Check existing payment status |
| `Booking not found` | Invalid booking_id | Verify booking exists and belongs to user |
| `Invalid webhook signature` | Signature mismatch | Check SECRET_KEY configuration |

### Error Response Format

```json
{
    "ok": false,
    "message": "Error description",
    "code": "ERROR_CODE"
}
```

---

## 📊 Database Queries

### Get Payment History

```python
from api.models import Payment

# All payments for user
payments = Payment.objects.filter(user=request.user)

# Completed payments
completed = Payment.objects.filter(user=request.user, status='completed')

# Payments for specific booking
payment = Payment.objects.get(booking__id=1)
```

### Get Transaction History

```python
from api.models import Transaction

# All transactions for payment
transactions = Transaction.objects.filter(payment_id=1)

# Failed transactions
failed = Transaction.objects.filter(status='failed')
```

---

## 🔄 Refund Processing

### Manual Refund

```python
from api.models import Payment, Transaction

payment = Payment.objects.get(id=1)

# Create refund transaction
Transaction.objects.create(
    payment=payment,
    transaction_type='refund',
    amount=payment.amount,
    status='success',
    notes='Manual refund processed'
)

# Update payment status
payment.status = 'refunded'
payment.save()
```

### Via Paystack Dashboard

1. Go to paystack.com dashboard
2. Navigate to Transactions
3. Find the transaction
4. Click "Refund"
5. Enter amount and reason
6. Confirm

---

## 📞 Support & Troubleshooting

### Payment Not Completing

1. Check Paystack API keys are correct
2. Verify webhook is configured in Paystack dashboard
3. Check logs: `tail -f logs/django.log`
4. Test payment endpoint directly

### Webhook Not Firing

1. Verify webhook URL in Paystack dashboard:
   - Should be: `https://yourdomain.com/api/payments/webhook/paystack/`
2. Check firewall allows POST requests
3. Verify public IP is whitelisted

### Test Payment Debugging

```bash
# Check if payment exists
python manage.py shell
>>> from api.models import Payment
>>> Payment.objects.all()

# Check transactions
>>> from api.models import Transaction
>>> Transaction.objects.filter(payment_id=1)

# View logs
>>> from api.models import Payment
>>> p = Payment.objects.get(id=1)
>>> p.transactions.all()
```

---

## 📚 Additional Resources

- [Paystack Documentation](https://paystack.com/docs)
- [Paystack API Reference](https://paystack.com/docs/api)
- [Paystack Test Keys](https://paystack.com/docs/test-keys)
- [Paystack Webhook Events](https://paystack.com/docs/webhooks)

---

## ✅ Deployment Checklist

### Before Production

- [ ] Generate Paystack production API keys
- [ ] Set environment variables in production platform
- [ ] Configure webhook URL in Paystack dashboard
- [ ] Test payment flow end-to-end
- [ ] Set up payment success/failure pages on frontend
- [ ] Configure email notifications for payment events
- [ ] Set up monitoring and alerts
- [ ] Document refund process for support team

### Production Deployment

- [ ] SSH into server
- [ ] Update code: `git pull`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run migrations: `python manage.py migrate`
- [ ] Collect static files: `python manage.py collectstatic --noinput`
- [ ] Restart application: `systemctl restart gunicorn`
- [ ] Test payment flow
- [ ] Monitor logs: `tail -f logs/django.log`

---

**Status:** ✅ Ready for Production  
**Last Updated:** 2026-07-24  
**Next Steps:** Deploy payment endpoints and test with live transactions
