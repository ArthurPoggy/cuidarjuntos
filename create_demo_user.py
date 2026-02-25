#!/usr/bin/env python
"""Script para criar usuário demo/visitante"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cuidarjuntos.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Profile
from care.models import CareGroup, Patient, GroupMembership
from datetime import date

def create_demo_user():
    username = "visitante"

    if User.objects.filter(username=username).exists():
        print("[OK] Usuário demo já existe!")
        print(f"   Username: visitante")
        print(f"   Password: demo123")
        print(f"   PIN: 1234")
        return

    # Criar usuário
    user = User.objects.create_user(
        username=username,
        password="demo123",
        email="visitante@cuidarjuntos.app"
    )

    # Atualizar perfil (criado automaticamente)
    profile = user.profile
    profile.full_name = "Visitante Demo"
    profile.cpf = "00000000000"
    profile.birth_date = date(1990, 1, 1)
    profile.role = "FAMILY"
    profile.save()

    # Criar paciente
    patient = Patient.objects.create(
        name="Paciente Demo",
        birth_date=date(1950, 1, 1)
    )

    # Criar grupo
    group = CareGroup.objects.create(
        name="Grupo Demo",
        patient=patient,
        created_by=user
    )
    group.set_join_code("1234")
    group.save()

    # Adicionar membro ao grupo
    GroupMembership.objects.create(
        user=user,
        group=group,
        relation_to_patient="Visitante"
    )

    print("[OK] Usuário demo criado com sucesso!")
    print(f"   Username: visitante")
    print(f"   Password: demo123")
    print(f"   Grupo: Grupo Demo")
    print(f"   PIN: 1234")

if __name__ == "__main__":
    create_demo_user()
