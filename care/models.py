# care/models.py
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone  # ← necessário para comparar com a hora atual


def humanize_identifier(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if "@" in value:
        value = value.split("@", 1)[0]
    value = value.replace(".", " ").replace("_", " ")
    normalized = " ".join(part.capitalize() for part in value.split() if part)
    return normalized or raw or ""


class Patient(models.Model):
    name = models.CharField("Nome", max_length=120)
    birth_date = models.DateField("Nascimento", null=True, blank=True)
    notes = models.TextField("Observações / Dados de saúde", blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="patients",
        null=True, blank=True, db_index=True
    )
    # opcional: se o paciente tem login próprio
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, related_name="as_patient",
        null=True, blank=True
    )

    def __str__(self):
        return self.name


class CareGroup(models.Model):
    """Um grupo contém exatamente 1 paciente."""
    name = models.CharField("Nome do grupo", max_length=120)
    patient = models.OneToOneField(
        Patient, on_delete=models.CASCADE, related_name="care_group"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_groups"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    join_code_hash = models.CharField("Senha do grupo", max_length=128, blank=True)

    def __str__(self):
        return f"{self.name} • Paciente: {self.patient.name}"

    # -------- senha de entrada --------
    def set_join_code(self, code: str | None):
        code = (code or "").strip()
        self.join_code_hash = make_password(code) if code else ""

    def check_join_code(self, code: str | None) -> bool:
        if not self.join_code_hash:
            return True  # grupos antigos ainda sem senha
        return check_password(code or "", self.join_code_hash)


class GroupMembership(models.Model):
    REL_CHOICES = (
        ("SELF", "Sou o paciente"),
        ("FAMILY", "Familiar"),
        ("DOCTOR", "Médico"),
        ("CAREGIVER", "Cuidador"),
        ("OTHER", "Outro"),
    )
    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="group_membership"
    )
    group = models.ForeignKey(
        "CareGroup", on_delete=models.CASCADE, related_name="members"
    )
    relation_to_patient = models.CharField(
        "Relação com o paciente", max_length=20, choices=REL_CHOICES
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], name="unique_user_one_group"),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.group.name} ({self.relation_to_patient})"


class Medication(models.Model):
    group = models.ForeignKey(
        CareGroup, on_delete=models.CASCADE, related_name="medications"
    )
    name = models.CharField("Nome", max_length=120)
    dosage = models.CharField("Dosagem", max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="medications_created"
    )

    class Meta:
        ordering = ["name", "dosage"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "name", "dosage"],
                name="unique_medication_per_group",
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.dosage}".strip()


class MedicationStockEntry(models.Model):
    medication = models.ForeignKey(
        Medication, on_delete=models.CASCADE, related_name="stock_entries"
    )
    quantity = models.PositiveIntegerField("Quantidade de cápsulas")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="medication_stock_entries"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"+{self.quantity} • {self.medication}"


