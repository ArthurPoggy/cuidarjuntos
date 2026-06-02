from django.contrib import admin
from .models import Patient, CareRecord, Medication, MedicationStockEntry, ChecklistItem, PushToken

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


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ["title", "group", "date", "done", "assigned_to", "created_by", "created_at"]
    list_filter = ["done", "date"]
    search_fields = ["title"]


@admin.register(PushToken)
class PushTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "platform", "created_at", "last_used_at")
    list_filter = ("platform",)
    search_fields = ("user__username", "token")
