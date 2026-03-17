import csv
from datetime import date as dt_date, datetime, timedelta, time as dt_time

from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from care.models import (
    CareRecord, CareGroup, GroupMembership,
    RecordReaction, RecordComment,
    Patient, Medication, MedicationStockEntry,
)
from care.utils import sync_recurrence_series
from api.permissions import HasGroupMembership, IsRecordOwnerOrSuperuser
from api.serializers.care import (
    CareRecordSerializer, RecordReactionSerializer, RecordCommentSerializer,
)


def _get_patient(user):
    try:
        mem = user.group_membership
        return mem.group.patient
    except (GroupMembership.DoesNotExist, AttributeError):
        return None


def _display_name(user):
    profile = getattr(user, "profile", None)
    if profile and profile.full_name:
        return profile.full_name
    full = (user.get_full_name() or "").strip()
    return full or user.username


def _parse_time_flex(s):
    s = (s or "").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


CATEGORY_META = {
    "medication": {"label": "Remedio", "icon": "pill"},
    "sleep": {"label": "Sono", "icon": "moon"},
    "meal": {"label": "Alimentacao", "icon": "utensils"},
    "bathroom": {"label": "Banheiro", "icon": "bath"},
    "activity": {"label": "Exercicio", "icon": "running"},
    "vital": {"label": "Sinais Vitais", "icon": "heart"},
    "progress": {"label": "Evolucao/Regressao", "icon": "chart"},
    "other": {"label": "Outros", "icon": "plus"},
}

REACTION_CODES = [r.value for r in RecordReaction.Reaction]


def _build_social_summary(record_ids, user):
    summary = {
        rid: {"counts": {c: 0 for c in REACTION_CODES}, "user": "", "comments": 0}
        for rid in record_ids
    }
    if not record_ids:
        return summary

    for row in (
        RecordReaction.objects.filter(record_id__in=record_ids)
        .values("record_id", "reaction")
        .annotate(total=Count("id"))
    ):
        rid = row["record_id"]
        if rid in summary:
            summary[rid]["counts"][row["reaction"]] = row["total"]

    if user and user.is_authenticated:
        for row in (
            RecordReaction.objects.filter(record_id__in=record_ids, user=user)
            .values("record_id", "reaction")
        ):
            rid = row["record_id"]
            if rid in summary:
                summary[rid]["user"] = row["reaction"]

    for row in (
        RecordComment.objects.filter(record_id__in=record_ids)
        .values("record_id")
        .annotate(total=Count("id"))
    ):
        rid = row["record_id"]
        if rid in summary:
            summary[rid]["comments"] = row["total"]

    return summary


