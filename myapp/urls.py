from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminViewSet, StudentViewSet, EventViewSet,
    QRTokenViewSet, AttendanceLogViewSet,
    sections_by_year_api,
)

router = DefaultRouter()
router.register(r'admins', AdminViewSet)
router.register(r'students', StudentViewSet)
router.register(r'events', EventViewSet)
router.register(r'qr-tokens', QRTokenViewSet)
router.register(r'attendance-logs', AttendanceLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('sections/', sections_by_year_api, name='sections_by_year'),
]
