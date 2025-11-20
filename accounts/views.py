# accounts/views.py
import logging
from smtplib import SMTPException

from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.core.mail import BadHeaderError
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_protect
from django.views.generic import CreateView

from .forms import RegisterForm

logger = logging.getLogger(__name__)


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("care:dashboard")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error(None, "Não foi possível concluir o cadastro: CPF, e-mail ou nome de usuário já estão cadastrados.")
            return self.form_invalid(form)
        login(self.request, user)  # loga automaticamente após cadastro
        return super().form_valid(form)


@csrf_protect
def logout_confirm(request):
    """
    GET  -> mostra página de confirmação com botão
    POST -> faz logout e redireciona para a tela de login
    """
    if request.method == "POST":
        logout(request)
        return redirect("accounts:login")
    return render(request, "accounts/logout_confirm.html")


class SafePasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except (SMTPException, BadHeaderError, ConnectionError, TimeoutError, OSError):  # pragma: no cover - defensivo
            logger.exception("Erro ao enviar e-mail de redefinição de senha")
            form.add_error(None, "Não foi possível enviar o e-mail agora. Tente novamente em instantes.")
            return self.form_invalid(form)


class SafePasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")
