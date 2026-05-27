from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404
from django.views.generic import RedirectView
from admin_panel.views import chairperson_login_view


def favicon_view(request):
    favicon_path = finders.find('student_portal/img/codenew (1).ico')
    if not favicon_path:
        raise Http404('favicon not found')
    response = FileResponse(open(favicon_path, 'rb'), content_type='image/x-icon')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


urlpatterns = [
    path('', RedirectView.as_view(pattern_name='student_portal:login', permanent=False)),
    path('favicon.ico', favicon_view, name='favicon'),
    path('admin/', admin.site.urls),
    path('api/', include('myapp.urls')),
    path('admin-panel/', include('admin_panel.urls', namespace='admin_panel')),
    path('chair_adminlogin/cp-x9k7m2v4-ctrl/', chairperson_login_view, name='chairperson_login'),
    path('student/', include('student_portal.urls', namespace='student_portal')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