class CareRecordViewSet(viewsets.ModelViewSet):
    serializer_class = CareRecordSerializer
    permission_classes = [IsAuthenticated, HasGroupMembership]

    def get_queryset(self):
        patient = _get_patient(self.request.user)
        if not patient:
            return CareRecord.objects.none()
        return (
            CareRecord.objects
            .filter(patient=patient)
            .select_related("patient", "medication", "created_by", "created_by__profile")
            .order_by("-date", "-time")
        )

    def perform_create(self, serializer):
        patient = _get_patient(self.request.user)
        instance = serializer.save(
            patient=patient,
            created_by=self.request.user,
            caregiver=_display_name(self.request.user),
        )
        sync_recurrence_series(instance)

    def perform_update(self, serializer):
        original = CareRecord.objects.filter(pk=serializer.instance.pk).only("recurrence_group").first()
        prev_group = original.recurrence_group if original else None
        instance = serializer.save()
        sync_recurrence_series(instance, previous_group=prev_group)

    # POST /{id}/set_status/
    @action(detail=True, methods=["post"], url_path="set_status")
    def set_status(self, request, pk=None):
        record = self.get_object()
        new_status = (request.data.get("status") or "").strip()
        if new_status not in ("pending", "done", "missed"):
            return Response({"detail": "Status invalido."}, status=status.HTTP_400_BAD_REQUEST)

        reason = (request.data.get("reason") or "").strip() if new_status == "missed" else ""
        if new_status == "missed" and not reason:
            return Response(
                {"code": "REASON_REQUIRED", "message": "Informe o motivo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()
        now_t = timezone.localtime().time()

        if new_status == "done":
            new_date_str = (request.data.get("date") or "").strip()
            new_time_str = (request.data.get("time") or "").strip()
            if not (new_date_str and new_time_str):
                return Response(
                    {"code": "TIME_REQUIRED", "message": "Informe data e horario."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                new_date = dt_date.fromisoformat(new_date_str)
            except Exception:
                return Response({"detail": "Data invalida."}, status=status.HTTP_400_BAD_REQUEST)
            new_time = _parse_time_flex(new_time_str)
            if not new_time:
                return Response({"detail": "Hora invalida."}, status=status.HTTP_400_BAD_REQUEST)
            if new_date > today or (new_date == today and new_time > now_t):
                return Response(
                    {"code": "TIME_IN_FUTURE", "message": "Data/hora deve ser no passado ou agora."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            record.date = new_date
            record.time = new_time
            record.created_by = request.user
            record.caregiver = _display_name(request.user)

        record.status = new_status
        record.missed_reason = reason if new_status == "missed" else ""

        if new_status == "done":
            record.save(update_fields=["date", "time", "status", "missed_reason", "created_by", "caregiver"])
        else:
            record.save(update_fields=["status", "missed_reason"])

        if new_status == "missed" and reason:
            RecordComment.objects.create(
                record=record, user=request.user,
                text=f"Motivo do nao realizado: {reason}",
            )

        return Response({"ok": True, "status": record.status})

    # POST /{id}/react/
    @action(detail=True, methods=["post"])
    def react(self, request, pk=None):
        record = self.get_object()
        reaction_code = (request.data.get("reaction") or "").strip()
        valid = {r.value for r in RecordReaction.Reaction}
        if reaction_code not in valid:
            return Response({"detail": "Reacao invalida."}, status=status.HTTP_400_BAD_REQUEST)

        obj, created = RecordReaction.objects.get_or_create(
            record=record, user=request.user,
            defaults={"reaction": reaction_code},
        )
        if not created and obj.reaction == reaction_code:
            obj.delete()
            user_reaction = ""
        else:
            if not created:
                obj.reaction = reaction_code
            obj.save()
            user_reaction = reaction_code

        summary = _build_social_summary({record.pk}, request.user)
        data = summary.get(record.pk, {})
        return Response({
            "ok": True,
            "counts": data.get("counts", {}),
            "user_reaction": user_reaction or data.get("user", ""),
            "comments": data.get("comments", 0),
        })

    # GET|POST /{id}/comments/
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        record = self.get_object()
        if request.method == "POST":
            text = (request.data.get("text") or "").strip()
            if len(text) < 2:
                return Response({"detail": "Comentario muito curto."}, status=status.HTTP_400_BAD_REQUEST)
            comment = RecordComment.objects.create(record=record, user=request.user, text=text)
            return Response(RecordCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

        comments = (
            RecordComment.objects.filter(record=record)
            .select_related("user", "user__profile")
            .order_by("created_at")
        )
        return Response(RecordCommentSerializer(comments, many=True).data)

    # POST /{id}/cancel_following/
    @action(detail=True, methods=["post"], url_path="cancel_following")
    def cancel_following(self, request, pk=None):
        record = self.get_object()
        if record.created_by_id != request.user.id and not request.user.is_superuser:
            return Response({"detail": "Sem permissao."}, status=status.HTTP_403_FORBIDDEN)

        if record.recurrence_group:
            cond = Q(date__gt=record.date)
            if record.time:
                cond |= Q(date=record.date, time__gte=record.time)
            else:
                cond |= Q(date=record.date)
            qs = CareRecord.objects.filter(
                patient=record.patient, recurrence_group=record.recurrence_group
            ).filter(cond)
            deleted, _ = qs.delete()
            base_deleted, _ = CareRecord.objects.filter(pk=record.pk).delete()
            deleted += base_deleted
        else:
            CareRecord.objects.filter(pk=record.pk).delete()
            deleted = 1

        return Response({"ok": True, "deleted": deleted})

    # POST /records/bulk_set_status/
    @action(detail=False, methods=["post"], url_path="bulk_set_status")
    def bulk_set_status(self, request):
        patient = _get_patient(request.user)
        if not patient:
            return Response({"detail": "Sem grupo."}, status=status.HTTP_400_BAD_REQUEST)

        ids = request.data.get("ids", [])
        new_status = request.data.get("status")
        if new_status not in ("done", "missed"):
            return Response({"detail": "Status invalido."}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(ids, list) or not ids:
            return Response({"detail": "IDs obrigatorios."}, status=status.HTTP_400_BAD_REQUEST)

        qs = CareRecord.objects.filter(pk__in=ids, patient=patient)
        updated_ids = list(qs.values_list("id", flat=True))

        if new_status == "done":
            date_str = (request.data.get("date") or "").strip()
            time_str = (request.data.get("time") or "").strip()
            if not (date_str and time_str):
                return Response(
                    {"code": "TIME_REQUIRED", "message": "Informe data e horario."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                new_date = dt_date.fromisoformat(date_str)
            except Exception:
                return Response({"detail": "Data invalida."}, status=status.HTTP_400_BAD_REQUEST)
            new_time = _parse_time_flex(time_str)
            if not new_time:
                return Response({"detail": "Hora invalida."}, status=status.HTTP_400_BAD_REQUEST)

            today = timezone.localdate()
            now_t = timezone.localtime().time()
            if new_date > today or (new_date == today and new_time > now_t):
                return Response(
                    {"code": "TIME_IN_FUTURE", "message": "Data/hora deve ser passado ou agora."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs.update(
                status=new_status,
                created_by_id=request.user.id,
                caregiver=_display_name(request.user),
                date=new_date,
                time=new_time,
            )
        else:
            qs.update(status=new_status)

        return Response({"ok": True, "updated": updated_ids, "status": new_status})

    # POST /records/reschedule/
    @action(detail=False, methods=["post"])
    def reschedule(self, request):
        patient = _get_patient(request.user)
        if not patient:
            return Response({"detail": "Sem grupo."}, status=status.HTTP_400_BAD_REQUEST)

        rid = request.data.get("id")
        rdate_str = request.data.get("date")
        rtime_str = request.data.get("time")
        if not (rid and rdate_str and rtime_str):
            return Response({"detail": "Parametros obrigatorios."}, status=status.HTTP_400_BAD_REQUEST)

        rdate = parse_date(rdate_str)
        if not rdate:
            return Response({"detail": "Data invalida."}, status=status.HTTP_400_BAD_REQUEST)

        rtime = _parse_time_flex(rtime_str)
        if not rtime:
            return Response({"detail": "Hora invalida."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rec = CareRecord.objects.get(pk=rid, patient=patient)
        except CareRecord.DoesNotExist:
            return Response({"detail": "Registro nao encontrado."}, status=status.HTTP_404_NOT_FOUND)

        rec.date = rdate
        rec.time = rtime
        rec.save(update_fields=["date", "time"])
        return Response({"ok": True, "id": rec.id, "date": rec.date.isoformat(), "time": rec.time.strftime("%H:%M")})


# --- Standalone endpoints ---

@api_view(["GET"])
@permission_classes([IsAuthenticated, HasGroupMembership])
def dashboard_data(request):
    patient = _get_patient(request.user)
    if not patient:
        return Response({"detail": "Sem grupo."}, status=status.HTTP_400_BAD_REQUEST)

    today = timezone.localdate()
    now_dt = timezone.localtime()

    base_qs = CareRecord.objects.filter(patient=patient).select_related("medication")

    # Parse filters
    start_str = (request.query_params.get("start") or "").strip()
    end_str = (request.query_params.get("end") or "").strip()
    clear = request.query_params.get("clear", "") == "1"
    exceptions_only = request.query_params.get("exceptions", "") in ("1", "true")
    count_done_only = request.query_params.get("count_done_only", "") == "1"
    categories_str = (request.query_params.get("categories") or "").strip()
    selected_categories = [c for c in categories_str.split(",") if c in CATEGORY_META]

    start = parse_date(start_str) if start_str else None
    end = parse_date(end_str) if end_str else None
    if not start and not end and not clear:
        start = end = today

    if exceptions_only:
        base_qs = base_qs.filter(is_exception=True)

    qs = base_qs
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    if selected_categories:
        qs_cat = qs.filter(type__in=selected_categories)
    else:
        qs_cat = qs

    # Counts
    qs_for_counts = qs if (start or end) else base_qs
    if count_done_only:
        qs_for_counts = qs_for_counts.filter(status="done")
    else:
        qs_for_counts = qs_for_counts.exclude(status="missed")
    raw_counts = dict(qs_for_counts.values_list("type").annotate(total=Count("id")))
    counts = {k: raw_counts.get(k, 0) for k in CATEGORY_META}

    # Records
    records_qs = qs_cat.order_by("-date", "-time")[:200]
    records_data = CareRecordSerializer(records_qs, many=True, context={"request": request}).data

    # Upcoming
    upcoming_qs = (
        base_qs.filter(status="pending")
        .filter(
            Q(date__gt=today)
            | Q(date=today, time__isnull=True)
            | Q(date=today, time__gt=now_dt.time())
        )
    )
    if selected_categories:
        upcoming_qs = upcoming_qs.filter(type__in=selected_categories)
    upcoming_qs = upcoming_qs.order_by("date", "time")[:10]
    upcoming_data = CareRecordSerializer(upcoming_qs, many=True, context={"request": request}).data

    return Response({
        "counts": counts,
        "records": records_data,
        "upcoming": upcoming_data,
        "filters": {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "categories": selected_categories,
            "exceptions": exceptions_only,
            "count_done_only": count_done_only,
        },
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasGroupMembership])
def calendar_data(request):
    patient = _get_patient(request.user)
    if not patient:
        return Response({"detail": "Sem grupo."}, status=status.HTTP_400_BAD_REQUEST)

    from calendar import Calendar

    base_qs = CareRecord.objects.filter(patient=patient).select_related("medication")

    categories_str = (request.query_params.get("categories") or "").strip()
    selected_categories = [c for c in categories_str.split(",") if c in CATEGORY_META]
    exceptions_only = request.query_params.get("exceptions", "") in ("1", "true")
    if exceptions_only:
        base_qs = base_qs.filter(is_exception=True)
    if selected_categories:
        base_qs = base_qs.filter(type__in=selected_categories)

    month_str = request.query_params.get("m")
    month_ref = (parse_date(month_str) if month_str else None) or timezone.localdate()
    month_ref = month_ref.replace(day=1)
    year, month = month_ref.year, month_ref.month

    cal = Calendar(firstweekday=6)
    weeks = cal.monthdayscalendar(year, month)

    in_month_qs = base_qs.filter(date__year=year, date__month=month).order_by("date", "time")
    days_with = sorted(set(r.date.day for r in in_month_qs.only("date")))

    events_by_date = {}
    for r in in_month_qs:
        key = r.date.isoformat()
        events_by_date.setdefault(key, []).append({
            "type": r.type,
            "title": r.get_type_display(),
            "what": r.what or "",
            "time": r.time.strftime("%H:%M") if r.time else "",
            "who": r.caregiver or "",
        })

    MONTH_NAMES = [
        "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]

    return Response({
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES[month - 1],
        "weeks": weeks,
        "days_with": days_with,
        "today_iso": timezone.localdate().isoformat(),
        "events_by_date": events_by_date,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasGroupMembership])
def upcoming_data(request):
    patient = _get_patient(request.user)
    if not patient:
        return Response({"items": []})

    qs = CareRecord.objects.filter(patient=patient).select_related("medication")

    categories_str = (request.query_params.get("categories") or "").strip()
    selected_categories = [c for c in categories_str.split(",") if c in CATEGORY_META]
    exceptions_only = request.query_params.get("exceptions", "") in ("1", "true")
    if exceptions_only:
        qs = qs.filter(is_exception=True)
    if selected_categories:
        qs = qs.filter(type__in=selected_categories)

    include_done = request.query_params.get("include_done") == "1"
    include_missed = request.query_params.get("include_missed") == "1"
    statuses = ["pending"]
    if include_done:
        statuses.append("done")
    if include_missed:
        statuses.append("missed")
    qs = qs.filter(status__in=statuses)

    today = timezone.localdate()
    now_t = timezone.localtime().time()
    qs = qs.filter(
        Q(date__gt=today)
        | Q(date=today, time__isnull=True)
        | Q(date=today, time__gt=now_t)
    ).order_by("date", "time")

    try:
        limit = int(request.query_params.get("limit", 50))
    except ValueError:
        limit = 50

    data = CareRecordSerializer(qs[:limit], many=True, context={"request": request}).data
    return Response({"ok": True, "items": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasGroupMembership])
def upcoming_buckets(request):
    patient = _get_patient(request.user)
    if not patient:
        return Response({"ok": False}, status=status.HTTP_400_BAD_REQUEST)

    today = timezone.localdate()
    dfrom = parse_date(request.query_params.get("from", "")) or today
    dto = parse_date(request.query_params.get("to", "")) or (today + timedelta(days=7))

    if dto < dfrom:
        return Response({"ok": False, "message": "Periodo invalido."}, status=status.HTTP_400_BAD_REQUEST)

    types_str = (request.query_params.get("types") or "").strip()
    types = [t for t in types_str.split(",") if t] if types_str else None
    q = (request.query_params.get("q") or "").strip()
    include_done = request.query_params.get("include_done") == "1"
    include_missed = request.query_params.get("include_missed") == "1"

    qs = CareRecord.objects.filter(patient=patient, date__range=(dfrom, dto)).order_by("date", "time")
    if types:
        qs = qs.filter(type__in=types)
    if q:
        qs = qs.filter(Q(what__icontains=q) | Q(description__icontains=q) | Q(caregiver__icontains=q))

    if include_done and include_missed:
        pass
    elif include_done:
        qs = qs.filter(status__in=["pending", "done"])
    elif include_missed:
        qs = qs.filter(status__in=["pending", "missed"])
    else:
        qs = qs.filter(status="pending")
        now_t = timezone.localtime().time()
        qs = qs.exclude(Q(date=today) & Q(time__isnull=False) & Q(time__lte=now_t))

    totals = {"pending": 0, "done": 0, "missed": 0}
    for row in qs.values("status").annotate(total=Count("id")):
        totals[row["status"]] = row["total"]

    buckets = {}
    for r in qs:
        k = r.date.isoformat()
        buckets.setdefault(k, []).append({
            "id": r.id,
            "type": r.type,
            "title": f"{r.get_type_display()}" + (f" \u2022 {r.what}" if r.what else ""),
            "time": r.time.strftime("%H:%M") if r.time else "",
            "who": r.caregiver or "",
            "status": r.status,
            "series": bool(r.recurrence_group),
        })

    ordered = []
    cur = dfrom
    while cur <= dto:
        k = cur.isoformat()
        if buckets.get(k):
            ordered.append({"date_iso": k, "items": buckets[k]})
        cur += timedelta(days=1)

    return Response({
        "ok": True,
        "from": dfrom.isoformat(),
        "to": dto.isoformat(),
        "totals": totals,
        "buckets": ordered,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasGroupMembership])
def export_csv(request):
    patient = _get_patient(request.user)
    if not patient:
        return Response({"detail": "Sem grupo."}, status=status.HTTP_400_BAD_REQUEST)

    qs = CareRecord.objects.filter(patient=patient).select_related("patient")

    start_str = request.query_params.get("start")
    end_str = request.query_params.get("end")
    if start_str:
        start = parse_date(start_str)
        if start:
            qs = qs.filter(date__gte=start)
    if end_str:
        end = parse_date(end_str)
        if end:
            qs = qs.filter(date__lte=end)

    categories_str = (request.query_params.get("categories") or "").strip()
    if categories_str:
        cats = [c for c in categories_str.split(",") if c]
        qs = qs.filter(type__in=cats)

    qs = qs.order_by("date", "time")

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="registros.csv"'
    resp.write("\ufeff")
    w = csv.writer(resp)
    w.writerow(["Data", "Hora", "Categoria", "O que", "Observacoes", "Cuidador", "Paciente", "Classificacao", "Excecao?"])
    for r in qs:
        w.writerow([
            r.date.isoformat(),
            r.time.strftime("%H:%M") if r.time else "",
            r.get_type_display(),
            r.what or "",
            (r.description or "").replace("\r\n", " ").replace("\n", " "),
            r.caregiver or "",
            str(r.patient),
            r.get_progress_trend_display() if r.progress_trend else "",
            "Sim" if r.is_exception else "Nao",
        ])
    return resp
