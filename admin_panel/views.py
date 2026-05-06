import hashlib
import uuid
import json
import secrets
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.utils import timezone as dj_timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from django.db.models import Count, Q
from django.contrib.auth.hashers import check_password, make_password
from django.core.paginator import Paginator
from django.core.cache import cache

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from myapp.models import Admin, AdminSection, Section, Student, Event, QRToken, AttendanceLog, ActivityLog
from .forms import LoginForm, EventForm, AdminRegisterForm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_password(raw: str) -> str:
    return make_password(raw)


def verify_password(raw: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith('pbkdf2_'):
        return check_password(raw, stored)
    return hashlib.sha256(raw.encode()).hexdigest() == stored


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def is_ip_locked(ip):
    return (cache.get(f'login_attempts_{ip}') or 0) >= 5


def track_login_failure(ip):
    key = f'login_attempts_{ip}'
    current = cache.get(key, 0)
    cache.set(key, current + 1, timeout=900)


def clear_login_failures(ip):
    cache.delete(f'login_attempts_{ip}')


def ph_now():
    return dj_timezone.now()


def auto_update_event_statuses():
    today = dj_timezone.now().date()
    now_time = dj_timezone.now()

    # pending → active: if date is today and start_time has passed
    for event in Event.objects.filter(status='pending'):
        if event.date < today:
            event.status = 'active'
            event.save(update_fields=['status'])
        elif event.date == today and event.start_time:
            event_start = dj_timezone.make_aware(datetime.combine(event.date, event.start_time))
            if now_time >= event_start:
                event.status = 'active'
                event.save(update_fields=['status'])

    # active → ended: if date is past or end_time has passed
    for event in Event.objects.filter(status='active'):
        if event.date < today:
            event.status = 'ended'
            event.save(update_fields=['status'])
        elif event.date == today and event.end_time:
            event_end = dj_timezone.make_aware(datetime.combine(event.date, event.end_time))
            if now_time >= event_end:
                event.status = 'ended'
                event.save(update_fields=['status'])


def get_sorted_sections():
    sections = list(Section.objects.all())
    def sort_key(s):
        try:
            parts = s.name.replace('BSIT ', '').split('-')
            return (s.year_level, int(parts[-1]) if parts else 0)
        except (ValueError, IndexError):
            return (s.year_level, 0)
    sections.sort(key=sort_key)
    return sections


def log_activity(request, action, target=None, description=None):
    admin = get_current_admin(request)
    try:
        ActivityLog.objects.create(
            id=uuid.uuid4(),
            admin=admin,
            action=action,
            target=target,
            description=description,
        )
    except Exception:
        pass


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_id'):
            messages.warning(request, 'Session expired. Please log in again.')
            return redirect('admin_panel:login')
        if request.session.get('force_password_change'):
            return redirect('admin_panel:force_password_change')
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
        ip = get_client_ip(request)
        if is_ip_locked(ip):
            messages.error(request, 'Too many failed attempts. Try again after 15 minutes.')
            return render(request, 'admin_panel/login.html', {'form': form})

        form = LoginForm(request.POST)
        if form.is_valid():
            email     = form.cleaned_data['email']
            password  = form.cleaned_data['password']
            role_mode = request.POST.get('role_mode', 'vits')
            if role_mode not in ('vits', 'representative'):
                role_mode = 'vits'
            try:
                admin = Admin.objects.get(email=email, is_active=True)
                if not verify_password(password, admin.password_hash):
                    raise Admin.DoesNotExist
                if admin.role == Admin.Role.CHAIRPERSON:
                    messages.error(request, 'Please use the chairperson login page.')
                    track_login_failure(ip)
                    return render(request, 'admin_panel/login.html', {'form': form})
                if admin.role != role_mode:
                    messages.error(request, f'This account is registered as {admin.get_role_display()}. Please select the correct role.')
                    track_login_failure(ip)
                    return render(request, 'admin_panel/login.html', {'form': form})
                # Hash migration
                if not admin.password_hash.startswith('pbkdf2_'):
                    admin.password_hash = make_password(password)
                    admin.save(update_fields=['password_hash'])
                clear_login_failures(ip)
                request.session['admin_id']             = str(admin.id)
                request.session['admin_name']           = admin.name
                request.session['admin_role']           = admin.role
                request.session['force_password_change'] = admin.force_password_change
                request.session.cycle_key()
                return redirect('admin_panel:dashboard')
            except Admin.DoesNotExist:
                messages.error(request, 'Invalid email or password.')
                track_login_failure(ip)

    return render(request, 'admin_panel/login.html', {'form': form})


def chairperson_login_view(request):
    if request.session.get('admin_id'):
        return redirect('admin_panel:dashboard')

    form = LoginForm()
    if request.method == 'POST':
        ip = get_client_ip(request)
        if is_ip_locked(ip):
            messages.error(request, 'Too many failed attempts. Try again after 15 minutes.')
            return render(request, 'admin_panel/chairperson_login.html', {'form': form})

        form = LoginForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                admin = Admin.objects.get(email=email, role=Admin.Role.CHAIRPERSON, is_active=True)
                if not verify_password(password, admin.password_hash):
                    raise Admin.DoesNotExist
                if not admin.password_hash.startswith('pbkdf2_'):
                    admin.password_hash = make_password(password)
                    admin.save(update_fields=['password_hash'])
                clear_login_failures(ip)
                request.session['admin_id']             = str(admin.id)
                request.session['admin_name']           = admin.name
                request.session['admin_role']           = admin.role
                request.session['force_password_change'] = admin.force_password_change
                request.session.cycle_key()
                return redirect('admin_panel:dashboard')
            except Admin.DoesNotExist:
                messages.error(request, 'Invalid credentials.')
                track_login_failure(ip)

    return render(request, 'admin_panel/chairperson_login.html', {'form': form})


def logout_view(request):
    request.session.flush()
    return redirect('admin_panel:login')


def register_view(request):
    if request.session.get('admin_id'):
        return redirect('admin_panel:dashboard')

    form = AdminRegisterForm()
    if request.method == 'POST':
        form = AdminRegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if Admin.objects.filter(email=email).exists():
                messages.error(request, 'An admin with that email already exists.')
            else:
                Admin.objects.create(
                    id=uuid.uuid4(),
                    name=form.cleaned_data['name'],
                    email=email,
                    password_hash=hash_password(form.cleaned_data['password']),
                    role=form.cleaned_data['role'],
                    is_active=True,
                    force_password_change=False,
                )
                messages.success(request, 'Account created! You can now log in.')
                return redirect('admin_panel:login')

    return render(request, 'admin_panel/register.html', {'form': form})


def force_password_change_view(request):
    if not request.session.get('admin_id'):
        return redirect('admin_panel:login')

    if request.method == 'POST':
        new_pw  = request.POST.get('new_password', '').strip()
        confirm = request.POST.get('confirm_password', '').strip()

        if len(new_pw) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_pw):
            messages.error(request, 'Password must contain at least one special character.')
        elif new_pw != confirm:
            messages.error(request, 'Passwords do not match.')
        else:
            admin = get_current_admin(request)
            if admin:
                admin.password_hash          = hash_password(new_pw)
                admin.force_password_change  = False
                admin.save(update_fields=['password_hash', 'force_password_change'])
                request.session['force_password_change'] = False
                messages.success(request, 'Password updated successfully.')
                return redirect('admin_panel:dashboard')

    return render(request, 'admin_panel/force_password_change.html')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_required
