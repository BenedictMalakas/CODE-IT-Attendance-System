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
from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth.hashers import check_password, make_password
from django.core.paginator import Paginator
from django.core.cache import cache
from django.urls import reverse

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from myapp.models import Admin, AdminSection, Section, Student, Event, QRToken, AttendanceLog, ActivityLog
from myapp.services import auto_update_event_statuses, sorted_sections
from .forms import LoginForm, EventForm


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


def start_admin_session(request, admin):
    request.session.flush()
    request.session['admin_id'] = str(admin.id)
    request.session['admin_name'] = admin.name
    request.session['admin_role'] = admin.role
    request.session['force_password_change'] = admin.force_password_change
    request.session.cycle_key()


def ph_now():
    return dj_timezone.now()


def get_sorted_sections():
    return sorted_sections()


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
            return redirect('student_portal:login')
        admin = get_current_admin(request)
        if not admin or not admin.is_active:
            request.session.flush()
            messages.warning(request, 'Your account is no longer active. Please contact the chairperson.')
            return redirect('student_portal:login')
        request.session['admin_name'] = admin.name
        request.session['admin_role'] = admin.role
        request.session['force_password_change'] = admin.force_password_change
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


def current_admin_role(request):
    admin = get_current_admin(request)
    return admin.role if admin and admin.is_active else None


def chairperson_required(request):
    if current_admin_role(request) != Admin.Role.CHAIRPERSON:
        messages.error(request, 'Only the Chairperson can perform this action.')
        return False
    return True


def admin_can_manage_student(admin, student):
    if not admin or not admin.is_active:
        return False
    if admin.role in (Admin.Role.CHAIRPERSON, Admin.Role.VITS):
        return True
    if admin.role == Admin.Role.REPRESENTATIVE:
        return AdminSection.objects.filter(admin=admin, section=student.section).exists()
    return False


def require_student_permission(request, student):
    admin = get_current_admin(request)
    if admin_can_manage_student(admin, student):
        return True
    messages.error(request, 'You do not have permission to manage that student.')
    return False


def _reauth_session_key(scope):
    return f'admin_reauth_{scope}_until'


def admin_has_recent_reauth(request, scope):
    until = request.session.get(_reauth_session_key(scope))
    try:
        return float(until) > dj_timezone.now().timestamp()
    except (TypeError, ValueError):
        return False


def set_admin_reauth(request, scope, minutes=30):
    expires_at = dj_timezone.now() + timedelta(minutes=minutes)
    request.session[_reauth_session_key(scope)] = expires_at.timestamp()
    clear_reauth_leave_marker(request, scope)


def _reauth_leave_scope_key():
    return 'admin_reauth_left_scope'


def _reauth_leave_until_key():
    return 'admin_reauth_left_until'


def clear_reauth_leave_marker(request, scope=None):
    if scope is None or request.session.get(_reauth_leave_scope_key()) == scope:
        request.session.pop(_reauth_leave_scope_key(), None)
        request.session.pop(_reauth_leave_until_key(), None)


def reauth_expired_after_leaving_scope(request, scope):
    if request.session.get(_reauth_leave_scope_key()) != scope:
        return False
    try:
        deadline = float(request.session.get(_reauth_leave_until_key()))
    except (TypeError, ValueError):
        clear_reauth_leave_marker(request, scope)
        return False
    if deadline > dj_timezone.now().timestamp():
        clear_reauth_leave_marker(request, scope)
        return False
    request.session.pop(_reauth_session_key(scope), None)
    clear_reauth_leave_marker(request, scope)
    return True


def verify_admin_current_password(request, password):
    admin = get_current_admin(request)
    return bool(admin and admin.is_active and verify_password(password or '', admin.password_hash))


def handle_view_reauth(request, scope, redirect_name):
    if request.method == 'POST' and request.POST.get('action') == 'reauth_view':
        if verify_admin_current_password(request, request.POST.get('reauth_password', '')):
            set_admin_reauth(request, scope)
            messages.success(request, 'Access confirmed.')
            return redirect(redirect_name)
        messages.error(request, 'Current password is incorrect.')
    return None


def render_reauth_page(request, scope, title, description):
    return render(request, 'admin_panel/reauth.html', {
        'scope': scope,
        'title': title,
        'description': description,
    })


