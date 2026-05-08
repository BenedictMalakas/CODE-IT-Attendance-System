import hashlib
import uuid
import re
from functools import wraps

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.db.models import Q
from django.contrib import messages
from django.utils import timezone as dj_timezone
from django.contrib.auth.hashers import check_password, make_password
from django.core.paginator import Paginator
from django.core.cache import cache

from myapp.models import Student, Section, Event, QRToken, AttendanceLog
from .forms import StudentLoginForm, StudentRegisterForm
from .file_security import validate_upload


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
    key     = f'login_attempts_{ip}'
    current = cache.get(key, 0)
    cache.set(key, current + 1, timeout=900)


def clear_login_failures(ip):
    cache.delete(f'login_attempts_{ip}')


def student_required(view_func):
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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    if request.session.get('student_id'):
        return redirect('student_portal:dashboard')

    form = StudentLoginForm()
    if request.method == 'POST':
        ip = get_client_ip(request)
        if is_ip_locked(ip):
            messages.error(request, 'Too many failed attempts. Try again after 15 minutes.')
            return render(request, 'student_portal/login.html', {'form': form})

        form = StudentLoginForm(request.POST)
        if form.is_valid():
            student_id_val = form.cleaned_data['student_id']
            password       = form.cleaned_data['password']
            try:
                student = Student.objects.get(student_id=student_id_val)
                if not verify_password(password, student.password_hash):
                    raise Student.DoesNotExist
                # Hash migration
                if student.password_hash and not student.password_hash.startswith('pbkdf2_'):
                    student.password_hash = make_password(password)
                    student.save(update_fields=['password_hash'])
                if student.status == 'pending':
                    messages.warning(request, 'Your account is still pending approval.')
                elif student.status == 'rejected':
                    note = student.rejection_note or 'No reason provided.'
                    messages.error(request, f'Your registration was rejected: {note}')
                else:
                    clear_login_failures(ip)
                    request.session['student_id']   = str(student.id)
                    request.session['student_name'] = student.name
                    request.session.cycle_key()
                    return redirect('student_portal:dashboard')
            except Student.DoesNotExist:
                messages.error(request, 'Invalid Student ID or password.')
                track_login_failure(ip)

    return render(request, 'student_portal/login.html', {'form': form})