def dashboard_view(request):
    auto_update_event_statuses()

    total_events     = Event.objects.count()
    
    current_admin = get_current_admin(request)
    admin_role = request.session.get('admin_role', 'vits')
    assigned_sections = Section.objects.all()

    if admin_role == 'representative':
        assigned_sections = Section.objects.filter(assigned_admins__admin=current_admin)
    
    total_students   = Student.objects.filter(status='active', section__in=assigned_sections).count()
    pending_students = Student.objects.filter(status='pending', section__in=assigned_sections).count()
    total_logs       = AttendanceLog.objects.filter(student__section__in=assigned_sections).count()
    total_sections   = assigned_sections.count()
    total_admins     = Admin.objects.filter(is_active=True).count()

    today        = dj_timezone.now().date()
    today_events = Event.objects.filter(date=today)
    recent_events = Event.objects.order_by('-date', '-start_time')[:5]
    upcoming_events = Event.objects.filter(date__gte=today).order_by('date', 'start_time')[:5]

    # Event selector for section overview
    all_events = Event.objects.order_by('-date', '-start_time')
    selected_event_id = request.GET.get('event')
    selected_event = None
    if selected_event_id:
        try:
            selected_event = Event.objects.get(id=selected_event_id)
        except Event.DoesNotExist:
            pass

    # Build section cards filtered by selected event
    section_cards = []
    for section in assigned_sections.order_by('year_level', 'name'):
        students = Student.objects.filter(section=section)
        if selected_event:
            section_logs = AttendanceLog.objects.filter(student__section=section, event=selected_event)
        else:
            section_logs = AttendanceLog.objects.none()
        present = section_logs.filter(status='present').count()
        late = section_logs.filter(status='late').count()
        absent = section_logs.filter(status='absent').count()
        section_cards.append({
            'name': section.name,
            'year_level': section.year_level,
            'total_students': students.count(),
            'active_students': students.filter(status='active').count(),
            'pending_students': students.filter(status='pending').count(),
            'present': present,
            'late': late,
            'absent': absent,
            'present_height': min(260, present * 7),
            'late_height': min(260, late * 7),
            'absent_height': min(260, absent * 7),
        })
    recent_students = Student.objects.filter(section__in=assigned_sections).select_related('section').order_by('-created_at')[:9]

    context = {
        'total_events':     total_events,
        'total_students':   total_students,
        'pending_students': pending_students,
        'total_logs':       total_logs,
        'total_sections':   total_sections,
        'total_admins':     total_admins,
        'today_events':     today_events,
        'recent_events':    recent_events,
        'upcoming_events':  upcoming_events,
        'admin_name':       request.session.get('admin_name', 'Admin'),
        'admin_role':       request.session.get('admin_role', 'vits'),
        'all_events':       all_events,
        'selected_event':   selected_event,
        'section_cards':    section_cards,
        'recent_students':  recent_students,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@admin_required
def sections_manage_view(request):
    import re as _re

    if request.method == 'POST':
        if request.session.get('admin_role') != 'chairperson':
            messages.error(request, 'Only the Chairperson can add sections.')
            return redirect('admin_panel:sections_manage')

        year_level_raw = request.POST.get('year_level', '1')
        count_raw = request.POST.get('count', '1')
        
        try:
            year_level = int(year_level_raw)
            if year_level not in (1, 2, 3, 4):
                year_level = 1
        except (TypeError, ValueError):
            year_level = 1

        try:
            count = int(count_raw)
            if count < 1: count = 1
            if count > 20: count = 20  # Limit max bulk creation
        except (TypeError, ValueError):
            count = 1

        added_sections = []
        for _ in range(count):
            # Auto-generate name: find max existing index for this year
            existing = Section.objects.filter(year_level=year_level)
            max_idx = 0
            for s in existing:
                m = _re.match(r'BSIT\s+\d+-(\d+)', s.name, _re.IGNORECASE)
                if m:
                    idx = int(m.group(1))
                    if idx > max_idx:
                        max_idx = idx
            section_name = f'BSIT {year_level}-{max_idx + 1}'

            if not Section.objects.filter(name__iexact=section_name).exists():
                Section.objects.create(id=uuid.uuid4(), name=section_name, year_level=year_level)
                added_sections.append(section_name)

        if added_sections:
            log_activity(request, 'ADD_SECTION', description=f'Added sections: {", ".join(added_sections)}')
            if len(added_sections) == 1:
                messages.success(request, f'{added_sections[0]} added.')
            else:
                messages.success(request, f'Successfully added {len(added_sections)} sections.')
        else:
            messages.warning(request, 'No new sections were added.')
            
        return redirect('admin_panel:sections_manage')

    # Filter and sort
    year_filter = request.GET.get('year', 'all')
    qs_list = get_sorted_sections()
    if year_filter != 'all':
        try:
            y = int(year_filter)
            qs_list = [s for s in qs_list if s.year_level == y]
        except (TypeError, ValueError):
            pass

    # Annotate with student counts
    sections = []
    for section in qs_list:
        section_students = Student.objects.filter(section=section)
        sections.append({
            'id': section.id,
            'name': section.name,
            'year_level': section.year_level,
            'total_students': section_students.count(),
            'active_students': section_students.filter(status='active').count(),
            'pending_students': section_students.filter(status='pending').count(),
        })

    # Pagination
    paginator = Paginator(sections, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_panel/sections_manage.html', {
        'sections':       page_obj,
        'page_obj':       page_obj,
        'total_sections': len(qs_list),
        'year_filter':    year_filter,
        'admin_role':     request.session.get('admin_role', 'vits'),
    })