def require_action_password(request, action_label):
    if verify_admin_current_password(request, request.POST.get('reauth_password', '')):
        return True
    messages.error(request, f'Current password is required to {action_label}.')
    return False


@admin_required
@require_POST
def verify_admin_password_api(request):
    return JsonResponse({
        'ok': verify_admin_current_password(request, request.POST.get('reauth_password', '')),
    })


@admin_required
@require_POST
def mark_reauth_leave_api(request):
    scope = request.POST.get('scope')
    if scope in ('students', 'officers') and admin_has_recent_reauth(request, scope):
        request.session[_reauth_leave_scope_key()] = scope
        request.session[_reauth_leave_until_key()] = (
            dj_timezone.now() + timedelta(seconds=5)
        ).timestamp()
    return JsonResponse({'ok': True})


def redirect_students_management(request):
    next_query = (request.POST.get('next') or '').strip().lstrip('?')
    if next_query:
        return redirect(f'{reverse("admin_panel:students")}?{next_query}')
    return redirect('admin_panel:students')


def section_name_sort_key(section):
    return (-(section.year_level or 0), (section.name or '').lower())


def pagination_window(page_obj, side_count=2):
    paginator = page_obj.paginator
    current = page_obj.number
    pages = []
    previous = None
    for page_number in range(1, paginator.num_pages + 1):
        show_page = (
            page_number == 1
            or page_number == paginator.num_pages
            or abs(page_number - current) <= side_count
        )
        if not show_page:
            continue
        if previous and page_number - previous > 1:
            pages.append(None)
        pages.append(page_number)
        previous = page_number
    return pages


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def chairperson_login_view(request):
    if request.session.get('admin_id'):
        admin = get_current_admin(request)
        if admin and admin.is_active:
            return redirect('admin_panel:dashboard')
        request.session.flush()

    form = LoginForm()
    if request.method == 'POST':
        ip = get_client_ip(request)
        if is_ip_locked(ip):
            messages.error(request, 'Too many failed attempts. Try again after 15 minutes.')
            return render(request, 'admin_panel/chairperson_login.html', {'form': form})

        form = LoginForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']
            try:
                admin = Admin.objects.get(email=email, role=Admin.Role.CHAIRPERSON, is_active=True)
                if not verify_password(password, admin.password_hash):
                    raise Admin.DoesNotExist
                if not admin.password_hash.startswith('pbkdf2_'):
                    admin.password_hash = make_password(password)
                    admin.save(update_fields=['password_hash'])
                clear_login_failures(ip)
                start_admin_session(request, admin)
                return redirect('admin_panel:dashboard')
            except Admin.DoesNotExist:
                messages.error(request, 'Invalid credentials.')
                track_login_failure(ip)

    return render(request, 'admin_panel/chairperson_login.html', {'form': form})


def logout_view(request):
    request.session.flush()
    return redirect('student_portal:login')


