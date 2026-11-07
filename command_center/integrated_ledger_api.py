"""Durable, staff-only API for the unified C01-C50 management ledger."""
import hashlib
import json
import re
from datetime import date
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, F, Count
from .models import CycleReport, CycleIssue, ApprovalDecision, WorkItem, InternalMessage, PrivateAuction, LedgerAuditEvent, CommandRequest
from accounting.models import JournalEntry, Account
from core.approval import ApprovalService
from core.models import ApprovalRequest, ResearchProject
from .zomorod_status import read_zomorod_health

PROJECTS = {
    "management": "مدیریت یکپارچه زمرد ملل", "zomorod-web": "وب‌سایت و فروشگاه‌های زمرد ملل",
    "mojplaywin": "فروشگاه MojPlayWin", "mojcoin": "بازی Moj Coin", "research": "مقاله و پژوهش علمی",
    "factory": "کارخانه و تولید", "books": "کتاب و محصولات نوشتاری", "trade": "تجارت، تریدر و ارزها",
    "profile": "وب‌سایت و معرفی مجتبی روزگار",
}
CYCLES = {f"C{i:02d}" for i in range(1, 51)}
DOMAINS = {"command": "فرمان و چرخه‌ها", "virtual": "سایت‌ها و کسب‌وکار مجازی", "physical": "شرکت و کسب‌وکار فیزیکی"}

def _text(value):
    return str(value or "").strip()

def _action_key(value):
    normalized = re.sub(r"[\W_]+", " ", _text(value).lower(), flags=re.UNICODE).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _report(row):
    return {"id": row.id, "domain": row.domain, "domain_name": DOMAINS.get(row.domain, row.domain), "cycle": row.cycle, "project": row.project_key, "project_name": row.project_name,
            "action": row.action, "result": row.result, "measure": row.measure, "blocker": row.blocker,
            "next": row.next_action, "evidence": row.evidence, "owner": row.owner,
            "date": row.action_date.isoformat(), "readonly": row.readonly, "created_at": row.created_at.isoformat()}

def _issue(row):
    return {"id": row.id, "domain": row.domain, "domain_name": DOMAINS.get(row.domain, row.domain), "cycle": row.cycle, "project": row.project_key, "title": row.title,
            "owner": row.owner, "date": row.observed_on.isoformat(), "verified": row.certainty == "verified",
            "source": row.source, "next": row.next_action, "status": row.status,
            "resolution_evidence": row.resolution_evidence, "created_at": row.created_at.isoformat()}

def _audit(action, entity, entity_id, summary, actor, evidence=""):
    LedgerAuditEvent.objects.create(action=action, entity=entity, entity_id=str(entity_id), summary=summary, evidence=evidence, actor=actor)

def _audit_row(row):
    return {"id": row.id, "action": row.action, "entity": row.entity, "entity_id": row.entity_id,
            "summary": row.summary, "evidence": row.evidence, "actor": row.actor.get_username(),
            "created_at": row.created_at.isoformat()}

def _decision(row):
    return {"id": row.id, "kind": row.kind, "status": row.status, "approver": row.approver,
            "evidence": row.evidence, "created_at": row.created_at.isoformat()}

def _approval_request(row):
    return {"id": row.id, "action_type": row.action_type, "target_type": row.target_type,
            "target_id": row.target_id, "reason": row.reason, "risk": row.risk,
            "status": row.status, "decision_note": row.decision_note,
            "requested_by": row.requested_by.get_username(),
            "created_at": row.created_at.isoformat()}

def _command(row):
    return {"id": row.id, "domain": row.domain, "domain_name": DOMAINS.get(row.domain, row.domain),
            "command": row.command, "status": row.status, "read_only": row.read_only,
            "result": row.result, "requested_by": row.requested_by.get_username(),
            "created_at": row.created_at.isoformat()}

