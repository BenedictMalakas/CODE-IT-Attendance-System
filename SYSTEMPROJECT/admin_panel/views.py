import hashlib
import uuid
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone as dj_timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from myapp.models import Admin, Student, Event, QRToken, AttendanceLog
from .forms import LoginForm, EventForm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_id'):
            return redirect('admin_panel:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_current_admin(request):
    admin_id = request.session.get('admin_id')
    if admin_id:
        try:
            return Admin.objects.get(id=admin_id)
        except Admin.DoesNotExist:
            pass
    return None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    if request.session.get('admin_id'):
        return redirect('admin_panel:dashboard')

    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email']
            password = form.cleaned_data['password']
            pw_hash  = hash_password(password)
            try:
                admin = Admin.objects.get(email=email, password_hash=pw_hash, is_active=True)
                request.session['admin_id']   = str(admin.id)
                request.session['admin_name'] = admin.name
                return redirect('admin_panel:dashboard')
            except Admin.DoesNotExist:
                messages.error(request, 'Invalid email or password.')

    return render(request, 'admin_panel/login.html', {'form': form})


def logout_view(request):
    request.session.flush()
    return redirect('admin_panel:login')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_required
def dashboard_view(request):
    total_events     = Event.objects.count()
    total_students   = Student.objects.filter(status='active').count()
    pending_students = Student.objects.filter(status='pending').count()
    total_logs       = AttendanceLog.objects.count()

    today        = dj_timezone.now().date()
    today_events = Event.objects.filter(date=today)
    recent_events = Event.objects.order_by('-date', '-start_time')[:5]

    context = {
        'total_events':     total_events,
        'total_students':   total_students,
        'pending_students': pending_students,
        'total_logs':       total_logs,
        'today_events':     today_events,
        'recent_events':    recent_events,
        'admin_name':       request.session.get('admin_name', 'Admin'),
    }
    return render(request, 'admin_panel/dashboard.html', context)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@admin_required
def events_view(request):
    events = Event.objects.order_by('-date', '-start_time')
    return render(request, 'admin_panel/events.html', {'events': events})


@admin_required
def event_create_view(request):
    form = EventForm()
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event            = form.save(commit=False)
            event.id         = uuid.uuid4()
            event.created_by = get_current_admin(request)
            event.save()
            messages.success(request, f'Event "{event.name}" created successfully.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})


@admin_required
def event_edit_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    form  = EventForm(instance=event)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, f'Event "{event.name}" updated.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Edit', 'event': event})


@admin_required
@require_POST
def event_delete_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    name  = event.name
    event.delete()
    messages.success(request, f'Event "{name}" deleted.')
    return redirect('admin_panel:events')


# ---------------------------------------------------------------------------
# Attendance (timestamps)
# ---------------------------------------------------------------------------

@admin_required
def attendance_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    logs  = (
        AttendanceLog.objects
        .filter(event=event)
        .select_related('student', 'scanned_by')
        .order_by('scanned_at')
    )
    context = {
        'event':   event,
        'logs':    logs,
        'present': logs.filter(status='present').count(),
        'late':    logs.filter(status='late').count(),
        'absent':  logs.filter(status='absent').count(),
        'total':   logs.count(),
    }
    return render(request, 'admin_panel/attendance.html', context)


# ---------------------------------------------------------------------------
# QR Scanner
# ---------------------------------------------------------------------------

@admin_required
def scanner_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'admin_panel/scanner.html', {'event': event})