@admin_required
def delete_section_view(request, pk):
    if request.method != 'POST':
        return redirect('admin_panel:sections_manage')
    try:
        section = Section.objects.get(id=pk)
        name = section.name
        section.delete()
        log_activity(request, 'DELETE_SECTION', description=f'Deleted section {name}')
        messages.success(request, f'{name} deleted.')
    except Section.DoesNotExist:
        messages.error(request, 'Section not found.')
    return redirect('admin_panel:sections_manage')



@admin_required
def admins_manage_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name  = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            role  = request.POST.get('role', Admin.Role.VITS)
            if role not in (Admin.Role.VITS, Admin.Role.REPRESENTATIVE):
                role = Admin.Role.VITS
            if not name or not email:
                messages.error(request, 'Name and email are required.')
            elif Admin.objects.filter(email=email).exists():
                messages.error(request, 'An officer with that email already exists.')
            else:
                generated_password = secrets.token_urlsafe(12)
                new_admin = Admin.objects.create(
                    id=uuid.uuid4(),
                    name=name,
                    email=email,
                    password_hash=hash_password(generated_password),
                    role=role,
                    is_active=True,
                    force_password_change=True,
                )
                # Assign sections for representatives
                if role == Admin.Role.REPRESENTATIVE:
                    section_ids = request.POST.getlist('section_ids')
                    for sid in section_ids:
                        try:
                            section = Section.objects.get(id=sid)
                            AdminSection.objects.get_or_create(
                                id=uuid.uuid4(),
                                admin=new_admin,
                                section=section,
                            )
                        except Section.DoesNotExist:
                            pass

                # Email credentials to new admin
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    subject = f'CODE-IT Admin Account — Your Login Credentials'
                    body = (
                        f'Hi {name},\n\n'
                        f'An admin account has been created for you in the CODE-IT Attendance System.\n\n'
                        f'Email: {email}\n'
                        f'Temporary Password: {generated_password}\n'
                        f'Role: {role.title()}\n\n'
                        f'You will be prompted to change your password on first login.\n\n'
                        f'— CODE-IT Attendance System'
                    )
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
                except Exception:
                    pass

                log_activity(request, 'ADMIN_CREATED', target=name, description=f'Created {role} account for {email}')
                messages.success(request, f'Officer account created. Temporary password: {generated_password} (also emailed).')

        elif action == 'delete':
            if request.session.get('admin_role') != 'chairperson':
                messages.error(request, 'Only the chairperson can remove officer accounts.')
                return redirect('admin_panel:admins_manage')
            admin_id = request.POST.get('admin_id')
            try:
                admin = Admin.objects.get(id=admin_id)
                if admin.role == Admin.Role.CHAIRPERSON:
                    messages.error(request, 'Chairperson account cannot be deleted here.')
                else:
                    name = admin.name
                    log_activity(request, 'ADMIN_DELETED', target=name, description=f'Deleted {admin.role} account {admin.email}')
                    admin.delete()
                    messages.success(request, f'{name} removed.')
            except Admin.DoesNotExist:
                messages.error(request, 'Officer account not found.')
        return redirect('admin_panel:admins_manage')

    admins = Admin.objects.order_by('name')
    all_sections = Section.objects.order_by('year_level', 'name')

    # Build sections map per admin
    admins_with_sections = []
    for admin in admins:
        assigned = AdminSection.objects.filter(admin=admin).select_related('section')
        admins_with_sections.append({
            'admin': admin,
            'sections': [a.section.name for a in assigned],
        })

    return render(request, 'admin_panel/admins_manage.html', {
        'admins': admins,
        'admins_with_sections': admins_with_sections,
        'total_admins': admins.count(),
        'admin_role': request.session.get('admin_role', 'vits'),
        'all_sections': all_sections,
    })


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@admin_required
def events_view(request):
    events = Event.objects.order_by('-date', '-start_time')
    return render(request, 'admin_panel/events.html', {
        'events': events,
        'admin_role': request.session.get('admin_role', 'vits'),
    })


