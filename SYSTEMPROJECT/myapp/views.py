from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Admin, Student, Event, QRToken, AttendanceLog
from .serializers import (
    AdminSerializer, StudentSerializer, StudentBasicSerializer,
    EventSerializer, QRTokenSerializer, AttendanceLogSerializer
)

class AdminViewSet(viewsets.ModelViewSet):
    queryset = Admin.objects.all()
    serializer_class = AdminSerializer

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

class QRTokenViewSet(viewsets.ModelViewSet):
    queryset = QRToken.objects.all()
    serializer_class = QRTokenSerializer

class AttendanceLogViewSet(viewsets.ModelViewSet):
    queryset = AttendanceLog.objects.all()
    serializer_class = AttendanceLogSerializer