"""Private operations desk for main MojPlayWin. No shared routing or payment side effects."""
import json
from uuid import uuid4
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .models import MpwRecord, TENANT
from .mpw_public import is_main
from .mpw_private_telemetry import snapshot
from .mpw_workflow import create_record, change_record, record_agent_outcome


def _payload(post, kind):
    if kind == "content":
        return {"title":post.get("title",""),"body":post.get("body",""),
                "slot":post.get("slot","card"),"group":post.get("group","editorial"),
                "url":post.get("url",""),"image":post.get("image","")}
    if kind == "offer":
        return {"title":post.get("title",""),"body":post.get("body",""),
                "price":post.get("price",""),"currency":post.get("currency","USD"),
                "checkout_path":post.get("checkout_path",""),
                "rights_verified": post.get("rights_verified") == "on",
                "payment_verified": post.get("payment_verified") == "on",
                "delivery_verified": post.get("delivery_verified") == "on",
                "payment_evidence":post.get("payment_evidence",""),
                "delivery_evidence":post.get("delivery_evidence","")}
    if kind == "job":
        return {"title":post.get("title",""),"origin":post.get("origin","site"),
                "source_ref":post.get("source_ref",""),
                "target_key":post.get("target_key","")}
    raise ValidationError("Unsupported record kind.")


@staff_member_required
@require_http_methods(["GET", "POST"])
def desk(request):
    if not is_main(request):
        raise Http404("Main MojPlayWin only.")
    if request.method == "POST":
        p = request.POST
        action = p.get("action","")
        try:
            if action == "create":
                kind = p.get("kind","")
                row = create_record(request.user,kind,p.get("key",""),
                                    p.get("page_path","/"),_payload(p,kind))
                messages.success(request,"Draft created: " + row.key)
            elif action == "record_outcome":
                counters = {key:int(p.get(key,"0")) for key in
                            ("completed","failed","produced","published","reworked")}
                record_agent_outcome(request.user,"evidence-"+uuid4().hex,
                    p.get("agent",""),p.get("observed_at",""),counters,
                    p.get("evidence",""))
                messages.success(request,"Evidence-backed outcome stored.")
            else:
                pk = int(p.get("record_id","0"))
                revision = int(p.get("revision","0"))
                current = MpwRecord.objects.get(pk=pk, tenant=TENANT)
                payload = _payload(p,current.kind) if action == "edit" else None
                row = change_record(request.user,pk,action,payload=payload,
                                    revision=revision,evidence=p.get("evidence",""),
                                    note=p.get("note",""))
                messages.success(request, "Recorded: " + row.key + " / " + row.state)
        except (ValidationError, IntegrityError, MpwRecord.DoesNotExist, ValueError) as error:
            if isinstance(error, ValidationError):
                detail = "; ".join(error.messages)
            else:
                detail = "Invalid entry or conflicting identifier."
            messages.error(request,detail)
        return redirect("mpw_operations")
    records = list(MpwRecord.objects.filter(tenant=TENANT)
                   .exclude(kind="agent_outcome").order_by("kind","key")[:300])
    outcomes = list(MpwRecord.objects.filter(tenant=TENANT,kind="agent_outcome")
                    .order_by("-created_at")[:50])
    telemetry = snapshot()
    context = {"records": records,"outcomes": outcomes,"telemetry":telemetry,
               "tenant":TENANT, "record_total":MpwRecord.objects.filter(tenant=TENANT).count()}
    response = render(request,"command_center/mpw_operations.html",context)
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
