import hashlib
import uuid
import re
import json
from datetime import datetime, timedelta, timezone as dt_timezone, time as dt_time

from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone as dj_timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from django.db.models import Count, Q
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from myapp.models import Admin, Student, Event, QRToken, AttendanceLog, Section, AdminSection
from .forms import LoginForm, EventForm

import zoneinfo
PH_TZ = zoneinfo.ZoneInfo("Asia/Manila")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def ph_now():
    """Return current Philippine time (Asia/Manila) as a timezone-aware datetime."""
    return datetime.now(PH_TZ)


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_id'):
            return redirect('admin_panel:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    """Restrict view to specific admin roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.session.get('admin_id'):
                return redirect('admin_panel:login')
            role = request.session.get('admin_role')
            if role not in allowed_roles:
                messages.error(request, 'You do not have permission to access that page.')
                return redirect('admin_panel:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_current_admin(request):
    admin_id = request.session.get('admin_id')
    if admin_id:
        try:
            return Admin.objects.get(id=admin_id)
        except Admin.DoesNotExist:
            pass
    return None


def get_rep_section_ids(admin):
    """Get section IDs assigned to a representative."""
    return list(AdminSection.objects.filter(admin=admin).values_list('section_id', flat=True))


def build_section_tiles_with_attendance(event=None):
    """Build section tiles with present/late/absent counts for a specific event.
    
    Absent = Total Students in Section - (Present + Late)
    If no event is selected/active, all stats are 0.
    """
    sections = Section.objects.all().order_by('year_level', 'name')

    tiles = []
    for sec in sections:
        active_students = Student.objects.filter(section=sec, status='active').count()
        present = 0
        late = 0
        absent = 0
        if event:
            students_in_sec = Student.objects.filter(section=sec, status='active')
            logs = AttendanceLog.objects.filter(event=event, student__in=students_in_sec)
            present = logs.filter(status='present').count()
            late = logs.filter(status='late').count()
            # Absent = everyone who hasn't scanned yet
            absent = active_students - (present + late)
            if absent < 0:
                absent = 0
        tiles.append({
            'section': sec,
            'active_students': active_students,
            'present': present,
            'late': late,
            'absent': absent,
        })
    return tiles


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    # Verify admin exists in DB before redirecting to dashboard
    if get_current_admin(request):
        return redirect('admin_panel:dashboard')
    elif request.session.get('admin_id'):
        # ID is in session but not in DB (likely deleted) - clear session
        request.session.flush()

    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email       = form.cleaned_data['email']
            password    = form.cleaned_data['password']
            chosen_role = form.cleaned_data['role']
            pw_hash     = hash_password(password)
            try:
                admin = Admin.objects.get(email=email, password_hash=pw_hash, is_active=True)
                # Chairperson uses the hidden endpoint, not this form
                if admin.role == 'chairperson':
                    messages.error(request, 'Invalid email or password.')
                elif admin.role != chosen_role:
                    role_display = admin.get_role_display()
                    messages.error(request, f'This account is registered as a {role_display}. Please select the correct role.')
                else:
                    request.session['admin_id']   = str(admin.id)
                    request.session['admin_name'] = admin.name
                    request.session['admin_role'] = admin.role
                    request.session['force_password_change'] = admin.force_password_change
                    return redirect('admin_panel:dashboard')
            except Admin.DoesNotExist:
                messages.error(request, 'Invalid email or password.')

    return render(request, 'admin_panel/login.html', {'form': form})


def logout_view(request):
    request.session.flush()
    return redirect('admin_panel:login')


# ---------------------------------------------------------------------------
# Forced Password Change (VITS/Rep first login)
# ---------------------------------------------------------------------------

@admin_required
@require_POST
def force_change_password_view(request):
    admin = get_current_admin(request)
    if not admin or not admin.force_password_change:
        return redirect('admin_panel:dashboard')

    new_pw  = request.POST.get('new_password', '').strip()
    confirm = request.POST.get('confirm_password', '').strip()

    # Validate
    if len(new_pw) < 8:
        messages.error(request, 'Password must be at least 8 characters.')
        return redirect('admin_panel:dashboard')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_pw):
        messages.error(request, 'Password must contain at least one special character.')
        return redirect('admin_panel:dashboard')
    if new_pw != confirm:
        messages.error(request, 'Passwords do not match.')
        return redirect('admin_panel:dashboard')

    # Ensure it's not the same as the default password (lastname_@2026#)
    # Extract last name from admin.name (last word)
    name_parts = admin.name.strip().split()
    last_name = name_parts[-1] if name_parts else ''
    default_pw = f"{last_name}_@2026#"
    if new_pw == default_pw:
        messages.error(request, 'You cannot use the default password. Please choose a new one.')
        return redirect('admin_panel:dashboard')

    admin.password_hash = hash_password(new_pw)
    admin.force_password_change = False
    admin.save()
    request.session['force_password_change'] = False
    messages.success(request, 'Password changed successfully! Welcome.')
    return redirect('admin_panel:dashboard')


# ---------------------------------------------------------------------------
# Chairperson hidden login
# ---------------------------------------------------------------------------

def chairperson_login_view(request):
    if request.session.get('admin_id'):
        role = request.session.get('admin_role')
        if role == 'chairperson':
            return redirect('admin_panel:chairperson_dashboard')
        return redirect('admin_panel:dashboard')

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        pw_hash  = hash_password(password)
        try:
            admin = Admin.objects.get(email=email, password_hash=pw_hash, is_active=True, role='chairperson')
            request.session['admin_id']   = str(admin.id)
            request.session['admin_name'] = admin.name
            request.session['admin_role'] = admin.role
            request.session['force_password_change'] = False
            return redirect('admin_panel:chairperson_dashboard')
        except Admin.DoesNotExist:
            messages.error(request, 'Invalid credentials.')

    return render(request, 'admin_panel/chairperson_login.html')


# ---------------------------------------------------------------------------
# Dashboard (routes by role)
# ---------------------------------------------------------------------------

@admin_required
def dashboard_view(request):
    role = request.session.get('admin_role')
    if role == 'chairperson':
        return redirect('admin_panel:chairperson_dashboard')
    elif role == 'representative':
        return _rep_dashboard(request)
    else:
        return _vits_dashboard(request)


def _vits_dashboard(request):
    total_events     = Event.objects.count()
    total_students   = Student.objects.filter(status='active').count()
    pending_students = Student.objects.filter(status='pending').count()
    total_logs       = AttendanceLog.objects.count()
    now              = ph_now()
    today            = now.date()
    today_events     = Event.objects.filter(date=today, status='active')
    recent_events    = Event.objects.order_by('-date', '-start_time')[:5]

    # Active events for section overview dropdown (only active)
    active_events = Event.objects.filter(status='active').order_by('-date', '-start_time')
    all_events = Event.objects.all().order_by('-date', '-start_time')

    # Determine which event to show stats for
    selected_event = None
    event_id = request.GET.get('event_id')
    if event_id:
        try:
            selected_event = Event.objects.get(id=event_id, status='active')
        except Event.DoesNotExist:
            pass
    if not selected_event:
        selected_event = active_events.first()

    section_tiles = build_section_tiles_with_attendance(event=selected_event)

    context = {
        'total_events':     total_events,
        'total_students':   total_students,
        'pending_students': pending_students,
        'total_logs':       total_logs,
        'today_events':     today_events,
        'recent_events':    recent_events,
        'section_tiles':    section_tiles,
        'active_events':    active_events,
        'all_events':       all_events,
        'selected_event_id': str(selected_event.id) if selected_event else '',
        'admin_name':       request.session.get('admin_name', 'Admin'),
        'admin_role':       request.session.get('admin_role'),
        'force_password_change': request.session.get('force_password_change', False),
    }
    return render(request, 'admin_panel/dashboard.html', context)


def _rep_dashboard(request):
    admin = get_current_admin(request)
    section_ids = get_rep_section_ids(admin)
    sections = Section.objects.filter(id__in=section_ids)

    now = ph_now()
    today = now.date()
    today_events = Event.objects.filter(date=today, status='active')

    # Build per-section stats for today's active events
    section_stats = []
    for sec in sections:
        students_in_section = Student.objects.filter(section=sec, status='active')
        for evt in today_events:
            logs = AttendanceLog.objects.filter(event=evt, student__in=students_in_section)
            section_stats.append({
                'section': sec,
                'event': evt,
                'present': logs.filter(status='present').count(),
                'late': logs.filter(status='late').count(),
                'absent': logs.filter(status='absent').count(),
                'total_students': students_in_section.count(),
            })

    context = {
        'sections': sections,
        'section_stats': section_stats,
        'today_events': today_events,
        'admin_name': request.session.get('admin_name', 'Admin'),
        'admin_role': 'representative',
        'force_password_change': request.session.get('force_password_change', False),
    }
    return render(request, 'admin_panel/rep_dashboard.html', context)


# ---------------------------------------------------------------------------
# Chairperson Dashboard
# ---------------------------------------------------------------------------

@role_required('chairperson')
def chairperson_dashboard_view(request):
    total_events     = Event.objects.count()
    active_events    = Event.objects.filter(status='active').order_by('-date', '-start_time')
    all_events       = Event.objects.all().order_by('-date', '-start_time')
    total_students   = Student.objects.filter(status='active').count()
    pending_students = Student.objects.filter(status='pending').count()
    total_sections   = Section.objects.count()
    total_admins     = Admin.objects.filter(is_active=True).exclude(role='chairperson').count()

    # Determine which event to show stats for (only active events)
    selected_event = None
    event_id = request.GET.get('event_id')
    if event_id:
        try:
            selected_event = Event.objects.get(id=event_id, status='active')
        except Event.DoesNotExist:
            pass
    if not selected_event:
        selected_event = active_events.first()

    section_tiles = build_section_tiles_with_attendance(event=selected_event)

    context = {
        'total_events':     total_events,
        'active_events':    active_events,
        'all_events':       all_events,
        'total_students':   total_students,
        'pending_students': pending_students,
        'total_sections':   total_sections,
        'total_admins':     total_admins,
        'section_tiles':    section_tiles,
        'selected_event_id': str(selected_event.id) if selected_event else '',
        'admin_name':       request.session.get('admin_name', 'Admin'),
        'admin_role':       'chairperson',
    }
    return render(request, 'admin_panel/chairperson_dashboard.html', context)


# ---------------------------------------------------------------------------
# Chart data API (Chairperson + VITS)
# ---------------------------------------------------------------------------

@admin_required
def chart_data_api(request):
    role = request.session.get('admin_role')
    if role not in ('chairperson', 'vits'):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    event_id = request.GET.get('event_id')
    if not event_id:
        return JsonResponse({'error': 'event_id required'}, status=400)

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)

    sections = Section.objects.all().order_by('year_level', 'name')
    labels = [s.name for s in sections]
    present_data = []
    late_data = []
    absent_data = []

    for sec in sections:
        students_in_sec = Student.objects.filter(section=sec, status='active')
        total_in_sec = students_in_sec.count()
        logs = AttendanceLog.objects.filter(event=event, student__in=students_in_sec)
        present = logs.filter(status='present').count()
        late = logs.filter(status='late').count()
        absent = total_in_sec - (present + late)
        if absent < 0:
            absent = 0
        present_data.append(present)
        late_data.append(late)
        absent_data.append(absent)

    return JsonResponse({
        'labels': labels,
        'present': present_data,
        'late': late_data,
        'absent': absent_data,
        'event_name': event.name,
    })