class CareRecord(models.Model):
    class Type(models.TextChoices):
        MEDICATION = "medication", "Medicação"
        MEAL       = "meal",       "Alimentação"
        VITAL      = "vital",      "Sinais Vitais"
        ACTIVITY   = "activity",   "Atividade"
        PROGRESS   = "progress",   "Evolução/Regressão"
        SLEEP      = "sleep",      "Sono"
        BATHROOM   = "bathroom",   "Banheiro"
        OTHER      = "other",      "Outros"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        DONE    = "done",    "Realizada"
        MISSED  = "missed", "Não realizado"

    class Recurrence(models.TextChoices):
        NONE    = "none",    "Não se repete"
        DAILY   = "daily",   "Diariamente"
        WEEKLY  = "weekly",  "Semanalmente"
        MONTHLY = "monthly", "Mensalmente"  # opcional, mas já deixamos preparado

    class ProgressTrend(models.TextChoices):
        EVOLUTION = "evolution", "Evolução"
        REGRESSION = "regression", "Regressão"

    # 🔗 Grupo de recorrência (todas as ocorrências geradas juntos compartilham o mesmo id)
    # Mantemos compatibilidade com a coluna existente 'series_id' usando db_column.
    recurrence_group = models.UUIDField(
        null=True, blank=True, db_index=True, db_column="series_id"
    )

    # Configuração de recorrência
    recurrence   = models.CharField(max_length=16, choices=Recurrence.choices, default=Recurrence.NONE)
    repeat_until = models.DateField(null=True, blank=True)

    patient     = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="records")
    caregiver   = models.CharField("Cuidador", max_length=120)
    type        = models.CharField("Tipo", max_length=20, choices=Type.choices, default=Type.MEDICATION)
    what        = models.CharField("O que", max_length=200)
    medication  = models.ForeignKey(
        Medication, on_delete=models.SET_NULL,
        related_name="care_records", null=True, blank=True
    )
    capsule_quantity = models.PositiveIntegerField("Quantidade de cápsulas", null=True, blank=True)
    description = models.TextField("Descrição", blank=True)
    missed_reason = models.TextField("Motivo do não realizado", blank=True)
    progress_trend = models.CharField(
        "Evolução ou Regressão",
        max_length=12,
        choices=ProgressTrend.choices,
        blank=True,
    )
    is_exception = models.BooleanField("É exceção", default=False, db_index=True)
    date        = models.DateField("Data", db_index=True)
    time        = models.TimeField("Hora")
    timestamp   = models.DateTimeField("Criado em", auto_now_add=True)
    created_by  = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="care_records",
        null=True, blank=True, db_index=True
    )
    status = models.CharField(
        "Status", max_length=10, choices=Status.choices,
        default=Status.PENDING, db_index=True
    )

    class Meta:
        ordering = ["-date", "-time"]
        indexes = [models.Index(fields=["patient", "date"])]

    def __str__(self):
        return f"{self.get_type_display()} • {self.patient} • {self.date} {self.time}"

    @property
    def is_from_series(self) -> bool:
        """Retorna True se o registro pertence a uma série recorrente."""
        return bool(self.recurrence_group)

    @property
    def author_name(self) -> str:
        if self.created_by:
            profile = getattr(self.created_by, "profile", None)
            if profile and profile.full_name:
                return profile.full_name
            full = (self.created_by.get_full_name() or "").strip()
            if full:
                return full
            if self.created_by.username:
                return humanize_identifier(self.created_by.username)
        return humanize_identifier(self.caregiver)

    @property
    def medication_detail(self) -> str:
        if self.type != CareRecord.Type.MEDICATION:
            return ""
        qty = self.capsule_quantity
        if self.medication:
            name = (self.medication.name or "").strip()
            dosage = (self.medication.dosage or "").strip()
            parts: list[str] = []
            if name:
                parts.append(f"Remédio: {name}")
            if dosage:
                parts.append(f"Dosagem: {dosage}")
            if qty is not None:
                parts.append(f"Qtd: {qty}")
            return " • ".join(parts)
        if self.what:
            text = self.what.strip()
            if qty is not None:
                return f"Remédio/Dose: {text} • Qtd: {qty}"
            return f"Remédio/Dose: {text}"
        if qty is not None:
            return f"Qtd: {qty}"
        return ""

    def save(self, *args, **kwargs):
        """
        Na criação: se o registro é para HOJE e a hora informada já passou,
        salva automaticamente como 'Realizada'.
        """
        if not self.pk:
            today = timezone.localdate()
            now_t = timezone.localtime().time()
            if (
                self.status in (None, "", CareRecord.Status.PENDING)
                and self.date == today
                and self.time is not None
                and self.time < now_t
            ):
                self.status = CareRecord.Status.DONE
        super().save(*args, **kwargs)


class RecordReaction(models.Model):
    class Reaction(models.TextChoices):
        HEART = "heart", "Carinho"
        CLAP  = "clap",  "Aplauso"
        PRAY  = "pray",  "Força"

    record = models.ForeignKey(CareRecord, on_delete=models.CASCADE, related_name="reactions")
    user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="record_reactions")
    reaction = models.CharField(max_length=20, choices=Reaction.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("record", "user")

    def __str__(self):
        return f"{self.get_reaction_display()} • {self.user}"


class RecordComment(models.Model):
    record = models.ForeignKey(CareRecord, on_delete=models.CASCADE, related_name="comments")
    user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name="record_comments")
    text   = models.TextField("Comentário")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comentário de {self.user}"