def force_password_change_view(request):
    if not request.session.get('admin_id'):
        return redirect('student_portal:login')
    admin = get_current_admin(request)
    if not admin or not admin.is_active:
        request.session.flush()
        messages.warning(request, 'Your account is no longer active. Please contact the chairperson.')
        return redirect('student_portal:login')

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
            admin.password_hash = hash_password(new_pw)
            admin.force_password_change = False
            admin.save(update_fields=['password_hash', 'force_password_change'])
            request.session['admin_name'] = admin.name
            request.session['admin_role'] = admin.role
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
    admin_role = current_admin.role
    assigned_sections = Section.objects.all()

    if admin_role == 'representative':
        assigned_sections = Section.objects.filter(assigned_admins__admin=current_admin)
    
    total_students   = Student.objects.filter(status='active', section__in=assigned_sections).count()
    pending_students = Student.objects.filter(status='pending', section__in=assigned_sections).count()
    total_logs       = AttendanceLog.objects.filter(student__section__in=assigned_sections).count()
    total_sections   = assigned_sections.count()
    total_admins     = Admin.objects.filter(is_active=True).count()

    today        = dj_timezone.localtime(dj_timezone.now()).date()
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

    selected_year = request.GET.get('year')
    if admin_role in (Admin.Role.CHAIRPERSON, Admin.Role.VITS):
        selected_year = selected_year or '1'
    else:
        selected_year = selected_year or 'all'

    section_overview_sections = assigned_sections
    if admin_role in (Admin.Role.CHAIRPERSON, Admin.Role.VITS) and selected_year != 'all':
        try:
            section_overview_sections = section_overview_sections.filter(year_level=int(selected_year))
        except (TypeError, ValueError):
            selected_year = '1'
            section_overview_sections = section_overview_sections.filter(year_level=1)

    dashboard_year_levels = (
        assigned_sections
        .values_list('year_level', flat=True)
        .distinct()
        .order_by('year_level')
    )

    # Build section cards filtered by selected event and dashboard year level.
    section_cards = []
    for section in sorted_sections(section_overview_sections):
        students = Student.objects.filter(section=section)
        if selected_event:
            section_logs = AttendanceLog.objects.filter(student__section=section, event=selected_event)
        else:
            section_logs = AttendanceLog.objects.none()
        present = section_logs.filter(status='present').count()
        late = section_logs.filter(status='late').count()
        absent = section_logs.filter(status='absent').count()
        section_cards.append({
            'id': section.id,
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
        'admin_role':       admin_role,
        'all_events':       all_events,
        'selected_event':   selected_event,
        'section_cards':    section_cards,
        'recent_students':  recent_students,
        'selected_year':    selected_year,
        'dashboard_year_levels': dashboard_year_levels,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@admin_required
def sections_manage_view(request):
    if current_admin_role(request) != Admin.Role.CHAIRPERSON:
        messages.error(request, 'Only the Chairperson can manage sections.')
        return redirect('admin_panel:dashboard')

    import re as _re

    if request.method == 'POST':
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
        'admin_role':     current_admin_role(request),
    })


@admin_required
def delete_section_view(request, pk):
    if current_admin_role(request) != Admin.Role.CHAIRPERSON:
        messages.error(request, 'Only the Chairperson can delete sections.')
        return redirect('admin_panel:dashboard')

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
    if current_admin_role(request) != Admin.Role.CHAIRPERSON:
        messages.error(request, 'Only the Chairperson can manage officer accounts.')
        return redirect('admin_panel:dashboard')

    reauth_response = handle_view_reauth(request, 'officers', 'admin_panel:admins_manage')
    if reauth_response:
        return reauth_response
    if reauth_expired_after_leaving_scope(request, 'officers') or not admin_has_recent_reauth(request, 'officers'):
        return render_reauth_page(
            request,
            'officers',
            'Officers & Representatives',
            'Confirm your password before viewing officer and representative accounts.',
        )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            name  = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            role  = request.POST.get('role', Admin.Role.VITS)
            if role not in (Admin.Role.VITS, Admin.Role.REPRESENTATIVE):
                role = Admin.Role.VITS
            if not name or not email:
                messages.error(request, 'Name and email are required.')
            elif Admin.objects.filter(email__iexact=email).exists():
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
                            if not AdminSection.objects.filter(admin=new_admin, section=section).exists():
                                AdminSection.objects.create(id=uuid.uuid4(), admin=new_admin, section=section)
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
            if not require_action_password(request, 'delete an officer account'):
                return redirect('admin_panel:admins_manage')
            admin_id = request.POST.get('admin_id')
            try:
                admin = Admin.objects.get(id=admin_id)
                if admin.role == Admin.Role.CHAIRPERSON:
                    messages.error(request, 'Chairperson account cannot be deleted here.')
                else:
                    name = admin.name
                    email = admin.email
                    role = admin.role
                    admin.delete()
                    log_activity(request, 'ADMIN_DELETED', target=name, description=f'Deleted {role} account {email}')
                    messages.success(request, f'{name} removed.')
            except Admin.DoesNotExist:
                messages.error(request, 'Officer account not found.')
        return redirect('admin_panel:admins_manage')

    admins = Admin.objects.order_by('name')
    all_sections = sorted_sections(Section.objects.all())

    # Build sections map per admin
    admins_with_sections = []
    for admin in admins:
        assigned = AdminSection.objects.filter(admin=admin).select_related('section')
        admins_with_sections.append({
            'admin': admin,
            'sections': [section.name for section in sorted_sections([a.section for a in assigned])],
        })
    paginator = Paginator(admins_with_sections, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_panel/admins_manage.html', {
        'admins': page_obj,
        'admins_with_sections': page_obj,
        'page_obj': page_obj,
        'pagination_pages': pagination_window(page_obj),
        'total_admins': admins.count(),
        'admin_role': current_admin_role(request),
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
        'admin_role': current_admin_role(request),
    })


