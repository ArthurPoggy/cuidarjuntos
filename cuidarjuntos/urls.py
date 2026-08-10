from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda r: redirect('care:dashboard'), name='home'),
    path('care/', include('care.urls')),
    path('accounts/', include('accounts.urls')),
    path('api/v1/', include('api.urls')),
]

if settings.DEBUG:
    # Em producao (PythonAnywhere), o servidor web serve /media diretamente;
    # em desenvolvimento local o Django precisa servir os arquivos ele mesmo.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
