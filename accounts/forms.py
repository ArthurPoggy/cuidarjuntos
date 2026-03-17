# accounts/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Profile

def so_digitos(s: str) -> str:
    return "".join(ch for ch in s or "" if ch.isdigit())

class RegisterForm(UserCreationForm):
    full_name = forms.CharField(label="Nome completo", max_length=150, required=True)

    cpf = forms.CharField(                     # <- obrigatório e vem logo após o nome
        label="CPF",
        required=True,
        max_length=14,                         # permite 000.000.000-00 na digitação
        widget=forms.TextInput(attrs={
            "inputmode": "numeric",
            "placeholder": "000.000.000-00",
        }),
        help_text="Informe seu CPF (será verificado se já existe conta).",
    )

    birth_date = forms.DateField(
        label="Data de nascimento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    email = forms.EmailField(label="E-mail", required=True)

    class Meta:
        model = User
        # ordem com CPF logo após o nome
        fields = ("full_name", "cpf", "birth_date", "email", "username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = "border rounded-lg w-full px-3 py-2"
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", base)

    # -------- validações ----------
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if " " in username:
            raise ValidationError("O nome de usuário não pode conter espaços.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean_cpf(self):
        raw = self.cleaned_data.get("cpf") or ""
        digits = so_digitos(raw)
        if len(digits) != 11:
            raise ValidationError("CPF deve ter 11 dígitos.")
        # checa unicidade no Profile
        if Profile.objects.filter(cpf=digits).exists():
            raise ValidationError("Já existe uma conta com este CPF.")
        # guarda normalizado para o save()
        self.cleaned_data["cpf_normalizado"] = digits
        return raw

    # -------- persistência ----------
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = (self.cleaned_data.get("email") or "").lower()

        # opcional: distribuir first_name/last_name a partir do full_name
        full_name = (self.cleaned_data.get("full_name") or "").strip()
        if full_name:
            partes = full_name.split(" ", 1)
            user.first_name = partes[0]
            if len(partes) > 1:
                user.last_name = partes[1]

        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.full_name  = full_name
            profile.birth_date = self.cleaned_data.get("birth_date")
            profile.cpf        = self.cleaned_data.get("cpf_normalizado")  # só dígitos
            profile.save()

        return user


class SingleUserPasswordResetForm(PasswordResetForm):
    """
    Garante que apenas um e-mail seja enviado mesmo se houver múltiplos usuários
    com o mesmo endereço (situação legada ou importada).
    """

    def get_users(self, email):
        email = (email or "").strip()
        if not email:
            return []

        user_model = get_user_model()
        email_field = user_model.get_email_field_name()
        lookup = {
            f"{email_field}__iexact": email,
            "is_active": True,
        }
        user = (
            user_model._default_manager
            .filter(**lookup)
            .order_by("pk")
            .first()
        )
        if user and user.has_usable_password():
            return [user]
        return []
