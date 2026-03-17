from django.db import transaction
from django.db.models import Sum, F, Value, IntegerField, OuterRef, Subquery, Q
from django.db.models.functions import Coalesce
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from care.models import Medication, MedicationStockEntry, CareRecord, GroupMembership
from api.permissions import HasGroupMembership
from api.serializers.care import (
    MedicationSerializer,
    MedicationWithStockSerializer,
    MedicationStockEntrySerializer,
)


def _get_group(user):
    try:
        return user.group_membership.group
    except (GroupMembership.DoesNotExist, AttributeError):
        return None


class MedicationViewSet(viewsets.ModelViewSet):
    serializer_class = MedicationSerializer
    permission_classes = [IsAuthenticated, HasGroupMembership]

    def get_queryset(self):
        group = _get_group(self.request.user)
        if not group:
            return Medication.objects.none()
        return Medication.objects.filter(group=group).order_by("name", "dosage")

    def perform_create(self, serializer):
        group = _get_group(self.request.user)
        serializer.save(group=group, created_by=self.request.user)

    # POST /{id}/add_stock/
    @action(detail=True, methods=["post"], url_path="add_stock")
    def add_stock(self, request, pk=None):
        medication = self.get_object()
        quantity = request.data.get("quantity")
        if not quantity or int(quantity) < 1:
            return Response(
                {"detail": "Quantidade deve ser >= 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry = MedicationStockEntry.objects.create(
            medication=medication,
            quantity=int(quantity),
            created_by=request.user,
        )
        return Response(MedicationStockEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    # GET /medications/stock_overview/
    @action(detail=False, methods=["get"], url_path="stock_overview")
    def stock_overview(self, request):
        group = _get_group(request.user)
        if not group:
            return Response({"sections": []})

        zero = Value(0, output_field=IntegerField())
        stock_sum = (
            MedicationStockEntry.objects
            .filter(medication=OuterRef("pk"))
            .values("medication")
            .annotate(total=Sum("quantity"))
            .values("total")[:1]
        )
        used_sum = (
            CareRecord.objects
            .filter(
                medication=OuterRef("pk"),
                status=CareRecord.Status.DONE,
                type=CareRecord.Type.MEDICATION,
            )
            .values("medication")
            .annotate(total=Sum("capsule_quantity"))
            .values("total")[:1]
        )
        medications = (
            Medication.objects.filter(group=group)
            .annotate(
                total_added=Coalesce(Subquery(stock_sum, output_field=IntegerField()), zero),
                total_used=Coalesce(Subquery(used_sum, output_field=IntegerField()), zero),
            )
            .annotate(current_stock=F("total_added") - F("total_used"))
            .order_by("name", "dosage")
        )

        q = (request.query_params.get("q") or "").strip()
        if q:
            medications = medications.filter(
                Q(name__icontains=q) | Q(dosage__icontains=q)
            )

        data = MedicationWithStockSerializer(medications, many=True).data

        # Group by status
        sections = {"danger": [], "warn": [], "ok": []}
        for item in data:
            sections[item["status"]].append(item)

        result = []
        for key, title in [("danger", "Sem estoque"), ("warn", "Estoque baixo"), ("ok", "Em estoque")]:
            if sections[key]:
                result.append({"key": key, "title": title, "items": sections[key]})

        return Response({"sections": result})
