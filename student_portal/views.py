import uuid
from functools import wraps

from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone as dj_timezone
from django.contrib.auth.hashers import make_password

from myapp.models import Student, Event, QRToken, AttendanceLog, Section
from myapp.utils import get_client_ip, is_ip_locked, track_login_failure, clear_login_failures, verify_password
from .forms import StudentLoginForm, StudentRegisterForm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def build_pagination_query(request):
    query = request.GET.copy()
    query.pop('page', None)
    return query.urlencode()


def student_required(view_func):
    """Redirect to login if there is no active student session."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('student_id'):
            messages.warning(request, 'Your session has expired. Please log in again.')
            return redirect('student_portal:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_current_student(request):
    sid = request.session.get('student_id')
    if sid:
        try:
            return Student.objects.select_related('section').get(id=sid)
        except Student.DoesNotExist:
            pass
    return None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    # Verify student exists in DB before redirecting to dashboard
    if get_current_student(request):
        return redirect('student_portal:dashboard')
    elif request.session.get('student_id'):
        # Only clear student keys, don't flush entire session (protects admin sessions)
        for key in ['student_id', 'student_name']:
            request.session.pop(key, None)
        request.session.cycle_key()

    ip = get_client_ip(request)
    if is_ip_locked(ip):
        messages.error(request, 'Too many failed attempts. Try again after 15 minutes.')
        return render(request, 'student_portal/login.html', {'form': StudentLoginForm()})

    form = StudentLoginForm()
    if request.method == 'POST':
        form = StudentLoginForm(request.POST)
        if form.is_valid():
            student_id_val = form.cleaned_data['student_id']
            password       = form.cleaned_data['password']
            
            try:
                student = Student.objects.get(student_id=student_id_val)
                if verify_password(password, student.password_hash):
                    clear_login_failures(ip)
                    
                    # Transparently upgrade legacy hash
                    if not student.password_hash.startswith('pbkdf2_'):
                        student.password_hash = make_password(password)
                        student.save(update_fields=['password_hash'])

                    if student.status == 'pending':
                        messages.warning(request, 'Your account is still pending approval.')
                    elif student.status == 'rejected':
                        note = student.rejection_note or 'No reason provided.'
                        messages.error(request, f'Your registration was rejected: {note}')
                    else:
                        request.session['student_id']   = str(student.id)
                        request.session['student_name'] = student.name
                        request.session.cycle_key()
                        return redirect('student_portal:dashboard')
                else:
                    track_login_failure(ip)
                    messages.error(request, 'Invalid Student ID or password.')
            except Student.DoesNotExist:
                track_login_failure(ip)
                messages.error(request, 'Invalid Student ID or password.')

    return render(request, 'student_portal/login.html', {'form': form})


def register_view(request):
    if request.session.get('student_id'):
        return redirect('student_portal:dashboard')

    from myapp.utils import get_sorted_sections
    sections = get_sorted_sections()
    form = StudentRegisterForm()
    if request.method == 'POST':
        form = StudentRegisterForm(request.POST)
        # Re-enable section field for validation (it was disabled in HTML)
        form.fields['section'].widget.attrs.pop('disabled', None)
        if form.is_valid():
            sid = form.cleaned_data['student_id']
            section_id = form.cleaned_data['section']
            year_level = int(form.cleaned_data['year_level'])

            if Student.objects.filter(student_id=sid).exists():
                messages.error(request, 'A student with that ID already exists.')
            else:
                try:
                    section = Section.objects.get(id=section_id)
                except Section.DoesNotExist:
                    messages.error(request, 'Invalid section selected.')
                    return render(request, 'student_portal/register.html', {'form': form, 'sections': sections})

                # Handle ID photo upload
                id_photo_path = ''
                if 'id_photo' in request.FILES:
                    import os
                    from django.conf import settings
                    from django.core.files.storage import default_storage

                    photo = request.FILES['id_photo']
                    ext = photo.name.split('.')[-1].lower()
                    
                    if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                        messages.error(request, 'Invalid file type. Only PNG, JPG, and WebP are allowed.')
                        return render(request, 'student_portal/register.html', {'form': form, 'sections': sections})

                    safe_id = sid.replace('-', '_')
                    filename = f"id_photos/id_{safe_id}.{ext}"

                    # Save using storage system (handles paths and permissions automatically)
                    if default_storage.exists(filename):
                        default_storage.delete(filename)
                        
                    saved_path = default_storage.save(filename, photo)
                    id_photo_path = f'/media/{saved_path}'

                Student.objects.create(
                    id=uuid.uuid4(),
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    student_id=sid,
                    section=section,
                    year_level=year_level,
                    email=form.cleaned_data['email'],
                    password_hash=make_password(form.cleaned_data['password']),
                    id_photo_path=id_photo_path,
                    status='pending',
                    rejection_note='',
                )
                messages.success(
                    request,
                    'Registration submitted! Please wait for admin approval before logging in.'
                )
                return redirect('student_portal:login')

    return render(request, 'student_portal/register.html', {'form': form, 'sections': sections})


def logout_view(request):
    request.session.flush()
    return redirect('student_portal:login')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@student_required
def dashboard_view(request):
    student = get_current_student(request)
    if not student:
        return redirect('student_portal:login')

    today  = dj_timezone.now().date()
    logs   = AttendanceLog.objects.filter(student=student).select_related('event')
    events = Event.objects.filter(date__gte=today, status='active').order_by('date', 'start_time')[:5]

    total_present = logs.filter(status='present').count()
    total_late    = logs.filter(status='late').count()
    total_absent  = logs.filter(status='absent').count()
    qr_token = QRToken.objects.filter(student=student).first()

    context = {
        'student':       student,
        'qr_token':      qr_token,
        'upcoming_events': events,
        'total_present': total_present,
        'total_late':    total_late,
        'total_absent':  total_absent,
        'total_records': logs.count(),
    }
    return render(request, 'student_portal/dashboard.html', context)


# ---------------------------------------------------------------------------
# My QR
# ---------------------------------------------------------------------------

@student_required
def my_qr_view(request):
    student = get_current_student(request)
    if not student:
        return redirect('student_portal:login')

    qr_token = None
    try:
        qr_token = QRToken.objects.get(student=student)
    except QRToken.DoesNotExist:
        pass

    return render(request, 'student_portal/my_qr.html', {
        'student':  student,
        'qr_token': qr_token,
    })


# ---------------------------------------------------------------------------
# My Attendance
# ---------------------------------------------------------------------------

@student_required
def attendance_view(request):
    student = get_current_student(request)
    if not student:
        return redirect('student_portal:login')

    logs = (
        AttendanceLog.objects
        .filter(student=student)
        .select_related('event')
        .order_by('-event__date', '-scanned_at')
    )
    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'student_portal/attendance.html', {
        'student': student,
        'logs':    page_obj,
        'page_obj': page_obj,
        'present': logs.filter(status='present').count(),
        'late':    logs.filter(status='late').count(),
        'absent':  logs.filter(status='absent').count(),
        'pagination_query': build_pagination_query(request),
    })


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@student_required
def profile_view(request):
    student = get_current_student(request)
    if not student:
        return redirect('student_portal:login')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # Handle profile picture upload
        if action == 'upload_photo' and 'profile_picture' in request.FILES:
            import os
            import time
            from django.conf import settings
            from django.core.files.storage import default_storage

            pic = request.FILES['profile_picture']
            ext = pic.name.split('.')[-1].lower()

            if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                messages.error(request, 'Invalid file type. Only PNG, JPG, and WebP are allowed.')
                return redirect('student_portal:profile')

            # Cache busting: add timestamp to filename
            timestamp = int(time.time())
            # Use id_photos subdirectory for all profile photos
            filename = f"id_photos/profile_{student.id}_{timestamp}.{ext}"

            # Only attempt cleanup if on a filesystem that supports it, otherwise ignore
            try:
                if default_storage.exists(filename):
                    default_storage.delete(filename)
            except Exception:
                pass

            saved_path = default_storage.save(filename, pic)
            # Ensure path starts with /media/ for consistent loading
            student.id_photo_path = f'/media/{saved_path}'
            student.save()
            messages.success(request, 'Profile picture updated successfully.')
            return redirect('student_portal:profile')

        # Handle password change
        if action == 'change_password':
            import re
            new_pw  = request.POST.get('new_password', '').strip()
            confirm = request.POST.get('confirm_password', '').strip()
            if not new_pw:
                messages.error(request, 'Please enter a new password.')
            elif len(new_pw) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
            elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_pw):
                messages.error(request, 'Password must contain at least one special character.')
            elif new_pw != confirm:
                messages.error(request, 'Passwords do not match.')
            else:
                student.password_hash = make_password(new_pw)
                student.save()
                messages.success(request, 'Password updated successfully.')
                return redirect('student_portal:profile')

    return render(request, 'student_portal/profile.html', {'student': student})