def register_view(request):
    if request.session.get('student_id'):
        return redirect('student_portal:dashboard')

    sections = get_sorted_sections()
    form     = StudentRegisterForm()

    if request.method == 'POST':
        form = StudentRegisterForm(request.POST, request.FILES)
        # Re-enable section field before validation
        form.fields['section'].disabled = False
        if form.is_valid():
            sid = form.cleaned_data['student_id']
            if Student.objects.filter(student_id=sid).exists():
                messages.error(request, 'A student with that ID already exists.')
            else:
                section = form.cleaned_data['section']

                # Handle optional ID photo upload
                id_photo_path = ''
                if 'id_photo' in request.FILES:
                    photo = request.FILES['id_photo']
                    is_valid, error_msg = validate_upload(photo)
                    if not is_valid:
                        messages.error(request, error_msg)
                        return render(request, 'student_portal/register.html', {'form': form, 'sections': sections})

                    import os
                    from django.core.files.storage import default_storage
                    ext      = os.path.splitext(photo.name)[1].lower()
                    safe_id  = sid.replace('-', '_')
                    filename = f'id_photos/id_{safe_id}{ext}'
                    if default_storage.exists(filename):
                        default_storage.delete(filename)
                    saved_path    = default_storage.save(filename, photo)
                    id_photo_path = f'/media/{saved_path}'

                Student.objects.create(
                    id=uuid.uuid4(),
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    student_id=sid,
                    section=section,
                    year_level=section.year_level,
                    email=form.cleaned_data['email'],
                    password_hash=hash_password(form.cleaned_data['password']),
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
    events = Event.objects.filter(
        date__gte=today, status='active'
    ).filter(
        Q(expected_sections=student.section) | Q(expected_sections__isnull=True)
    ).distinct().order_by('date', 'start_time')[:5]

    total_present = logs.filter(status='present').count()
    total_late    = logs.filter(status='late').count()
    total_absent  = logs.filter(status='absent').count()

    qr_token = None
    try:
        qr_token = QRToken.objects.get(student=student)
    except QRToken.DoesNotExist:
        pass

    context = {
        'student':         student,
        'qr_token':        qr_token,
        'upcoming_events': events,
        'total_present':   total_present,
        'total_late':      total_late,
        'total_absent':    total_absent,
        'total_records':   logs.count(),
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


@student_required
def download_qr_view(request):
    """Serve the QR code PNG as a proper file download."""
    student = get_current_student(request)
    if not student:
        return redirect('student_portal:login')

    try:
        qr_token = QRToken.objects.get(student=student)
    except QRToken.DoesNotExist:
        messages.error(request, 'No QR code found.')
        return redirect('student_portal:dashboard')

    if not qr_token.qr_path:
        messages.error(request, 'QR code image not available.')
        return redirect('student_portal:dashboard')

    from django.core.files.storage import default_storage
    import os

    # qr_path is like /media/qr_xxxx.png — extract the filename
    filename = os.path.basename(qr_token.qr_path)

    try:
        f = default_storage.open(filename, 'rb')
        image_data = f.read()
        f.close()
    except Exception:
        messages.error(request, 'QR code file not found on server.')
        return redirect('student_portal:dashboard')

    response = HttpResponse(image_data, content_type='image/png')
    safe_name = f'QR_Code_{student.student_id}.png'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
    return response


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
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'student_portal/attendance.html', {
        'student':  student,
        'logs':     page_obj,
        'page_obj': page_obj,
        'present':  logs.filter(status='present').count(),
        'late':     logs.filter(status='late').count(),
        'absent':   logs.filter(status='absent').count(),
    })


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@student_required
def profile_view(request):
    student = get_current_student(request)
    if not student:
        return redirect('student_portal:login')

    qr_token = None
    try:
        qr_token = QRToken.objects.get(student=student)
    except QRToken.DoesNotExist:
        pass

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'upload_photo' or 'profile_picture' in request.FILES:
            pic = request.FILES.get('profile_picture')
            if not pic:
                messages.error(request, 'No file selected.')
                return redirect('student_portal:profile')

            is_valid, error_msg = validate_upload(pic)
            if not is_valid:
                messages.error(request, error_msg)
                return redirect('student_portal:profile')

            import os, time
            from django.core.files.storage import default_storage
            ext       = os.path.splitext(pic.name)[1].lower()
            timestamp = int(time.time())
            filename  = f'id_photos/profile_{student.id}_{timestamp}{ext}'
            if default_storage.exists(filename):
                default_storage.delete(filename)
            saved_path            = default_storage.save(filename, pic)
            student.id_photo_path = default_storage.url(saved_path)
            student.save(update_fields=['id_photo_path'])
            messages.success(request, 'Profile picture updated successfully.')
            return redirect('student_portal:profile')

        new_pw  = request.POST.get('new_password', '').strip()
        confirm = request.POST.get('confirm_password', '').strip()
        if new_pw:
            if len(new_pw) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
            elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_pw):
                messages.error(request, 'Password must contain at least one special character.')
            elif new_pw != confirm:
                messages.error(request, 'Passwords do not match.')
            else:
                student.password_hash = hash_password(new_pw)
                student.save(update_fields=['password_hash'])
                messages.success(request, 'Password updated successfully.')
                return redirect('student_portal:profile')
        elif not new_pw and action != 'upload_photo':
            messages.error(request, 'Please enter a new password.')

    return render(request, 'student_portal/profile.html', {
        'student':  student,
        'qr_token': qr_token,
    })
