from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

from .deploy_webhook import github_deploy_hook

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda r: redirect('care:dashboard'), name='home'),
    path('care/', include('care.urls')),
    path('accounts/', include('accounts.urls')),
    path('api/v1/', include('api.urls')),
    path('deploy-hook/', github_deploy_hook, name='deploy-hook'),
]
