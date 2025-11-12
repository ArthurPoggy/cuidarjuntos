# care/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Patient, CareRecord, CareGroup, GroupMembership
from django.core.exceptions import ValidationError
from django.utils import timezone

BASE_INPUT = "w-full rounded-lg border px-3 py-2"

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
    sleep_event = forms.ChoiceField(
        label="Status do sono",
        choices=(("dormiu", "Dormiu"), ("acordou", "Acordou")),
        widget=forms.RadioSelect(attrs={
            # mantém visual limpo e alinhado
            "class": "flex gap-4 [&>label]:inline-flex [&>label]:items-center [&>label]:gap-2"
        }),
        required=False,
    )

    date = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
        label="Data",
    )
    time = forms.TimeField(
        input_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.TimeInput(attrs={"type": "time", "class": BASE_INPUT}),
        label="Horário",
    )

    class Meta:
        model = CareRecord
        fields = [
            "patient", "type", "what", "description",
            "progress_trend", "is_exception",
            "date", "time", "recurrence", "repeat_until",
        ]
        widgets = {
            "patient": forms.HiddenInput(),
            "type": forms.Select(attrs={"class": BASE_INPUT}),
            "what": forms.TextInput(attrs={
                "class": BASE_INPUT,
                "placeholder": "Ex.: 500mg / Refeição / Urina / Caminhada...",
            }),
            "description": forms.Textarea(attrs={"class": BASE_INPUT, "rows": 4}),
            "date": forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "time": forms.TimeInput(attrs={"type": "time", "class": BASE_INPUT}),

            # 🔧 Padronização pedida:
            "recurrence": forms.Select(attrs={"class": BASE_INPUT}),
            "repeat_until": forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "is_exception": forms.CheckboxInput(attrs={"class": "h-4 w-4 text-blue-600"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1) remove placeholders “de exemplo”
        for name in ("what", "description"):
            if name in self.fields:
                self.fields[name].widget.attrs.pop("placeholder", None)

        # 2) ajuda visual (os textos que aparecem abaixo do campo)
        if "recurrence" in self.fields:
            self.fields["recurrence"].help_text = "Quando ativada, cria uma série até a data final."
        if "repeat_until" in self.fields:
            self.fields["repeat_until"].help_text = "Não pode ser anterior à Data."

        # 3) liga/desliga o seletor de sono conforme o type
        current_type = (self.data.get("type")
                        or self.initial.get("type")
                        or getattr(self.instance, "type", None))

        if current_type == CareRecord.Type.SLEEP:
            # esconde o 'what' e usa o sleep_event
            self.fields["what"].required = False
            self.fields["what"].widget = forms.HiddenInput()
            self.fields["sleep_event"].required = True

            # se estiver editando e já tiver valor em what, seta como inicial
            val = (self.data.get("sleep_event")
                   or self.initial.get("sleep_event")
                   or getattr(self.instance, "what", "")).strip().lower()
            if val in ("dormiu", "acordou"):
                self.fields["sleep_event"].initial = val
        else:
            # fora do tipo "sleep" o campo não aparece
            self.fields["sleep_event"].widget = forms.HiddenInput()

        self.show_progress_trend = False
        if "progress_trend" in self.fields:
            pt_field = self.fields["progress_trend"]
            pt_field.widget = forms.RadioSelect(attrs={
                "class": "flex flex-wrap gap-3 [&>label]:inline-flex [&>label]:items-center [&>label]:gap-2"
            })
            is_progress = current_type == CareRecord.Type.PROGRESS
            self.show_progress_trend = is_progress
            pt_field.required = is_progress
            if not is_progress:
                pt_field.widget = forms.HiddenInput()

        if "is_exception" in self.fields:
            self.fields["is_exception"].required = False

    def clean(self):
        cleaned = super().clean()
        rec = cleaned.get("recurrence") or CareRecord.Recurrence.NONE
        date = cleaned.get("date")
        until = cleaned.get("repeat_until")

        # Regra: só permite recorrência para data futura
        if rec != CareRecord.Recurrence.NONE and date:
            if date < timezone.localdate():
                self.add_error("date", "Recorrência só é permitida para datas futuras.")
            if not until:
                self.add_error("repeat_until", "Informe a data final da recorrência.")
            elif until < date:
                self.add_error("repeat_until", "A data final deve ser igual ou posterior à data inicial.")

        current_type = (
            cleaned.get("type")
            or self.initial.get("type")
            or getattr(self.instance, "type", None)
        )
        if current_type == CareRecord.Type.PROGRESS:
            if not cleaned.get("progress_trend"):
                self.add_error("progress_trend", "Selecione se é evolução ou regressão.")
        else:
            cleaned["progress_trend"] = ""
        return cleaned


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
    group_pin = forms.RegexField(
        label="Senha do grupo (4 dígitos)",
        regex=r"^\d{4}$",
        error_messages={"invalid": "Informe exatamente 4 dígitos."},
        widget=forms.TextInput(attrs={
            "class": "border rounded-lg w-full px-3 py-2",
            "inputmode": "numeric",
            "maxlength": "4",
            "placeholder": "0000",
        }),
        help_text="Compartilhe com quem for entrar no grupo.",
    )

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
        group.set_join_code(self.cleaned_data.get("group_pin"))
        group.save(update_fields=["join_code_hash"])
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
    pin = forms.CharField(
        label="Senha do grupo",
        min_length=4,
        max_length=4,
        widget=forms.TextInput(attrs={
            "class": "border rounded-lg w-full px-3 py-2",
            "inputmode": "numeric",
            "maxlength": "4",
            "placeholder": "0000",
        })
    )

    def clean_pin(self):
        pin = (self.cleaned_data.get("pin") or "").strip()
        if pin and not pin.isdigit():
            raise ValidationError("A senha deve conter apenas números.")
        return pin

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [c for c in GroupMembership.REL_CHOICES if c[0] != "SELF"]
        self.fields["relation_to_patient"].choices = choices

    def join(self, user):
        if hasattr(user, "group_membership"):
            raise forms.ValidationError("Você já está atrelado a um grupo.")
        group = self.cleaned_data["group"]
        rel = self.cleaned_data["relation_to_patient"]
        pin = (self.cleaned_data.get("pin") or "").strip()

        if not group.check_join_code(pin):
            raise forms.ValidationError("Senha do grupo incorreta.")

        GroupMembership.objects.create(user=user, group=group, relation_to_patient=rel)
        return group

    def clean(self):
        cleaned = super().clean()
        group = cleaned.get("group")
        pin   = (cleaned.get("pin") or "").strip()

        if group and group.join_code_hash and len(pin) != 4:
            self.add_error("pin", "Informe a senha do grupo (4 dígitos).")

        return cleaned
