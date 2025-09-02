from django.contrib.auth import login
from django.urls import reverse_lazy
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