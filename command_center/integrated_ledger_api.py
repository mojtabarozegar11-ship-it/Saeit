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
from django.db.models import Q, Sum
from .models import CycleReport, CycleIssue, ApprovalDecision, WorkItem, InternalMessage, PrivateAuction, LedgerAuditEvent, CommandRequest
from accounting.models import JournalEntry, Account
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

def _no_output_rows():
    return [{"id": row.id, "title": row.title, "status": row.status, "priority": row.priority,
             "due_at": row.due_at.isoformat() if row.due_at else None, "reason": "مرجع نتیجه یا رفع کامل ثبت نشده است."}
            for row in WorkItem.objects.filter(status__in=("open", "in_progress", "blocked")).filter(
                Q(resolution_reference="") | Q(resolution_reference__isnull=True))[:100]]

def _auto_execute_command(request, domain, command_text):
    text = command_text.lower()
    sensitive = ("ارسال", "ایمیل", "استقرار", "انتشار", "هزینه", "خرید", "پرداخت", "حذف", "تغییر رمز", "برداشت")
    readonly = ("وضعیت", "گزارش", "پایش", "ممیزی", "بررسی", "تعداد", "سلامت")
    if any(term in text for term in sensitive):
        return "pending", False, "این فرمان حساس است و برای اجرا به تأیید موردی نیاز دارد."
    if any(term in text for term in readonly):
        systems = _system_status(request)
        connected = sum(1 for item in systems if item["state"] in ("connected", "healthy"))
        open_work = WorkItem.objects.filter(status__in=("open", "in_progress", "blocked")).count()
        return "executed", True, f"پایش read-only خودکار انجام شد؛ {connected} اتصال دارای شاهد و {open_work} کار باز/درحال اجرا/متوقف ثبت شده است."
    return "pending", True, "فرمان در صف تحلیل قرار گرفت؛ الگوی اجرایی امن برای آن شناسایی نشد."

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
        # HTTP GET is strictly read-only: never complete commands or write audit rows.
        return JsonResponse({"captured_at": timezone.now().isoformat(),
            "reports": [_report(x) for x in CycleReport.objects.all()],
            "issues": [_issue(x) for x in CycleIssue.objects.all()],
            "decisions": [_decision(x) for x in ApprovalDecision.objects.all()],
            "audit": [_audit_row(x) for x in LedgerAuditEvent.objects.select_related("actor")[:100]],
            "commands": [_command(x) for x in CommandRequest.objects.select_related("requested_by")[:100]],
            "systems": _system_status(request),
            "finance": _finance_snapshot(),
            "no_output": _no_output_rows(),
            "release_readiness": {"open_issues": CycleIssue.objects.filter(status="open").count(),
                                  "blocked_work": WorkItem.objects.filter(status="blocked").count(),
                                  "pending_approvals": ApprovalRequest.objects.filter(status="pending").count(),
                                  "unknown_connections": sum(1 for item in _system_status(request) if item["state"] == "unknown")},
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
    except json.JSONDecodeError:
        return JsonResponse({"error": "بدنهٔ درخواست معتبر نیست."}, status=400)
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
        # Staff may inspect requests, but a staff role alone must never approve
        # sensitive external actions or impersonate the owner's decision.
        if not request.user.is_superuser:
            return JsonResponse({"error": "تصمیم حساس فقط برای مدیر ارشد مجاز است و تأیید موردی مالک همچنان الزامی است."}, status=403)
        try:
            row = ApprovalRequest.objects.select_for_update().get(pk=int(payload.get("id")))
        except (ApprovalRequest.DoesNotExist, TypeError, ValueError):
            return JsonResponse({"error": "درخواست تأیید پیدا نشد."}, status=404)
        action = _text(payload.get("action"))
        note = _text(payload.get("note"))
        if action not in {"approved", "rejected", "explanation"}:
            return JsonResponse({"error": "عملیات باید قبول، رد یا توضیح باشد."}, status=400)
        if row.status != "pending":
            return JsonResponse({"error": "درخواست قبلاً تصمیم‌گیری شده و قابل تغییر نیست."}, status=409)
        if action in {"approved", "rejected"} and not note:
            return JsonResponse({"error": "توضیح تصمیم و مرجع مجوز موردی مالک الزامی است."}, status=400)
        if action == "explanation":
            if not note:
                return JsonResponse({"error": "توضیح خالی است."}, status=400)
            row.decision_note = note
            row.save(update_fields=["decision_note", "updated_at"])
            _audit("approve", "approval_request", row.id, "توضیح برای درخواست تأیید ثبت شد.", request.user, note)
            return JsonResponse({"approval_request": _approval_request(row)})
        row.status = action
        row.decision_note = note
        row.save(update_fields=["status", "decision_note", "updated_at"])
        _audit("approve", "approval_request", row.id, f"درخواست تأیید {action} شد.", request.user, note)
        return JsonResponse({"approval_request": _approval_request(row)})

    if kind == "approval":
        # Legacy decisions are audit records only, never executable owner grants.
        # Reject ordinary staff and spoofed names before writing any approval record.
        if not request.user.is_superuser:
            return JsonResponse({"error": "ثبت تصمیم حساس فقط برای مدیر ارشد مجاز است."}, status=403)
        decision = _text(payload.get("status"))
        approver = _text(payload.get("approver"))
        evidence = _text(payload.get("evidence"))
        if (_text(payload.get("kind")) not in {"email", "deploy", "cost"}
                or decision not in {"approved", "rejected"}
                or approver != request.user.get_username() or not evidence):
            return JsonResponse({"error": "نوع تصمیم، هویت تأییدکننده و شاهد موردی معتبر الزامی است."}, status=400)
        row = ApprovalDecision.objects.create(kind=_text(payload.get("kind")), status=decision, approver=approver, evidence=evidence, created_by=request.user)
        _audit("approve", "approval", row.id, f"تصمیم {row.kind} با وضعیت {row.status} ثبت شد.", request.user, row.evidence)
        return JsonResponse({"decision": _decision(row)}, status=201)
    return JsonResponse({"error": "نوع عملیات شناخته نشد."}, status=400)
