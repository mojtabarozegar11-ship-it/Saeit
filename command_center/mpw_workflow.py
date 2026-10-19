"""Fail-closed, auditable review-to-release state machine for main-site work."""
from copy import deepcopy
from datetime import timedelta
from django.utils.dateparse import parse_datetime
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.models import AuditLog
from .models import MpwRecord, TENANT, local_path
from .mpw_public import safe_payload, editable_main_path

ORIGINS = ("site", "customer", "market", "invention", "agent")
EDITABLE = {
    "content": ("title", "body", "slot", "group", "url", "image"),
    "offer": ("title", "body", "price", "currency", "checkout_path",
              "rights_verified", "payment_verified", "delivery_verified",
              "payment_evidence", "delivery_evidence"),
    "job": ("title", "origin", "source_ref", "target_key"),
}
TRANSITIONS = {"submit": ("draft", "needs_revision"),
               "reject": ("review",),
               "qa_pass": ("review",),
               "approve": ("awaiting_approval",),
               "publish": ("approved",)}


def checked_payload(kind, payload):
    if kind not in EDITABLE or not isinstance(payload, dict):
        raise ValidationError("Unknown record type or source.")
    unexpected = set(payload) - set(EDITABLE[kind])
    if unexpected:
        raise ValidationError("Unapproved editable fields.")
    data = {k: payload.get(k, "") for k in EDITABLE[kind]}
    data["title"] = str(data["title"]).strip()[:200]
    if not data["title"]:
        raise ValidationError("Title is required.")
    if kind == "content":
        data["body"] = str(data["body"])[:2000]
        data["slot"] = data["slot"] if data["slot"] in ("section", "row", "card") else "card"
        data["group"] = str(data["group"] or "editorial")[:80]
        data["url"] = str(data["url"] or "")
        data["image"] = str(data["image"] or "")
        if safe_payload(kind, data) is None:
            raise ValidationError("Invalid local link or static image path.")
    elif kind == "offer":
        for key in ("rights_verified", "payment_verified", "delivery_verified"):
            data[key] = data[key] is True or data[key] == "true"
        for key in ("payment_evidence", "delivery_evidence"):
            data[key] = str(data[key] or "").strip()[:240]
        data["checkout_path"] = str(data["checkout_path"] or "")
        data["currency"] = str(data["currency"] or "USD").upper()
        try:
            amount = Decimal(str(data["price"]))
            if not amount.is_finite() or amount < 0 or amount > 999999999:
                raise ValidationError("Invalid price.")
            data["price"] = str(amount.quantize(Decimal("0.01")))
        except (InvalidOperation, TypeError):
            raise ValidationError("Invalid price.")
        # A preview may remain in draft until rights are verified.
        if not local_path(data["checkout_path"], allow_empty=True):
            raise ValidationError("Only a local checkout path is permitted.")
        if data["currency"] not in ("USD", "EUR", "IRR", "CAD"):
            raise ValidationError("Unsupported currency.")
    else:
        data["origin"] = str(data["origin"] or "")
        if data["origin"] not in ORIGINS:
            raise ValidationError("Invalid work origin.")
        data["target_key"] = str(data["target_key"] or "")[:100]
        data["source_ref"] = str(data["source_ref"] or "").strip()[:240]
    return data


def audit(user, rec, action, before, after):
    AuditLog.objects.create(actor_type="staff", actor_id=str(user.pk),
        action="mpw_control_" + action, target_type="MpwRecord",
        target_id=str(rec.pk), before_state=before, after_state=after,
        trace_id="mpw:" + rec.key + ":" + str(rec.revision))


@transaction.atomic
def create_record(user, kind, key, page_path, payload):
    if kind not in EDITABLE:
        raise ValidationError("Unsupported kind.")
    if not editable_main_path(page_path):
        raise ValidationError("Invalid site page.")
    if kind == "offer" and page_path != "/store/":
        raise ValidationError("Offers belong only to the main store.")
    source = checked_payload(kind, payload)
    row = MpwRecord(tenant=TENANT, kind=kind, key=key, page_path=page_path,
                    title=source["title"], draft=source)
    row.full_clean()
    row.save()
    audit(user, row, "create", {}, {"kind":kind,"state":row.state})
    return row


