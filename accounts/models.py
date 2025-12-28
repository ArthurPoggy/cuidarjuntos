# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    ROLE_CHOICES = [
        ("PATIENT", "Paciente"),
        ("FAMILY",  "Familiar"),
        ("DOCTOR",  "Médico"),
        ("ADMIN",   "Admin"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="FAMILY")

    # >>> novos campos <<<
    full_name  = models.CharField("Nome completo", max_length=150, blank=True)
    birth_date = models.DateField("Data de nascimento", null=True, blank=True)
    # CPF armazenado apenas com dígitos, único mas opcional
    cpf = models.CharField("CPF", max_length=11, unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, "profile"):
        Profile.objects.create(user=instance)