@admin_required
@require_POST
def scan_qr_api(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    try:
        data  = json.loads(request.body)
        token = data.get('token', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)

    if not token:
        return JsonResponse({'success': False, 'message': 'No QR token provided.'})

    try:
        qr_token = QRToken.objects.select_related('student').get(token=token)
    except QRToken.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Unrecognized QR code.'})

    student = qr_token.student

    if student.status != 'active':
        return JsonResponse({'success': False, 'message': f'Student "{student.name}" is not active.'})

    # Prevent duplicate scans
    existing = AttendanceLog.objects.filter(student=student, event=event).first()
    if existing:
        return JsonResponse({
            'success':         False,
            'already_scanned': True,
            'message':         f'{student.name} already recorded as {existing.status.upper()}.',
            'student_name':    student.name,
            'student_id':      student.student_id,
            'status':          existing.status,
        })

    # Determine PRESENT or LATE
    now         = dj_timezone.now()
    event_start = datetime.combine(event.date, event.start_time, tzinfo=dt_timezone.utc)
    cutoff      = event_start + timedelta(minutes=event.late_cutoff_mins)
    status      = 'present' if now <= cutoff else 'late'

    admin = get_current_admin(request)
    AttendanceLog.objects.create(
        id=uuid.uuid4(),
        student=student,
        event=event,
        scanned_by=admin,
        status=status,
        scanned_at=now,
    )

    return JsonResponse({
        'success':      True,
        'student_name': student.name,
        'student_id':   student.student_id,
        'section':      student.section,
        'status':       status,
        'scanned_at':   now.strftime('%I:%M:%S %p'),
    })


# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------

@admin_required
def export_attendance_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    logs  = (
        AttendanceLog.objects
        .filter(event=event)
        .select_related('student', 'scanned_by')
        .order_by('scanned_at')
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Attendance'

    ws.merge_cells('A1:F1')
    title_cell            = ws['A1']
    title_cell.value      = f'Attendance: {event.name}'
    title_cell.font       = Font(bold=True, size=14)
    title_cell.alignment  = Alignment(horizontal='center')

    ws.merge_cells('A2:F2')
    sub_cell           = ws['A2']
    sub_cell.value     = f'Date: {event.date}  |  Start: {event.start_time.strftime("%I:%M %p")}  |  Late cutoff: {event.late_cutoff_mins} mins'
    sub_cell.alignment = Alignment(horizontal='center')

    headers     = ['Student ID', 'Name', 'Section', 'Status', 'Scanned At', 'Scanned By']
    header_fill = PatternFill(start_color='1F3864', end_color='1F3864', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)

    for col, header in enumerate(headers, start=1):
        cell           = ws.cell(row=4, column=col, value=header)
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = Alignment(horizontal='center')

    status_colors = {'present': 'C6EFCE', 'late': 'FFEB9C', 'absent': 'FFC7CE'}

    for row_idx, log in enumerate(logs, start=5):
        scanned_at = log.scanned_at.strftime('%Y-%m-%d %I:%M:%S %p') if log.scanned_at else '—'
        row_data   = [
            log.student.student_id,
            log.student.name,
            log.student.section,
            log.status.upper(),
            scanned_at,
            log.scanned_by.name if log.scanned_by else '—',
        ]
        row_fill = PatternFill(
            start_color=status_colors.get(log.status, 'FFFFFF'),
            end_color=status_colors.get(log.status, 'FFFFFF'),
            fill_type='solid'
        )
        for col, value in enumerate(row_data, start=1):
            cell           = ws.cell(row=row_idx, column=col, value=value)
            cell.alignment = Alignment(horizontal='center' if col != 2 else 'left')
            if col == 4:
                cell.fill = row_fill
                cell.font = Font(bold=True)

    for col, width in enumerate([15, 25, 15, 12, 25, 20], start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value='Summary').font = Font(bold=True)
    ws.cell(row=summary_row, column=2, value=f'Present: {logs.filter(status="present").count()}')
    ws.cell(row=summary_row, column=3, value=f'Late: {logs.filter(status="late").count()}')
    ws.cell(row=summary_row, column=4, value=f'Absent: {logs.filter(status="absent").count()}')
    ws.cell(row=summary_row, column=5, value=f'Total: {logs.count()}')

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_name = event.name.replace(' ', '_').replace('/', '-')
    response['Content-Disposition'] = f'attachment; filename="attendance_{safe_name}_{event.date}.xlsx"'
    wb.save(response)
    return response


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@admin_required
def students_view(request):
    status_filter = request.GET.get('status', 'all')
    students      = Student.objects.order_by('-created_at')
    if status_filter in ('pending', 'active', 'rejected'):
        students = students.filter(status=status_filter)
    return render(request, 'admin_panel/students.html', {
        'students':      students,
        'status_filter': status_filter,
    })


@admin_required
@require_POST
def student_approve_view(request, pk):
    student                = get_object_or_404(Student, id=pk)
    student.status         = 'active'
    student.rejection_note = None
    student.save()
    messages.success(request, f'{student.name} approved.')
    return redirect('admin_panel:students')


@admin_required
@require_POST
def student_reject_view(request, pk):
    student                = get_object_or_404(Student, id=pk)
    note                   = request.POST.get('rejection_note', '').strip()
    student.status         = 'rejected'
    student.rejection_note = note or 'Rejected by admin.'
    student.save()
    messages.warning(request, f'{student.name} rejected.')
    return redirect('admin_panel:students')
