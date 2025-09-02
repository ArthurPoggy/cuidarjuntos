from django.db import models
from django.contrib.auth.models import User  # <- novo

class Patient(models.Model):
    name = models.CharField("Nome", max_length=120)
    birth_date = models.DateField("Nascimento", null=True, blank=True)
    notes = models.TextField("Observações", blank=True)
    created_by = models.ForeignKey(  # <- novo
        User, on_delete=models.CASCADE, related_name='patients',
        null=True, blank=True, db_index=True
    )

    def __str__(self):
        return self.name


class CareRecord(models.Model):
    class Type(models.TextChoices):
        MEDICATION = 'medication', 'Medicação'
        MEAL       = 'meal',       'Alimentação'
        VITAL      = 'vital',      'Sinais Vitais'
        ACTIVITY   = 'activity',   'Atividade'
        SLEEP      = 'sleep',      'Sono'
        BATHROOM   = 'bathroom',   'Banheiro'
        OTHER      = 'other',      'Outros'

    patient     = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='records')
    caregiver   = models.CharField("Cuidador", max_length=120)
    type        = models.CharField("Tipo", max_length=20, choices=Type.choices, default=Type.MEDICATION)
    what        = models.CharField("O que", max_length=200)
    description = models.TextField("Descrição", blank=True)
    date        = models.DateField("Data", db_index=True)
    time        = models.TimeField("Hora")
    timestamp   = models.DateTimeField("Criado em", auto_now_add=True)
    created_by  = models.ForeignKey(  # <- novo
        User, on_delete=models.CASCADE, related_name='care_records',
        null=True, blank=True, db_index=True
    )

    class Meta:
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.get_type_display()} • {self.patient} • {self.date} {self.time}"
