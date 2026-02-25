#!/usr/bin/env python
"""Script para criar dados de exemplo para o usuário visitante"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cuidarjuntos.settings')
django.setup()

from django.contrib.auth.models import User
from care.models import CareRecord, Medication, MedicationStockEntry
from datetime import date, time, timedelta

def create_demo_data():
    # Obter usuário visitante
    try:
        user = User.objects.get(username="visitante")
    except User.DoesNotExist:
        print("[ERRO] Usuario visitante nao encontrado. Execute create_demo_user.py primeiro.")
        return

    # Obter grupo e paciente
    from care.models import GroupMembership
    try:
        membership = GroupMembership.objects.get(user=user)
        group = membership.group
        patient = group.patient
    except GroupMembership.DoesNotExist:
        print("[ERRO] Visitante nao pertence a nenhum grupo.")
        return

    print(f"[OK] Criando dados de exemplo para {user.username}...")

    # Criar medicamentos
    med1, _ = Medication.objects.get_or_create(
        group=group,
        name="Paracetamol",
        defaults={'dosage': '500mg', 'created_by': user}
    )

    med2, _ = Medication.objects.get_or_create(
        group=group,
        name="Omeprazol",
        defaults={'dosage': '20mg', 'created_by': user}
    )

    # Adicionar estoque
    MedicationStockEntry.objects.get_or_create(
        medication=med1,
        quantity=30,
        defaults={'created_by': user}
    )

    MedicationStockEntry.objects.get_or_create(
        medication=med2,
        quantity=15,
        defaults={'created_by': user}
    )

    # Criar registros de cuidado (últimos 7 dias)
    today = date.today()

    # Medicação
    for i in range(7):
        day = today - timedelta(days=i)
        CareRecord.objects.get_or_create(
            patient=patient,
            created_by=user,
            type='medication',
            date=day,
            time=time(8, 0),
            defaults={
                'what': 'Paracetamol 500mg',
                'medication': med1,
                'capsule_quantity': 1,
                'status': 'done' if i < 3 else 'pending',
                'caregiver': user.profile.full_name
            }
        )

    # Refeições
    for i in range(3):
        day = today - timedelta(days=i)
        CareRecord.objects.get_or_create(
            patient=patient,
            created_by=user,
            type='meal',
            date=day,
            time=time(12, 0),
            defaults={
                'what': 'Almoco - Boa aceitacao',
                'status': 'done',
                'caregiver': user.profile.full_name
            }
        )

    # Sinais vitais
    CareRecord.objects.get_or_create(
        patient=patient,
        created_by=user,
        type='vital',
        date=today,
        time=time(9, 0),
        defaults={
            'what': 'Pressao Arterial - Normal',
            'status': 'done',
            'caregiver': user.profile.full_name
        }
    )

    # Sono
    CareRecord.objects.get_or_create(
        patient=patient,
        created_by=user,
        type='sleep',
        date=today,
        time=time(22, 0),
        defaults={
            'what': 'Dormiu',
            'status': 'pending',
            'caregiver': user.profile.full_name
        }
    )

    # Atividade
    CareRecord.objects.get_or_create(
        patient=patient,
        created_by=user,
        type='activity',
        date=today - timedelta(days=1),
        time=time(15, 0),
        defaults={
            'what': 'Caminhada no parque',
            'description': 'Caminhada de 20 minutos',
            'status': 'done',
            'caregiver': user.profile.full_name
        }
    )

    # Banheiro
    CareRecord.objects.get_or_create(
        patient=patient,
        created_by=user,
        type='bathroom',
        date=today,
        time=time(7, 30),
        defaults={
            'what': 'Banho',
            'status': 'done',
            'caregiver': user.profile.full_name
        }
    )

    print("[OK] Dados de exemplo criados!")
    print(f"   - 2 medicamentos")
    print(f"   - ~15 registros de cuidado")
    print("")
    print("Agora voce pode fazer login como visitante e ver os dados!")

if __name__ == "__main__":
    create_demo_data()
