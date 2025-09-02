from django.contrib import admin
from .models import Patient, CareRecord

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "birth_date")
    search_fields = ("name",)

@admin.register(CareRecord)
class CareRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "type", "what", "date", "time", "caregiver")
    list_filter = ("type", "date", "patient")
    search_fields = ("what", "description", "caregiver")
