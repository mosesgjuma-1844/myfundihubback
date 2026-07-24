# Paystack Callout Fee Payment - Updated Guide

**Status:** ✅ Updated for Callout Fee Model  
**Date:** 2026-07-24  
**Callout Fee:** 1000 (KES)  
**Payment Method:** M-Pesa via Paystack  

---

## 📋 Overview

The payment system now follows a **callout fee model**:

1. **Customer books a service** → Booking created with status `pending`
2. **Customer is prompted to pay the callout fee** (KES 1000) before the booking is assigned
3. **Payment is made via M-Pesa through Paystack**
4. **After successful payment** → Booking status changes to `assigned` and technician can view it

This ensures technicians get compensated for the service call before dispatch.

---

## 🔄 Payment Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Customer Books Service                                    │
│    - Service type, location, date/time selected              │
│    - Booking created with status='pending'                   │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. System Displays Callout Fee                              │
│    - Fee: KES 1000                                           │
│    - "Pay Now" button shown                                  │
│    - Payment required before booking is active              │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Customer Clicks "Pay Now"                                │
│    - Frontend calls POST /api/payments/initialize/           │
│    - Booking status → 'pending_payment'                      │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Paystack Payment Page                                    │
│    - Customer redirected to Paystack checkout               │
│    - Payment method: M-Pesa (primary), Card (secondary)     │
│    - Amount: 1000 KES                                        │
└────────────────────┬────────────────────────────────────────┘
                     ↓
         ┌──────────┴──────────┐
         ↓                     ↓
    ✅ SUCCESS            ❌ FAILED
         ↓                     ↓
  Paystack processes   Customer returned
  and redirects        to failure page
         ↓
┌──────────────────────────────────────────┐
│ 5. Payment Verification                  │
│    - Frontend calls /api/payments/verify/ │
│    - Backend verifies with Paystack      │
└────────────────┬─────────────────────────┘
                 ↓
    ┌────────────┴───────────┐
    ↓                        ↓
  SUCCESS                FAILURE
    ↓                        ↓
Booking Status         Booking Status
Changed to              Stays in
'assigned'              'pending'
    ↓
✅ Technician Can Now See Booking
✅ Customer Receives Confirmation
```

---

## 💾 Data Model Changes

### Booking Model (Updated)

```python
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),                    # NEW: Not yet paid
        ('pending_payment', 'Pending Payment'),    # NEW: Payment in progress
        ('assigned', 'Assigned'),                  # Technician assigned (after payment)
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # ... existing fields ...
    callout_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=1000  # Fixed fee
    )
```

### Payment Model (Updated)

```python
class Payment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('callout_fee', 'Callout Fee'),       # NEW: Fixed fee for dispatch
        ('service_cost', 'Service Cost'),     # Future: Final service payment
    ]
    
    # ... existing fields ...
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='callout_fee'
    )
```

---

## 🔌 API Endpoints

### 1. Create Booking

**Endpoint:** `POST /api/bookings/`

**Request:**
```json
{
    "service_type": "electrical",
    "location": "123 Main St, Nairobi",
    "county": "Nairobi",
    "town_or_estate": "Westlands",
    "description": "Fix electrical outlet",
    "service_window": "immediate"
}
```

**Response (201 Created):**
```json
{
    "id": 1,
    "status": "pending",
    "callout_fee": 1000,
    "message": "Booking created. Please pay KES 1000 callout fee."
}
```

### 2. Initialize Payment (for Callout Fee)

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
    "payment_id": 1,
    "authorization_url": "https://checkout.paystack.com/...",
    "access_code": "0pepo1p7tr",
    "reference": "FUNDI-1-1",
    "message": "Payment initialized for KES 1000 callout fee"
}
```

**What happens:**
- Booking status changes to `pending_payment`
- User redirected to Paystack checkout
- User pays 1000 KES via M-Pesa or card

### 3. Verify Payment

**Endpoint:** `GET/POST /api/payments/verify/{reference}/`

**Authentication:** Required (JWT)

**Response (200 OK - Success):**
```json
{
    "ok": true,
    "payment_id": 1,
    "status": "completed",
    "reference": "FUNDI-1-1",
    "message": "Payment verified successfully"
}
```

**What happens:**
- Backend verifies with Paystack
- Payment marked as `completed`
- Booking status changed to `assigned`
- Technician notified to view booking
- Customer receives confirmation

**Response (200 OK - Failed):**
```json
{
    "ok": false,
    "payment_id": 1,
    "status": "failed",
    "reference": "FUNDI-1-1",
    "message": "Payment verification failed"
}
```

---

## 🔑 Key Differences from Previous Model

| Aspect | Previous | Current (Callout Fee) |
|--------|----------|----------------------|
| **Amount** | Based on `estimated_cost` | Fixed at **KES 1000** |
| **Payment Timing** | Optional after booking | **Required** before booking active |
| **Booking Status** | Created as `pending` or `assigned` | Created as `pending`, then `pending_payment`, then `assigned` |
| **Payment Type** | Service payment | **Callout fee** (dispatch cost) |
| **Purpose** | Final service payment | **Upfront dispatch fee** to ensure quality |

---

## 💳 Payment Methods

Customers can pay the KES 1000 callout fee using:

