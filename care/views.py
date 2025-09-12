# care/views.py
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.shortcuts import render, redirect
from django import forms
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, TemplateView, FormView
)

from .models import Patient, CareRecord, CareGroup, GroupMembership
from .forms import (
    PatientForm, CareRecordForm,
    SignUpForm, GroupCreateForm, GroupJoinForm
)
from django.utils.translation import gettext as _
from django.views import View
from django.utils import timezone


# ---------- helpers ----------
def user_group(user):
    try:
        return user.group_membership
    except GroupMembership.DoesNotExist:
        return None

@login_required
def record_quick(request):
    gm = user_group(request.user)
    if not gm or not gm.group or not gm.group.patient:
        messages.error(request, "Você precisa estar em um grupo com paciente definido.")
        return redirect('care:choose-group')

    patient = gm.group.patient

    # categoria pré-selecionada
    selected = request.GET.get('category') or CareRecord.Type.MEDICATION

    if request.method == "POST":
        data = request.POST.copy()
        data['patient'] = str(patient.pk)               # força paciente do grupo
        form = CareRecordForm(data=data)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.created_by = request.user
            if not getattr(rec, 'caregiver', None):
                rec.caregiver = request.user.get_full_name() or request.user.username
            # Se o usuário trocou a categoria pelo select, usamos a do form;
            # caso contrário, aplica a da querystring.
            if not rec.type:
                rec.type = selected
            rec.save()
            messages.success(request, "Atividade registrada!")
            return redirect('care:record-list')
        else:
            # opcional: log para depuração
            print(form.errors)
            pass
    else:
        form = CareRecordForm(initial={
            'patient': patient.pk,
            'type': selected,
            'date': timezone.localdate(),
        })

    context = {
        'form': form,
        'categories': CareRecord.Type.choices,
        'selected_category': selected,
        'current_patient': patient,
    }
    return render(request, 'care/record_quick.html', context)

def users_patient(user):
    """Retorna o paciente do grupo do usuário (ou None)."""
    gm = user_group(user)
    return gm.group.patient if gm else None


# =========================
# Registro + Fluxo de Grupo
# =========================

class SignUpView(FormView):
    template_name = "accounts/register.html"
    form_class = SignUpForm
    success_url = reverse_lazy("care:choose-group")

    def form_valid(self, form):
        with transaction.atomic():
            user = form.create_user()
        login(self.request, user)
        messages.success(self.request, "Cadastro realizado. Agora escolha: criar grupo ou entrar em um.")
        return super().form_valid(form)


class ChooseGroupView(LoginRequiredMixin, TemplateView):
    template_name = "care/choose_group.html"

    def dispatch(self, request, *args, **kwargs):
        if user_group(request.user):
            return redirect("care:dashboard")
        return super().dispatch(request, *args, **kwargs)


class GroupLeaveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            GroupMembership.objects.get(user=request.user).delete()
            messages.success(request, "Você saiu do grupo.")
        except GroupMembership.DoesNotExist:
            messages.info(request, "Você não está em nenhum grupo.")
        # após sair, leve para a tela de escolha/criação de grupo
        return redirect(reverse_lazy("care:choose-group"))


