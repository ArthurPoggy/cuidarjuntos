# care/views.py
from datetime import datetime, time, timedelta
from datetime import date, timedelta, datetime, time as dtime
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.utils.dateparse import parse_date
from django.db.models import Q, Count
from .models import CareRecord, GroupMembership
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import login
from django.http import JsonResponse
from calendar import Calendar, month_name
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
from django.utils.timezone import localtime
from django.http import HttpResponseRedirect

from datetime import date, datetime, timedelta
from calendar import Calendar, month_name
import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone

# ---------- helpers ----------
def _aware_dt(d, t):
    """Combina data+hora em um datetime c/ timezone atual.
    Se hora vier vazia, usa 00:00."""
    if t is None:
        t = time(0, 0)
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(d, t), tz)

def display_name(user):
    full = (user.get_full_name() or "").strip()
    if full:
        return full
    uname = user.username or ""
    # se o username for um email, exibe só o antes do @
    if "@" in uname:
        return uname.split("@")[0]
    return uname or "Usuário"

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

@login_required
@require_POST
def record_set_status(request, pk):
    rec = get_object_or_404(CareRecord, pk=pk)
    # segurança: precisa ser do mesmo paciente do grupo (ou superuser)
    if not request.user.is_superuser and rec.patient != users_patient(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)

    new_status = request.POST.get("status")
    if new_status not in ("pending", "done", "missed"):
        return JsonResponse({"error": "bad_status"}, status=400)

    rec.status = new_status
    rec.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": rec.status})

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
def calendar_data(request):
    # segurança básica: precisa ter grupo/paciente
    if not user_group(request.user):
        return JsonResponse({"error": "no_group"}, status=403)

    p = users_patient(request.user)
    base_qs = CareRecord.objects.filter(patient=p) if p else CareRecord.objects.none()

    m_param = _parse_date(request.GET.get("m"))
    month_ref = (m_param or timezone.localdate()).replace(day=1)
    year, month = month_ref.year, month_ref.month

    cal = Calendar(firstweekday=6)
    weeks = cal.monthdayscalendar(year, month)

    in_month_qs = base_qs.filter(date__year=year, date__month=month).order_by("date", "time")
    days_with = sorted(set(d["date"].day for d in in_month_qs.values("date")))

    events_by_date = {}
    for r in in_month_qs:
        key = r.date.isoformat()
        events_by_date.setdefault(key, []).append({
            "type": r.type,
            "title": f"{r.get_type_display()}" + (f" • {r.what}" if r.what else ""),
            "time": r.time.strftime("%H:%M") if r.time else "",
            "who": r.caregiver or "",
            "url": "",
        })

    return JsonResponse({
        "year": year,
        "month": month,
        "month_name": month_name[month],
        "weeks": weeks,              # [[0,0,1,...], ...]
        "days_with": days_with,      # [1,5,13,...]
        "today_iso": timezone.localdate().isoformat(),
        "events_by_date": events_by_date,
    })

@login_required
def upcoming_data(request):
    """JSON dos próximos compromissos (direita do dashboard).
    Agora filtra por status pendente e respeita a categoria."""
    if not user_group(request.user):
        return JsonResponse({"error": "no_group"}, status=403)

    p = users_patient(request.user)
    base_qs = CareRecord.objects.filter(patient=p).select_related("patient") if p else CareRecord.objects.none()

    today  = timezone.localdate()
    now_dt = timezone.localtime()

    # filtros extras
    category = (request.GET.get("category") or "").strip() or None
    include_done   = request.GET.get("include_done") == "1"
    include_missed = request.GET.get("include_missed") == "1"

    qs = base_qs
    if category:
        qs = qs.filter(type=category)

    # status (por padrão, só pendentes)
    if include_done and include_missed:
        pass  # todos os status
    elif include_done:
        qs = qs.filter(status__in=["pending", "done"])
    elif include_missed:
        qs = qs.filter(status__in=["pending", "missed"])
    else:
        qs = qs.filter(status="pending")

    # escopo por dia ou próximos 10
    day = _parse_date(request.GET.get("day"))
    if day:
        if day == today:
            qs = qs.filter(date=today, time__gt=now_dt.time()).order_by("time")
        elif day > today:
            qs = qs.filter(date=day).order_by("time")
        else:
            qs = CareRecord.objects.none()
    else:
        qs = qs.filter(
            Q(date__gt=today) | Q(date=today, time__gt=now_dt.time())
        ).order_by("date", "time")[:10]

    items = [{
        "type": r.type,
        "title": f"{r.get_type_display()}" + (f" • {r.what}" if r.what else ""),
        "date": r.date.strftime("%d/%m/%Y"),
        "time": r.time.strftime("%H:%M") if r.time else "",
        "who": r.caregiver or "",
    } for r in qs]

    return JsonResponse({"items": items})