# ---------------------------------------------------------------------------
# Section Management (Chairperson only)
# ---------------------------------------------------------------------------

@role_required('chairperson')
def sections_manage_view(request):
    # Fetch sections and apply numeric sorting (BSIT 1-1, 1-2, ..., 1-10)
    sections_list = list(Section.objects.all())
    def sort_key(s):
        try:
            # name is "BSIT {year}-{number}"
            # Extract the number after the dash
            num_part = s.name.split('-')[-1]
            return (s.year_level, int(num_part))
        except (ValueError, IndexError):
            return (s.year_level, s.name)
    
    sections_list.sort(key=sort_key)
    if request.method == 'POST':
        year = request.POST.get('year_level', '1')
        section_number = request.POST.get('section_number', '').strip()

        if year and section_number:
            try:
                total_to_create = int(section_number)
                added_count = 0
                for i in range(1, total_to_create + 1):
                    name = f"BSIT {year}-{i}"
                    if not Section.objects.filter(name=name).exists():
                        Section.objects.create(id=uuid.uuid4(), name=name, year_level=int(year))
                        added_count += 1
                
                if added_count > 0:
                    messages.success(request, f'Successfully created {added_count} new section(s) for Year {year}.')
                else:
                    messages.info(request, f'No new sections created (all sections up to {total_to_create} already exist).')
            except ValueError:
                messages.error(request, 'Please enter a valid number for the total sections.')
        else:
            messages.error(request, 'Please fill in all fields.')
        return redirect('admin_panel:sections_manage')
    return render(request, 'admin_panel/sections_manage.html', {'sections': sections_list})


