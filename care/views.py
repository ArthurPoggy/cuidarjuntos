from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Patient, CareRecord
from .forms import PatientForm, CareRecordForm

@login_required
def dashboard(request):
    patient_id = request.GET.get("patient")
    start = request.GET.get("start")
    end = request.GET.get("end")

    qs = CareRecord.objects.filter(created_by=request.user)  # <- filtro por dono

    if patient_id:
        # garante que o paciente também é do usuário
        qs = qs.filter(patient_id=patient_id, patient__created_by=request.user)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    by_type = qs.values("type").annotate(total=Count("id")).order_by()
    caregivers = qs.values_list("caregiver", flat=True).distinct()

    ctx = {
        "patients": Patient.objects.filter(created_by=request.user).order_by("name"),  # <- só dele
        "records": qs.select_related("patient")[:200],
        "by_type": by_type,
        "caregivers_count": len(caregivers),
        "total": qs.count(),
        "filters": {"patient": patient_id, "start": start, "end": end},
    }
    return render(request, "care/dashboard.html", ctx)


class OwnObjectsMixin(LoginRequiredMixin):
    """Restringe queryset ao usuário logado."""
    def get_queryset(self):
        qs = super().get_queryset()
        if self.model is Patient:
            return qs.filter(created_by=self.request.user)
        if self.model is CareRecord:
            return qs.filter(created_by=self.request.user, patient__created_by=self.request.user)
        return qs


class PatientList(OwnObjectsMixin, ListView):
    model = Patient
    template_name = "care/patient_list.html"
    context_object_name = "patients"


class PatientCreate(OwnObjectsMixin, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = "care/patient_form.html"
    success_url = reverse_lazy("care:patient-list")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.created_by = self.request.user  # <- vincula dono
        obj.save()
        return super().form_valid(form)


class PatientUpdate(OwnObjectsMixin, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = "care/patient_form.html"
    success_url = reverse_lazy("care:patient-list")


class PatientDelete(OwnObjectsMixin, DeleteView):
    model = Patient
    template_name = "care/confirm_delete.html"
    success_url = reverse_lazy("care:patient-list")


class RecordList(OwnObjectsMixin, ListView):
    model = CareRecord
    template_name = "care/record_list.html"
    context_object_name = "records"

    def get_queryset(self):
        qs = super().get_queryset().select_related("patient")
        date = self.request.GET.get("date")
        patient_id = self.request.GET.get("patient")
        if date:
            qs = qs.filter(date=date)
        if patient_id:
            qs = qs.filter(patient_id=patient_id, patient__created_by=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["patients"] = Patient.objects.filter(created_by=self.request.user).order_by("name")
        ctx["date"] = self.request.GET.get("date", "")
        ctx["patient_selected"] = self.request.GET.get("patient", "")
        return ctx


class RecordCreate(OwnObjectsMixin, CreateView):
    model = CareRecord
    form_class = CareRecordForm
    template_name = "care/record_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # limitar o select de pacientes ao usuário
        form.fields['patient'].queryset = Patient.objects.filter(created_by=self.request.user)
        # preencher caregiver automaticamente
        form.fields['caregiver'].initial = self.request.user.get_full_name() or self.request.user.username
        return form

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.created_by = self.request.user  # <- vincula dono
        if not obj.caregiver:
            obj.caregiver = self.request.user.get_full_name() or self.request.user.username
        obj.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("care:record-list")


class RecordUpdate(OwnObjectsMixin, UpdateView):
    model = CareRecord
    form_class = CareRecordForm
    template_name = "care/record_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['patient'].queryset = Patient.objects.filter(created_by=self.request.user)
        return form

    def get_success_url(self):
        return reverse("care:record-list")


class RecordDelete(OwnObjectsMixin, DeleteView):
    model = CareRecord
    template_name = "care/confirm_delete.html"
    success_url = reverse_lazy("care:record-list")
