from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import JsonResponse
from .models import Admin, Section, Student, Event, QRToken, AttendanceLog
from .services import sorted_sections
from .serializers import (
    AdminSerializer, StudentSerializer, EventSerializer,
    QRTokenSerializer, AttendanceLogSerializer
)


@api_view(['GET'])
def sections_by_year_api(request):
    year = request.GET.get('year', '')
    if year:
        sections = sorted_sections(Section.objects.filter(year_level=year))
    else:
        sections = sorted_sections(Section.objects.all())
    data = [{'id': str(s.id), 'name': s.name} for s in sections]
    return Response({'sections': data})


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
