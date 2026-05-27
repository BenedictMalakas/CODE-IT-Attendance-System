from django.db import models
import uuid


class Section(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    year_level = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'sections'

    def __str__(self):
        return self.name


class Admin(models.Model):
    class Role(models.TextChoices):
        CHAIRPERSON = 'chairperson', 'Chairperson'
        VITS = 'vits', 'VITS Officer'
        REPRESENTATIVE = 'representative', 'Representative'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VITS)
    is_active = models.BooleanField(default=True)
    force_password_change = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'admins'

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"


class AdminSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE, db_column='admin_id', related_name='admin_sections')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, db_column='section_id', related_name='assigned_admins')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'admin_sections'

class Student(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        REJECTED = 'rejected', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    
    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"
    
    section = models.ForeignKey(Section, on_delete=models.CASCADE, db_column='section_id', related_name='students')
    student_id = models.CharField(max_length=50, unique=True)
    email = models.CharField(max_length=150, unique=True, blank=True)
    year_level = models.IntegerField(default=1)
    password_hash = models.CharField(max_length=255, null=True, blank=True)
    id_photo_path = models.CharField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    rejection_note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'students'

class Event(models.Model):
    class EventStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        ENDED = 'ended', 'Ended'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    late_cutoff_mins = models.IntegerField(default=15)
    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.PENDING)
    created_by = models.ForeignKey(Admin, on_delete=models.SET_NULL, db_column='created_by', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expected_sections = models.ManyToManyField(Section, db_table='event_sections', related_name='expected_events', blank=True)

    class Meta:
        managed = False
        db_table = 'events'

class QRToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(Student, on_delete=models.CASCADE, db_column='student_id')
    token = models.CharField(max_length=255, unique=True)
    qr_path = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'qr_tokens'

class AttendanceLog(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        LATE = 'late', 'Late'
        ABSENT = 'absent', 'Absent'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_column='event_id')
    scanned_by = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, db_column='scanned_by')
    status = models.CharField(max_length=20, choices=Status.choices)
    scanned_at = models.DateTimeField(null=True, blank=True)
    scanned_out_at = models.DateTimeField(null=True, blank=True)
    override_note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_logs'


class ActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, db_column='admin_id', related_name='activity_logs')
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'activity_logs'

    def __str__(self):
        return f"{self.action} by {self.admin} at {self.created_at}"