@admin_required
def event_create_view(request):
    if request.session.get('admin_role') == 'representative':
        messages.error(request, 'Representatives do not have permission to create events.')
        return redirect('admin_panel:events')
    form = EventForm()
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event_date = form.cleaned_data.get('date')
            event_start_time = form.cleaned_data.get('start_time')
            
            # Time Zone Validation: Prevent past events
            if event_date:
                now = dj_timezone.localtime(dj_timezone.now())
                if event_start_time:
                    event_dt = dj_timezone.make_aware(datetime.combine(event_date, event_start_time))
                    # Allow a 1-minute grace period so "exactly now" works
                    if event_dt < (now - timedelta(minutes=1)):
                        messages.error(request, 'You cannot schedule an event in the past.')
                        return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})
                else:
                    if event_date < now.date():
                        messages.error(request, 'You cannot schedule an event on a past date.')
                        return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})

            event            = form.save(commit=False)
            event.id         = uuid.uuid4()
            event.created_by = get_current_admin(request)
            event.save()
            log_activity(request, 'EVENT_CREATED', target=event.name, description=f'Created event "{event.name}" on {event.date}')
            messages.success(request, f'Event "{event.name}" created successfully.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})


@admin_required
def event_edit_view(request, pk):
    if request.session.get('admin_role') == 'representative':
        messages.error(request, 'Representatives do not have permission to edit events.')
        return redirect('admin_panel:events')
    event = get_object_or_404(Event, id=pk)
    form  = EventForm(instance=event)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            log_activity(request, 'EVENT_EDITED', target=event.name, description=f'Edited event "{event.name}"')
            messages.success(request, f'Event "{event.name}" updated.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Edit', 'event': event})


@admin_required
@require_POST
def event_delete_view(request, pk):
    if request.session.get('admin_role') == 'representative':
        messages.error(request, 'Representatives do not have permission to delete events.')
        return redirect('admin_panel:events')
    event = get_object_or_404(Event, id=pk)
    name = event.name
    log_activity(request, 'EVENT_DELETED', target=name, description=f'Deleted event "{name}"')
    event.delete()
    messages.success(request, f'Event "{name}" deleted.')
    return redirect('admin_panel:events')


@admin_required
@require_POST
def start_event_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    if event.status != 'pending':
        messages.error(request, f'Only pending events can be started.')
        return redirect('admin_panel:events')
    event.status = 'active'
    if not event.start_time:
        event.start_time = dj_timezone.now().time()
    event.save(update_fields=['status', 'start_time'])
    log_activity(request, 'EVENT_STARTED', target=event.name, description=f'Started event "{event.name}"')
    messages.success(request, f'Event "{event.name}" started.')
    return redirect('admin_panel:events')


@admin_required
@require_POST
def end_event_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    if event.status != 'active':
        messages.error(request, f'Only active events can be ended.')
        return redirect('admin_panel:events')
    event.status = 'ended'
    event.save(update_fields=['status'])
    log_activity(request, 'EVENT_ENDED', target=event.name, description=f'Ended event "{event.name}" — check-out mode enabled')
    messages.success(request, f'Event "{event.name}" ended. Check-out scanning is now enabled.')
    return redirect('admin_panel:events')


@admin_required
@require_POST
def close_event_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    if request.session.get('admin_role') != 'chairperson':
        messages.error(request, 'Only the chairperson can close events.')
        return redirect('admin_panel:events')
    if event.status != 'ended':
        messages.error(request, 'Only ended events can be closed.')
        return redirect('admin_panel:events')
    event.status = 'closed'
    event.save(update_fields=['status'])
    log_activity(request, 'EVENT_CLOSED', target=event.name, description=f'Closed event "{event.name}" — final comparison enabled')
    messages.success(request, f'Event "{event.name}" closed. Final comparison is now available.')
    return redirect('admin_panel:events')


@admin_required
@require_POST
def extend_grace_event_view(request, pk):
    event = get_object_or_404(Event, id=pk)
    if event.status != 'active':
        messages.error(request, 'Grace period can only be extended for active events.')
        return redirect('admin_panel:events')
    event.late_cutoff_mins += 15
    event.save(update_fields=['late_cutoff_mins'])
    log_activity(request, 'GRACE_EXTENDED', target=event.name, description=f'Extended grace period to {event.late_cutoff_mins} mins for "{event.name}"')
    messages.success(request, f'Grace period extended to {event.late_cutoff_mins} minutes.')
    return redirect('admin_panel:events')


# ---------------------------------------------------------------------------
# Finalize Event (lock absent students)
# ---------------------------------------------------------------------------

