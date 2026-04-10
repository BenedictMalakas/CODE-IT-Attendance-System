from django.db import models
import uuid

class Admin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'admins'

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
    
    section = models.CharField(max_length=50)
    student_id = models.CharField(max_length=50, unique=True)
    email = models.CharField(max_length=150, unique=True, blank=True)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    date = models.DateField()
    start_time = models.TimeField()
    late_cutoff_mins = models.IntegerField(default=15)
    created_by = models.ForeignKey(Admin, on_delete=models.CASCADE, db_column='created_by')
    created_at = models.DateTimeField(auto_now_add=True)

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
    override_note = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'attendance_logs'