def _finance_snapshot():
    posted = JournalEntry.objects.filter(status=JournalEntry.Status.POSTED)
    rows = Account.objects.filter(kind__in=(Account.Kind.REVENUE, Account.Kind.EXPENSE)).annotate(
        debit_total=Sum("journal_lines__debit", filter=Q(journal_lines__entry__in=posted)),
        credit_total=Sum("journal_lines__credit", filter=Q(journal_lines__entry__in=posted)),
    )
    return [{"name": row.name, "kind": row.kind, "debit": str(row.debit_total or 0), "credit": str(row.credit_total or 0)} for row in rows]

def _finance_integrity():
    """One grouped query; do not load all financial documents on every UI poll."""
    invalid = (JournalEntry.objects.filter(status=JournalEntry.Status.POSTED)
               .annotate(total_debit=Sum("lines__debit"), total_credit=Sum("lines__credit"))
               .filter(Q(total_debit__isnull=True) | Q(total_debit__lte=0) |
                       ~Q(total_debit=F("total_credit"))).exists())
    return {"balanced_posted_entries": not invalid, "source": "Django double-entry ledger (posted only)"}

def _no_output_rows():
    return [{"id": row.id, "title": row.title, "status": row.status, "priority": row.priority,
             "due_at": row.due_at.isoformat() if row.due_at else None, "reason": "مرجع نتیجه یا رفع کامل ثبت نشده است."}
            for row in WorkItem.objects.filter(status__in=("open", "in_progress", "blocked")).filter(
                Q(resolution_reference="") | Q(resolution_reference__isnull=True))[:100]]

def cycle_health():
    """Read-only coverage and exceptions; reporting alone never means completion."""
    rows = CycleReport.objects.values("project_key", "cycle").annotate(actions=Count("pk"))
    by_project = {project: set() for project in PROJECTS}
    total_actions = 0
    for row in rows:
        if row["project_key"] in by_project:
            by_project[row["project_key"]].add(row["cycle"])
        total_actions += row["actions"]
    coverage = []
    for key, name in PROJECTS.items():
        recorded = by_project[key]
        remaining = sorted(CYCLES - recorded)
        coverage.append({"project": key, "name": name, "cycles_with_reports": len(recorded),
                         "next_unreported": remaining[0] if remaining else None,
                         "missing_cycles": len(remaining)})
    now = timezone.now()
    return {"coverage": coverage, "recorded_actions": total_actions,
            "overdue_open_work": WorkItem.objects.filter(status__in=("open", "in_progress", "blocked"), due_at__lt=now).count(),
            "no_result_reference": WorkItem.objects.filter(status__in=("open", "in_progress", "blocked")).filter(
                Q(resolution_reference="") | Q(resolution_reference__isnull=True)).count(),
            "done_without_evidence": WorkItem.objects.filter(status="done").filter(
                Q(resolution_reference="") | Q(resolution_reference__isnull=True)).count(),
            "pending_owner_approval": ApprovalRequest.objects.filter(status="pending").count(),
            "verified_completions": None,
            "note": "وجود گزارش فقط ثبت ادعاست؛ تکمیل واقعی بدون شاهد مستقل احراز نمی‌شود."}

def _auto_execute_command(request, domain, command_text):
    # Arbitrary natural language is NEVER an executable instruction. Only exact,
    # bounded local queries may be labeled executed. In particular, a sentence
    # containing the word "audit" must not silently become a successful job.
    command = command_text.strip().lower()
    if command in ("monitor:systems", "پایش وضعیت سامانه"):
        systems = _system_status(request)
        connected = sum(1 for item in systems if item["state"] in ("connected", "healthy"))
        return "executed", True, f"وضعیت اتصال‌ها خوانده شد؛ {connected} مورد دارای شاهد داخلی است؛ سایر اتصال‌ها نامشخص باقی می‌مانند."
    if command in ("monitor:work", "پایش کارهای بدون خروجی"):
        open_work = WorkItem.objects.filter(status__in=("open", "in_progress", "blocked")).count()
        unproven = len(_no_output_rows())
        return "executed", True, f"صف داخلی خوانده شد؛ {open_work} کار ناتمام، و حداقل {unproven} کار فاقد مرجع نتیجه در نمونهٔ ۱۰۰تایی وجود دارد."
    return "pending", False, "فرمان فقط ثبت شد؛ هیچ اجرای خودکار یا تأیید ضمنی برای متن آزاد وجود ندارد."

