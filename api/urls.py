from django.urls import path
from .views import (
    bookings_view,
    forgot_password_view,
    login_view,
    register_view,
    reset_password_view,
    user_view,
    menu_view,
    customer_dashboard_view,
    admin_dashboard_view,
    technician_dashboard_view,
    technicians_view,
    assign_booking_view,
    verify_reset_code_view,
)

urlpatterns = [
    path('auth/login/', login_view, name='login'),
    path('auth/register/', register_view, name='register'),
    path('auth/forgot-password/', forgot_password_view, name='forgot-password'),
    path('auth/verify-reset-code/', verify_reset_code_view, name='verify-reset-code'),
    path('auth/reset-password/', reset_password_view, name='reset-password'),
    path('bookings/', bookings_view, name='bookings'),
    path('bookings/assign/', assign_booking_view, name='assign-booking'),
    path('technicians/', technicians_view, name='technicians'),
    path('user/', user_view, name='user'),
    path('menu/', menu_view, name='menu'),
    path('dashboard/customer/', customer_dashboard_view, name='customer-dashboard'),
    path('dashboard/admin/', admin_dashboard_view, name='admin-dashboard'),
    path('dashboard/technician/', technician_dashboard_view, name='technician-dashboard'),
]
