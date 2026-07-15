from django.contrib.auth.models import User
from django.db import models


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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_service_type_display()} - {self.location}"