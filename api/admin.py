from django.contrib import admin
from .models import Booking, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number')
    search_fields = ('user__username', 'user__email', 'phone_number')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('customer', 'service_type', 'location', 'status', 'created_at')
    list_filter = ('status', 'service_type', 'service_window')
    search_fields = ('location', 'description', 'customer__username')
