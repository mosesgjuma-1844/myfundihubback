from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_codes')
    code = models.CharField(max_length=32, unique=True)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def mark_as_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])

    @staticmethod
    def create_code(user, email, expiry_minutes=15):
        # Delete old unused codes
        PasswordResetCode.objects.filter(user=user, is_used=False).delete()
        
        code = secrets.token_urlsafe(24)
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        return PasswordResetCode.objects.create(
            user=user,
            code=code,
            email=email,
            expires_at=expires_at
        )

    def __str__(self):
        return f"Reset code for {self.email}"


class Profile(models.Model):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('technician', 'Technician'),
        ('admin', 'Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    phone_number = models.CharField(max_length=20, blank=True)
    specialization = models.CharField(max_length=100, blank=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    admin_key = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Booking(models.Model):
    SERVICE_CHOICES = [
        ('electrical', 'Electrical & Electronics'),
        ('plumbing', 'Plumbing'),
        ('carpentry', 'Carpentry'),
        ('installation', 'Home Installations'),
        ('appliance-repair', 'Appliance Repair'),
    ]

    WINDOW_CHOICES = [
        ('immediate', 'Immediate Service'),
        ('scheduled', 'Schedule Appointment'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_payment', 'Pending Payment'),
        ('assigned', 'Assigned'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    assigned_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bookings')
    service_type = models.CharField(max_length=30, choices=SERVICE_CHOICES)
    location = models.CharField(max_length=255)
    county = models.CharField(max_length=100, blank=True)
    town_or_estate = models.CharField(max_length=100, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    description = models.TextField(blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    service_window = models.CharField(max_length=20, choices=WINDOW_CHOICES, default='scheduled')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    estimated_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    callout_fee = models.DecimalField(max_digits=8, decimal_places=2, default=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_service_type_display()} - {self.location}"


class Payment(models.Model):
    """Payment records for bookings."""
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('paystack', 'Paystack'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('callout_fee', 'Callout Fee'),
        ('service_cost', 'Service Cost'),
    ]

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='paystack')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='callout_fee')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Paystack transaction details
    paystack_reference = models.CharField(max_length=255, unique=True, blank=True)
    paystack_authorization_url = models.URLField(blank=True)
    paystack_access_code = models.CharField(max_length=255, blank=True)
    
    # Payment metadata
    description = models.TextField(blank=True)
    receipt_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} - {self.user.username} ({self.status})"

    def mark_as_completed(self):
        """Mark payment as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def mark_as_failed(self):
        """Mark payment as failed."""
        self.status = 'failed'
        self.save(update_fields=['status', 'updated_at'])


class Transaction(models.Model):
    """Transaction log for payment tracking and auditing."""
    
    TRANSACTION_TYPE_CHOICES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('adjustment', 'Adjustment'),
    ]

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Paystack details
    paystack_reference = models.CharField(max_length=255, blank=True)
    paystack_transaction_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Transaction details
    status = models.CharField(max_length=20)  # pending, success, failed
    response = models.JSONField(default=dict)  # Full Paystack API response
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transaction {self.id} - {self.transaction_type} ({self.status})"