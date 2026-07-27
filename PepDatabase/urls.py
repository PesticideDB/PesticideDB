from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('base.urls')),
]

if settings.DJANGO_ENABLE_ADMIN:
    urlpatterns.append(path(settings.DJANGO_ADMIN_URL, admin.site.urls))

if settings.DJANGO_SERVE_MEDIA:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
