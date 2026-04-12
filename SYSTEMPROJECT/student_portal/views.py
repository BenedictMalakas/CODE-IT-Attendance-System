import hashlib
import uuid
from functools import wraps

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone as dj_timezone

from myapp.models import Student, Event, QRToken, AttendanceLog, Section
from .forms import StudentLoginForm, StudentRegisterForm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def student_required(view_func):
    """Redirect to login if there is no active student session."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('student_id'):
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
    if request.session.get('student_id'):
        return redirect('student_portal:dashboard')

    form = StudentLoginForm()
    if request.method == 'POST':
        form = StudentLoginForm(request.POST)
        if form.is_valid():
            student_id_val = form.cleaned_data['student_id']
            password       = form.cleaned_data['password']
            pw_hash        = hash_password(password)
            try:
                student = Student.objects.get(student_id=student_id_val, password_hash=pw_hash)
                if student.status == 'pending':
                    messages.warning(request, 'Your account is still pending approval.')
                elif student.status == 'rejected':
                    note = student.rejection_note or 'No reason provided.'
                    messages.error(request, f'Your registration was rejected: {note}')
                else:
                    request.session['student_id']   = str(student.id)
                    request.session['student_name'] = student.name
                    return redirect('student_portal:dashboard')
            except Student.DoesNotExist:
                messages.error(request, 'Invalid Student ID or password.')

    return render(request, 'student_portal/login.html', {'form': form})


def register_view(request):
    if request.session.get('student_id'):
        return redirect('student_portal:dashboard')

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
                    return render(request, 'student_portal/register.html', {'form': form})

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
                        return render(request, 'student_portal/register.html', {'form': form})

                    safe_id = sid.replace('-', '_')
                    filename = f"id_photos/id_{safe_id}.{ext}"

                    # Ensure directory exists
                    upload_dir = os.path.join(settings.MEDIA_ROOT, 'id_photos')
                    os.makedirs(upload_dir, exist_ok=True)

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

    return render(request, 'student_portal/register.html', {'form': form})


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

    context = {
        'student':       student,
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

    return render(request, 'student_portal/attendance.html', {
        'student': student,
        'logs':    logs,
        'present': logs.filter(status='present').count(),
        'late':    logs.filter(status='late').count(),
        'absent':  logs.filter(status='absent').count(),
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
            from django.conf import settings
            from django.core.files.storage import default_storage

            pic = request.FILES['profile_picture']
            ext = pic.name.split('.')[-1].lower()

            if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                messages.error(request, 'Invalid file type. Only PNG, JPG, and WebP are allowed.')
                return redirect('student_portal:profile')

            filename = f"profile_{student.id}.{ext}"

            filepath = os.path.join(settings.MEDIA_ROOT, filename)
            if default_storage.exists(filepath):
                default_storage.delete(filepath)

            saved_path = default_storage.save(filename, pic)
            student.id_photo_path = default_storage.url(saved_path)
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
                student.password_hash = hash_password(new_pw)
                student.save()
                messages.success(request, 'Password updated successfully.')
                return redirect('student_portal:profile')

    return render(request, 'student_portal/profile.html', {'student': student})