@transaction.atomic
def change_record(user, pk, action, payload=None, evidence="", note="", revision=None):
    rec = MpwRecord.objects.select_for_update().get(pk=pk, tenant=TENANT)
    if revision is None or rec.revision != revision:
        raise ValidationError("Record was changed. Refresh and retry.")
    if rec.kind == "agent_outcome":
        raise ValidationError("Outcome evidence is immutable.")
    before = {"state":rec.state, "revision":rec.revision}
    if action == "edit":
        if rec.state not in ("draft", "needs_revision", "published"):
            raise ValidationError("Finish the existing review before editing.")
        rec.draft = checked_payload(rec.kind, payload)
        rec.title = rec.draft["title"]
        rec.state = "draft"  # Published snapshot remains visible.
        rec.quality_evidence = ""
        rec.approval_evidence = ""
        rec.quality_note = ""
    else:
        if action not in TRANSITIONS or rec.state not in TRANSITIONS[action]:
            raise ValidationError("Illegal lifecycle transition.")
        if action == "submit":
            rec.state = "review"
        elif action == "reject":
            if not note.strip():
                raise ValidationError("A concrete defect and rework instructions are required.")
            rec.quality_note = note.strip()[:2000]
            rec.quality_evidence = ""
            rec.approval_evidence = ""
            rec.state = "needs_revision"  # Never discard failed-quality material.
        elif action == "qa_pass":
            if not evidence.strip():
                raise ValidationError("A QA evidence reference is required.")
            rec.quality_evidence = evidence.strip()[:240]
            rec.quality_note = ""
            rec.state = "awaiting_approval"
        elif action == "approve":
            if not user.is_superuser or not evidence.strip():
                raise ValidationError("A superuser approval and evidence are required.")
            rec.approval_evidence = evidence.strip()[:240]
            rec.state = "approved"
        elif action == "publish":
            if not rec.quality_evidence or not rec.approval_evidence:
                raise ValidationError("Missing QA or owner-approval evidence.")
            if rec.kind == "offer":
                if not rec.draft.get("rights_verified"):
                    raise ValidationError("Rights must be verified before a public offer.")
                if safe_payload("offer", rec.draft) is None:
                    raise ValidationError("Offer failed the public catalog gate.")
            elif rec.kind == "content":
                if safe_payload("content", rec.draft) is None:
                    raise ValidationError("Content failed the public card gate.")
            elif rec.kind == "job":
                target = MpwRecord.objects.filter(tenant=TENANT, key=rec.draft.get("target_key"),
                         kind__in=("offer","content")).first()
                if not target or not target.published_snapshot:
                    raise ValidationError("The reviewed product/content must be published first.")
            if rec.kind in ("content", "offer"):
                rec.published_snapshot = deepcopy(rec.draft)
                rec.published_at = timezone.now()
            rec.state = "published"
    rec.revision += 1
    rec.full_clean()
    rec.save()
    audit(user, rec, action, before, {"state":rec.state,"revision":rec.revision})
    return rec


@transaction.atomic
def record_agent_outcome(user, key, agent, observed_at, metrics, evidence):
    timestamp = parse_datetime(observed_at) if isinstance(observed_at, str) else None
    if timestamp is None or timezone.is_naive(timestamp) or timestamp > timezone.now() + timedelta(minutes=5) or timestamp < timezone.now() - timedelta(days=90):
        raise ValidationError("A recent timezone-aware observation is required.")
    if not evidence.strip() or not agent.strip():
        raise ValidationError("Agent name and external execution evidence are required.")
    if not isinstance(metrics, dict) or any((not isinstance(v,int) or isinstance(v,bool) or v < 0)
                       for v in metrics.values()):
        raise ValidationError("Metrics must contain nonnegative integer counts.")
    if set(metrics) - {"completed","failed","produced","published","reworked"}:
        raise ValidationError("Unsupported metric.")
    row = MpwRecord(tenant=TENANT, kind="agent_outcome", key=key,
                    title=agent[:200], draft={"agent":agent[:200],"observed_at":timestamp.isoformat(),
                    "metrics":metrics,"evidence":evidence.strip()[:240]}, state="approved")
    row.full_clean()
    row.save()
    audit(user,row,"agent_outcome",{},{"evidence":evidence.strip()[:240]})
    return row
