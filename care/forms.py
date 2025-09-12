# care/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Patient, CareRecord, CareGroup, GroupMembership
from django.core.exceptions import ValidationError

# =========================
# ModelForms básicos (CRUD)
# =========================

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["name", "birth_date", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "border rounded-lg w-full px-3 py-2"}),
            "notes": forms.Textarea(attrs={"rows": 4, "class": "border rounded-lg w-full px-3 py-2"}),
        }


class CareRecordForm(forms.ModelForm):
    date = forms.DateField(
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full rounded-lg border px-3 py-2'
        }),
        label="Data"
    )
    time = forms.TimeField(
        input_formats=['%H:%M', '%H:%M:%S'],
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'w-full rounded-lg border px-3 py-2'
        }),
        label="Horário"
    )

    class Meta:
        model = CareRecord
        fields = ["patient", "type", "what", "description", "date", "time"]
        widgets = {
            "patient": forms.HiddenInput(),
            "type": forms.Select(attrs={"class": "w-full rounded-lg border px-3 py-2"}),
            "what": forms.TextInput(attrs={"class": "w-full rounded-lg border px-3 py-2",
                                           "placeholder": "Ex.: 500mg / Refeição / Urina / Caminhada..."}),
            "description": forms.Textarea(attrs={"class": "w-full rounded-lg border px-3 py-2", "rows": 4}),
            "date": forms.DateInput(attrs={"type": "date", "class": "w-full rounded-lg border px-3 py-2"}),
            "time": forms.TimeInput(attrs={"type": "time", "class": "w-full rounded-lg border px-3 py-2"}),
        }
        # Como o input nativo envia YYYY-MM-DD / HH:MM:
        input_formats = {}


# =========================
# Fluxo de cadastro/Grupo
# =========================

class SignUpForm(forms.Form):
    full_name = forms.CharField(label="Nome completo", max_length=120,
                                widget=forms.TextInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}))
    birth_date = forms.DateField(label="Data de nascimento",
                                 widget=forms.DateInput(attrs={"type": "date", "class": "border rounded-lg w-full px-3 py-2"}))
    email = forms.EmailField(label="E-mail",
                             widget=forms.EmailInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}))
    username = forms.CharField(label="Nome de usuário", max_length=150,
                               widget=forms.TextInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}))
    cpf = forms.CharField(label="CPF", max_length=14,
                          widget=forms.TextInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}))
    password = forms.CharField(label="Senha",
                               widget=forms.PasswordInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}))

    def clean_username(self):
        u = self.cleaned_data["username"]
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Este nome de usuário já está em uso.")
        return u

    def clean_email(self):
        e = self.cleaned_data["email"]
        if User.objects.filter(email=e).exists():
            raise forms.ValidationError("Este e-mail já está em uso.")
        return e

    def create_user(self):
        cd = self.cleaned_data
        user = User.objects.create_user(
            username=cd["username"],
            email=cd["email"],
            password=cd["password"],
            first_name=cd["full_name"],  # guardando nome no first_name por simplicidade
        )
        # birth_date e cpf podem ir para um Profile no futuro, se você quiser persistir.
        return user


class GroupCreateForm(forms.Form):
    group_name = forms.CharField(label="Nome do grupo", max_length=120,
                                 widget=forms.TextInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}))
    patient_name = forms.CharField(label="Nome do paciente", max_length=120,
                                   widget=forms.TextInput(attrs={"class": "border rounded-lg w-full px-3 py-2"}))
    patient_birth_date = forms.DateField(label="Data de nascimento do paciente",
                                         widget=forms.DateInput(attrs={"type": "date", "class": "border rounded-lg w-full px-3 py-2"}))
    relation_to_patient = forms.ChoiceField(label="Relação com o paciente",
                                            choices=GroupMembership.REL_CHOICES,
                                            widget=forms.Select(attrs={"class": "border rounded-lg w-full px-3 py-2"}))
    health_data = forms.CharField(label="Dados de saúde", required=False,
                                  widget=forms.Textarea(attrs={"rows": 4, "class": "border rounded-lg w-full px-3 py-2"}))

    def create_everything(self, user):
        patient = Patient.objects.create(
            name=self.cleaned_data["patient_name"],
            birth_date=self.cleaned_data["patient_birth_date"],
            notes=self.cleaned_data["health_data"],
            created_by=user,
        )
        group = CareGroup.objects.create(
            name=self.cleaned_data["group_name"],
            patient=patient,
            created_by=user,
        )
        GroupMembership.objects.create(
            user=user,
            group=group,
            relation_to_patient=self.cleaned_data["relation_to_patient"],
        )
        return group


class GroupJoinForm(forms.Form):
    group = forms.ModelChoiceField(
        label="Escolha um grupo (teste)",
        queryset=CareGroup.objects.all().select_related("patient"),
        empty_label=None,
        widget=forms.Select(attrs={"class": "border rounded-lg w-full px-3 py-2"})
    )
    relation_to_patient = forms.ChoiceField(
        label="Relação com o paciente",
        choices=GroupMembership.REL_CHOICES,
        widget=forms.Select(attrs={"class": "border rounded-lg w-full px-3 py-2"})
    )

    def join(self, user):
        if hasattr(user, "group_membership"):
            raise forms.ValidationError("Você já está atrelado a um grupo.")
        group = self.cleaned_data["group"]
        rel = self.cleaned_data["relation_to_patient"]
        GroupMembership.objects.create(user=user, group=group, relation_to_patient=rel)
        return group

    def clean(self):
        cleaned = super().clean()
        group = cleaned.get("group")
        rel = cleaned.get("relation_to_patient")
        if group and rel == "SELF":
            if GroupMembership.objects.filter(group=group, relation_to_patient="SELF").exists():
                raise ValidationError("Este grupo já possui um paciente associado.")
        return cleaned
