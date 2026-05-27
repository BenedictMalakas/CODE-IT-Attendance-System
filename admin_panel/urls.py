from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Auth
    path('logout/',                 views.logout_view,                name='logout'),
    path('force-password-change/',  views.force_password_change_view, name='force_password_change'),
    path('verify-password/',        views.verify_admin_password_api,  name='verify_password'),
    path('mark-reauth-leave/',      views.mark_reauth_leave_api,      name='mark_reauth_leave'),

    # Dashboard
    path('',          views.dashboard_view,       name='dashboard'),
    path('sections/',                  views.sections_manage_view, name='sections_manage'),
    path('sections/<uuid:pk>/delete/', views.delete_section_view,  name='delete_section'),
    path('officers/', views.admins_manage_view,   name='admins_manage'),

    # Activity Logs
    path('activity-logs/', views.activity_logs_view, name='activity_logs'),

    # Events
    path('events/',                            views.events_view,             name='events'),
    path('events/create/',                     views.event_create_view,       name='event_create'),
    path('events/<uuid:pk>/edit/',             views.event_edit_view,         name='event_edit'),
    path('events/<uuid:pk>/delete/',           views.event_delete_view,       name='event_delete'),
    path('events/<uuid:pk>/start/',            views.start_event_view,        name='start_event'),
    path('events/<uuid:pk>/end/',              views.end_event_view,          name='end_event'),
    path('events/<uuid:pk>/close/',            views.close_event_view,        name='close_event'),
    path('events/<uuid:pk>/extend-grace/',     views.extend_grace_event_view, name='extend_grace'),

    # Expected students
    path('events/<uuid:event_id>/expected/',  views.set_expected_students_view, name='set_expected'),
    path('events/<uuid:event_id>/finalize/',  views.finalize_event_view,        name='finalize_event'),

    # Attendance & timestamps
    path('events/<uuid:event_id>/attendance/', views.attendance_view, name='attendance'),

    # QR Scanner
    path('events/<uuid:event_id>/scanner/', views.scanner_view, name='scanner'),
    path('events/<uuid:event_id>/scan/',    views.scan_qr_api,  name='scan_qr'),

    # Excel export
    path('events/<uuid:event_id>/export/', views.export_attendance_view, name='export'),

    # Students
    path('students/',                          views.students_view,        name='students'),
    path('students/<uuid:pk>/approve/',        views.student_approve_view, name='student_approve'),
    path('students/<uuid:pk>/reject/',         views.student_reject_view,  name='student_reject'),
    path('students/<uuid:pk>/delete/',         views.student_delete_view,  name='student_delete'),
    path('students/<uuid:pk>/revoke-qr/',     views.revoke_qr_view,       name='revoke_qr'),
]
