# care/urls.py
from django.urls import path
from . import views
from .views import (
    SignUpView, ChooseGroupView, GroupCreateView, GroupJoinView, GroupLeaveView,
    PatientList, PatientCreate, PatientUpdate, PatientDelete,
    RecordList, RecordCreate, RecordUpdate,
)

app_name = "care"

urlpatterns = [
    # Fluxo de conta/grupo
    path("register/",        SignUpView.as_view(),      name="register"),
    path("choose-group/",    ChooseGroupView.as_view(), name="choose-group"),
    path("groups/create/",   GroupCreateView.as_view(), name="group-create"),
    path("groups/join/",     GroupJoinView.as_view(),   name="group-join"),
    path("groups/leave/",    GroupLeaveView.as_view(),  name="group-leave"),

    # Dashboard + APIs auxiliares
    path("dashboard/",       views.dashboard,           name="dashboard"),
    path("medication-stock/", views.medication_stock,   name="medication-stock"),
    path("medications/<int:pk>/edit/", views.medication_edit, name="medication-edit"),
    path("medications/<int:pk>/delete/", views.medication_delete, name="medication-delete"),
    path("admin/overview/",  views.admin_overview,      name="admin-overview"),
    path("calendar-data/",   views.calendar_data,       name="calendar-data"),
    path("upcoming-data/",   views.upcoming_data,       name="upcoming-data"),
    path("upcoming/",        views.upcoming_view,       name="upcoming-view"),
    path("upcoming/buckets/",views.upcoming_buckets,    name="upcoming-buckets"),

    # Registros (CRUD + ações)
    path("records/",                         RecordList.as_view(),        name="record-list"),
    path("records/new/",                     RecordCreate.as_view(),      name="record-create"),
    path("records/<int:pk>/edit/",           RecordUpdate.as_view(),      name="record-update"),
    # Use a view function para suportar JSON/AJAX como você implementou:
    path("records/<int:pk>/delete/",         views.record_delete,         name="record-delete"),
    path("records/<int:pk>/set-status/",     views.record_set_status,     name="record-set-status"),
    path("records/<int:pk>/cancel-following/", views.record_cancel_following, name="record-cancel-following"),
    path("records/<int:pk>/react/",          views.record_react,          name="record-react"),
    path("records/<int:pk>/comments/",       views.record_comments,       name="record-comments"),

    # Operações em lote e reagendamento
    path("record/bulk-set-status/",          views.record_bulk_set_status, name="record-bulk-set-status"),
    path("record/reschedule/",               views.record_reschedule,      name="record-reschedule"),
    path("records/<int:pk>/delete/", views.record_delete, name="record_delete"),

    # Pacientes (admin)
    path("patients/",                PatientList.as_view(),   name="patient-list"),
    path("patients/new/",            PatientCreate.as_view(), name="patient-create"),
    path("patients/<int:pk>/edit/",  PatientUpdate.as_view(), name="patient-update"),
    path("patients/<int:pk>/delete/",PatientDelete.as_view(), name="patient-delete"),

]
