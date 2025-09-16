# care/views.py
from django.contrib import messages
from django.contrib.auth import login
from itertools import groupby
from django.core.paginator import Paginator
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
from django.http import HttpResponseRedirect

from datetime import date, datetime, timedelta
from calendar import Calendar, month_name
import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
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
        messages.success(request, "Atividade registrada!")
        return redirect(f"{reverse('care:record-create')}?category={rec.type}#history")

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

    recent = None
    if patient:
        recent_qs = CareRecord.objects.filter(patient=patient).select_related("patient")
        recent = Paginator(recent_qs, 15).get_page(request.GET.get("page"))

    context = {
        'form': form,
        'categories': CareRecord.Type.choices,
        'selected_category': selected,
        'current_patient': patient,
        'recent': recent,             # <-- NOVO
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

CATEGORY_META = {
    "medication": {"label": "Remédio",     "icon": "💊", "bg": "bg-blue-50",   "ring": "ring-blue-200"},
    "sleep":      {"label": "Sono",        "icon": "🌙", "bg": "bg-purple-50", "ring": "ring-purple-200"},
    "meal":       {"label": "Alimentação", "icon": "🍽️","bg": "bg-green-50",  "ring": "ring-green-200"},
    "bathroom":   {"label": "Banheiro",    "icon": "🚽", "bg": "bg-yellow-50", "ring": "ring-yellow-200"},
    "activity":   {"label": "Exercício",   "icon": "🏃", "bg": "bg-orange-50", "ring": "ring-orange-200"},
    "other":      {"label": "Outros",      "icon": "➕", "bg": "bg-rose-50",   "ring": "ring-rose-200"},
}

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    # tenta ISO (YYYY-MM-DD) e dd/mm/YYYY
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

@login_required
def dashboard(request):
    if not user_group(request.user):
        return redirect("care:choose-group")

    p = users_patient(request.user)
    base_qs = CareRecord.objects.filter(patient=p).select_related("patient") if p else CareRecord.objects.none()

    # filtros de período (opcionais, independentes do dia selecionado)
    start = _parse_date(request.GET.get("start"))
    end   = _parse_date(request.GET.get("end"))

    day_param = _parse_date(request.GET.get("day"))
    if day_param:
        start = None
        end = None

    qs = base_qs
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    today = timezone.localdate()
    now   = timezone.localtime()

    # ---------------- MODO PERÍODO (quando há start ou end) ----------------
    range_mode = bool(start or end)

    range_groups = []
    if range_mode:
        qs_range = qs.order_by("date", "time")  # já filtrado por start/end
        for day, items in groupby(qs_range, key=lambda r: r.date):
            items_list = []
            for r in items:
                pending = (day > today) or (day == today and r.time > now.time())
                items_list.append({"obj": r, "status": "pending" if pending else "done"})
            range_groups.append({"date": day, "items": items_list})

    if request.GET.get("export") == "csv":
        # Se o usuário selecionou um dia específico e não há start/end, exporta só esse dia
        day_param = _parse_date(request.GET.get("day"))
        qs_export = qs
        if not start and not end and day_param:
            qs_export = base_qs.filter(date=day_param)

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        # nome do arquivo
        fn_start = (start or day_param or timezone.localdate()).isoformat()
        fn_end   = (end or day_param or timezone.localdate()).isoformat()
        resp["Content-Disposition"] = f'attachment; filename="registros_{fn_start}_{fn_end}.csv"'

        # BOM para abrir acentos no Excel
        resp.write("\ufeff")

        w = csv.writer(resp)
        w.writerow(["Data", "Hora", "Categoria", "O que", "Observações", "Cuidador", "Paciente"])
        for r in qs_export.order_by("date", "time"):
            w.writerow([
                r.date.isoformat(),
                r.time.strftime("%H:%M"),
                r.get_type_display(),
                r.what or "",
                (r.description or "").replace("\r\n", " ").replace("\n", " "),
                r.caregiver or "",
                str(r.patient),
            ])
        return resp

    # contagem por categoria -> meta com count
    raw_counts = dict(qs.values_list("type").annotate(total=Count("id")))
    counts = {k: raw_counts.get(k, 0) for k in CATEGORY_META.keys()}
    meta = {k: {**v, "count": counts.get(k, 0)} for k, v in CATEGORY_META.items()}

    today = timezone.localdate()
    now   = timezone.localtime()

    # ------------- DIA SELECIONADO E MÊS DO CALENDÁRIO -------------
    # day = dia clicado no calendário (tem prioridade)
    day_param = _parse_date(request.GET.get("day"))
    # m = mês base do calendário (YYYY-MM-01); se não vier, usa o do day/schedule_day
    month_param = _parse_date(request.GET.get("m"))

    # regra do cronograma: se usuário filtrou um único dia pelo período, usa ele;
    # senão, usa o dia clicado; senão, hoje.
    schedule_day = (day_param or (start if (start and end and start == end) else today))

    # mês de referência do calendário
    month_ref = (day_param or month_param or schedule_day).replace(day=1)
    year, month = month_ref.year, month_ref.month

    # registros do dia (cronograma)
    schedule = []
    for r in base_qs.filter(date=schedule_day).order_by("time"):
        pending = (schedule_day > today) or (schedule_day == today and r.time > now.time())
        schedule.append({"obj": r, "status": "pending" if pending else "done"})

    # calendário mensal (domingo como primeiro dia)
    cal = Calendar(firstweekday=6)
    cal_weeks = cal.monthdayscalendar(year, month)  # 0 fora do mês

    # dias com registros nesse mês
    in_month_qs = base_qs.filter(date__year=year, date__month=month)
    days_with = set(d["date"].day for d in in_month_qs.values("date"))

    # navegação do calendário
    prev_month = (month_ref - timedelta(days=1)).replace(day=1)
    next_month = (month_ref + timedelta(days=31)).replace(day=1)

    # próximos compromissos (futuros em relação a agora)
    upcoming = base_qs.filter(
        Q(date__gt=today) | Q(date=today, time__gt=now.time())
    ).order_by("date", "time")[:10]

    ctx = {
        "filters": {"start": start, "end": end},
        "meta": meta,
        "month": month,
        "range_mode": range_mode,
        "range_groups": range_groups,
        "schedule_day": schedule_day,
        "schedule": schedule,
        "month_name": month_name[month],
        "year": year,
        "cal_weeks": cal_weeks,
        "days_with": days_with,
        # só marca selecionado se for do mesmo mês/ano do calendário atual
        "selected_day": schedule_day.day if (schedule_day.month == month and schedule_day.year == year) else None,
        "today": today,
        "prev_month": prev_month,
        "next_month": next_month,
        "upcoming": upcoming,
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
    template_name = "care/record_quick.html"

    # categoria escolhida no grid (com fallback)
    def _selected_category(self):
        cat = self.request.GET.get("category") or self.request.POST.get("type")
        return cat if cat in dict(CareRecord.Type.choices) else CareRecord.Type.MEDICATION

    def get_initial(self):
        initial = super().get_initial().copy()
        initial.setdefault("date", timezone.localdate())
        initial.setdefault("time", timezone.localtime().strftime("%H:%M"))
        initial.setdefault("type", self._selected_category())

        # paciente do grupo
        grp = getattr(self.request.user, "group_membership", None)
        if grp and getattr(grp, "group", None) and getattr(grp.group, "patient_id", None):
            initial.setdefault("patient", grp.group.patient_id)
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # paciente: oculto e travado no paciente do grupo
        grp = getattr(self.request.user, "group_membership", None)
        if grp and getattr(grp, "group", None) and getattr(grp.group, "patient_id", None):
            pid = grp.group.patient_id
            form.fields["patient"].queryset = Patient.objects.filter(pk=pid)
            form.fields["patient"].initial = pid
        else:
            form.fields["patient"].queryset = Patient.objects.none()
        form.fields["patient"].widget = forms.HiddenInput()

        # categoria: oculto e vindo do grid
        if "type" in form.fields:
            form.fields["type"].widget = forms.HiddenInput()
            form.initial["type"] = self._selected_category()
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        selected = self._selected_category()

        # grid de categorias + selecionada (usa seus labels de UI)
        ctx["categories"] = CATEGORY_CHOICES_UI  # se preferir: CareRecord.Type.choices
        ctx["selected_category"] = selected

        # paciente atual (para exibir nome)
        grp = getattr(self.request.user, "group_membership", None)
        patient = grp.group.patient if (grp and getattr(grp, "group", None)) else None
        ctx["current_patient"] = patient

        # histórico recente (paginado)
        if patient:
            recent_qs = CareRecord.objects.filter(patient=patient).select_related("patient")
            ctx["recent"] = Paginator(recent_qs, 15).get_page(self.request.GET.get("page"))
        else:
            ctx["recent"] = None
        return ctx

    def form_valid(self, form):
        self.object = form.save(commit=False)

        # garantia extra de categoria
        if not self.object.type:
            self.object.type = self._selected_category()

        # garante paciente do grupo
        if not self.object.patient_id:
            grp = getattr(self.request.user, "group_membership", None)
            if grp and getattr(grp, "group", None):
                self.object.patient_id = grp.group.patient_id

        # cuidador e created_by
        if not self.object.caregiver:
            self.object.caregiver = self.request.user.get_full_name() or self.request.user.username
        self.object.created_by = self.request.user

        self.object.save()
        messages.success(self.request, "Atividade registrada!")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        base = reverse("care:record-create")
        return f"{base}?category={self._selected_category()}#history"


class RecordUpdate(LoginRequiredMixin, UpdateView):
    model = CareRecord
    form_class = CareRecordForm
    template_name = "care/record_form.html"

    def get_queryset(self):
        qs = CareRecord.objects.all()
        # (opcional) superuser pode tudo. Se NÃO quiser, remova este if.
        if self.request.user.is_superuser:
            return qs
        # só pode editar registros que ELE criou
        return qs.filter(created_by=self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # mantém o paciente travado no paciente do grupo do usuário
        if "patient" in form.fields:
            p = users_patient(self.request.user)
            form.fields["patient"].queryset = Patient.objects.filter(pk=p.pk) if p else Patient.objects.none()
        # se quiser esconder patient/type:
        # form.fields["patient"].widget = forms.HiddenInput()
        # form.fields["type"].widget = forms.HiddenInput()
        return form

    def get_success_url(self):
        messages.success(self.request, _("Registro atualizado!"))
        return reverse("care:record-list")


class RecordDelete(LoginRequiredMixin, DeleteView):
    model = CareRecord
    template_name = "care/confirm_delete.html"
    success_url = reverse_lazy("care:record-list")

    def get_queryset(self):
        qs = CareRecord.objects.all()
        if self.request.user.is_superuser:
            return qs
        return qs.filter(created_by=self.request.user)