def _system_status(request):
    names = {
        "iran_site": "سایت زمرد ملل", "cpanel": "هاست و cPanel", "factory": "کارخانه",
        "mojplaywin": "فروشگاه MojPlayWin", "mojcoin": "بازی Moj Coin",
        "research": "مقاله و پژوهش", "books": "کتاب و محصولات نوشتاری",
        "trade": "تجارت و ارزها", "accounting": "حسابداری",
    }
    links = {
        "iran_site": "https://zomorodmelal.ir/", "mojplaywin": "https://mojplaywin.com/",
        "accounting": "/staff/command-center/accounting/", "research": "/research/projects/",
        "trade": "/business/", "factory": "/staff/command-center/",
    }
    rows = {key: {"id": key, "name": label, "url": links.get(key), "state": "unknown",
                  "detail": "آداپتور زنده برای این بخش ثبت نشده است.", "observed_at": None}
            for key, label in names.items()}
    host = request.get_host().split(":")[0].lower()
    if host in ("zomorodmelal.ir", "www.zomorodmelal.ir"):
        observations, _ = read_zomorod_health()
        for item in observations:
            if item.get("component") in rows:
                rows[item["component"]].update(state=item.get("state", "unknown"),
                    detail=item.get("detail", "پایش read-only"), observed_at=item.get("observed_at"))
    rows["accounting"].update(state="connected", detail="اتصال مستقیم به دفتر مالی داخلی")
    return list(rows.values())