class GroupCreateView(LoginRequiredMixin, FormView):
    template_name = "care/group_create.html"
    form_class = GroupCreateForm
    success_url = reverse_lazy("care:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if user_group(request.user):
            return redirect("care:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            form.create_everything(self.request.user)
        messages.success(self.request, "Grupo criado e você foi atrelado a ele.")
        return super().form_valid(form)


class GroupJoinView(LoginRequiredMixin, FormView):
    template_name = "care/group_join.html"
    form_class = GroupJoinForm
    success_url = reverse_lazy("care:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if user_group(request.user):
            return redirect("care:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            try:
                form.join(self.request.user)
            except Exception as e:
                form.add_error(None, str(e))
                return self.form_invalid(form)
        messages.success(self.request, "Você entrou no grupo selecionado.")
        return super().form_valid(form)


# =========================
# Dashboard (agora por grupo)
# =========================

@login_required
def dashboard(request):
    if not user_group(request.user):
        return redirect("care:choose-group")

    p = users_patient(request.user)
    qs = CareRecord.objects.filter(patient=p)

    patient_id = request.GET.get("patient")  # opcional (se admin quiser ver outro)
    start = request.GET.get("start")
    end = request.GET.get("end")

    if patient_id and request.user.is_superuser:
        qs = CareRecord.objects.filter(patient_id=patient_id)

    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    by_type = qs.values("type").annotate(total=Count("id")).order_by()
    caregivers = qs.values_list("caregiver", flat=True).distinct()

    ctx = {
        "patients": [p] if p else [],
        "records": qs.select_related("patient")[:200],
        "by_type": by_type,
        "caregivers_count": len(caregivers),
        "total": qs.count(),
        "filters": {"patient": patient_id, "start": start, "end": end},
    }
    return render(request, "care/dashboard.html", ctx)


# =========================
# Patients (CRUD – médico/admin)
# =========================

class PatientList(LoginRequiredMixin, ListView):
    model = Patient
    template_name = "care/patient_list.html"
    context_object_name = "patients"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Patient.objects.all().order_by("name")
        p = users_patient(self.request.user)
        return Patient.objects.filter(pk=p.pk) if p else Patient.objects.none()


class PatientCreate(LoginRequiredMixin, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = "care/patient_form.html"
    success_url = reverse_lazy("care:patient-list")

    def dispatch(self, request, *args, **kwargs):
        # permitir apenas admins por enquanto (ou médicos, se quiser)
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.created_by = self.request.user
        obj.save()
        return super().form_valid(form)


class PatientUpdate(PatientCreate.__bases__[0], UpdateView):  # LoginRequiredMixin, UpdateView
    model = Patient
    form_class = PatientForm
    template_name = "care/patient_form.html"
    success_url = reverse_lazy("care:patient-list")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class PatientDelete(PatientCreate.__bases__[0], DeleteView):
    model = Patient
    template_name = "care/confirm_delete.html"
    success_url = reverse_lazy("care:patient-list")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# =========================
# Care Records (limitados ao paciente do grupo)
# =========================

class RecordList(LoginRequiredMixin, ListView):
    model = CareRecord
    template_name = "care/record_list.html"
    context_object_name = "records"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CareRecord.objects.select_related("patient")
        p = users_patient(self.request.user)
        return CareRecord.objects.filter(patient=p).select_related("patient") if p else CareRecord.objects.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = users_patient(self.request.user)
        ctx["patients"] = [p] if p else []
        return ctx


CATEGORY_CHOICES_UI = [
    ("medication", "Remédio"),
    ("sleep",      "Sono"),
    ("meal",       "Alimentação"),
    ("bathroom",   "Banheiro"),
    ("activity",   "Exercício"),
    ("other",      "Outros"),
]

class OwnObjectsMixin(LoginRequiredMixin):
    """Restringe queryset ao usuário logado."""
    def get_queryset(self):
        qs = super().get_queryset()
        try:
            model = self.model
        except AttributeError:
            return qs

        if model.__name__ == "Patient":
            return qs.filter(created_by=self.request.user)

        if model.__name__ == "CareRecord":
            return qs.filter(
                created_by=self.request.user,
                patient__created_by=self.request.user
            )

        return qs

class RecordCreate(OwnObjectsMixin, CreateView):
    model = CareRecord
    form_class = CareRecordForm
    template_name = "care/record_quick.html"   # ou o que você estiver usando

    def get_initial(self):
        initial = super().get_initial().copy()
        now = timezone.localtime()  # respeita TIME_ZONE/DST

        # pré-preenche data e hora
        initial.setdefault("date", timezone.localdate())
        initial.setdefault("time", timezone.localtime().strftime("%H:%M"))

        # manter a categoria vinda do grid, se houver
        category = self.request.GET.get("category")
        if category in dict(CareRecord.Type.choices):
            initial.setdefault("type", category)

        # se você já guarda o paciente do grupo atual, também pode setar:
        grp = getattr(self.request.user, "group_membership", None)
        if grp and getattr(grp, "patient_id", None):
            initial.setdefault("patient", grp.patient_id)

        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # paciente é único por grupo => restringe e oculta
        qs = Patient.objects.filter(created_by=self.request.user)
        form.fields["patient"].queryset = qs
        if qs.count() == 1:
            form.fields["patient"].initial = qs.first().pk
        form.fields["patient"].widget = forms.HiddenInput()

        # “caregiver” não está no form; setamos no save()
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        selected = self.request.GET.get("category") or self.request.POST.get("type") or "medication"
        ctx["categories"] = CATEGORY_CHOICES_UI
        ctx["selected_category"] = selected
        # paciente para exibir nome na UI
        patient = Patient.objects.filter(created_by=self.request.user).first()
        ctx["current_patient"] = patient
        return ctx

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.created_by = self.request.user
        # garante patient se só existe 1 no grupo
        if not obj.patient:
            p = Patient.objects.filter(created_by=self.request.user).first()
            if p:
                obj.patient = p
        # preenche cuidador automaticamente
        if not obj.caregiver:
            obj.caregiver = self.request.user.get_full_name() or self.request.user.username
        obj.save()
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("care:record-list")


class RecordUpdate(LoginRequiredMixin, UpdateView):
    model = CareRecord
    form_class = CareRecordForm
    template_name = "care/record_form.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CareRecord.objects.all()
        p = users_patient(self.request.user)
        return CareRecord.objects.filter(patient=p)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if "patient" in form.fields:
            p = users_patient(self.request.user)
            form.fields["patient"].queryset = Patient.objects.filter(pk=p.pk) if p else Patient.objects.none()
        return form

    def get_success_url(self):
        return reverse("care:record-list")


class RecordDelete(LoginRequiredMixin, DeleteView):
    model = CareRecord
    template_name = "care/confirm_delete.html"
    success_url = reverse_lazy("care:record-list")

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CareRecord.objects.all()
        p = users_patient(self.request.user)
        return CareRecord.objects.filter(patient=p)
