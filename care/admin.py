from django.contrib import admin
from .models import (
    Patient, CareRecord, Medication, MedicationStockEntry, ChecklistItem,
    Notification, PushToken, ChatMessage, ChatConsent,
)

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "birth_date")
    search_fields = ("name",)

@admin.register(CareRecord)
class CareRecordAdmin(admin.ModelAdmin):
    # Exclusao logica: exibe tambem registros excluidos para permitir
    # auditoria (quem excluiu e quando), sem oferecer restauracao aqui.
    list_display = ("id", "patient", "type", "what", "date", "time", "caregiver", "deleted_at", "deleted_by")
    list_filter = ("type", "date", "patient", "deleted_at")
    search_fields = ("what", "description", "caregiver")
    readonly_fields = ("deleted_at", "deleted_by")

    def get_queryset(self, request):
        return CareRecord.all_objects.all()

    def has_delete_permission(self, request, obj=None):
        # Exclusao fisica desabilitada no admin: a exclusao deste registro
        # e sempre logica (deleted_at/deleted_by), feita pela aplicacao.
        return False


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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "read", "created_at")
    list_filter = ("read",)
    search_fields = ("title", "body", "user__username")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(PushToken)
class PushTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "platform", "created_at", "last_used_at")
    list_filter = ("platform",)
    search_fields = ("user__username", "token")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    # Privacidade: 'content' guarda texto de conversas clínicas com a IA.
    # Não é exposto em busca; é somente-leitura no admin para evitar edição.
    list_display = ("id", "user", "group", "role", "created_at")
    list_filter = ("role", "group", "created_at")
    search_fields = ("user__username",)
    readonly_fields = ("user", "group", "role", "content", "created_at")
    date_hierarchy = "created_at"


@admin.register(ChatConsent)
class ChatConsentAdmin(admin.ModelAdmin):
    # Registro de aceite: serve como trilha de auditoria, então é somente-leitura
    # aqui (conceder/revogar é ação do próprio usuário, pelo app).
    list_display = ("id", "user", "group", "version", "accepted_at")
    list_filter = ("version", "group")
    search_fields = ("user__username",)
    readonly_fields = ("user", "group", "version", "accepted_at")
    date_hierarchy = "accepted_at"