@role_required('chairperson')
@require_POST
def section_delete_view(request, pk):
    section = get_object_or_404(Section, id=pk)
    name = section.name
    section.delete()
    messages.success(request, f'Section "{name}" deleted.')
    return redirect('admin_panel:sections_manage')


# ---------------------------------------------------------------------------
# Admin (Officer/Rep) Management (Chairperson only)
# ---------------------------------------------------------------------------

@role_required('chairperson')
def admins_manage_view(request):
    admins = Admin.objects.filter(is_active=True).exclude(role='chairperson').order_by('role', 'name')
    sections = Section.objects.all().order_by('year_level', 'name')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name     = request.POST.get('name', '').strip()
            email    = request.POST.get('email', '').strip()
            role     = request.POST.get('role', 'vits')
            sec_ids  = request.POST.getlist('sections')

            if not all([name, email]):
                messages.error(request, 'Name and email are required.')
            elif Admin.objects.filter(email=email).exists():
                messages.error(request, 'An admin with that email already exists.')
            else:
                # Auto-generate password: lastname_@2026#
                name_parts = name.strip().split()
                last_name = name_parts[-1] if name_parts else 'user'
                default_password = f"{last_name}_@2026#"

                new_admin = Admin.objects.create(
                    id=uuid.uuid4(),
                    name=name,
                    email=email,
                    password_hash=hash_password(default_password),
                    role=role,
                    is_active=True,
                    force_password_change=True,  # Must change on first login
                )
                # Assign sections for representatives
                if role == 'representative' and sec_ids:
                    for sid in sec_ids:
                        AdminSection.objects.create(id=uuid.uuid4(), admin=new_admin, section_id=sid)

                # Send email with credentials
                role_display = new_admin.get_role_display()
                try:
                    send_mail(
                        subject=f'CODE-IT System — You have been added as {role_display}',
                        message=(
                            f'Hello {name},\n\n'
                            f'You have been added as a {role_display} in the CODE-IT Attendance System.\n\n'
                            f'Your login credentials:\n'
                            f'  Email: {email}\n'
                            f'  Password: {default_password}\n\n'
                            f'IMPORTANT: You will be required to change your password on your first login.\n\n'
                            f'Login at the admin panel to get started.\n\n'
                            f'— CODE-IT System'
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    messages.success(request, f'{role_display} "{name}" added. Credentials sent to {email}.')
                except Exception as e:
                    messages.warning(request,
                        f'{role_display} "{name}" added, but email failed to send: {str(e)}. '
                        f'Default password: {default_password}'
                    )
        return redirect('admin_panel:admins_manage')

    # Annotate with assigned sections
    admin_data = []
    for a in admins:
        assigned = AdminSection.objects.filter(admin=a).select_related('section')
        admin_data.append({
            'admin': a,
            'sections': [asc.section for asc in assigned],
        })

    return render(request, 'admin_panel/admins_manage.html', {
        'admin_data': admin_data,
        'sections': sections,
    })


@role_required('chairperson')
@require_POST
def admin_remove_view(request, pk):
    admin = get_object_or_404(Admin, id=pk)
    if admin.role == 'chairperson':
        messages.error(request, 'Cannot remove the chairperson.')
        return redirect('admin_panel:admins_manage')
    admin.is_active = False
    admin.save()
    messages.success(request, f'{admin.name} has been deactivated.')
    return redirect('admin_panel:admins_manage')


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@admin_required
def events_view(request):
    role = request.session.get('admin_role')
    events = Event.objects.order_by('-date', '-start_time')
    return render(request, 'admin_panel/events.html', {
        'events': events,
        'admin_role': role,
        'force_password_change': request.session.get('force_password_change', False),
    })


@role_required('chairperson', 'vits')
def event_create_view(request):
    form = EventForm()
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event            = form.save(commit=False)
            event.id         = uuid.uuid4()
            event.created_by = get_current_admin(request)

            now = ph_now()
            event_date = event.date
            event_start = event.start_time

            if event_date == now.date():
                # Compare at the minute level to allow starting at the current time
                now_mins = now.hour * 60 + now.minute
                start_mins = event_start.hour * 60 + event_start.minute
                if start_mins < now_mins:
                    messages.error(
                        request,
                        f'Cannot set start time to {event_start.strftime("%I:%M %p")} — '
                        f'that time has already passed. Current PH time is {now.strftime("%I:%M %p")}.'
                    )
                    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})

            if event_date < now.date():
                messages.error(request, 'Cannot create an event in the past.')
                return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})

            # End time must be later than start time
            if event.end_time and event.end_time <= event.start_time:
                messages.error(request, 'End time must be later than start time.')
                return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})
            event.status = 'pending'  # Events start as pending
            event.save()
            messages.success(request, f'Event "{event.name}" created. It will remain pending until you start it.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})


@role_required('chairperson', 'vits')
def event_edit_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    form  = EventForm(instance=event)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            updated = form.save(commit=False)

            # Time integrity check for edits too
            now = ph_now()
            if updated.date == now.date() and event.status == 'pending':
                now_mins = now.hour * 60 + now.minute
                start_mins = updated.start_time.hour * 60 + updated.start_time.minute
                if start_mins < now_mins:
                    messages.error(
                        request,
                        f'Cannot set start time to {updated.start_time.strftime("%I:%M %p")} — '
                        f'that time has already passed. Current PH time is {now.strftime("%I:%M %p")}.'
                    )
                    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Edit', 'event': event})

            # End time must be later than start time
            if updated.end_time and updated.end_time <= updated.start_time:
                messages.error(request, 'End time must be later than start time.')
                return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Edit', 'event': event})

            updated.save()
            messages.success(request, f'Event "{event.name}" updated.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Edit', 'event': event})