@admin_required
@require_POST
def finalize_event_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    absent_logs = AttendanceLog.objects.filter(event=event, status='absent')
    count = absent_logs.count()
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

    existing_logs = AttendanceLog.objects.filter(event=event).select_related('student')
    expected_ids  = set(str(log.student.id) for log in existing_logs)
    locked_ids    = set(str(log.student.id) for log in existing_logs if log.status in ('present', 'late'))

    if request.method == 'POST':
        selected_ids = set(request.POST.getlist('student_ids'))
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

        removed = 0
        for log in existing_logs:
            sid = str(log.student.id)
            if sid not in selected_ids and log.status == 'absent':
                log.delete()
                removed += 1

        messages.success(request, f'Expected list updated — {added} added, {removed} removed.')
        return redirect('admin_panel:attendance', event_id=event_id)

    context = {
        'event':        event,
        'students':     students,
        'expected_ids': expected_ids,
        'locked_ids':   locked_ids,
    }
    return render(request, 'admin_panel/expected_students.html', context)


# ---------------------------------------------------------------------------
# Attendance
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

    status_filter = request.GET.get('status', 'all')
    if status_filter in ('present', 'late', 'absent'):
        logs_filtered = logs.filter(status=status_filter)
    else:
        logs_filtered = logs

    paginator = Paginator(logs_filtered, 25)
    page_obj  = paginator.get_page(request.GET.get('page'))

    present = logs.filter(status='present').count()
    late    = logs.filter(status='late').count()
    absent  = logs.filter(status='absent').count()
    total   = logs.count()

    # Check-out stats for ended/closed events
    checked_out     = logs.filter(scanned_out_at__isnull=False).count()
    not_checked_out = logs.filter(status__in=('present', 'late'), scanned_out_at__isnull=True).count()

    # Year filter for section tiles
    year_filter = request.GET.get('year', 'all')
    all_sections = Section.objects.order_by('year_level', 'name')
    if year_filter and year_filter != 'all':
        try:
            all_sections = all_sections.filter(year_level=int(year_filter))
        except (ValueError, TypeError):
            pass

    # Distinct year levels for dropdown
    year_levels = Section.objects.values_list('year_level', flat=True).distinct().order_by('year_level')

    # Section-level check-in tiles (ALL sections)
    section_tiles = []
    for section in all_sections:
        s_logs = logs.filter(student__section=section)
        section_tiles.append({
            'name': section.name,
            'year_level': section.year_level,
            'total_students': Student.objects.filter(section=section, status='active').count(),
            'present': s_logs.filter(status='present').count(),
            'late': s_logs.filter(status='late').count(),
            'absent': s_logs.filter(status='absent').count(),
        })

    # Section-level check-out tiles (ALL sections, for ended/closed events)
    checkout_tiles = []
    if event.status in ('ended', 'closed'):
        for section in all_sections:
            s_logs = logs.filter(student__section=section)
            checkout_tiles.append({
                'name': section.name,
                'year_level': section.year_level,
                'checked_out': s_logs.filter(scanned_out_at__isnull=False).count(),
                'not_checked_out': s_logs.filter(
                    status__in=('present', 'late'),
                    scanned_out_at__isnull=True
                ).count(),
            })

    context = {
        'event':            event,
        'logs':             logs_filtered,
        'page_obj':         page_obj,
        'status_filter':    status_filter,
        'present':          present,
        'late':             late,
        'absent':           absent,
        'total':            total,
        'checked_out':      checked_out,
        'not_checked_out':  not_checked_out,
        'section_tiles':    section_tiles,
        'checkout_tiles':   checkout_tiles,
        'year_filter':      year_filter,
        'year_levels':      year_levels,
    }
    return render(request, 'admin_panel/attendance.html', context)


# ---------------------------------------------------------------------------
# QR Scanner
# ---------------------------------------------------------------------------

@admin_required
def scanner_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'admin_panel/scanner.html', {
        'event': event,
        'is_checkout_mode': event.status == 'ended',
    })


