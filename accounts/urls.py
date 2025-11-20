from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    RegisterView,
    SafePasswordResetConfirmView,
    SafePasswordResetView,
    logout_confirm,
)

app_name = "accounts"

urlpatterns = [
    path("login/",  __import__("django.contrib.auth.views").contrib.auth.views.LoginView.as_view(
        template_name="registration/login.html",
        redirect_authenticated_user=False,
    ), name="login"),
    path("logout/", logout_confirm, name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("password-reset/", SafePasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        SafePasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
