from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Admin, Student, Event, QRToken, AttendanceLog
from .serializers import (
    AdminSerializer, StudentSerializer, EventSerializer,
    QRTokenSerializer, AttendanceLogSerializer
)


class AdminViewSet(viewsets.ModelViewSet):
    queryset = Admin.objects.all()
    serializer_class = AdminSerializer


class StudentViewSet(viewsets.ModelViewSet):
    """
    Student API — frontend-ready endpoints.

    GET  /api/students/          → list all students
    POST /api/students/          → create student (send: name, section, student_id)
    GET  /api/students/{id}/     → get one student
    PUT  /api/students/{id}/     → update student
    DELETE /api/students/{id}/   → delete student
    """
    queryset = Student.objects.all().order_by('-created_at')
    serializer_class = StudentSerializer

    def perform_create(self, serializer):
        """Set defaults for DB columns that aren't part of the registration input."""
        serializer.save(
            password_hash='',     # will be set later during full registration
            id_photo_path='',     # will be uploaded later
        )


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class QRTokenViewSet(viewsets.ModelViewSet):
    queryset = QRToken.objects.all()
    serializer_class = QRTokenSerializer


class AttendanceLogViewSet(viewsets.ModelViewSet):
    queryset = AttendanceLog.objects.all()
    serializer_class = AttendanceLogSerializer