@admin_required
@require_POST
def scan_qr_api(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if event.status == 'pending':
        return JsonResponse({'success': False, 'message': 'Event has not started yet.'})
    if event.status == 'closed':
        return JsonResponse({'success': False, 'message': 'Event is closed. No more scanning allowed.'})

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

    now   = dj_timezone.now()
    admin = get_current_admin(request)

    # --- CHECK-OUT MODE (event ended) ---
    if event.status == 'ended':
        existing = AttendanceLog.objects.filter(student=student, event=event).first()
        if not existing:
            return JsonResponse({'success': False, 'message': f'{student.name} was not checked in for this event.'})
        if existing.status == 'absent':
            return JsonResponse({'success': False, 'message': f'{student.name} was marked absent.'})
        if existing.scanned_out_at:
            return JsonResponse({
                'success': False,
                'already_scanned': True,
                'message': f'{student.name} already checked out at {existing.scanned_out_at.strftime("%I:%M:%S %p")}.',
                'student_name': student.name,
                'student_id':   student.student_id,
                'photo_url':    student.id_photo_path,
                'status':       'checkout',
            })
        existing.scanned_out_at = now
        existing.save(update_fields=['scanned_out_at'])
        return JsonResponse({
            'success':      True,
            'checkout':     True,
            'student_name': student.name,
            'student_id':   student.student_id,
            'section':      student.section.name,
            'photo_url':    student.id_photo_path,
            'status':       'checkout',
            'scanned_at':   now.strftime('%I:%M:%S %p'),
        })

    # --- CHECK-IN MODE (event active) ---
    if event.start_time:
        event_start = dj_timezone.make_aware(datetime.combine(event.date, event.start_time))
        cutoff      = event_start + timedelta(minutes=event.late_cutoff_mins)
        status      = 'present' if now <= cutoff else 'late'
    else:
        status = 'present'

    existing = AttendanceLog.objects.filter(student=student, event=event).first()

    if existing:
        if existing.status in ('present', 'late'):
            return JsonResponse({
                'success':         False,
                'already_scanned': True,
                'message':         f'{student.name} already recorded as {existing.status.upper()}.',
                'student_name':    student.name,
                'student_id':      student.student_id,
                'photo_url':       student.id_photo_path,
                'status':          existing.status,
            })
        # Was pre-marked absent → update to present/late
        existing.status     = status
        existing.scanned_by = admin
        existing.scanned_at = now
        existing.save(update_fields=['status', 'scanned_by', 'scanned_at'])
    else:
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
        'section':      student.section.name,
        'photo_url':    student.id_photo_path,
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

    ws.merge_cells('A1:G1')
    title_cell            = ws['A1']
    title_cell.value      = f'Attendance: {event.name}'
    title_cell.font       = Font(bold=True, size=14)
    title_cell.alignment  = Alignment(horizontal='center')

    ws.merge_cells('A2:G2')
    sub_cell           = ws['A2']
    sub_cell.value     = f'Date: {event.date}  |  Start: {event.start_time.strftime("%I:%M %p") if event.start_time else "N/A"}  |  Late cutoff: {event.late_cutoff_mins} mins  |  Status: {event.status.upper()}'
    sub_cell.alignment = Alignment(horizontal='center')

    headers     = ['Student ID', 'Name', 'Year', 'Section', 'Status', 'Scanned At (In)', 'Scanned Out At']
    header_fill = PatternFill(start_color='1F3864', end_color='1F3864', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)

    for col, header in enumerate(headers, start=1):
        cell           = ws.cell(row=4, column=col, value=header)
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = Alignment(horizontal='center')

    status_colors = {'present': 'C6EFCE', 'late': 'FFEB9C', 'absent': 'FFC7CE'}

    for row_idx, log in enumerate(logs, start=5):
        scanned_at     = log.scanned_at.strftime('%Y-%m-%d %I:%M:%S %p') if log.scanned_at else '—'
        scanned_out_at = log.scanned_out_at.strftime('%Y-%m-%d %I:%M:%S %p') if log.scanned_out_at else '—'
        row_data = [
            log.student.student_id,
            log.student.name,
            log.student.year_level,
            log.student.section.name,
            log.status.upper(),
            scanned_at,
            scanned_out_at,
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

    for col, width in enumerate([15, 25, 8, 15, 12, 25, 25], start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    summary_row = ws.max_row + 2
    ws.cell(row=summary_row, column=1, value='Summary').font = Font(bold=True)
    ws.cell(row=summary_row, column=2, value=f'Present: {logs.filter(status="present").count()}')
    ws.cell(row=summary_row, column=3, value=f'Late: {logs.filter(status="late").count()}')
    ws.cell(row=summary_row, column=4, value=f'Absent: {logs.filter(status="absent").count()}')
    ws.cell(row=summary_row, column=5, value=f'Total: {logs.count()}')
    ws.cell(row=summary_row, column=6, value=f'Checked Out: {logs.filter(scanned_out_at__isnull=False).count()}')

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_name = event.name.replace(' ', '_').replace('/', '-')
    response['Content-Disposition'] = f'attachment; filename="Attendance_{safe_name}_{event.date}.xlsx"'
    wb.save(response)
    return response


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@admin_required
def students_view(request):
    status_filter  = request.GET.get('status', 'all')
    section_filter = request.GET.get('section', 'all')
    
    current_admin = get_current_admin(request)
    admin_role = request.session.get('admin_role', 'vits')
    
    assigned_sections = Section.objects.order_by('year_level', 'name')
    if admin_role == 'representative':
        assigned_sections = assigned_sections.filter(assigned_admins__admin=current_admin)

    students = Student.objects.filter(section__in=assigned_sections).select_related('section').order_by('-created_at')

    if status_filter in ('pending', 'active', 'rejected'):
        students = students.filter(status=status_filter)
    if section_filter != 'all':
        students = students.filter(section_id=section_filter)

    paginator = Paginator(students, 25)
    page_obj  = paginator.get_page(request.GET.get('page'))

    # Bulk approve
    if request.method == 'POST' and request.POST.get('action') == 'bulk_approve':
        selected_ids = request.POST.getlist('student_ids')
        approved_count = 0
        for sid in selected_ids:
            try:
                _bulk_approve_student(request, sid)
                approved_count += 1
            except Exception:
                pass
        log_activity(request, 'BULK_APPROVE', description=f'Bulk approved {approved_count} students')
        messages.success(request, f'{approved_count} student(s) approved.')
        return redirect('admin_panel:students')

    all_sections = assigned_sections
    return render(request, 'admin_panel/students.html', {
        'students':       page_obj,
        'page_obj':       page_obj,
        'status_filter':  status_filter,
        'section_filter': section_filter,
        'all_sections':   all_sections,
    })


def _bulk_approve_student(request, student_id):
    import qrcode
    import os
    from io import BytesIO
    from django.core.files.storage import default_storage
    from django.conf import settings

    student = Student.objects.get(id=student_id)
    if student.status == 'active':
        return
    student.status         = 'active'
    student.rejection_note = ''
    student.save()

    if not QRToken.objects.filter(student=student).exists():
        token_value = secrets.token_urlsafe(32)
        qr_token    = QRToken.objects.create(
            id=uuid.uuid4(), student=student, token=token_value, qr_path=''
        )
    else:
        qr_token = QRToken.objects.get(student=student)

    try:
        qr_img   = qrcode.make(qr_token.token, box_size=10, border=2)
        buf      = BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)
        filename = f'qr_{student.id}.png'
        if default_storage.exists(filename):
            default_storage.delete(filename)
        saved_path       = default_storage.save(filename, buf)
        qr_token.qr_path = default_storage.url(saved_path)
        qr_token.save()
        if student.email:
            from django.core.mail import EmailMessage
            buf.seek(0)
            mail = EmailMessage(
                subject=f'Your CODE-IT QR Code — {student.name}',
                body=(
                    f'Hi {student.name},\n\nYour account has been approved!\n\n'
                    f'Your QR code is attached. Show it at events to record attendance.\n\n'
                    f'Student ID: {student.student_id}\nSection: {student.section}\n\n— CODE-IT'
                ),
                from_email=settings.EMAIL_HOST_USER,
                to=[student.email],
            )
            mail.attach('qr_code.png', buf.getvalue(), 'image/png')
            mail.send(fail_silently=True)
    except Exception:
        pass


@admin_required
@require_POST
def student_approve_view(request, pk):
    student = get_object_or_404(Student, id=pk)

    if student.status == 'active':
        messages.info(request, f'{student.name} is already active.')
        return redirect('admin_panel:students')

    student.status         = 'active'
    student.rejection_note = ''
    student.save()

    qr_token = None
    if not QRToken.objects.filter(student=student).exists():
        token_value = secrets.token_urlsafe(32)
        qr_token    = QRToken.objects.create(
            id=uuid.uuid4(), student=student, token=token_value, qr_path=''
        )
    else:
        qr_token = QRToken.objects.get(student=student)

    import qrcode
    from io import BytesIO
    from django.core.files.storage import default_storage
    from django.conf import settings
    import os

    try:
        qr_img = qrcode.make(qr_token.token, box_size=10, border=2)
        buf    = BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)
        filename = f'qr_{student.id}.png'
        filepath = os.path.join(settings.MEDIA_ROOT, filename)
        if default_storage.exists(filepath):
            default_storage.delete(filepath)
        saved_path       = default_storage.save(filename, buf)
        qr_token.qr_path = default_storage.url(saved_path)
        qr_token.save()
    except Exception as e:
        messages.error(request, f'Failed to save QR Image for {student.name}: {e}')

    if student.email:
        try:
            from django.core.mail import EmailMessage
            buf.seek(0)
            subject = f'Your CODE-IT QR Code — {student.name}'
            body = (
                f'Hi {student.name},\n\nYour account has been approved! 🎉\n\n'
                f'Your QR code is attached to this email. '
                f'Show it at events to record your attendance.\n\n'
                f'Student ID: {student.student_id}\nSection: {student.section}\n\n— CODE-IT Attendance System'
            )
            email = EmailMessage(subject=subject, body=body,
                                 from_email=settings.EMAIL_HOST_USER, to=[student.email])
            email.attach('qr_code.png', buf.getvalue(), 'image/png')
            email.send(fail_silently=False)
            messages.success(request, f'{student.name} approved — QR code emailed to {student.email}.')
        except Exception as e:
            messages.error(request, f'{student.name} approved BUT email failed: {e}')
    else:
        messages.success(request, f'{student.name} approved — no email on file, QR generated only.')

    log_activity(request, 'STUDENT_APPROVED', target=student.name, description=f'Approved student {student.student_id}')
    return redirect('admin_panel:students')


@admin_required
@require_POST
def student_reject_view(request, pk):
    student                = get_object_or_404(Student, id=pk)
    note                   = request.POST.get('rejection_note', '').strip()
    student.status         = 'rejected'
    student.rejection_note = note or 'No reason provided.'
    student.save()
    log_activity(request, 'STUDENT_REJECTED', target=student.name, description=f'Rejected student {student.student_id}: {student.rejection_note}')
    messages.warning(request, f'{student.name} rejected.')
    return redirect('admin_panel:students')


@admin_required
@require_POST
def student_delete_view(request, pk):
    student = get_object_or_404(Student, id=pk)
    name    = student.name
    log_activity(request, 'STUDENT_DELETED', target=name, description=f'Deleted student {student.student_id}')
    student.delete()
    messages.success(request, f'Student "{name}" has been deleted.')
    return redirect('admin_panel:students')


@admin_required
@require_POST
def generate_qr_view(request, pk):
    import qrcode
    import os
    from io import BytesIO
    from django.core.files.storage import default_storage
    from django.conf import settings as django_settings

    student = get_object_or_404(Student, id=pk)

    if student.status != 'active':
        messages.error(request, f'{student.name} must be active to generate a QR code.')
        return redirect('admin_panel:students')

    try:
        qr_token = QRToken.objects.get(student=student)
    except QRToken.DoesNotExist:
        qr_token = QRToken.objects.create(
            id=uuid.uuid4(), student=student, token=secrets.token_urlsafe(32), qr_path=''
        )

    try:
        qr_img   = qrcode.make(qr_token.token, box_size=10, border=2)
        buf      = BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)
        filename = f'qr_{student.id}.png'
        if default_storage.exists(filename):
            default_storage.delete(filename)
        saved_path       = default_storage.save(filename, buf)
        qr_token.qr_path = default_storage.url(saved_path)
        qr_token.save()

        if student.email:
            try:
                from django.core.mail import EmailMessage
                buf.seek(0)
                mail = EmailMessage(
                    subject=f'Your CODE-IT QR Code — {student.name}',
                    body=(
                        f'Hi {student.name},\n\nYour QR code has been generated!\n\n'
                        f'Show it at events to record your attendance.\n\n'
                        f'Student ID: {student.student_id}\nSection: {student.section}\n\n— CODE-IT'
                    ),
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

    log_activity(request, 'QR_GENERATED', target=student.name, description=f'Generated QR for student {student.student_id}')
    return redirect('admin_panel:students')


@admin_required
@require_POST
def revoke_qr_view(request, pk):
    import qrcode
    import os
    from io import BytesIO
    from django.core.files.storage import default_storage
    from django.conf import settings as django_settings

    student = get_object_or_404(Student, id=pk)

    if student.status != 'active':
        messages.error(request, f'{student.name} must be active to revoke QR.')
        return redirect('admin_panel:students')

    # Delete old token
    QRToken.objects.filter(student=student).delete()

    # Create new token
    new_token = secrets.token_urlsafe(32)
    qr_token  = QRToken.objects.create(
        id=uuid.uuid4(), student=student, token=new_token, qr_path=''
    )

    try:
        qr_img   = qrcode.make(qr_token.token, box_size=10, border=2)
        buf      = BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)
        filename = f'qr_{student.id}_rev.png'
        if default_storage.exists(filename):
            default_storage.delete(filename)
        saved_path       = default_storage.save(filename, buf)
        qr_token.qr_path = default_storage.url(saved_path)
        qr_token.save()

        if student.email:
            try:
                from django.core.mail import EmailMessage
                buf.seek(0)
                mail = EmailMessage(
                    subject=f'Your New CODE-IT QR Code — {student.name}',
                    body=(
                        f'Hi {student.name},\n\nYour QR code has been revoked and a new one generated.\n\n'
                        f'Please use the new QR code attached to this email.\n\n'
                        f'Student ID: {student.student_id}\nSection: {student.section}\n\n— CODE-IT'
                    ),
                    from_email=django_settings.EMAIL_HOST_USER,
                    to=[student.email],
                )
                mail.attach('new_qr_code.png', buf.getvalue(), 'image/png')
                mail.send(fail_silently=False)
                messages.success(request, f'QR code revoked and new one emailed to {student.email}.')
            except Exception as e:
                messages.warning(request, f'QR revoked but email failed: {e}')
        else:
            messages.success(request, f'QR code revoked and new one generated for {student.name}.')

    except Exception as e:
        messages.error(request, f'QR revocation failed: {e}')

    log_activity(request, 'QR_REVOKED', target=student.name, description=f'Revoked and regenerated QR for student {student.student_id}')
    return redirect('admin_panel:students')


