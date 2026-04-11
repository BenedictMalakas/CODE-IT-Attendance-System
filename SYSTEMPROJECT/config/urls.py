from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from admin_panel.views import chairperson_login_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('myapp.urls')),
    path('admin-panel/', include('admin_panel.urls', namespace='admin_panel')),
    path('student/', include('student_portal.urls', namespace='student_portal')),

    # Chairperson hidden login — completely separate from admin_panel
    path('chair_adminlogin/cp-x9k7m2v4-ctrl/', chairperson_login_view, name='chairperson_login'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)