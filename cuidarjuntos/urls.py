from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda r: redirect('care:dashboard'), name='home'),
    path('care/', include('care.urls')),
    path('accounts/', include('accounts.urls')),
]