@admin_required
def event_create_view(request):
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
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

            # Handle the combined expected_year_section dropdown
            choice = form.cleaned_data.get('expected_year_section', '')
            if choice.startswith('year_'):
                year_level = int(choice.replace('year_', ''))
                event.expected_sections.set(Section.objects.filter(year_level=year_level))
            elif choice.startswith('section_'):
                section_id = choice.replace('section_', '')
                event.expected_sections.set(Section.objects.filter(id=section_id))
            else:
                event.expected_sections.clear()  # Open to all

            log_activity(request, 'EVENT_CREATED', target=event.name, description=f'Created event "{event.name}" on {event.date}')
            messages.success(request, f'Event "{event.name}" created successfully.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Create'})


@admin_required
def event_edit_view(request, pk):
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
        messages.error(request, 'Representatives do not have permission to edit events.')
        return redirect('admin_panel:events')
    event = get_object_or_404(Event, id=pk)
    form  = EventForm(instance=event)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            ev = form.save(commit=False)
            ev.save()
            
            # Handle the combined expected_year_section dropdown
            choice = form.cleaned_data.get('expected_year_section', '')
            if choice.startswith('year_'):
                year_level = int(choice.replace('year_', ''))
                ev.expected_sections.set(Section.objects.filter(year_level=year_level))
            elif choice.startswith('section_'):
                section_id = choice.replace('section_', '')
                ev.expected_sections.set(Section.objects.filter(id=section_id))
            else:
                ev.expected_sections.clear()  # Open to all

            log_activity(request, 'EVENT_EDITED', target=event.name, description=f'Edited event "{event.name}"')
            messages.success(request, f'Event "{event.name}" updated.')
            return redirect('admin_panel:events')
    return render(request, 'admin_panel/event_form.html', {'form': form, 'action': 'Edit', 'event': event})


@admin_required
@require_POST
def event_delete_view(request, pk):
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
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
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
        messages.error(request, 'Representatives do not have permission to start events.')
        return redirect('admin_panel:events')
    event = get_object_or_404(Event, id=pk)
    if event.status != 'pending':
        messages.error(request, f'Only pending events can be started.')
        return redirect('admin_panel:events')
    event.status = 'active'
    if not event.start_time:
        event.start_time = dj_timezone.localtime(dj_timezone.now()).time()
    event.save(update_fields=['status', 'start_time'])
    log_activity(request, 'EVENT_STARTED', target=event.name, description=f'Started event "{event.name}"')
    messages.success(request, f'Event "{event.name}" started.')
    return redirect('admin_panel:events')


@admin_required
@require_POST
def end_event_view(request, pk):
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
        messages.error(request, 'Representatives do not have permission to end events.')
        return redirect('admin_panel:events')
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
    if current_admin_role(request) != Admin.Role.CHAIRPERSON:
        messages.error(request, 'Only the chairperson can close events.')
        return redirect('admin_panel:events')
    if event.status != 'ended':
        messages.error(request, 'Only ended events can be closed.')
        return redirect('admin_panel:events')
    event.status = 'closed'
    event.save(update_fields=['status'])

    # Auto-mark absent: create "absent" logs for expected students with no record
    expected_sections = event.expected_sections.all()
    if expected_sections.exists():
        expected_students = Student.objects.filter(status='active', section__in=expected_sections)
    else:
        # Event was open to all — mark ALL active students
        expected_students = Student.objects.filter(status='active')

    already_logged_ids = set(
        AttendanceLog.objects.filter(event=event).values_list('student_id', flat=True)
    )
    absent_created = 0
    for student in expected_students:
        if student.id not in already_logged_ids:
            AttendanceLog.objects.create(
                id=uuid.uuid4(),
                student=student,
                event=event,
                scanned_by=None,
                status='absent',
                scanned_at=None,
            )
            absent_created += 1

    log_activity(request, 'EVENT_CLOSED', target=event.name, description=f'Closed event "{event.name}" — {absent_created} student(s) marked absent')
    messages.success(request, f'Event "{event.name}" closed. {absent_created} student(s) marked absent. Final comparison is now available.')
    return redirect('admin_panel:events')