# ---------------------------------------------------------------------------
# Activity Logs
# ---------------------------------------------------------------------------

@admin_required
def activity_logs_view(request):
    if request.session.get('admin_role') not in ('chairperson', 'vits'):
        messages.error(request, 'You do not have permission to view activity logs.')
        return redirect('admin_panel:dashboard')

    logs = ActivityLog.objects.select_related('admin').order_by('-created_at')

    action_filter = request.GET.get('action', 'all')
    admin_filter  = request.GET.get('admin_id', 'all')
    date_from     = request.GET.get('date_from', '')
    date_to       = request.GET.get('date_to', '')

    if action_filter != 'all':
        logs = logs.filter(action=action_filter)
    if admin_filter != 'all':
        logs = logs.filter(admin_id=admin_filter)
    if date_from:
        try:
            logs = logs.filter(created_at__date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            logs = logs.filter(created_at__date__lte=date_to)
        except Exception:
            pass

    # Clear logs (chairperson only)
    if request.method == 'POST' and request.POST.get('action') == 'clear_logs':
        if request.session.get('admin_role') == 'chairperson':
            ActivityLog.objects.all().delete()
            admin = get_current_admin(request)
            ActivityLog.objects.create(
                id=uuid.uuid4(),
                admin=admin,
                action='LOGS_CLEARED',
                description='Admin cleared all activity logs',
            )
            messages.success(request, 'All activity logs cleared.')
            return redirect('admin_panel:activity_logs')
        else:
            messages.error(request, 'Only the chairperson can clear activity logs.')

    distinct_actions = ActivityLog.objects.values_list('action', flat=True).distinct().order_by('action')
    all_admins       = Admin.objects.filter(is_active=True).order_by('name')

    paginator = Paginator(logs, 25)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_panel/activity_logs.html', {
        'logs':             page_obj,
        'page_obj':         page_obj,
        'action_filter':    action_filter,
        'admin_filter':     admin_filter,
        'date_from':        date_from,
        'date_to':          date_to,
        'distinct_actions': distinct_actions,
        'all_admins':       all_admins,
        'admin_role':       request.session.get('admin_role', 'vits'),
    })