@role_required('chairperson', 'vits')
@require_POST
def event_delete_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    name  = event.name
    event.delete()
    messages.success(request, f'Event "{name}" deleted.')
    return redirect('admin_panel:events')


@role_required('chairperson', 'vits')
@require_POST
def event_start_view(request, pk):
    """Chairperson explicitly starts a pending event."""
    event = get_object_or_404(Event, id=pk)
    if event.status != 'pending':
        messages.warning(request, f'Event "{event.name}" is already {event.status}.')
        return redirect('admin_panel:events')

    # Time integrity: warn if start_time is in the past
    now = ph_now()
    if event.date == now.date() and event.start_time < now.time():
        messages.warning(
            request,
            f'Warning: The scheduled start time ({event.start_time.strftime("%I:%M %p")}) '
            f'has already passed. Current PH time is {now.strftime("%I:%M %p")}. '
            f'The event has been started anyway — attendance timing will use the original start time.'
        )

    event.status = 'active'
    event.save()
    messages.success(request, f'Event "{event.name}" is now ACTIVE.')
    return redirect('admin_panel:events')


@role_required('chairperson', 'vits')
@require_POST
def event_end_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    event.status = 'ended'
    event.save()
    messages.success(request, f'Event "{event.name}" has been ended.')
    return redirect('admin_panel:events')


