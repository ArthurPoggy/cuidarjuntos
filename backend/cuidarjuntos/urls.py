from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.views.checklist import ChecklistItemViewSet
from api.views.shifts import CareShiftViewSet
from api.views.charts import chart_data
from api.views.exports import export_records
from api.views.patients import PatientAdminViewSet
from api.views.notifications import NotificationViewSet

router = DefaultRouter()
router.register(r"checklist", ChecklistItemViewSet, basename="checklist")
router.register(r"shifts", CareShiftViewSet, basename="shift")
router.register(r"patients", PatientAdminViewSet, basename="patient")
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/charts/<str:kind>/", chart_data, name="chart-data"),
    path("api/v1/exports/", export_records, name="export-records"),
    path("api/v1/", include(router.urls)),
]
