from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Auth
    path('login/',    views.login_view,    name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/',   views.logout_view,   name='logout'),

    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Events
    path('events/',                    views.events_view,       name='events'),
    path('events/create/',             views.event_create_view, name='event_create'),
    path('events/<uuid:pk>/edit/',     views.event_edit_view,   name='event_edit'),
    path('events/<uuid:pk>/delete/',   views.event_delete_view, name='event_delete'),

    # Attendance & timestamps
    path('events/<uuid:event_id>/attendance/', views.attendance_view, name='attendance'),

    # QR Scanner
    path('events/<uuid:event_id>/scanner/', views.scanner_view, name='scanner'),
    path('events/<uuid:event_id>/scan/',    views.scan_qr_api,  name='scan_qr'),

    # Excel export
    path('events/<uuid:event_id>/export/', views.export_attendance_view, name='export'),

    # Students
    path('students/',                        views.students_view,        name='students'),
    path('students/<uuid:pk>/approve/',      views.student_approve_view, name='student_approve'),
    path('students/<uuid:pk>/reject/',       views.student_reject_view,  name='student_reject'),
]
