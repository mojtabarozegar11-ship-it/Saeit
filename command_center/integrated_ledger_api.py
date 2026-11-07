"""Durable, staff-only API for the unified C01-C50 management ledger."""
import hashlib
import json
import re
from datetime import date
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError
from .models import CycleReport, CycleIssue, ApprovalDecision, WorkItem, InternalMessage, PrivateAuction, LedgerAuditEvent
from accounting.models import JournalEntry
from core.models import ApprovalRequest, ResearchProject

PROJECTS = {
    "management": "مدیریت یکپارچه زمرد ملل", "zomorod-web": "وب‌سایت و فروشگاه‌های زمرد ملل",
    "mojplaywin": "فروشگاه MojPlayWin", "mojcoin": "بازی Moj Coin", "research": "مقاله و پژوهش علمی",
    "factory": "کارخانه و تولید", "books": "کتاب و محصولات نوشتاری", "trade": "تجارت، تریدر و ارزها",
    "profile": "وب‌سایت و معرفی مجتبی روزگار",
}
CYCLES = {f"C{i:02d}" for i in range(1, 51)}

def _text(value):
    return str(value or "").strip()

def _action_key(value):
    normalized = re.sub(r"[\W_]+", " ", _text(value).lower(), flags=re.UNICODE).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _report(row):
    return {"id": row.id, "cycle": row.cycle, "project": row.project_key, "project_name": row.project_name,
            "action": row.action, "result": row.result, "measure": row.measure, "blocker": row.blocker,
            "next": row.next_action, "evidence": row.evidence, "owner": row.owner,
            "date": row.action_date.isoformat(), "readonly": row.readonly, "created_at": row.created_at.isoformat()}

def _issue(row):
    return {"id": row.id, "cycle": row.cycle, "project": row.project_key, "title": row.title,
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

@staff_member_required
@require_http_methods(["GET", "POST"])
def integrated_ledger_api(request):
    if request.method == "GET":
        return JsonResponse({"captured_at": timezone.now().isoformat(),
            "reports": [_report(x) for x in CycleReport.objects.all()],
            "issues": [_issue(x) for x in CycleIssue.objects.all()],
            "decisions": [_decision(x) for x in ApprovalDecision.objects.all()],
            "audit": [_audit_row(x) for x in LedgerAuditEvent.objects.select_related("actor")[:100]],
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
    if kind == "report":
        cycle, project, action = _text(payload.get("cycle")), _text(payload.get("project")), _text(payload.get("action"))
        result, measure, evidence = _text(payload.get("result")), _text(payload.get("measure")), _text(payload.get("evidence"))
        owner, next_action = _text(payload.get("owner")), _text(payload.get("next"))
        if cycle not in CYCLES or project not in PROJECTS or not all((action, result, measure, evidence, owner, next_action)):
            return JsonResponse({"error": "چرخه، پروژه، اقدام، نتیجه، واحد سنجش، شاهد، مسئول و اقدام بعدی الزامی است."}, status=400)
        if len(result) > 240 or len(measure) > 160 or len(owner) > 160 or len(next_action) > 240:
            return JsonResponse({"error": "یکی از فیلدهای گزارش بیش از حد مجاز طولانی است."}, status=400)
        key = _action_key(action)
        if CycleReport.objects.filter(cycle=cycle, project_key=project, action_key=key).exists():
            return JsonResponse({"error": "گزارش تکراری است و ذخیره نشد."}, status=409)
        try: action_date = date.fromisoformat(_text(payload.get("date")))
        except ValueError: return JsonResponse({"error": "تاریخ اقدام معتبر نیست."}, status=400)
        try:
            row = CycleReport.objects.create(cycle=cycle, project_key=project, project_name=PROJECTS[project], action=action,
                action_key=key, result=result, measure=measure, blocker=_text(payload.get("blocker")),
                next_action=next_action, evidence=evidence, owner=owner,
                action_date=action_date, readonly=bool(payload.get("readonly")), created_by=request.user)
        except IntegrityError:
            return JsonResponse({"error": "گزارش تکراری است و ذخیره نشد."}, status=409)
        _audit("create", "report", row.id, f"گزارش {cycle} برای {PROJECTS[project]} ثبت شد.", request.user, evidence)
        return JsonResponse({"report": _report(row)}, status=201)
    if kind == "issue":
        cycle, project, title = _text(payload.get("cycle")), _text(payload.get("project")), _text(payload.get("title"))
        certainty, source = _text(payload.get("certainty")) or "unverified", _text(payload.get("source"))
        owner, next_action = _text(payload.get("owner")), _text(payload.get("next"))
        if cycle not in CYCLES or project not in PROJECTS or not title or not owner or not next_action or certainty not in ("verified", "unverified"):
            return JsonResponse({"error": "چرخه، پروژه، شرح مشکل، مسئول و اقدام بعدی الزامی است."}, status=400)
        if len(owner) > 160 or len(next_action) > 240:
            return JsonResponse({"error": "مسئول یا اقدام بعدی بیش از حد مجاز طولانی است."}, status=400)
        if certainty == "verified" and not source: return JsonResponse({"error": "برای مانع تأییدشده، منبع الزامی است."}, status=400)
        try: observed_on = date.fromisoformat(_text(payload.get("date")))
        except ValueError: return JsonResponse({"error": "تاریخ مشاهده معتبر نیست."}, status=400)
        row = CycleIssue.objects.create(cycle=cycle, project_key=project, title=title, owner=owner,
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
    if kind == "approval":
        decision = _text(payload.get("status"))
        if _text(payload.get("kind")) not in {"email", "deploy", "cost"} or decision not in {"approved", "rejected"} or not _text(payload.get("approver")):
            return JsonResponse({"error": "نوع تصمیم، وضعیت و نام تأییدکننده الزامی است."}, status=400)
        row = ApprovalDecision.objects.create(kind=_text(payload.get("kind")), status=decision, approver=_text(payload.get("approver")), evidence=_text(payload.get("evidence")), created_by=request.user)
        _audit("approve", "approval", row.id, f"تصمیم {row.kind} با وضعیت {row.status} ثبت شد.", request.user, row.evidence)
        return JsonResponse({"decision": _decision(row)}, status=201)
    return JsonResponse({"error": "نوع عملیات شناخته نشد."}, status=400)
