#!/usr/bin/env python
"""Cria (ou recria) o usuário demo 'visitante' para o login de visitante.

Idempotente: remove qualquer estado anterior do demo antes de recriar, para
poder rodar quantas vezes precisar sem colisões. O CPF fica nulo de propósito
(é opcional) para não conflitar com cadastros existentes.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cuidarjuntos.settings')
django.setup()

from django.contrib.auth.models import User
from care.models import CareGroup, Patient, GroupMembership
from datetime import date


def create_demo_user():
    # Limpa estado anterior (inclusive um 'visitante' meio-criado) para recriar do zero.
    User.objects.filter(username="visitante").delete()
    CareGroup.objects.filter(name="Grupo Demo").delete()
    Patient.objects.filter(name="Paciente Demo").delete()

    user = User.objects.create_user(
        username="visitante",
        password="demo123",
        email="visitante@cuidarjuntos.app",
    )

    profile = user.profile  # criado automaticamente pelo signal
    profile.full_name = "Visitante Demo"
    profile.birth_date = date(1990, 1, 1)
    profile.role = "FAMILY"
    profile.cpf = None  # CPF é opcional; nulo evita colisão de unicidade
    profile.save()

    patient = Patient.objects.create(
        name="Paciente Demo",
        birth_date=date(1950, 1, 1),
        created_by=user,
    )

    group = CareGroup.objects.create(
        name="Grupo Demo",
        patient=patient,
        created_by=user,
    )
    group.set_join_code("1234")
    group.save()

    GroupMembership.objects.create(
        user=user,
        group=group,
        relation_to_patient="FAMILY",
    )

    print("[OK] Usuário demo criado com sucesso!")
    print("   Username: visitante")
    print("   Password: demo123")
    print(f"   Grupo: {group.name}")
    print("   PIN: 1234")


if __name__ == "__main__":
    create_demo_user()
