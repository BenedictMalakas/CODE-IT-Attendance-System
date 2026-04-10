from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('myapp.urls')),
    path('admin-panel/', include('admin_panel.urls', namespace='admin_panel')),
    path('student/', include('student_portal.urls', namespace='student_portal')),
]