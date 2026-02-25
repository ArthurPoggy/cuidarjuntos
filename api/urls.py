from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views.auth import register, me
from .views.groups import group_create, group_join, group_leave, group_current, group_list
from .views.care import (
    CareRecordViewSet, dashboard_data, calendar_data,
    upcoming_data, upcoming_buckets, export_csv,
)
from .views.medications import MedicationViewSet
from .views.admin import admin_overview

router = DefaultRouter()
router.register(r"records", CareRecordViewSet, basename="record")
router.register(r"medications", MedicationViewSet, basename="medication")

app_name = "api"

urlpatterns = [
    # Auth
    path("auth/register/", register, name="register"),
    path("auth/me/", me, name="me"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Groups
    path("groups/", group_list, name="group-list"),
    path("groups/create/", group_create, name="group-create"),
    path("groups/join/", group_join, name="group-join"),
    path("groups/leave/", group_leave, name="group-leave"),
    path("groups/current/", group_current, name="group-current"),

    # Dashboard / Calendar / Upcoming
    path("dashboard/", dashboard_data, name="dashboard"),
    path("calendar/", calendar_data, name="calendar"),
    path("upcoming/", upcoming_data, name="upcoming"),
    path("upcoming/buckets/", upcoming_buckets, name="upcoming-buckets"),

    # Export
    path("export/csv/", export_csv, name="export-csv"),

    # Admin
    path("admin/overview/", admin_overview, name="admin-overview"),

    # Schema / Docs
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),

    # Router (records, medications)
    path("", include(router.urls)),
]
