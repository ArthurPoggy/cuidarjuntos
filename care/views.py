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
from datetime import datetime, time as dt_time, date as dt_date
from django.utils import timezone
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
def _parse_iso(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        return None

def _parse_time_flex(s: str) -> dt_time | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None

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
    if not gm or not getattr(gm, "group", None) or not getattr(gm.group, "patient", None):
        messages.error(request, "Você precisa estar em um grupo com paciente para registrar.")
        return redirect("care:dashboard")

    patient = gm.group.patient

    # categoria pré-selecionada (fallback = MEDICATION)
    selected = request.GET.get("category") or getattr(CareRecord.Type, "MEDICATION", "medication")

    if request.method == "POST":
        data = request.POST.copy()
        data["patient"] = str(patient.pk)  # força paciente do grupo
        form = CareRecordForm(data=data)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.created_by = request.user
            if not getattr(rec, "caregiver", None):
                rec.caregiver = request.user.get_full_name() or request.user.username
            # Se o select do form não enviar, usa a categoria pré-selecionada
            if not rec.type:
                rec.type = selected
            rec.save()

            messages.success(request, "Atividade registrada!")
            # usa o tipo REAL salvo no registro
            return redirect(f"{reverse('care:record-create')}?category={rec.type}#history")
        else:
            # mantém destaque visual da categoria escolhida no POST
            selected = data.get("type", selected)
    else:
        form = CareRecordForm(initial={
            "patient": patient.pk,
            "type": selected,
            "date": timezone.localdate(),
        })

    # histórico recente do paciente
    recent = None
    if patient:
        recent_qs = (
            CareRecord.objects
            .filter(patient=patient)
            .select_related("patient")
            .order_by("-date", "-time")
        )
        recent = Paginator(recent_qs, 15).get_page(request.GET.get("page"))

    context = {
        "form": form,
        "categories": CareRecord.Type.choices,
        "selected_category": selected,
        "current_patient": patient,
        "recent": recent,
    }
    return render(request, "care/record_quick.html", context)

@login_required
@require_POST
def record_set_status(request, pk):
    m = _membership_or_404(request.user)
    r = get_object_or_404(CareRecord, pk=pk, patient=m.group.patient)

    status = (request.POST.get("status") or "").strip()
    if status not in ("pending", "done", "missed"):
        return JsonResponse({"ok": False, "error": "invalid_status"}, status=400)

    today = timezone.localdate()
    now_local = timezone.localtime()
    now_t = now_local.time()

    def is_future(rec: CareRecord) -> bool:
        if rec.date and rec.date > today:
            return True
        if rec.date == today:
            return (rec.time is None) or (rec.time > now_t)
        return False

    # Se tentar aprovar futuro, exigir data/hora
    if status == "done" and is_future(r):
        new_date_str = (request.POST.get("date") or "").strip()
        new_time_str = (request.POST.get("time") or "").strip()

        if not (new_date_str and new_time_str):
            return JsonResponse({
                "ok": False,
                "code": "FUTURE_NEEDS_TIME",
                "message": "Defina data e horário para concluir este registro.",
                "suggested_date": today.isoformat(),
                "suggested_time": now_local.strftime("%H:%M"),
            }, status=409)

        # parse robusto
        try:
            new_date = dt_date.fromisoformat(new_date_str)  # yyyy-mm-dd
        except Exception:
            return JsonResponse({"ok": False, "error": "bad_date"}, status=400)

        new_time = _parse_time_flex(new_time_str)
        if not new_time:
            return JsonResponse({"ok": False, "error": "bad_time"}, status=400)

        # bloquear futuro
        if (new_date > today) or (new_date == today and new_time > now_t):
            return JsonResponse({
                "ok": False,
                "code": "TIME_IN_FUTURE",
                "message": "A data/hora precisa ser no passado ou agora."
            }, status=400)

        # aplicar antes de marcar done
        r.date = new_date
        r.time = new_time

    r.status = status
    # salva campos necessários
    if status == "done":
        r.save(update_fields=["date", "time", "status"])
    else:
        r.save(update_fields=["status"])

    return JsonResponse({
    "ok": True,
    "status": r.status,
    "date_iso": r.date.isoformat() if getattr(r, "date", None) else None,
    "time": r.time.strftime("%H:%M") if getattr(r, "time", None) else "",
})

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
        try:
            with transaction.atomic():
                form.create_everything(self.request.user)
        except ValidationError as e:
            # Erros vindos do clean() (ex.: já existe SELF no grupo) → exibidos no form
            form.add_error(None, "; ".join(e.messages))
            return self.form_invalid(form)
        except Exception as e:
            # fallback p/ qualquer outro erro inesperado
            form.add_error(None, str(e))
            return self.form_invalid(form)

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
        try:
            with transaction.atomic():
                form.join(self.request.user)
        except ValidationError as e:
            # Mostra mensagens vindas de validações de membership (p.ex. duplicidade)
            form.add_error(None, "; ".join(e.messages))
            return self.form_invalid(form)
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
    "vital":      {"label": "Sinais Vitais","icon": "❤️", "bg": "bg-rose-50", "ring": "ring-black-200"},
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
    m = _membership_or_404(request.user)
    p = m.group.patient

    qs = CareRecord.objects.filter(patient=p)

    # filtros opcionais
    category = (request.GET.get("category") or "").strip()
    if category:
        qs = qs.filter(type=category)

    include_done   = request.GET.get("include_done") == "1"
    include_missed = request.GET.get("include_missed") == "1"
    statuses = ["pending"]
    if include_done:   statuses.append("done")
    if include_missed: statuses.append("missed")
    qs = qs.filter(status__in=statuses)

    today = timezone.localdate()
    now_t = timezone.localtime().time()

    day_str = (request.GET.get("day") or "").strip()
    if day_str:
        try:
            day = dt_date.fromisoformat(day_str)
        except ValueError:
            return JsonResponse({"ok": False, "items": []})
        if day < today:
            return JsonResponse({"ok": True, "items": []})
        elif day == today:
            qs = qs.filter(Q(date=today, time__isnull=True) | Q(date=today, time__gt=now_t))
        else:
            qs = qs.filter(date=day)
    else:
        # FUTURO: hoje a partir de agora + próximos dias
        qs = qs.filter(
            Q(date__gt=today) |
            Q(date=today, time__isnull=True) |
            Q(date=today, time__gt=now_t)
        )

    qs = qs.order_by("date", "time")

    # novo: permite aumentar o limite
    try:
        limit = int(request.GET.get("limit", 50))  # default 50 (era 10)
    except ValueError:
        limit = 50

    items = [{
        "type": r.type,
        "title": f"{r.get_type_display()}" + (f" • {r.what}" if r.what else ""),
        "date": r.date.strftime("%d/%m/%Y"),
        "time": r.time.strftime("%H:%M") if r.time else "",
        "who": r.caregiver or "",
    } for r in qs[:limit]]

    return JsonResponse({"ok": True, "items": items})

@login_required
def record_delete(request, pk):
    membership = _membership_or_404(request.user)  # você já tem esse helper
    patient = membership.group.patient
    rec = get_object_or_404(CareRecord, pk=pk, patient=patient)

    # só criador ou superuser pode excluir
    if rec.created_by_id != request.user.id and not request.user.is_superuser:
        return HttpResponseForbidden("Sem permissão para excluir este registro.")

    if request.method == "POST":
        rec.delete()
        # AJAX/JSON?
        wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest" \
                     or "json" in (request.headers.get("accept") or "").lower()
        if wants_json:
            return JsonResponse({"ok": True})
        messages.success(request, "Registro excluído.")
        return redirect("care:dashboard")

    # Fallback opcional (GET) – página de confirmação tradicional
    return render(request, "care/record_confirm_delete.html", {"record": rec})

@login_required
def dashboard(request):
    if not user_group(request.user):
        return redirect("care:choose-group")

    p = users_patient(request.user)
    base_qs = CareRecord.objects.filter(patient=p).select_related("patient") if p else CareRecord.objects.none()

    # -------- Data/hora de referência --------
    today  = timezone.localdate()
    now_dt = timezone.localtime()

    # -------- Leitura de parâmetros --------
    start_str = (request.GET.get("start") or "").strip()
    end_str   = (request.GET.get("end") or "").strip()
    category  = (request.GET.get("category") or "").strip() or None
    clear     = (request.GET.get("clear") or "").strip() == "1"   # << flag do "X"

    start = _parse_date(start_str) if start_str else None
    end   = _parse_date(end_str)   if end_str   else None

    # ✅ Regra: se NÃO há start/end e NÃO é clear, defaulta hoje (filtro ativo).
    if not start and not end and not clear:
        start = end = today

    # range_mode só quando existe período aplicável
    range_mode = bool(start or end)

    # -------- Query base + período --------
    qs = base_qs
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    # Categoria
    qs_cat = qs.filter(type=category) if category else qs
    base_qs_cat = base_qs.filter(type=category) if category else base_qs

    # -------- Helpers --------
    def _status_of(r):
        s = getattr(r, "status", None)
        return s if s in ("pending", "done", "missed") else "pending"

    # -------- Listagens --------
    range_groups, schedule = [], []
    if range_mode:
        qs_range = qs_cat.order_by("-date", "-time")
        for day, items in groupby(qs_range, key=lambda r: r.date):
            items_list = [{"obj": r, "status": _status_of(r)} for r in items]
            range_groups.append({"date": day, "items": items_list})
    else:
        schedule_qs = qs_cat.order_by("-date", "-time")
        schedule = [{"obj": r, "status": _status_of(r)} for r in schedule_qs]

    # -------- Export CSV --------
    if request.GET.get("export") == "csv":
        qs_export = qs_cat if range_mode else base_qs_cat
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        fn_start = (start.isoformat() if start else "all")
        fn_end   = (end.isoformat()   if end   else "all")
        resp["Content-Disposition"] = (
            f'attachment; filename="registros_{fn_start}_{fn_end}'
            + (f'_{category}' if category else '')
            + '.csv"'
        )
        resp.write("\ufeff")
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

    # -------- Cards (ignora 'missed') --------
    qs_for_counts = (qs if range_mode else base_qs).exclude(status="missed")
    raw_counts = dict(qs_for_counts.values_list("type").annotate(total=Count("id")))
    counts = {k: raw_counts.get(k, 0) for k in CATEGORY_META.keys()}
    meta = {k: {**v, "count": counts.get(k, 0)} for k, v in CATEGORY_META.items()}

    # -------- Calendário --------
    month_param = _parse_date(request.GET.get("m"))
    month_ref = (month_param or today).replace(day=1)
    year, month = month_ref.year, month_ref.month

    cal = Calendar(firstweekday=6)
    cal_weeks = cal.monthdayscalendar(year, month)

    in_month_qs = base_qs.filter(date__year=year, date__month=month).order_by("date", "time")
    days_with = set(d["date"].day for d in in_month_qs.values("date"))

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

    prev_month = (month_ref - timedelta(days=1)).replace(day=1)
    next_month = (month_ref + timedelta(days=31)).replace(day=1)

    # -------- Próximos (futuro; respeita categoria) --------
    up_base = base_qs_cat.filter(status="pending")
    upcoming = up_base.filter(
        Q(date__gt=today) |
        Q(date=today, time__isnull=True) |
        Q(date=today, time__gt=now_dt.time())
    ).order_by("date", "time")[:10]

    # -------- Choices de categoria --------
    try:
        type_enum = getattr(CareRecord, "Type", None)
        record_categories = list(type_enum.choices) if type_enum and getattr(type_enum, "choices", None) else None
    except Exception:
        record_categories = None
    if record_categories is None:
        record_categories = []
        for key, data in CATEGORY_META.items():
            label = (data.get("label") or data.get("name") or data.get("title")) if isinstance(data, dict) else None
            if not label:
                label = key.replace("_", " ").capitalize()
            record_categories.append((key, label))

    ctx = {
        "filters":    {"start": start, "end": end, "category": category},
        "filters_ui": {"start": start.isoformat() if start else "", "end": end.isoformat() if end else "", "category": category},

        "record_categories": record_categories,
        "meta": meta,
        "month": month,
        "range_mode": range_mode,
        "range_groups": range_groups,
        "schedule": schedule,
        "month_name": month_name[month],
        "year": year,
        "cal_weeks": cal_weeks,
        "days_with": days_with,
        "selected_day": start if (start and end and start == end) else None,
        "today": today,
        "prev_month": prev_month,
        "next_month": next_month,
        "upcoming": upcoming,
        "calendar_events_by_date": events_by_date,
        "schedule_day": today,
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
    ('medication', 'Remédio'),
    ('sleep', 'Sono'),
    ('meal', 'Alimentação'),
    ('bathroom', 'Banheiro'),
    ('activity', 'Exercício'),
    ('vital', 'Sinais Vitais'),   # ✅ adicionado
    ('other', 'Outros'),
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

        # aceita ?date=YYYY-MM-DD e ?time=HH:MM
        date_q = (self.request.GET.get("date") or "").strip()
        if date_q:
            try:
                d = parse_date(date_q)
                if d:
                    initial["date"] = d
            except Exception:
                pass

        time_q = (self.request.GET.get("time") or "").strip()
        if time_q:
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

    def form_valid(self, form):
        """
        Mantém o que já fazia, e adiciona suporte a recorrência:
        repeat=none|daily|weekly, repeat_until=YYYY-MM-DD, repeat_times=int
        """
        self.object = form.save(commit=False)

        if not self.object.type:
            self.object.type = self._selected_category()

        # paciente do grupo (se faltar)
        if not self.object.patient_id:
            grp = getattr(self.request.user, "group_membership", None)
            if grp and getattr(grp, "group", None):
                self.object.patient_id = grp.group.patient_id

        # caregiver/autor
        if not self.object.caregiver:
            self.object.caregiver = self.request.user.get_full_name() or self.request.user.username
        self.object.created_by = self.request.user

        # -------- Recorrência (novidade) --------
        repeat = (self.request.POST.get("repeat") or "none").strip().lower()  # none|daily|weekly
        repeat_until = parse_date(self.request.POST.get("repeat_until") or "")  # opcional
        try:
            repeat_times = int(self.request.POST.get("repeat_times") or "0")
        except ValueError:
            repeat_times = 0

        # Defaults seguros se usuário marcou recorrência mas não passou limites:
        if repeat in {"daily", "weekly"} and not repeat_until and repeat_times <= 0:
            repeat_times = 7 if repeat == "daily" else 4  # daily→7 ocorrências, weekly→4

        # Persistimos a 1ª ocorrência normalmente
        # Se houver campo series_code no modelo, inicializamos
        series_code = None
        if hasattr(self.object, "series_code"):
            series_code = f"ser-{uuid.uuid4().hex[:16]}"
            setattr(self.object, "series_code", series_code)

        self.object.save()  # salva a primeira

        # Gera as próximas (se pedido)
        if repeat in {"daily", "weekly"}:
            step_days = 1 if repeat == "daily" else 7
            base_date = self.object.date
            base_time = self.object.time

            # Monta uma sequência de datas a partir da PRÓXIMA ocorrência
            dates = []
            cur_date = base_date + timedelta(days=step_days)

            # Critérios de parada: até repeat_until (se dado) OU até repeat_times total (inclui a primeira)
            remaining = max(0, (repeat_times - 1)) if repeat_times else None  # já temos a 1ª salva

            while True:
                if repeat_until and cur_date > repeat_until:
                    break
                if remaining is not None and remaining <= 0:
                    break
                dates.append(cur_date)
                cur_date += timedelta(days=step_days)
                if remaining is not None:
                    remaining -= 1

            clones = []
            for d in dates:
                clone = CareRecord(
                    patient_id=self.object.patient_id,
                    type=self.object.type,
                    what=self.object.what,
                    description=self.object.description,
                    date=d,
                    time=base_time,
                    caregiver=self.object.caregiver,
                    status="pending",
                    created_by=self.request.user,
                )
                if series_code and hasattr(clone, "series_code"):
                    clone.series_code = series_code
                clones.append(clone)

            if clones:
                CareRecord.objects.bulk_create(clones, ignore_conflicts=True)

        messages.success(self.request, "Atividade registrada!")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        base = reverse("care:record-create")
        return f"{base}?category={self._selected_category()}#history"

@require_POST
@login_required
def record_cancel_following(request, pk):
    """
    Cancela uma série a partir deste item:
    - Se houver series_code: apaga todas as ocorrências da mesma série
      com data/hora >= a deste registro.
    - Se não houver series_code: apaga apenas este item (conservador).
    Retorna JSON.
    """
    membership = _membership_or_404(request.user)
    patient = membership.group.patient

    rec = get_object_or_404(CareRecord, pk=pk, patient=patient)

    # permissão: criador ou superuser
    if rec.created_by_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({"ok": False, "message": "Sem permissão."}, status=403)

    deleted = 0
    if hasattr(rec, "series_code") and getattr(rec, "series_code", ""):
        code = rec.series_code
        # seleciona "a partir de"
        cond = Q(date__gt=rec.date)
        if rec.time:
            cond |= Q(date=rec.date, time__gte=rec.time)
        else:
            cond |= Q(date=rec.date)

        qs = CareRecord.objects.filter(patient=patient, series_code=code).filter(cond)
        deleted, _ = qs.delete()

        # também pode excluir o próprio, se desejado:
        self_too = (request.POST.get("include_current") == "1")
        if self_too:
            d1, _ = CareRecord.objects.filter(pk=rec.pk).delete()
            deleted += d1
    else:
        # sem series_code → só o próprio
        d1, _ = CareRecord.objects.filter(pk=rec.pk).delete()
        deleted += d1

    return JsonResponse({"ok": True, "deleted": int(deleted)})

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

    # Status: por padrão só 'pending'; com flags, inclui conforme solicitado
    if include_done and include_missed:
        pass  # todos os status
    elif include_done:
        qs = qs.filter(status__in=['pending', 'done'])
    elif include_missed:
        qs = qs.filter(status__in=['pending', 'missed'])
    else:
        qs = qs.filter(status='pending')

        # Corte por horário para HOJE: exclui o que já passou (com hora definida)
        now_t = timezone.localtime().time()
        qs = qs.exclude(Q(date=today) & Q(time__isnull=False) & Q(time__lte=now_t))
        # Observação:
        # - Itens de HOJE sem hora continuam aparecendo (pendentes).
        # - Dias futuros entram normalmente.
        # - Dias passados no intervalo (se houver) permanecem, o corte é só para a data de hoje.

    # Totais (respeitam os mesmos filtros aplicados a 'qs')
    totals = {'pending': 0, 'done': 0, 'missed': 0}
    for row in qs.values('status').annotate(total=Count('id')):
        totals[row['status']] = row['total']

    # Buckets agrupados por dia
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
        # Novos campos para o botão no dashboard:
        'series': bool(getattr(r, 'series_code', None)),
        'cancel_from_here_url': reverse('care:record-cancel-following', args=[r.id]),
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