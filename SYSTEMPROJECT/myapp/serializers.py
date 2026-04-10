from rest_framework import serializers
from .models import Admin, Student, Event, QRToken, AttendanceLog


class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ['id', 'name', 'email', 'is_active', 'created_at']
        # Do not expose password_hash!


class StudentSerializer(serializers.ModelSerializer):
    """
    Handles creating and listing students.
    POST only needs: name, section, student_id
    GET returns all stored fields.
    """
    class Meta:
        model = Student
        fields = ['id', 'name', 'section', 'student_id', 'status', 'created_at', 'updated_at']
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