@admin_required
@require_POST
def extend_grace_event_view(request, pk):
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
        messages.error(request, 'Representatives do not have permission to extend grace periods.')
        return redirect('admin_panel:events')
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
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
        messages.error(request, 'Representatives do not have permission to finalize events.')
        return redirect('admin_panel:events')
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
    if current_admin_role(request) == Admin.Role.REPRESENTATIVE:
        messages.error(request, 'Representatives do not have permission to edit expected students.')
        return redirect('admin_panel:events')
    event    = get_object_or_404(Event, id=event_id)
    
    expected_sections = event.expected_sections.all()
    if expected_sections.exists():
        students = Student.objects.filter(status='active', section__in=expected_sections).order_by('last_name', 'first_name')
    else:
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

    # Year filter for section tiles — scoped to expected sections
    year_filter = request.GET.get('year', 'all')
    expected_sections = event.expected_sections.all()
    if expected_sections.exists():
        # Event is restricted — only show expected sections
        all_sections_qs = expected_sections.all()
        year_levels = all_sections_qs.values_list('year_level', flat=True).distinct().order_by('year_level')
    else:
        # Event is open to everyone — show all sections
        all_sections_qs = Section.objects.all()
        year_levels = Section.objects.values_list('year_level', flat=True).distinct().order_by('year_level')

    if year_filter and year_filter != 'all':
        try:
            all_sections_qs = all_sections_qs.filter(year_level=int(year_filter))
        except (ValueError, TypeError):
            pass
    all_sections = sorted_sections(all_sections_qs)

    # Section-level check-in tiles
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


def resolve_scan_student(scan_value):
    qr_token = (
        QRToken.objects
        .select_related('student', 'student__section')
        .filter(token=scan_value)
        .first()
    )
    if qr_token:
        return qr_token.student, 'qr'

    student = (
        Student.objects
        .select_related('section')
        .filter(student_id__iexact=scan_value)
        .first()
    )
    if student:
        return student, 'student_id'

    return None, None


def student_is_expected_for_event(student, event):
    expected_sections = event.expected_sections.all()
    if not expected_sections.exists():
        return True
    return expected_sections.filter(id=student.section_id).exists()


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

    student, scan_type = resolve_scan_student(token)
    if not student:
        return JsonResponse({'success': False, 'message': 'Unrecognized QR token or Student ID.'})

    if student.status != 'active':
        return JsonResponse({'success': False, 'message': f'Student "{student.name}" is not active.'})
    if not student_is_expected_for_event(student, event):
        return JsonResponse({'success': False, 'message': f'{student.name} is not expected for this event.'})

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

    with transaction.atomic():
        existing = (
            AttendanceLog.objects
            .select_for_update()
            .filter(student=student, event=event)
            .first()
        )

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
            # Was pre-marked absent, so update the existing row.
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
        'scan_type':    scan_type,
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

def export_status_for_log(log):
    if log.status == AttendanceLog.Status.ABSENT:
        return 'ABSENT'
    if not log.scanned_at:
        return 'NO CHECK-IN'
    if not log.scanned_out_at:
        return 'NO CHECK-OUT'
    return log.status.upper()


