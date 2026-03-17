from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Profile
from care.models import Patient, CareGroup, CareRecord, GroupMembership
from api.permissions import IsSuperUser
from api.serializers.admin import AdminUserSerializer


@api_view(["GET"])
@permission_classes([IsSuperUser])
def admin_overview(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    # Users
    users_total = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    superusers_total = User.objects.filter(is_superuser=True).count()
    inactive_users = users_total - active_users
    new_users_month = User.objects.filter(date_joined__date__gte=month_start).count()

    role_labels = dict(Profile.ROLE_CHOICES)
    role_breakdown = [
        {"role": row["role"], "label": role_labels.get(row["role"], row["role"]), "total": row["total"]}
        for row in Profile.objects.values("role").annotate(total=Count("id")).order_by("-total")
    ]

    # Patients/Groups
    patients_total = Patient.objects.count()
    patients_with_group = Patient.objects.filter(care_group__isnull=False).count()
    patients_without_group = max(patients_total - patients_with_group, 0)
    patients_active_week = Patient.objects.filter(records__date__gte=week_start).distinct().count()

    groups_total = CareGroup.objects.count()
    groups_without_members = (
        CareGroup.objects.annotate(total_members=Count("members")).filter(total_members=0).count()
    )

    # Records
    record_totals = CareRecord.objects.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=CareRecord.Status.PENDING)),
        done=Count("id", filter=Q(status=CareRecord.Status.DONE)),
        missed=Count("id", filter=Q(status=CareRecord.Status.MISSED)),
    )
    links_total = GroupMembership.objects.count()

    type_labels = dict(CareRecord.Type.choices)
    by_type = [
        {"code": row["type"], "label": type_labels.get(row["type"], row["type"]), "total": row["total"]}
        for row in CareRecord.objects.values("type").annotate(total=Count("id")).order_by("-total")
    ]

    relation_labels = dict(GroupMembership.REL_CHOICES)
    relation_breakdown = [
        {
            "code": row["relation_to_patient"],
            "label": relation_labels.get(row["relation_to_patient"], row["relation_to_patient"]),
            "total": row["total"],
        }
        for row in GroupMembership.objects.values("relation_to_patient").annotate(total=Count("id")).order_by("-total")
    ]

    # Daily series
    daily_rows = {
        row["date"]: row
        for row in (
            CareRecord.objects.filter(date__gte=week_start, date__lte=today)
            .values("date")
            .annotate(
                total=Count("id"),
                done=Count("id", filter=Q(status=CareRecord.Status.DONE)),
                pending=Count("id", filter=Q(status=CareRecord.Status.PENDING)),
                missed=Count("id", filter=Q(status=CareRecord.Status.MISSED)),
            )
        )
    }
    daily_series = []
    cursor = week_start
    while cursor <= today:
        row = daily_rows.get(cursor, {})
        daily_series.append({
            "label": cursor.strftime("%d/%m"),
            "date": cursor.isoformat(),
            "total": row.get("total", 0),
            "done": row.get("done", 0),
            "pending": row.get("pending", 0),
            "missed": row.get("missed", 0),
        })
        cursor += timedelta(days=1)

    # User list
    search = (request.query_params.get("q") or "").strip()
    status_filter = (request.query_params.get("status") or "all").lower()
    user_qs = (
        User.objects
        .select_related("profile", "group_membership__group")
        .annotate(records_total=Count("care_records", distinct=True))
    )
    if search:
        user_qs = user_qs.filter(
            Q(username__icontains=search) | Q(email__icontains=search)
            | Q(first_name__icontains=search) | Q(last_name__icontains=search)
            | Q(profile__full_name__icontains=search)
        )
    if status_filter == "inactive":
        user_qs = user_qs.filter(is_active=False)
    elif status_filter == "staff":
        user_qs = user_qs.filter(is_staff=True)
    elif status_filter == "superuser":
        user_qs = user_qs.filter(is_superuser=True)
    elif status_filter == "no-group":
        user_qs = user_qs.filter(group_membership__isnull=True)
    user_qs = user_qs.order_by("-date_joined")

    users_data = AdminUserSerializer(user_qs[:50], many=True).data

    alerts = {
        "patients_without_group": patients_without_group,
        "groups_without_members": groups_without_members,
        "inactive_users": inactive_users,
    }

    return Response({
        "users": {
            "total": users_total,
            "active": active_users,
            "staff": staff_users,
            "superusers": superusers_total,
            "inactive": inactive_users,
            "new_this_month": new_users_month,
            "list": users_data,
        },
        "patients": {
            "total": patients_total,
            "active_week": patients_active_week,
            "without_group": patients_without_group,
        },
        "groups": {
            "total": groups_total,
            "without_members": groups_without_members,
            "links_total": links_total,
        },
        "records": {
            **record_totals,
            "by_type": by_type,
        },
        "role_breakdown": role_breakdown,
        "relation_breakdown": relation_breakdown,
        "daily_series": daily_series,
        "alerts": alerts,
    })
