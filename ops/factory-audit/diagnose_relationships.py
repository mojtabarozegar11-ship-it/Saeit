#!/usr/bin/env python3
"""Read-only cardinality audit for factory owner/project provenance.

Does not print personal details or confidential product data.
"""
from __future__ import annotations
import collections
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Count

run=apps.get_model("core","FactoryRun")
task=apps.get_model("core","AgentTask")
project=apps.get_model("core","ResearchProject")
product=apps.get_model("core","Product")
user=get_user_model()
owners=list(user.objects.filter(is_active=True,is_superuser=True).values_list("pk",flat=True))
print("TRUSTED_ACTIVE_OWNER_COUNT="+str(len(owners)))
print("RUN_HAS_PRODUCT_FIELD="+str("product" in {f.name for f in run._meta.fields}))
print("PROJECT_HAS_FACTORY_RUN_FIELD="+str("factory_run" in {f.name for f in project._meta.fields}))
print("PROJECT_HAS_OWNER_FIELD="+str("owner" in {f.name for f in project._meta.fields}))

blocked=task.objects.filter(status="blocked").select_related("factory_run")
counter=collections.Counter()
for t in blocked.iterator(chunk_size=200):
    fr=getattr(t,"factory_run",None)
    counter["blocked_total"]+=1
    if fr is None:
        counter["blocked_missing_run"]+=1
        continue
    if fr.product_id is not None:
        counter["blocked_run_has_product"]+=1
        p=product.objects.filter(pk=fr.product_id).values("factory_managed","owner_id","active").first()
        if p and p["factory_managed"] and not p["active"]:
            counter["blocked_run_factory_draft"]+=1
        if p and p["owner_id"] in owners:
            counter["blocked_run_product_trusted_owner"]+=1
    qs=project.objects.filter(factory_run_id=fr.pk)
    size=qs.count()
    counter["blocked_associated_project_"+("0" if size==0 else "1" if size==1 else "multiple")]+=1
    if size==1:
        project_row=qs.values("owner_id").first()
        if project_row["owner_id"] in owners:
            counter["blocked_unique_project_trusted_owner"]+=1
        if fr.product_id is not None and project_row["owner_id"] in owners:
            counter["blocked_repairable_provenance_candidate"]+=1

for label,n in sorted(counter.items()):
    print("FACTORY_LINK_"+label.upper()+"="+str(n))
print("PROJECT_WITH_OWNER_AND_RUN="+str(project.objects.filter(factory_run__isnull=False,owner__isnull=False).count()))
print("FACTORY_DRAFT_OWNER_NULL="+str(product.objects.filter(factory_managed=True,active=False,owner__isnull=True).count()))
print("TRUSTED_MAPPING_AUDIT_COMPLETE")