@admin_required
def export_attendance_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    logs  = (
        AttendanceLog.objects
        .filter(event=event)
        .select_related('student', 'student__section', 'scanned_by')
        .order_by('student__section__year_level', 'student__section__name', 'student__last_name', 'student__first_name')
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

    status_colors = {
        'PRESENT': 'C6EFCE',
        'LATE': 'FFEB9C',
        'ABSENT': 'FFC7CE',
        'NO CHECK-OUT': 'FCE4D6',
        'NO CHECK-IN': 'FCE4D6',
    }

    for row_idx, log in enumerate(logs, start=5):
        scanned_at     = log.scanned_at.strftime('%Y-%m-%d %I:%M:%S %p') if log.scanned_at else '—'
        scanned_out_at = log.scanned_out_at.strftime('%Y-%m-%d %I:%M:%S %p') if log.scanned_out_at else '—'
        export_status  = export_status_for_log(log)
        row_data = [
            log.student.student_id,
            log.student.name,
            log.student.year_level,
            log.student.section.name,
            export_status,
            scanned_at,
            scanned_out_at,
        ]
        row_fill = PatternFill(
            start_color=status_colors.get(export_status, 'FFFFFF'),
            end_color=status_colors.get(export_status, 'FFFFFF'),
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
    present_count = sum(1 for log in logs if export_status_for_log(log) == 'PRESENT')
    late_count = sum(1 for log in logs if export_status_for_log(log) == 'LATE')
    no_checkout_count = sum(1 for log in logs if export_status_for_log(log) == 'NO CHECK-OUT')
    ws.cell(row=summary_row, column=2, value=f'Present: {present_count}')
    ws.cell(row=summary_row, column=3, value=f'Late: {late_count}')
    ws.cell(row=summary_row, column=4, value=f'Absent: {logs.filter(status="absent").count()}')
    ws.cell(row=summary_row, column=5, value=f'Total: {logs.count()}')
    ws.cell(row=summary_row, column=6, value=f'No Check-Out: {no_checkout_count}')

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

class StudentApprovalError(Exception):
    pass


def _storage_name_from_url(path_or_url):
    if not path_or_url:
        return ''
    media_url = '/media/'
    if path_or_url.startswith(media_url):
        return path_or_url[len(media_url):]
    return path_or_url.lstrip('/')


def _delete_storage_file(path_or_url):
    if not path_or_url:
        return
    from django.core.files.storage import default_storage

    storage_name = _storage_name_from_url(path_or_url)
    try:
        if storage_name and default_storage.exists(storage_name):
            default_storage.delete(storage_name)
    except Exception:
        pass


def _build_and_save_qr(student, token_value, label=''):
    import qrcode
    from io import BytesIO
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    qr_img = qrcode.make(token_value, box_size=10, border=2)
    buf = BytesIO()
    qr_img.save(buf, format='PNG')
    qr_bytes = buf.getvalue()
    suffix = f'_{label}' if label else ''
    filename = f'qr_{student.id}{suffix}_{secrets.token_urlsafe(8)}.png'
    saved_path = default_storage.save(filename, ContentFile(qr_bytes))
    return default_storage.url(saved_path), qr_bytes


def _send_student_qr_email(student, subject, body, attachment_name, qr_bytes):
    if not student.email:
        return
    from django.conf import settings
    from django.core.mail import EmailMessage

    mail = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[student.email],
    )
    mail.attach(attachment_name, qr_bytes, 'image/png')
    mail.send(fail_silently=False)


def approve_student_with_qr(student):
    if student.status == Student.Status.ACTIVE:
        return 'already_active'

    existing_token = QRToken.objects.filter(student=student).first()
    token_value = existing_token.token if existing_token else secrets.token_urlsafe(32)
    qr_path = ''
    try:
        qr_path, qr_bytes = _build_and_save_qr(student, token_value)
        with transaction.atomic():
            QRToken.objects.update_or_create(
                student=student,
                defaults={'token': token_value, 'qr_path': qr_path},
            )
            if student.email:
                _send_student_qr_email(
                    student,
                    f'Your CODE-IT QR Code - {student.name}',
                    (
                        f'Hi {student.name},\n\n'
                        f'Your account has been approved.\n\n'
                        f'Your QR code is attached. Show it at events to record attendance.\n\n'
                        f'Student ID: {student.student_id}\nSection: {student.section}\n\n'
                        f'- CODE-IT Attendance System'
                    ),
                    'qr_code.png',
                    qr_bytes,
                )
            student.status = Student.Status.ACTIVE
            student.rejection_note = ''
            student.save(update_fields=['status', 'rejection_note'])
    except Exception as exc:
        _delete_storage_file(qr_path)
        raise StudentApprovalError(str(exc)) from exc

    if existing_token and existing_token.qr_path != qr_path:
        _delete_storage_file(existing_token.qr_path)
    return 'approved'


def reissue_student_qr(student):
    existing_token = QRToken.objects.filter(student=student).first()
    token_value = secrets.token_urlsafe(32)
    qr_path = ''
    try:
        qr_path, qr_bytes = _build_and_save_qr(student, token_value, 'rev')
        with transaction.atomic():
            QRToken.objects.update_or_create(
                student=student,
                defaults={'token': token_value, 'qr_path': qr_path},
            )
            if student.email:
                body = (
                    f'Hi {student.name},\n\n'
                    f'Your QR code has been revoked and replaced.\n\n'
                    f'Please use the attached QR code at events to record attendance.\n\n'
                    f'Student ID: {student.student_id}\nSection: {student.section}\n\n'
                    f'- CODE-IT Attendance System'
                )
                _send_student_qr_email(
                    student,
                    f'Your New CODE-IT QR Code - {student.name}',
                    body,
                    'new_qr_code.png',
                    qr_bytes,
                )
    except Exception as exc:
        _delete_storage_file(qr_path)
        raise StudentApprovalError(str(exc)) from exc

    if existing_token and existing_token.qr_path != qr_path:
        _delete_storage_file(existing_token.qr_path)
    return qr_path


@admin_required
def students_view(request):
    reauth_response = handle_view_reauth(request, 'students', 'admin_panel:students')
    if reauth_response:
        return reauth_response
    if reauth_expired_after_leaving_scope(request, 'students') or not admin_has_recent_reauth(request, 'students'):
        return render_reauth_page(
            request,
            'students',
            'Student Management',
            'Confirm your password before viewing student names, IDs, sections, and account actions.',
        )

    status_filter = request.GET.get('status', 'all')
    if status_filter not in ('all', 'pending', 'active', 'rejected'):
        status_filter = 'all'
    year_filter = request.GET.get('year', 'all')
    section_filter = request.GET.get('section', 'all')
    
    current_admin = get_current_admin(request)
    admin_role = current_admin.role
    
    assigned_sections = Section.objects.order_by('-year_level', 'name')
    if admin_role == Admin.Role.REPRESENTATIVE:
        assigned_sections = assigned_sections.filter(assigned_admins__admin=current_admin).distinct()
    assigned_sections = list(assigned_sections)

    year_levels = sorted(
        {section.year_level for section in assigned_sections if section.year_level},
        reverse=True,
    )
    selected_year = None
    if year_filter != 'all':
        try:
            selected_year = int(year_filter)
        except (TypeError, ValueError):
            year_filter = 'all'
        else:
            if selected_year not in year_levels:
                year_filter = 'all'
                selected_year = None

    sections_for_dropdown = assigned_sections
    if selected_year:
        sections_for_dropdown = [
            section for section in assigned_sections if section.year_level == selected_year
        ]
        if section_filter != 'all' and not any(str(section.id) == section_filter for section in sections_for_dropdown):
            section_filter = 'all'

    students = Student.objects.filter(section__in=assigned_sections).select_related('section')

    if status_filter != 'all':
        students = students.filter(status=status_filter)
    if selected_year:
        students = students.filter(section__year_level=selected_year)
    if section_filter != 'all':
        students = students.filter(section_id=section_filter)
    students = students.order_by('-section__year_level', 'section__name', 'last_name', 'first_name', 'student_id')

    paginator = Paginator(students, 10)
    page_obj  = paginator.get_page(request.GET.get('page'))

    # Bulk approve
    if request.method == 'POST' and request.POST.get('action') == 'bulk_approve':
        selected_ids = request.POST.getlist('student_ids')
        approved_count = 0
        failures = []
        for sid in selected_ids:
            try:
                student = Student.objects.select_related('section').get(id=sid)
                if not admin_can_manage_student(current_admin, student):
                    failures.append('Permission denied for one selected student.')
                    continue
                result = approve_student_with_qr(student)
                if result == 'approved':
                    approved_count += 1
            except Student.DoesNotExist:
                failures.append('One selected student was not found.')
            except StudentApprovalError as exc:
                failures.append(str(exc))
            except Exception as exc:
                failures.append(str(exc))
        if approved_count:
            log_activity(request, 'BULK_APPROVE', description=f'Bulk approved {approved_count} students')
            messages.success(request, f'{approved_count} student(s) approved.')
        if failures:
            messages.error(request, f'{len(failures)} student(s) were not approved: {"; ".join(failures[:3])}')
        if not approved_count and not failures:
            messages.info(request, 'No students were selected for approval.')
        return redirect_students_management(request)

    all_sections = sorted(assigned_sections, key=section_name_sort_key)
    sections_for_dropdown = sorted(sections_for_dropdown, key=section_name_sort_key)
    return render(request, 'admin_panel/students.html', {
        'students':       page_obj,
        'page_obj':       page_obj,
        'status_filter':  status_filter,
        'year_filter':    year_filter,
        'section_filter': section_filter,
        'all_sections':   all_sections,
        'section_options': sections_for_dropdown,
        'year_levels':    year_levels,
        'current_query':  request.GET.urlencode(),
        'pagination_pages': pagination_window(page_obj),
    })


def _bulk_approve_student(request, student_id):
    student = Student.objects.select_related('section').get(id=student_id)
    if not admin_can_manage_student(get_current_admin(request), student):
        raise StudentApprovalError('Permission denied.')
    return approve_student_with_qr(student)


@admin_required
@require_POST
def student_approve_view(request, pk):
    student = get_object_or_404(Student.objects.select_related('section'), id=pk)
    if not require_student_permission(request, student):
        return redirect_students_management(request)

    if student.status == 'active':
        messages.info(request, f'{student.name} is already active.')
        return redirect_students_management(request)

    try:
        approve_student_with_qr(student)
    except StudentApprovalError as exc:
        messages.error(request, f'{student.name} was not approved: {exc}')
        return redirect_students_management(request)

    log_activity(request, 'STUDENT_APPROVED', target=student.name, description=f'Approved student {student.student_id}')
    if student.email:
        messages.success(request, f'{student.name} approved and QR code emailed to {student.email}.')
    else:
        messages.success(request, f'{student.name} approved and QR code generated.')
    return redirect_students_management(request)


@admin_required
@require_POST
def student_reject_view(request, pk):
    student                = get_object_or_404(Student.objects.select_related('section'), id=pk)
    if not require_student_permission(request, student):
        return redirect_students_management(request)
    note                   = request.POST.get('rejection_note', '').strip()
    student.status         = 'rejected'
    student.rejection_note = note or 'No reason provided.'
    student.save()
    log_activity(request, 'STUDENT_REJECTED', target=student.name, description=f'Rejected student {student.student_id}: {student.rejection_note}')
    messages.warning(request, f'{student.name} rejected.')
    return redirect_students_management(request)


@admin_required
@require_POST
def student_delete_view(request, pk):
    student = get_object_or_404(Student.objects.select_related('section'), id=pk)
    if not require_student_permission(request, student):
        return redirect_students_management(request)
    if not require_action_password(request, 'delete a student account'):
        return redirect_students_management(request)
    name    = student.name
    student_id = student.student_id
    student.delete()
    log_activity(request, 'STUDENT_DELETED', target=name, description=f'Deleted student {student_id}')
    messages.success(request, f'Student "{name}" has been deleted.')
    return redirect_students_management(request)


@admin_required
@require_POST
def revoke_qr_view(request, pk):
    student = get_object_or_404(Student.objects.select_related('section'), id=pk)
    if not require_student_permission(request, student):
        return redirect_students_management(request)
    if not require_action_password(request, 'renew a student QR code'):
        return redirect_students_management(request)

    if student.status != 'active':
        messages.error(request, f'{student.name} must be active to revoke QR.')
        return redirect_students_management(request)

    try:
        reissue_student_qr(student)
    except StudentApprovalError as exc:
        messages.error(request, f'QR revocation failed. Existing QR token was kept active: {exc}')
        return redirect_students_management(request)

    log_activity(request, 'QR_REVOKED', target=student.name, description=f'Revoked and regenerated QR for student {student.student_id}')
    if student.email:
        messages.success(request, f'QR code revoked and new one emailed to {student.email}.')
    else:
        messages.success(request, f'QR code revoked and new one generated for {student.name}.')
    return redirect_students_management(request)


# ---------------------------------------------------------------------------
# Activity Logs
# ---------------------------------------------------------------------------

@admin_required
def activity_logs_view(request):
    if current_admin_role(request) not in (Admin.Role.CHAIRPERSON, Admin.Role.VITS):
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
        if current_admin_role(request) == Admin.Role.CHAIRPERSON:
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
        'admin_role':       current_admin_role(request),
    })