1. **M-Pesa (Recommended)** - Fastest, most popular in Kenya
   - Enter M-Pesa phone number
   - Enter M-Pesa PIN when prompted
   - Instant confirmation

2. **Card (Visa/Mastercard)** - International cards accepted
   - Enter card number, expiry, CVV
   - 3D Secure verification (if required)
   - Supported via Paystack

3. **Bank Transfer** - For larger amounts (future)

---

## 🧪 Testing

### Test Scenario 1: Successful Payment

```bash
# 1. Create booking
POST /api/bookings/
# Response: {"id": 1, "status": "pending", "callout_fee": 1000}

# 2. Initialize payment
POST /api/payments/initialize/
{"booking_id": 1}
# Response: {"authorization_url": "https://checkout.paystack.com/..."}

# 3. Pay with test card (simulating M-Pesa in test env)
# Card: 4084084084084081
# Expiry: 12/25, CVV: 123, OTP: 123456

# 4. Verify payment
GET /api/payments/verify/FUNDI-1-1/
# Response: {"ok": true, "status": "completed"}

# 5. Check booking status
GET /api/bookings/1/
# Response: {"status": "assigned"}  ✅ Changed from pending
```

### Test Scenario 2: Payment Failure

```bash
# 1-2. Same as above

# 3. Pay with test card (failure)
# Card: 4111111111111111
# This card will fail in test mode

# 4. Verify payment
GET /api/payments/verify/FUNDI-1-1/
# Response: {"ok": false, "status": "failed"}

# 5. Check booking status
GET /api/bookings/1/
# Response: {"status": "pending"}  ✅ Still pending (not assigned)
```

---

## 🔐 Security

✅ **Webhook Verification** - Paystack webhooks verified with HMAC-SHA512  
✅ **User Authorization** - Users can only pay for their own bookings  
✅ **Rate Limiting** - 10 payment attempts per hour per user  
✅ **Booking Ownership** - Validated before payment initialization  
✅ **Transaction Auditing** - All payments logged with full details  

---

## 📊 Payment Status Workflow

```
Payment States:
    pending → processing → completed (✅ BOOKING → assigned)
                       ↘ failed (❌ BOOKING stays → pending)

Booking States:
    pending → pending_payment (payment init)
                          ↓ payment success
                       assigned (✅ ACTIVE)
                          ↓ payment failure
                       pending (can retry)
```

---

## 🚀 Deployment Checklist

Before going live with callout fee payments:

- [ ] Create database migration: `python manage.py makemigrations api`
- [ ] Apply migration: `python manage.py migrate`
- [ ] Get Paystack **live** API keys (not test keys)
- [ ] Set environment variables on production
- [ ] Configure webhook URL in Paystack dashboard
- [ ] Test end-to-end payment flow
- [ ] Set up payment success/failure email notifications
- [ ] Configure customer support process for payment issues
- [ ] Train support team on refund procedure
- [ ] Monitor first 100 transactions for issues

---

## 💡 Important Notes

1. **Callout Fee is Non-Refundable** (in most cases)
   - Set clear policy in terms & conditions
   - Refunds only for system errors
   - Keep audit trail of all refunds

2. **Booking Creation vs. Activation**
   - Booking is "created" when form submitted (status: `pending`)
   - Booking is "activated" when payment cleared (status: `assigned`)
   - Technicians only see "assigned" bookings

3. **Repeated Payment Attempts**
   - Users can retry failed payments
   - Previous failed payment record kept for auditing
   - New payment creates new Payment record

4. **M-Pesa Dominance**
   - 80%+ of payments in Kenya via M-Pesa
   - Paystack handles M-Pesa natively
   - Instant confirmation via USSD

---

## 📞 Troubleshooting

### Payment Initialized but Customer Never Redirected

**Cause:** Redirect URL not working  
**Solution:** Check `FRONTEND_URL` environment variable

```bash
# Should be EXACTLY your frontend domain
FRONTEND_URL=https://yourdomain.com
```

### Payment Successful but Booking Still "Pending"

**Cause:** Webhook not processed or verification endpoint not called  
**Solution:** 
1. Check webhook URL in Paystack dashboard
2. Verify user calls `/api/payments/verify/{reference}/`

### "Payment already in progress" Error

**Cause:** User trying to create second payment without completing first  
**Solution:** Let user verify existing payment or cancel and start over

---

## 🎯 Success Metrics

Track these after launch:

- Payment success rate (target: >95%)
- Average time from booking to payment
- M-Pesa vs Card payment ratio
- Failed payment retry rate
- Customer support tickets related to payments
- Revenue per booking

---

## 📚 Related Documentation

- [PAYSTACK_QUICK_SETUP.md](PAYSTACK_QUICK_SETUP.md) - Setup guide
- [PAYSTACK_DEPLOYMENT_GUIDE.md](PAYSTACK_DEPLOYMENT_GUIDE.md) - Deployment steps
- [PAYSTACK_INTEGRATION_GUIDE.md](PAYSTACK_INTEGRATION_GUIDE.md) - Technical details

---

**Status:** ✅ Ready for Migration & Testing  
**Next Steps:** Run migrations, then test with Paystack test keys  
**Estimated Time:** 30 minutes for setup + 15 minutes for testing
