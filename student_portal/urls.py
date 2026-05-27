from django.urls import path
from . import views

app_name = 'student_portal'

urlpatterns = [
    # Auth
    path('login/',    views.login_view,    name='login'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('register/', views.register_view, name='register'),
    path('logout/',   views.logout_view,   name='logout'),

    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # My QR
    path('my-qr/', views.my_qr_view, name='my_qr'),
    path('download-qr/', views.download_qr_view, name='download_qr'),

    # My Attendance
    path('attendance/', views.attendance_view, name='attendance'),

    # Profile
    path('profile/', views.profile_view, name='profile'),
]
