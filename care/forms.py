# care/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import (
    Patient,
    CareRecord,
    CareGroup,
    GroupMembership,
    Medication,
    MedicationStockEntry,
)
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
    medication = forms.ModelChoiceField(
        label="Remédio/Dose",
        queryset=Medication.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": BASE_INPUT}),
    )
    capsule_quantity = forms.IntegerField(
        label="Quantidade de cápsulas",
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={
            "class": BASE_INPUT,
            "min": 1,
            "inputmode": "numeric",
        }),
    )
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
            "patient", "type", "what", "medication", "capsule_quantity",
            "description", "missed_reason",
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
            "missed_reason": forms.Textarea(attrs={
                "class": BASE_INPUT,
                "rows": 3,
                "placeholder": "Preencha quando marcar como não realizado.",
            }),
            "medication": forms.Select(attrs={"class": BASE_INPUT}),
            "capsule_quantity": forms.NumberInput(attrs={
                "class": BASE_INPUT,
                "min": 1,
                "inputmode": "numeric",
            }),
            "date": forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "time": forms.TimeInput(attrs={"type": "time", "class": BASE_INPUT}),

            # 🔧 Padronização pedida:
            "recurrence": forms.Select(attrs={"class": BASE_INPUT}),
            "repeat_until": forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "is_exception": forms.CheckboxInput(attrs={"class": "h-4 w-4 text-blue-600"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.show_sleep_event = False
        self.show_progress_trend = False
        self.show_medication_fields = False

        # 1) remove placeholders “de exemplo”
        for name in ("what", "description"):
            if name in self.fields:
                self.fields[name].widget.attrs.pop("placeholder", None)

        # 2) ajuda visual (os textos que aparecem abaixo do campo)
        if "recurrence" in self.fields:
            self.fields["recurrence"].help_text = "Quando ativada, cria uma série até a data final."
        if "repeat_until" in self.fields:
            self.fields["repeat_until"].help_text = "Não pode ser anterior à Data."

        # 3) liga/desliga blocos especiais conforme o tipo
        current_type = (self.data.get("type")
                        or self.initial.get("type")
                        or getattr(self.instance, "type", None))

        if "medication" in self.fields:
            if self.user:
                gm = getattr(self.user, "group_membership", None)
                if gm and getattr(gm, "group", None):
                    self.fields["medication"].queryset = (
                        Medication.objects
                        .filter(group=gm.group)
                        .order_by("name", "dosage")
                    )
            if not self.fields["medication"].queryset.exists() and self.instance.medication_id:
                self.fields["medication"].queryset = Medication.objects.filter(
                    pk=self.instance.medication_id
                )

        if current_type == CareRecord.Type.MEDICATION:
            self.show_medication_fields = True
            if "medication" in self.fields:
                self.fields["medication"].required = True
            if "capsule_quantity" in self.fields:
                self.fields["capsule_quantity"].required = True
            if "what" in self.fields:
                self.fields["what"].required = False
                self.fields["what"].widget = forms.HiddenInput()
        else:
            if "medication" in self.fields:
                self.fields["medication"].widget = forms.HiddenInput()
            if "capsule_quantity" in self.fields:
                self.fields["capsule_quantity"].widget = forms.HiddenInput()

        self.show_sleep_event = current_type == CareRecord.Type.SLEEP
        if self.show_sleep_event:
            # esconde o 'what' e usa o sleep_event
            self.fields["what"].required = False
            self.fields["what"].widget = forms.HiddenInput()
            self.fields["sleep_event"].required = True

            val = (self.data.get("sleep_event")
                   or self.initial.get("sleep_event")
                   or getattr(self.instance, "what", "")).strip().lower()
            if val in ("dormiu", "acordou"):
                self.fields["sleep_event"].initial = val
        else:
            self.fields["sleep_event"].widget = forms.HiddenInput()

        self.show_progress_trend = False
        if "progress_trend" in self.fields:
            pt_field = self.fields["progress_trend"]
            pt_field.widget = forms.RadioSelect(attrs={
                "class": "flex gap-3"
            })
            is_progress = current_type == CareRecord.Type.PROGRESS
            self.show_progress_trend = is_progress
            pt_field.required = is_progress
            if not is_progress:
                pt_field.widget = forms.HiddenInput()
            else:
                what_field = self.fields.get("what")
                if what_field:
                    what_field.required = True
                    what_field.label = "O que mudou?"
                    what_field.widget.attrs.setdefault(
                        "placeholder",
                        "Ex.: Humor, apetite, mobilidade…",
                    )

        # Mostra razão de não realizado apenas para status missed
        inst_status = getattr(self.instance, "status", "")
        if inst_status != CareRecord.Status.MISSED and "missed_reason" in self.fields:
            self.fields["missed_reason"].help_text = "Campo usado apenas quando status for 'não realizado'."
        elif "missed_reason" in self.fields:
            self.fields["missed_reason"].label = "Motivo do não realizado"

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
        if current_type == CareRecord.Type.MEDICATION:
            med = cleaned.get("medication")
            qty = cleaned.get("capsule_quantity")
            if not med:
                self.add_error("medication", "Selecione o remédio.")
            if qty is None:
                self.add_error("capsule_quantity", "Informe a quantidade de cápsulas.")
            cleaned["what"] = str(med).strip() if med else ""
        else:
            cleaned["medication"] = None
            cleaned["capsule_quantity"] = None

        if current_type == CareRecord.Type.PROGRESS:
            if not cleaned.get("progress_trend"):
                self.add_error("progress_trend", "Selecione se é evolução ou regressão.")
            if not (cleaned.get("what") or "").strip():
                self.add_error("what", "Descreva o que evoluiu ou regrediu.")
        else:
            cleaned["progress_trend"] = ""
        return cleaned

    def save(self, commit=True):
        rec: CareRecord = super().save(commit=False)
        if rec.type == CareRecord.Type.MEDICATION:
            if rec.medication:
                rec.what = str(rec.medication).strip()
        else:
            rec.medication = None
            rec.capsule_quantity = None
        if rec.status != CareRecord.Status.MISSED:
            rec.missed_reason = ""
        if commit:
            rec.save()
            self.save_m2m()
        return rec


class MedicationStockEntryForm(forms.ModelForm):
    quantity = forms.IntegerField(
        label="Quantidade de cápsulas",
        min_value=1,
        widget=forms.NumberInput(attrs={
            "class": BASE_INPUT,
            "min": 1,
            "inputmode": "numeric",
        }),
    )

    class Meta:
        model = MedicationStockEntry
        fields = ["medication", "quantity"]
        widgets = {
            "medication": forms.Select(attrs={"class": BASE_INPUT}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            gm = getattr(self.user, "group_membership", None)
            if gm and getattr(gm, "group", None):
                self.fields["medication"].queryset = (
                    Medication.objects
                    .filter(group=gm.group)
                    .order_by("name", "dosage")
                )
            else:
                self.fields["medication"].queryset = Medication.objects.none()
        else:
            self.fields["medication"].queryset = Medication.objects.none()


class MedicationCreateForm(forms.Form):
    name = forms.CharField(
        label="Nome do remédio",
        max_length=120,
        widget=forms.TextInput(attrs={"class": BASE_INPUT}),
    )
    dosage = forms.CharField(
        label="Dosagem",
        max_length=50,
        widget=forms.TextInput(attrs={"class": BASE_INPUT, "placeholder": "Ex.: 500mg"}),
    )
    quantity = forms.IntegerField(
        label="Quantidade de cápsulas",
        min_value=1,
        widget=forms.NumberInput(attrs={
            "class": BASE_INPUT,
            "min": 1,
            "inputmode": "numeric",
        }),
    )

    def __init__(self, *args, **kwargs):
        self.group = kwargs.pop("group", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        name = (cleaned.get("name") or "").strip()
        dosage = (cleaned.get("dosage") or "").strip()
        if self.group and name and dosage:
            exists = Medication.objects.filter(
                group=self.group,
                name__iexact=name,
                dosage__iexact=dosage,
            ).exists()
            if exists:
                self.add_error("name", "Este remédio/dosagem já está cadastrado.")
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
