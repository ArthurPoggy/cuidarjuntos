from django.contrib import admin
from .models import Patient, CareRecord, Medication, MedicationStockEntry

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "birth_date")
    search_fields = ("name",)

@admin.register(CareRecord)
class CareRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "type", "what", "date", "time", "caregiver")
    list_filter = ("type", "date", "patient")
    search_fields = ("what", "description", "caregiver")


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "name", "dosage", "created_at")
    search_fields = ("name", "dosage")
    list_filter = ("group",)


@admin.register(MedicationStockEntry)
class MedicationStockEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "medication", "quantity", "created_at", "created_by")
    list_filter = ("medication",)
