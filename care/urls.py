# care/urls.py
from django.urls import path, include
from .views import (
    SignUpView, ChooseGroupView, GroupCreateView, GroupJoinView,
    dashboard,
    PatientList, PatientCreate, PatientUpdate, PatientDelete,
    RecordList, RecordCreate, RecordUpdate, RecordDelete,
)
from .views import GroupLeaveView
from . import views

app_name = "care"

urlpatterns = [
    # registro + fluxo de grupo
    path("care/", include(("care.urls", "care"), namespace="care")),
    path("register/", SignUpView.as_view(), name="register"),
    path("choose-group/", ChooseGroupView.as_view(), name="choose-group"),
    path("groups/create/", GroupCreateView.as_view(), name="group-create"),
    path("groups/join/", GroupJoinView.as_view(), name="group-join"),
    path("records/<int:pk>/set-status/", views.record_set_status, name="record-set-status"),
    path("dashboard/upcoming-data/", views.upcoming_data, name="upcoming-data"),
    path("records/<int:pk>/edit/", RecordUpdate.as_view(), name="record-update"),
    path("dashboard/calendar-data/", views.calendar_data, name="calendar-data"),

    path('upcoming/', views.upcoming_view, name='upcoming-view'),
    path('upcoming/buckets/', views.upcoming_buckets, name='upcoming-buckets'),
    path('record/bulk-set-status/', views.record_bulk_set_status, name='record-bulk-set-status'),
    path('record/reschedule/', views.record_reschedule, name='record-reschedule'),

    # app em si
    path("dashboard/", dashboard, name="dashboard"),

    path("patients/", PatientList.as_view(), name="patient-list"),
    path("patients/new/", PatientCreate.as_view(), name="patient-create"),
    path("patients/<int:pk>/edit/", PatientUpdate.as_view(), name="patient-update"),
    path("patients/<int:pk>/delete/", PatientDelete.as_view(), name="patient-delete"),

    path("records/", RecordList.as_view(), name="record-list"),
    path("records/new/", RecordCreate.as_view(), name="record-create"),
    path("records/<int:pk>/edit/", RecordUpdate.as_view(), name="record-update"),
    path("records/<int:pk>/delete/", RecordDelete.as_view(), name="record-delete"),
    path("groups/leave/", GroupLeaveView.as_view(), name="group-leave"),
]