# ---------------------------------------------------------------------------
# Finalize Event (lock absent students)
# ---------------------------------------------------------------------------

@admin_required
@require_POST
def finalize_event_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Count how many are still absent (pre-marked but didn't scan)
    absent_logs = AttendanceLog.objects.filter(event=event, status='absent')
    count       = absent_logs.count()

    if count == 0:
        messages.info(request, f'No absent students to finalize for "{event.name}".')
    else:
        messages.success(request, f'Event "{event.name}" finalized — {count} student(s) marked as Absent.')

    return redirect('admin_panel:attendance', event_id=event_id)


# ---------------------------------------------------------------------------
# Expected Students (pre-mark absent)
# ---------------------------------------------------------------------------

@admin_required
def set_expected_students_view(request, event_id):
    event    = get_object_or_404(Event, id=event_id)
    students = Student.objects.filter(status='active').order_by('last_name', 'first_name')

    # IDs of students already in the expected list for this event
    existing_logs   = AttendanceLog.objects.filter(event=event).select_related('student')
    expected_ids    = set(str(log.student.id) for log in existing_logs)
    locked_ids      = set(str(log.student.id) for log in existing_logs if log.status in ('present', 'late'))

    if request.method == 'POST':
        selected_ids = set(request.POST.getlist('student_ids'))
        admin        = get_current_admin(request)

        # Add new expected students (not already in the list)
        added = 0
        for student in students:
            sid = str(student.id)
            if sid in selected_ids and sid not in expected_ids:
                AttendanceLog.objects.create(
                    id=uuid.uuid4(),
                    student=student,
                    event=event,
                    scanned_by=None,
                    status='absent',
                    scanned_at=None,
                )
                added += 1

        # Remove unchecked students — only if they are still absent (not scanned yet)
        removed = 0
        for log in existing_logs:
            sid = str(log.student.id)
            if sid not in selected_ids and log.status == 'absent':
                log.delete()
                removed += 1

        messages.success(request, f'Expected list updated — {added} added, {removed} removed.')
        return redirect('admin_panel:attendance', event_id=event_id)

    context = {
        'event':       event,
        'students':    students,
        'expected_ids': expected_ids,
        'locked_ids':  locked_ids,
    }
    return render(request, 'admin_panel/expected_students.html', context)


# ---------------------------------------------------------------------------
# Attendance (timestamps)
# ---------------------------------------------------------------------------

@admin_required
def attendance_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    admin = get_current_admin(request)
    role  = request.session.get('admin_role')

    logs = (
        AttendanceLog.objects
        .filter(event=event)
        .select_related('student', 'scanned_by', 'student__section')
        .order_by('scanned_at')
    )

    # Representatives only see their assigned sections
    if role == 'representative':
        section_ids = get_rep_section_ids(admin)
        logs = logs.filter(student__section_id__in=section_ids)

    # Check if event has ended
    event_ended = False
    if event.end_time:
        event_end   = datetime.combine(event.date, event.end_time, tzinfo=PH_TZ)
        event_ended = ph_now() > event_end

    context = {
        'event':       event,
        'logs':        logs,
        'present':     logs.filter(status='present').count(),
        'late':        logs.filter(status='late').count(),
        'absent':      logs.filter(status='absent').count(),
        'total':       logs.count(),
        'event_ended': event_ended,
        'admin_role':  role,
    }
    return render(request, 'admin_panel/attendance.html', context)


# ---------------------------------------------------------------------------
# QR Scanner (VITS only)
# ---------------------------------------------------------------------------

@role_required('vits')
def scanner_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if event.status != 'active':
        messages.warning(request, f'Cannot scan: event "{event.name}" is {event.status}.')
        return redirect('admin_panel:events')
    return render(request, 'admin_panel/scanner.html', {'event': event})


@role_required('vits')
@require_POST
def scan_qr_api(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if event.status != 'active':
        return JsonResponse({'success': False, 'message': 'Event is not active.'}, status=400)

    # Block scans if event has ended
    if event.end_time:
        now_time = ph_now()
        event_end = datetime.combine(event.date, event.end_time, tzinfo=PH_TZ)
        if now_time > event_end:
            return JsonResponse({
                'success': False,
                'event_ended': True,
                'message': f'This event has already ended at {event.end_time.strftime("%I:%M %p")}. No more scans allowed.',
            })

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

    # Use Philippine time for attendance determination
    now = ph_now()
    event_start = datetime.combine(event.date, event.start_time, tzinfo=PH_TZ)
    cutoff      = event_start + timedelta(minutes=event.late_cutoff_mins)
    status      = 'present' if now <= cutoff else 'late'

    admin    = get_current_admin(request)
    existing = AttendanceLog.objects.filter(student=student, event=event).first()

    if existing:
        # Already scanned as present or late — block duplicate
        if existing.status in ('present', 'late'):
            return JsonResponse({
                'success':         False,
                'already_scanned': True,
                'message':         f'{student.name} already recorded as {existing.status.upper()}.',
                'student_name':    student.name,
                'student_id':      student.student_id,
                'status':          existing.status,
            })
        # Was pre-marked as absent — update to present/late
        existing.status     = status
        existing.scanned_by = admin
        existing.scanned_at = now
        existing.save()
    else:
        # Walk-in: not in expected list — create new record
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
        'section':      student.section.name if student.section else '',
        'status':       status,
        'scanned_at':   now.strftime('%I:%M:%S %p'),
    })


# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------

@admin_required
def export_attendance_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    admin = get_current_admin(request)
    role  = request.session.get('admin_role')

    logs = (
        AttendanceLog.objects
        .filter(event=event)
        .select_related('student', 'scanned_by', 'student__section')
        .order_by('scanned_at')
    )

    if role == 'representative':
        section_ids = get_rep_section_ids(admin)
        logs = logs.filter(student__section_id__in=section_ids)

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Attendance'

    ws.merge_cells('A1:G1')
    title_cell            = ws['A1']
    title_cell.value      = f'Attendance: {event.name}'
    title_cell.font       = Font(bold=True, size=14)
    title_cell.alignment  = Alignment(horizontal='center')

    ws.merge_cells('A2:G2')
    sub_cell           = ws['A2']
    sub_cell.value     = f'Date: {event.date}  |  Start: {event.start_time.strftime("%I:%M %p")}  |  Late cutoff: {event.late_cutoff_mins} mins'
    sub_cell.alignment = Alignment(horizontal='center')

    headers     = ['Student ID', 'Name', 'Section', 'Year', 'Status', 'Scanned At', 'Scanned By']
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
        row_data = [
            log.student.student_id,
            log.student.name,
            log.student.section.name if log.student.section else '',
            log.student.year_level,
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
            if col == 5:
                cell.fill = row_fill
                cell.font = Font(bold=True)

    for col, width in enumerate([15, 25, 15, 8, 12, 25, 20], start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    from django.utils.text import slugify
    safe_name = slugify(event.name)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="attendance_{safe_name}_{event.date}.xlsx"'
    wb.save(response)
    return response


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@admin_required
def students_view(request):
    admin = get_current_admin(request)
    role  = request.session.get('admin_role')

    status_filter = request.GET.get('status', 'all')
    students      = Student.objects.select_related('section').order_by('-created_at')

    if role == 'representative':
        section_ids = get_rep_section_ids(admin)
        students = students.filter(section_id__in=section_ids)

    if status_filter in ('pending', 'active', 'rejected'):
        students = students.filter(status=status_filter)

    return render(request, 'admin_panel/students.html', {
        'students':      students,
        'status_filter': status_filter,
        'admin_role':    role,
        'force_password_change': request.session.get('force_password_change', False),
    })


@role_required('chairperson', 'vits')
@require_POST
@transaction.atomic
def student_approve_view(request, pk):
    import os
    import qrcode
    from io import BytesIO
    from django.core.mail import EmailMessage

    # Use select_for_update to lock the row and prevent simultaneous approvals
    student = get_object_or_404(Student.objects.select_for_update(), id=pk)
    student.status         = 'active'
    student.rejection_note = None
    student.save()

    # --- Auto-generate QR code on approval ---
    qr_created = False
    qr_file_path = ''

    if not QRToken.objects.filter(student=student).exists():
        token = str(uuid.uuid4())

        # Generate the physical QR PNG using the qrcode library
        qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
        os.makedirs(qr_dir, exist_ok=True)

        safe_sid = student.student_id.replace('-', '_')
        filename = f'qr_{safe_sid}.png'
        full_path = os.path.join(qr_dir, filename)

        # Build QR image
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(token)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        img.save(full_path)

        # Save relative path for serving via /media/
        qr_relative = f'/media/qr_codes/{filename}'

        QRToken.objects.create(
            id=uuid.uuid4(),
            student=student,
            token=token,
            qr_path=qr_relative,
        )
        qr_created = True
        qr_file_path = full_path

    # --- Email QR code to student ---
    if qr_created and student.email and qr_file_path:
        try:
            email = EmailMessage(
                subject='CODE-IT: Your Account Has Been Approved! 🎉',
                body=(
                    f'Hi {student.first_name},\n\n'
                    f'Great news! Your CODE-IT student account has been approved.\n\n'
                    f'Student ID: {student.student_id}\n'
                    f'Section: {student.section.name}\n'
                    f'Status: ACTIVE\n\n'
                    f'Your unique QR code is attached to this email. '
                    f'Please save it — you will need to present this code '
                    f'for attendance scanning at every event.\n\n'
                    f'You can also view your QR code anytime by logging into '
                    f'the CODE-IT Student Portal.\n\n'
                    f'— CODE-IT Attendance System'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[student.email],
            )
            email.attach_file(qr_file_path)
            email.send(fail_silently=False)
            messages.success(
                request,
                f'{student.name} approved. QR code generated and emailed to {student.email}.'
            )
        except Exception as e:
            messages.warning(
                request,
                f'{student.name} approved and QR generated, '
                f'but email failed to send: {e}. '
                f'The student can still view their QR in the portal.'
            )
    else:
        messages.success(request, f'{student.name} approved.')

    return redirect('admin_panel:students')


@role_required('chairperson', 'vits')
@require_POST
def student_reject_view(request, pk):
    student                = get_object_or_404(Student, id=pk)
    note                   = request.POST.get('rejection_note', '').strip()
    student.status         = 'rejected'
    student.rejection_note = note or 'Rejected by admin.'
    student.save()
    messages.warning(request, f'{student.name} rejected.')
    return redirect('admin_panel:students')


@role_required('chairperson', 'vits')
@require_POST
def student_delete_view(request, pk):
    student = get_object_or_404(Student, id=pk)
    name    = student.name
    student.delete()
    messages.success(request, f'Student "{name}" has been deleted.')
    return redirect('admin_panel:students')


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Generate / Regenerate QR Code
# ---------------------------------------------------------------------------

@role_required('chairperson', 'vits')
@require_POST
def generate_qr_view(request, pk):
    """Manual QR generation/regeneration tool."""
    import qrcode
    import secrets
    import os
    from io import BytesIO
    from django.core.files.storage import default_storage
    from django.conf import settings as django_settings

    student = get_object_or_404(Student, id=pk)

    if student.status != 'active':
        messages.error(request, f'{student.name} must be active to generate a QR code.')
        return redirect('admin_panel:students')

    # Get or create QR token
    try:
        qr_token = QRToken.objects.get(student=student)
    except QRToken.DoesNotExist:
        qr_token = QRToken.objects.create(
            id=uuid.uuid4(),
            student=student,
            token=secrets.token_urlsafe(32),
            qr_path='',
        )

    # Generate QR image
    try:
        qr_img   = qrcode.make(qr_token.token, box_size=10, border=2)
        buf      = BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)

        filename = f'qr_{student.id}.png'
        filepath = os.path.join(django_settings.MEDIA_ROOT, filename)

        # Overwrite if exists
        if default_storage.exists(filename):
            default_storage.delete(filename)

        saved_path       = default_storage.save(filename, buf)
        qr_token.qr_path = default_storage.url(saved_path)
        qr_token.save()

        # Send QR via email
        if student.email:
            try:
                from django.core.mail import EmailMessage
                buf.seek(0)
                subject = f'Your CODE-IT QR Code — {student.name}'
                body = (
                    f'Hi {student.name},\n\n'
                    f'Your QR code has been generated!\n\n'
                    f'Show this QR code at events to record your attendance.\n\n'
                    f'Student ID: {student.student_id}\n'
                    f'Section: {student.section}\n\n'
                    f'— CODE-IT Attendance System'
                )
                mail = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=django_settings.EMAIL_HOST_USER,
                    to=[student.email],
                )
                mail.attach('qr_code.png', buf.getvalue(), 'image/png')
                mail.send(fail_silently=False)
                messages.success(request, f'QR code generated and emailed to {student.email}.')
            except Exception as e:
                messages.warning(request, f'QR generated but email failed: {e}')
        else:
            messages.success(request, f'QR code generated for {student.name} (no email on file).')

    except Exception as e:
        messages.error(request, f'QR generation failed: {e}')

    return redirect('admin_panel:students')


# ---------------------------------------------------------------------------
# Sections API (for student registration dynamic dropdown)
# ---------------------------------------------------------------------------

def sections_by_year_api(request):
    """Public API: returns sections filtered by year_level."""
    year = request.GET.get('year', '')
    if not year or not year.isdigit():
        return JsonResponse([], safe=False)
    sections = list(Section.objects.filter(year_level=int(year)))
    
    def sort_key(s):
        try:
            num_part = s.name.split('-')[-1]
            return int(num_part)
        except (ValueError, IndexError):
            return s.name
            
    sections.sort(key=sort_key)
    
    data = [{'id': str(s.id), 'name': s.name} for s in sections]
    return JsonResponse(data, safe=False)
