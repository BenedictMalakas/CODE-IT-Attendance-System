from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Auth
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Forced password change
    path('force-change-password/', views.force_change_password_view, name='force_change_password'),

    # Dashboard (auto-routes by role)
    path('', views.dashboard_view, name='dashboard'),

    # Chairperson Dashboard
    path('chairperson/', views.chairperson_dashboard_view, name='chairperson_dashboard'),
    path('chairperson/chart-data/', views.chart_data_api, name='chart_data'),

    # Chairperson: Section Management
    path('sections/', views.sections_manage_view, name='sections_manage'),
    path('sections/<uuid:pk>/delete/', views.section_delete_view, name='section_delete'),

    # Chairperson: Admin Management
    path('admins/', views.admins_manage_view, name='admins_manage'),
    path('admins/<uuid:pk>/remove/', views.admin_remove_view, name='admin_remove'),

    # Events
    path('events/',                    views.events_view,       name='events'),
    path('events/create/',             views.event_create_view, name='event_create'),
    path('events/<uuid:pk>/edit/',     views.event_edit_view,   name='event_edit'),
    path('events/<uuid:pk>/delete/',   views.event_delete_view, name='event_delete'),
    path('events/<uuid:pk>/start/',    views.event_start_view,  name='event_start'),
    path('events/<uuid:pk>/end/',      views.event_end_view,    name='event_end'),

    # Attendance & timestamps
    path('events/<uuid:event_id>/attendance/', views.attendance_view, name='attendance'),
    path('events/<uuid:event_id>/set-expected/', views.set_expected_view, name='set_expected'),

    # QR Scanner
    path('events/<uuid:event_id>/scanner/', views.scanner_view, name='scanner'),
    path('events/<uuid:event_id>/scan/',    views.scan_qr_api,  name='scan_qr'),

    # Excel export
    path('events/<uuid:event_id>/export/', views.export_attendance_view, name='export'),

    # Students
    path('students/',                        views.students_view,        name='students'),
    path('students/<uuid:pk>/approve/',      views.student_approve_view, name='student_approve'),
    path('students/<uuid:pk>/reject/',       views.student_reject_view,  name='student_reject'),
    path('students/<uuid:pk>/delete/',       views.student_delete_view,  name='student_delete'),
    path('students/<uuid:pk>/generate-qr/',  views.generate_qr_view,    name='generate_qr'),

    # Public API for dynamic section dropdown
    path('api/sections/', views.sections_by_year_api, name='sections_by_year'),
]
