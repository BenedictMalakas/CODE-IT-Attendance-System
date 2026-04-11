from rest_framework import serializers
from .models import Admin, Student, Event, QRToken, AttendanceLog, Section


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'name', 'year_level', 'created_at']


class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ['id', 'name', 'email', 'role', 'is_active', 'created_at']
        # Do not expose password_hash!


class StudentSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source='section.name', read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'first_name', 'last_name', 'name', 'section', 'section_name',
                  'student_id', 'email', 'year_level', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'


class QRTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRToken
        fields = '__all__'


class AttendanceLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    event_name = serializers.CharField(source='event.name', read_only=True)

    class Meta:
        model = AttendanceLog
        fields = '__all__'