@staff_member_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def integrated_ledger_api(request):
    if request.method == "GET":
        # GET must not acknowledge, execute, or mutate queued work.
        systems = _system_status(request)
        integrity = _finance_integrity()
        return JsonResponse({"captured_at": timezone.now().isoformat(),
            "reports": [_report(x) for x in CycleReport.objects.all()],
            "issues": [_issue(x) for x in CycleIssue.objects.all()],
            "decisions": [_decision(x) for x in ApprovalDecision.objects.all()],
            "audit": [_audit_row(x) for x in LedgerAuditEvent.objects.select_related("actor")[:100]],
            "commands": [_command(x) for x in CommandRequest.objects.select_related("requested_by")[:100]],
            "pending_approvals": [_approval_request(x) for x in ApprovalRequest.objects.filter(
                status="pending", requested_by=request.user).select_related("requested_by").order_by("created_at")[:100]],
            "systems": systems,
            "finance": _finance_snapshot(),
            "finance_integrity": integrity,
            "no_output": _no_output_rows(),
            "cycle_health": cycle_health(),
            "release_readiness": {"open_issues": CycleIssue.objects.filter(status="open").count(),
                                  "blocked_work": WorkItem.objects.filter(status="blocked").count(),
                                  "pending_approvals": ApprovalRequest.objects.filter(status="pending").count(),
                                  "unknown_connections": sum(1 for item in systems if item["state"] == "unknown"),
                                  "ledger_balanced": integrity["balanced_posted_entries"]},
            "live_summary": {
                "accounting": {"posted": JournalEntry.objects.filter(status=JournalEntry.Status.POSTED).count(),
                               "draft": JournalEntry.objects.filter(status=JournalEntry.Status.DRAFT).count()},
                "work": {"open": WorkItem.objects.filter(status="open").count(),
                         "in_progress": WorkItem.objects.filter(status="in_progress").count(),
                         "blocked": WorkItem.objects.filter(status="blocked").count(),
                         "done": WorkItem.objects.filter(status="done").count()},
                "communications": {"unread_for_me": InternalMessage.objects.filter(recipient=request.user, read_at__isnull=True).count()},
                "auctions": {"draft": PrivateAuction.objects.filter(status="draft").count(),
                             "open": PrivateAuction.objects.filter(status="open").count()},
                "approvals": {"pending": ApprovalRequest.objects.filter(status="pending").count()},
                "projects": {"active_or_draft": ResearchProject.objects.exclude(status__in=["done", "closed", "archived"]).count()},
            }})
    try:
        payload = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "بدنهٔ درخواست معتبر نیست."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "فرمت درخواست باید شیء JSON باشد."}, status=400)
    kind = _text(payload.get("kind"))
    if kind == "command":
        domain, command_text = _text(payload.get("domain")) or "command", _text(payload.get("command"))
        if domain not in DOMAINS or not command_text:
            return JsonResponse({"error": "قلمرو و متن فرمان الزامی است."}, status=400)
        status, read_only, result = _auto_execute_command(request, domain, command_text)
        row = CommandRequest.objects.create(domain=domain, command=command_text, status=status, read_only=read_only,
            result=result, requested_by=request.user, executed_at=timezone.now() if status == "executed" else None)
        _audit("create", "command", row.id, "فرمان خودکار ثبت و ارزیابی شد.", request.user, result)
        return JsonResponse({"command": _command(row)}, status=201)

    if kind == "report":
        domain = _text(payload.get("domain")) or "command"
        cycle, project, action = _text(payload.get("cycle")), _text(payload.get("project")), _text(payload.get("action"))
        result, measure, evidence = _text(payload.get("result")), _text(payload.get("measure")), _text(payload.get("evidence"))
        owner, next_action = _text(payload.get("owner")), _text(payload.get("next"))
        if domain not in DOMAINS or cycle not in CYCLES or project not in PROJECTS or not all((action, result, measure, evidence, owner, next_action)):
            return JsonResponse({"error": "چرخه، پروژه، اقدام، نتیجه، واحد سنجش، شاهد، مسئول و اقدام بعدی الزامی است."}, status=400)
        if len(result) > 240 or len(measure) > 160 or len(owner) > 160 or len(next_action) > 240:
            return JsonResponse({"error": "یکی از فیلدهای گزارش بیش از حد مجاز طولانی است."}, status=400)
        key = _action_key(action)
        if CycleReport.objects.filter(cycle=cycle, project_key=project, action_key=key).exists():
            return JsonResponse({"error": "گزارش تکراری است و ذخیره نشد."}, status=409)
        try: action_date = date.fromisoformat(_text(payload.get("date")))
        except ValueError: return JsonResponse({"error": "تاریخ اقدام معتبر نیست."}, status=400)
        try:
            row = CycleReport.objects.create(domain=domain, cycle=cycle, project_key=project, project_name=PROJECTS[project], action=action,
                action_key=key, result=result, measure=measure, blocker=_text(payload.get("blocker")),
                next_action=next_action, evidence=evidence, owner=owner,
                action_date=action_date, readonly=bool(payload.get("readonly")), created_by=request.user)
        except IntegrityError:
            return JsonResponse({"error": "گزارش تکراری است و ذخیره نشد."}, status=409)
        _audit("create", "report", row.id, f"گزارش {cycle} برای {PROJECTS[project]} ثبت شد.", request.user, evidence)
        return JsonResponse({"report": _report(row)}, status=201)
    if kind == "issue":
        domain = _text(payload.get("domain")) or "command"
        cycle, project, title = _text(payload.get("cycle")), _text(payload.get("project")), _text(payload.get("title"))
        certainty, source = _text(payload.get("certainty")) or "unverified", _text(payload.get("source"))
        owner, next_action = _text(payload.get("owner")), _text(payload.get("next"))
        if domain not in DOMAINS or cycle not in CYCLES or project not in PROJECTS or not title or not owner or not next_action or certainty not in ("verified", "unverified"):
            return JsonResponse({"error": "چرخه، پروژه، شرح مشکل، مسئول و اقدام بعدی الزامی است."}, status=400)
        if len(owner) > 160 or len(next_action) > 240:
            return JsonResponse({"error": "مسئول یا اقدام بعدی بیش از حد مجاز طولانی است."}, status=400)
        if certainty == "verified" and not source: return JsonResponse({"error": "برای مانع تأییدشده، منبع الزامی است."}, status=400)
        try: observed_on = date.fromisoformat(_text(payload.get("date")))
        except ValueError: return JsonResponse({"error": "تاریخ مشاهده معتبر نیست."}, status=400)
        row = CycleIssue.objects.create(domain=domain, cycle=cycle, project_key=project, title=title, owner=owner,
            observed_on=observed_on, certainty=certainty, source=source, next_action=next_action, created_by=request.user)
        _audit("create", "issue", row.id, f"مانع {cycle} برای {PROJECTS[project]} ثبت شد.", request.user, source)
        return JsonResponse({"issue": _issue(row)}, status=201)
    if kind == "issue_update":
        try: row = CycleIssue.objects.get(pk=int(payload.get("id")))
        except (CycleIssue.DoesNotExist, TypeError, ValueError): return JsonResponse({"error": "مانع پیدا نشد."}, status=404)
        evidence = _text(payload.get("evidence"))
        if not evidence: return JsonResponse({"error": "مدرک الزامی است."}, status=400)
        if _text(payload.get("action")) == "resolve": row.status, row.resolution_evidence, row.resolved_at = "resolved", evidence, timezone.now()
        else: row.certainty, row.source = "verified", evidence
        row.save(update_fields=["status", "resolution_evidence", "resolved_at", "certainty", "source"])
        event_action = "resolve" if _text(payload.get("action")) == "resolve" else "verify"
        _audit(event_action, "issue", row.id, f"مانع {row.cycle} به‌روزرسانی شد.", request.user, evidence)
        return JsonResponse({"issue": _issue(row)})
    if kind == "approval_request":
        try:
            row = ApprovalRequest.objects.select_for_update().get(pk=int(payload.get("id")))
        except (ApprovalRequest.DoesNotExist, TypeError, ValueError):
            return JsonResponse({"error": "درخواست تأیید پیدا نشد."}, status=404)
        action = _text(payload.get("action"))
        note = _text(payload.get("note"))
        if action not in {"approved", "rejected", "explanation"}:
            return JsonResponse({"error": "عملیات باید قبول، رد یا توضیح باشد."}, status=400)
        if row.status != "pending":
            return JsonResponse({"error": "درخواست قبلاً تعیین تکلیف شده است."}, status=409)
        if row.requested_by_id != request.user.pk:
            return JsonResponse({"error": "فقط مالک تعیین‌شدهٔ درخواست اجازهٔ تصمیم دارد."}, status=403)
        if action == "explanation":
            if not note:
                return JsonResponse({"error": "توضیح خالی است."}, status=400)
            row.decision_note = note
            row.save(update_fields=["decision_note", "updated_at"])
            _audit("approve", "approval_request", row.id, "توضیح برای درخواست تأیید ثبت شد.", request.user, note)
            return JsonResponse({"approval_request": _approval_request(row)})
        try:
            # Use the canonical owner-only lifecycle; it validates the target
            # and updates any dependent task/intent atomically and auditably.
            row = ApprovalService().decide(row.pk, approved=action == "approved",
                                          actor_id=request.user.pk, note=note, actor_type="owner")
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        _audit("approve", "approval_request", row.id, f"درخواست تأیید {action} شد.", request.user, note)
        return JsonResponse({"approval_request": _approval_request(row)})

    if kind == "approval":
        decision = _text(payload.get("status"))
        decision_kind = _text(payload.get("approval_kind"))
        if not request.user.is_superuser:
            return JsonResponse({"error": "ثبت تصمیم حساس فقط با حساب مالک مجاز است."}, status=403)
        if decision_kind not in {"email", "deploy", "cost"} or decision not in {"approved", "rejected"}:
            return JsonResponse({"error": "نوع تصمیم، وضعیت و نام تأییدکننده الزامی است."}, status=400)
        row = ApprovalDecision.objects.create(kind=decision_kind, status=decision, approver=request.user.get_username(), evidence=_text(payload.get("evidence")), created_by=request.user)
        _audit("approve", "approval", row.id, f"تصمیم {row.kind} با وضعیت {row.status} ثبت شد.", request.user, row.evidence)
        return JsonResponse({"decision": _decision(row)}, status=201)
    return JsonResponse({"error": "نوع عملیات شناخته نشد."}, status=400)
