from django.urls import path
from . import views

app_name = "care"

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),

    path('patients/', views.PatientList.as_view(), name='patient-list'),
    path('patients/new/', views.PatientCreate.as_view(), name='patient-create'),
    path('patients/<int:pk>/edit/', views.PatientUpdate.as_view(), name='patient-update'),
    path('patients/<int:pk>/delete/', views.PatientDelete.as_view(), name='patient-delete'),

    path('records/', views.RecordList.as_view(), name='record-list'),
    path('records/new/', views.RecordCreate.as_view(), name='record-create'),
    path('records/<int:pk>/edit/', views.RecordUpdate.as_view(), name='record-update'),
    path('records/<int:pk>/delete/', views.RecordDelete.as_view(), name='record-delete'),
]
