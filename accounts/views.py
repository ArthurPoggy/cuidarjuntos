# accounts/views.py
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_protect
from django.views.generic import CreateView
from .forms import RegisterForm


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("care:dashboard")

    def form_valid(self, form):
        user = form.save()
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
