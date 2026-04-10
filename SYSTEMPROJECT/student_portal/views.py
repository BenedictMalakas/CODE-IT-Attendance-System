import hashlib
import uuid
from functools import wraps

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone as dj_timezone

from myapp.models import Student, Event, QRToken, AttendanceLog
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
            return Student.objects.get(id=sid)
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
        if form.is_valid():
            sid = form.cleaned_data['student_id']
            if Student.objects.filter(student_id=sid).exists():
                messages.error(request, 'A student with that ID already exists.')
            else:
                Student.objects.create(
                    id=uuid.uuid4(),
                    name=form.cleaned_data['name'],
                    student_id=sid,
                    section=form.cleaned_data['section'],
                    email=form.cleaned_data['email'],
                    password_hash=hash_password(form.cleaned_data['password']),
                    id_photo_path='',
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
    events = Event.objects.filter(date__gte=today).order_by('date', 'start_time')[:5]

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
        new_pw  = request.POST.get('new_password', '').strip()
        confirm = request.POST.get('confirm_password', '').strip()
        if new_pw:
            if len(new_pw) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
            elif new_pw != confirm:
                messages.error(request, 'Passwords do not match.')
            else:
                student.password_hash = hash_password(new_pw)
                student.save()
                messages.success(request, 'Password updated successfully.')
                return redirect('student_portal:profile')

    return render(request, 'student_portal/profile.html', {'student': student})
