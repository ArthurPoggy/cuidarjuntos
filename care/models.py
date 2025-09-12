# care/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q

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

    def __str__(self):
        return f"{self.name} • Paciente: {self.patient.name}"


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


class CareRecord(models.Model):
    class Type(models.TextChoices):
        MEDICATION = "medication", "Medicação"
        MEAL       = "meal",       "Alimentação"
        VITAL      = "vital",      "Sinais Vitais"
        ACTIVITY   = "activity",   "Atividade"
        SLEEP      = "sleep",      "Sono"
        BATHROOM   = "bathroom",   "Banheiro"
        OTHER      = "other",      "Outros"

    patient     = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="records")
    caregiver   = models.CharField("Cuidador", max_length=120)
    type        = models.CharField("Tipo", max_length=20, choices=Type.choices, default=Type.MEDICATION)
    what        = models.CharField("O que", max_length=200)
    description = models.TextField("Descrição", blank=True)
    date        = models.DateField("Data", db_index=True)
    time        = models.TimeField("Hora")
    timestamp   = models.DateTimeField("Criado em", auto_now_add=True)
    created_by  = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="care_records",
        null=True, blank=True, db_index=True
    )

    class Meta:
        ordering = ["-date", "-time"]
        indexes = [models.Index(fields=["patient", "date"])]

    def __str__(self):
        return f"{self.get_type_display()} • {self.patient} • {self.date} {self.time}"