@login_required
def dashboard(request):
    if not user_group(request.user):
        return redirect("care:choose-group")

    p = users_patient(request.user)
    base_qs = CareRecord.objects.filter(patient=p).select_related("patient") if p else CareRecord.objects.none()

    # -------- Data/hora "hoje" (para defaults de UI) --------
    today  = timezone.localdate()
    now_dt = timezone.localtime()  # datetime com fuso
    today_str = today.strftime("%d/%m/%Y")  # p/ inputs do filtro

    # -------- Filtros --------
    start = _parse_date(request.GET.get("start"))
    end   = _parse_date(request.GET.get("end"))
    category = (request.GET.get("category") or "").strip() or None

    # strings para UI dos inputs (se não veio GET, usar hoje)
    start_ui = start.strftime("%d/%m/%Y") if start else today_str
    end_ui   = end.strftime("%d/%m/%Y")   if end   else today_str

    # base com período
    qs = base_qs
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    # aplica categoria quando existir
    qs_cat = qs.filter(type=category) if category else qs
    base_qs_cat = base_qs.filter(type=category) if category else base_qs

    # helper para status manual (não deduz mais por data/hora)
    def _status_of(r):
        s = getattr(r, "status", None)
        return s if s in ("pending", "done", "missed") else "pending"

    # ---------------- MODO PERÍODO (quando há start ou end) ----------------
    range_mode = bool(start or end)

    range_groups = []
    if range_mode:
        # ordem mais recente -> mais antiga
        qs_range = qs_cat.order_by("-date", "-time")
        for day, items in groupby(qs_range, key=lambda r: r.date):
            items_list = [{"obj": r, "status": _status_of(r)} for r in items]
            range_groups.append({"date": day, "items": items_list})

    # ---------------- Export CSV (respeita período e categoria; se não houver, exporta hoje [+ categoria]) ----------------
    if request.GET.get("export") == "csv":
        if (start or end):
            qs_export = qs_cat
        else:
            qs_export = (base_qs_cat.filter(date=today))

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        fn_start = (start or today).isoformat()
        fn_end   = (end or today).isoformat()
        resp["Content-Disposition"] = f'attachment; filename="registros_{fn_start}_{fn_end}' + (f'_{category}' if category else '') + '.csv"'
        resp.write("\ufeff")  # BOM

        w = csv.writer(resp)
        w.writerow(["Data", "Hora", "Categoria", "O que", "Observações", "Cuidador", "Paciente"])
        for r in qs_export.order_by("date", "time"):
            w.writerow([
                r.date.isoformat(),
                r.time.strftime("%H:%M") if r.time else "",
                r.get_type_display(),
                r.what or "",
                (r.description or "").replace("\r\n", " ").replace("\n", " "),
                r.caregiver or "",
                str(r.patient),
            ])
        return resp

    # -------- contagem por categoria -> meta com count (ignora 'missed')
    # (mantém a lógica atual: conta todas as categorias dentro do PERÍODO, independentemente do filtro de categoria)
    qs_for_counts = qs.exclude(status="missed")
    raw_counts = dict(qs_for_counts.values_list("type").annotate(total=Count("id")))
    counts = {k: raw_counts.get(k, 0) for k in CATEGORY_META.keys()}
    meta = {k: {**v, "count": counts.get(k, 0)} for k, v in CATEGORY_META.items()}

    # ------------- CALENDÁRIO -------------
    month_param = _parse_date(request.GET.get("m"))
    month_ref = (month_param or today).replace(day=1)
    year, month = month_ref.year, month_ref.month

    # --------- CRONOGRAMA PRINCIPAL ---------
    # Sem filtro de período -> mostra TODOS os registros (mais recentes primeiro)
    # Com filtro -> a lista já vem via range_groups (acima)
    schedule = []
    if not range_mode:
        for r in base_qs_cat.order_by("-date", "-time"):
            schedule.append({"obj": r, "status": _status_of(r)})

    # calendário mensal (domingo como primeiro dia)
    cal = Calendar(firstweekday=6)
    cal_weeks = cal.monthdayscalendar(year, month)  # 0 fora do mês

    # dias com registros nesse mês (não filtra por categoria para manter visão geral)
    in_month_qs = base_qs.filter(date__year=year, date__month=month).order_by("date", "time")
    days_with = set(d["date"].day for d in in_month_qs.values("date"))

    # ---------- mapa para o popover: "AAAA-MM-DD" -> lista de compromissos ----------
    events_by_date: dict[str, list[dict]] = {}
    for r in in_month_qs:
        key = r.date.isoformat()
        events_by_date.setdefault(key, []).append({
            "type": r.type,
            "title": f"{r.get_type_display()}" + (f" • {r.what}" if r.what else ""),
            "time": r.time.strftime("%H:%M") if r.time else "",
            "who": r.caregiver or "",
            "url": "",
        })

    # navegação do calendário
    prev_month = (month_ref - timedelta(days=1)).replace(day=1)
    next_month = (month_ref + timedelta(days=31)).replace(day=1)

    # próximos compromissos (mantém visão geral; não filtra por categoria)
    upcoming = (
        base_qs_cat
        .filter(status='pending')
        .filter(Q(date__gt=today) | Q(date=today, time__gt=now_dt.time()))
        .order_by("date", "time")[:10]
    )

    # -------- choices para o <select> de categorias --------
    try:
        type_enum = getattr(CareRecord, "Type", None)
        if type_enum and getattr(type_enum, "choices", None):
            record_categories = list(type_enum.choices)
        else:
            raise AttributeError
    except Exception:
        record_categories = []
        for key, data in CATEGORY_META.items():
            label = None
            if isinstance(data, dict):
                label = data.get("label") or data.get("name") or data.get("title")
            if not label:
                label = key.replace("_", " ").capitalize()
            record_categories.append((key, label))

    ctx = {
        # objetos para lógica (parsers e queryset)
        "filters": {"start": start, "end": end, "category": category},
        # strings para preencher inputs (default = hoje)
        "filters_ui": {"start": start_ui, "end": end_ui, "category": category},
        "today_str": today_str,

        "record_categories": record_categories,
        "meta": meta,
        "month": month,
        "range_mode": range_mode,
        "range_groups": range_groups,     # usado quando há período (já com categoria)
        "schedule": schedule,             # usado quando NÃO há período (já com categoria)
        "month_name": month_name[month],
        "year": year,
        "cal_weeks": cal_weeks,
        "days_with": days_with,
        "selected_day": None,
        "today": today,
        "prev_month": prev_month,
        "next_month": next_month,
        "upcoming": upcoming,
        "calendar_events_by_date": events_by_date,
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

        # defaults
        initial.setdefault("date", timezone.localdate())
        initial.setdefault("time", timezone.localtime().strftime("%H:%M"))
        initial.setdefault("type", self._selected_category())

        # ✔️ aceita ?date=YYYY-MM-DD e ?time=HH:MM
        date_q = (self.request.GET.get("date") or "").strip()
        if date_q:
            try:
                # usa parse_date do Django (já importado no arquivo)
                d = parse_date(date_q)
                if d:
                    initial["date"] = d
            except Exception:
                pass

        time_q = (self.request.GET.get("time") or "").strip()
        if time_q:
            # valida formato HH:MM; se ok, usa como string mesmo
            try:
                datetime.strptime(time_q, "%H:%M")
                initial["time"] = time_q
            except Exception:
                pass

        # paciente do grupo (travado)
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
        ctx["categories"] = CATEGORY_CHOICES_UI
        ctx["selected_category"] = selected

        grp = getattr(self.request.user, "group_membership", None)
        patient = grp.group.patient if (grp and getattr(grp, "group", None)) else None
        ctx["current_patient"] = patient

        if patient:
            recent_qs = CareRecord.objects.filter(patient=patient).select_related("patient")
            ctx["recent"] = Paginator(recent_qs, 15).get_page(self.request.GET.get("page"))
        else:
            ctx["recent"] = None
        return ctx

    def form_valid(self, form):
        self.object = form.save(commit=False)

        if not self.object.type:
            self.object.type = self._selected_category()

        if not self.object.patient_id:
            grp = getattr(self.request.user, "group_membership", None)
            if grp and getattr(grp, "group", None):
                self.object.patient_id = grp.group.patient_id

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
        return reverse("care:record-create")


class RecordDelete(LoginRequiredMixin, DeleteView):
    model = CareRecord
    template_name = "care/confirm_delete.html"
    success_url = reverse_lazy("care:record-list")

    def get_queryset(self):
        qs = CareRecord.objects.all()
        if self.request.user.is_superuser:
            return qs
        return qs.filter(created_by=self.request.user)

TYPE_EMOJI = {
    'medication': '💊', 'sleep': '🌙', 'meal': '🍽️',
    'bathroom': '🚽', 'activity': '🏃', 'other': '📝'
}

def _membership_or_404(user):
    return get_object_or_404(GroupMembership, user=user)

@login_required
def upcoming_view(request):
    filter_types = [
        ('medication', 'Medicamentos'),
        ('meal', 'Refeições'),
        ('vital', 'Sinais vitais'),
        ('activity', 'Atividades'),
        ('sleep', 'Sono'),
        ('bathroom', 'Banheiro'),
        ('other', 'Outros'),
    ]
    return render(request, 'care/upcoming.html', {
        'filter_types': filter_types,
        'today': date.today(),
    })

@require_GET
@login_required
def upcoming_buckets(request):
    """
    JSON com compromissos agrupados por dia (buckets).
    Filtros:
      from=YYYY-MM-DD  to=YYYY-MM-DD
      types=comma,separated   q=texto
      include_done=0|1        include_missed=0|1
    """
    gm = _membership_or_404(request.user)
    patient = gm.group.patient

    today = timezone.localdate()
    dfrom = parse_date(request.GET.get('from') or '') or today
    dto   = parse_date(request.GET.get('to')   or '') or (today + timedelta(days=7))
    if dto < dfrom:
        return JsonResponse({'ok': False, 'message': 'Período inválido.'}, status=400)

    types_str = (request.GET.get('types') or '').strip()
    types = [t for t in types_str.split(',') if t] if types_str else None
    q = (request.GET.get('q') or '').strip()
    include_done   = request.GET.get('include_done')   == '1'
    include_missed = request.GET.get('include_missed') == '1'

    qs = (CareRecord.objects
          .filter(patient=patient, date__range=(dfrom, dto))
          .order_by('date', 'time'))

    if types:
        qs = qs.filter(type__in=types)
    if q:
        qs = qs.filter(Q(what__icontains=q) |
                       Q(description__icontains=q) |
                       Q(caregiver__icontains=q))

    status_q = Q(status='pending')
    if include_done and include_missed:
        status_q = Q()
    elif include_done:
        status_q = Q(status__in=['pending', 'done'])
    elif include_missed:
        status_q = Q(status__in=['pending', 'missed'])
    qs = qs.filter(status_q)

    totals = {'pending': 0, 'done': 0, 'missed': 0}
    for row in qs.values('status').annotate(total=Count('id')):
        totals[row['status']] = row['total']

    buckets = {}
    for r in qs:
        k = r.date.isoformat()
        buckets.setdefault(k, []).append({
            'id': r.id,
            'type': r.type,
            'emoji': TYPE_EMOJI.get(r.type, '📝'),
            'title': f"{r.get_type_display()}" + (f" • {r.what}" if r.what else ""),
            'time': r.time.strftime('%H:%M') if r.time else '—',
            'who': r.caregiver or '',
            'status': r.status,
            'edit_url': reverse('care:record-update', args=[r.id]),
        })

    ordered = []
    cur = dfrom
    while cur <= dto:
        k = cur.isoformat()
        if buckets.get(k):
            ordered.append({'date_iso': k, 'items': buckets[k]})
        cur += timedelta(days=1)

    return JsonResponse({'ok': True,
                         'from': dfrom.isoformat(), 'to': dto.isoformat(),
                         'totals': totals, 'buckets': ordered})

def _label_for_day(d: date, today: date) -> str:
    weekdays = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
    # Python: Monday=0 ... Sunday=6; queremos rótulo pt-br simples
    wd = weekdays[d.weekday()]
    if d == today:
        prefix = 'Hoje'
    elif d == today + timedelta(days=1):
        prefix = 'Amanhã'
    else:
        prefix = d.strftime('%d/%m')
    return f"{prefix} • {wd}"

@require_POST
@login_required
def record_bulk_set_status(request):
    """
    Marca status em lote: ids=1,2,3  status=done|missed
    """
    membership = _membership_or_404(request.user)

    # garante paciente do grupo
    group = membership.group
    pid = getattr(group, "patient_id", None)
    if not pid:
        return JsonResponse(
            {"ok": False, "message": "Grupo sem paciente definido."},
            status=400,
        )

    ids_str = request.POST.get('ids') or ''
    status = request.POST.get('status')
    if status not in {'done', 'missed'}:
        return JsonResponse({'ok': False, 'message': 'Status inválido.'}, status=400)

    try:
        ids = [int(x) for x in ids_str.split(',') if x.strip()]
    except ValueError:
        return JsonResponse({'ok': False, 'message': 'IDs inválidos.'}, status=400)

    qs = CareRecord.objects.filter(pk__in=ids, patient_id=pid)
    updated_ids = list(qs.values_list('id', flat=True))
    qs.update(status=status)

    return JsonResponse({'ok': True, 'updated': updated_ids, 'status': status})

@require_POST
@login_required
def record_reschedule(request):
    """
    Reagenda 1 item: id=.., date=YYYY-MM-DD, time=HH:MM
    """
    membership = _membership_or_404(request.user)

    # garante paciente do grupo
    group = membership.group
    pid = getattr(group, "patient_id", None)
    if not pid:
        return JsonResponse(
            {"ok": False, "message": "Grupo sem paciente definido."},
            status=400,
        )

    rid = request.POST.get('id')
    rdate = parse_date(request.POST.get('date') or '')
    rtime_str = request.POST.get('time') or ''
    if not (rid and rdate and rtime_str):
        return JsonResponse({'ok': False, 'message': 'Parâmetros obrigatórios ausentes.'}, status=400)

    try:
        hh, mm = [int(x) for x in rtime_str.split(':', 1)]
        rtime = dtime(hour=hh, minute=mm)
    except Exception:
        return JsonResponse({'ok': False, 'message': 'Hora inválida.'}, status=400)

    rec = get_object_or_404(CareRecord, pk=rid, patient_id=pid)
    rec.date = rdate
    rec.time = rtime
    rec.save(update_fields=['date', 'time'])

    return JsonResponse({'ok': True, 'id': rec.id, 'date': rec.date.isoformat(), 'time': rec.time.strftime('%H:%M')})