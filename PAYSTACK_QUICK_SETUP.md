# Paystack Integration - Quick Setup (5 minutes)

## 📋 What You'll Get

After this setup, you can:
- Accept card payments via Paystack
- Process payments in real-time
- Track all transactions
- Handle refunds
- Monitor payment history

---

## 🔑 Step 1: Get Paystack API Keys (2 minutes)

### Option A: For Testing (Development)

1. Go to [paystack.com](https://paystack.com)
2. Click **"Get Started"** → **"Sign Up"**
3. Create account (you can use test email)
4. Go to **Settings** → **API Keys & Webhooks**
5. You'll see two keys:
   ```
   Public Key (starts with pk_test_)
   Secret Key (starts with sk_test_)
   ```
6. Copy both keys

### Option B: For Production (Live Payments)

Same as above, but after setting up testing:
1. Go to **Settings** → **API Keys & Webhooks**
2. Switch to **Live** tab (instead of Test)
3. Complete business verification (Paystack will guide you)
4. Once verified, get your **live** keys:
   ```
   Public Key (starts with pk_live_)
   Secret Key (starts with sk_live_)
   ```

---

## 🚀 Step 2: Configure Backend (2 minutes)

### Local Development

Create `Backend/.env`:

```env
# Paystack Test Keys
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key_here
PAYSTACK_SECRET_KEY=sk_test_your_secret_key_here
FRONTEND_URL=http://localhost:5173
```

### Production (Railway/Heroku)

1. Go to your hosting platform dashboard
2. Add environment variables:
   - `PAYSTACK_PUBLIC_KEY` = pk_live_...
   - `PAYSTACK_SECRET_KEY` = sk_live_...
   - `FRONTEND_URL` = https://yourdomain.com

---

## 🔗 Step 3: Setup Webhook (1 minute)

The webhook allows Paystack to notify your app when payments succeed/fail.

1. Go to [paystack.com](https://paystack.com) → **Settings** → **API Keys & Webhooks**
2. Scroll to **Webhooks**
3. Click **Add Webhook**
4. Paste your webhook URL:
   ```
   https://your-backend-domain.com/api/payments/webhook/paystack/
   ```
5. Select events: **charge.success** (at minimum)
6. Click **Add Webhook**

---

## 🔧 Step 4: Install & Migrate (1 minute)

```bash
cd Backend

# Install dependencies
pip install -r requirements.txt

# Create database tables
python manage.py makemigrations
python manage.py migrate

# Test
python manage.py runserver
```

---

## ✅ That's It!

Your Paystack integration is ready! 

### Next: Test a Payment

**Test Card (Use for testing):**
```
Card Number: 4084084084084081
Expiry: Any future date (e.g., 12/25)
CVV: Any 3 digits (e.g., 123)
OTP: 123456 (when prompted)
```

---

## 📊 Payment Flow After Setup

```
Customer Books Service
         ↓
    "Pay Now" Button
         ↓
Frontend calls /api/payments/initialize/
         ↓
Backend returns payment URL
         ↓
Customer redirected to Paystack
         ↓
Customer enters card details
         ↓
Paystack processes & returns status
         ↓
Backend verifies payment
         ↓
Booking Status Updated ✅
Payment Recorded ✅
```

---

## 🧪 Test Endpoints

Use these to test the payment flow:

### 1. Create a Booking
```bash
POST /api/bookings/
{
    "service_type": "electrical",
    "location": "123 Main St",
    "estimated_cost": "5000.00"
}
```

### 2. Initialize Payment
```bash
POST /api/payments/initialize/
{
    "booking_id": 1
}
```

Response will include `authorization_url` to redirect to Paystack.

### 3. After Payment, Verify
```bash
GET /api/payments/verify/FUNDI-1-1/
```

---

## 🔐 API Keys Security

✅ **DO:**
- Store keys in environment variables (`.env`)
- Never commit `.env` to Git
- Rotate keys quarterly
- Use different keys for test vs production

❌ **DON'T:**
- Hardcode keys in source code
- Share keys via email/chat
- Use production keys for testing
- Commit `.env` to repository

---

## 🆘 Troubleshooting

### "PAYSTACK_SECRET_KEY not configured"

**Fix:**
```bash
# Check .env file exists
cat Backend/.env

# Should include:
PAYSTACK_PUBLIC_KEY=pk_test_...
PAYSTACK_SECRET_KEY=sk_test_...
```

### Payment Not Processing

1. Check Paystack test cards work: [test-cards](https://paystack.com/docs/test-keys)
2. Verify webhook URL is correct in Paystack dashboard
3. Check backend logs: `python manage.py tail` (if available)

### "Invalid webhook signature"

1. Verify `PAYSTACK_SECRET_KEY` is correct
2. Re-add webhook in Paystack dashboard
3. Check webhook URL is exactly: `/api/payments/webhook/paystack/`

---

## 📞 Get Help

- [Paystack Docs](https://paystack.com/docs)
- [Test Cards](https://paystack.com/docs/test-keys)
- [API Reference](https://paystack.com/docs/api)

---

**You're ready to accept payments!** 🎉

Next: Test a payment with the test card above.
