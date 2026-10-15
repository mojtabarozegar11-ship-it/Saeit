#!/usr/bin/env python3
"""Read-only, redacted assessment of SaaS factory research/owner bottlenecks.

Runs inside the existing private Django VPS runtime. No writes, file export,
network requests or sensitive task payloads printed. Detects reasons before
attempting remediation.
"""
from __future__ import annotations

import collections
import hashlib
import os
import re
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

def safe_count(label, predicate):
    try:
        print(label + "=" + str(predicate.count()), flush=True)
    except Exception as e:
        print(label + "_ERROR=" + type(e).__name__, flush=True)

Product = apps.get_model("core", "Product")
Task = apps.get_model("core", "AgentTask")
Run = apps.get_model("core", "FactoryRun")
Project = apps.get_model("core", "ResearchProject")
Source = apps.get_model("core", "ResearchSource")
Evidence = apps.get_model("core", "Evidence")
Report = apps.get_model("core", "Report")
Owner = get_user_model()

print("AUDIT_MODE=STRICT_READ_ONLY", flush=True)
safe_count("OWNERS_ACTIVE_SUPERUSER", Owner.objects.filter(is_active=True, is_superuser=True))
safe_count("PRODUCTS_FACTORY_DRAFT", Product.objects.filter(factory_managed=True, active=False))
safe_count("PRODUCTS_FACTORY_NO_OWNER", Product.objects.filter(factory_managed=True, owner__isnull=True))
safe_count("PRODUCTS_FACTORY_NO_KNOWLEDGE", Product.objects.filter(factory_managed=True, knowledge_article__isnull=True))
safe_count("PRODUCTS_FACTORY_ZERO_PRICE", Product.objects.filter(factory_managed=True, price=0))
safe_count("PROJECTS_OWNER_MISSING", Project.objects.filter(owner__isnull=True))
safe_count("FACTORY_RUN_BLOCKED", Run.objects.filter(status="blocked"))
safe_count("TASKS_BLOCKED", Task.objects.filter(status="blocked"))
safe_count("TASKS_BLOCKED_NULL_PROJECT", Task.objects.filter(status="blocked", project__isnull=True))
safe_count("TASKS_BLOCKED_NULL_PRODUCT", Task.objects.filter(status="blocked", product__isnull=True))
safe_count("TASKS_BLOCKED_NULL_RUN", Task.objects.filter(status="blocked", factory_run__isnull=True))
safe_count("PROJECTS_HAS_EVIDENCE", Project.objects.filter(evidence__isnull=False).distinct())
safe_count("RESEARCH_SOURCES_NO_URL", Source.objects.filter(url=""))
safe_count("REPORTS_DRAFT", Report.objects.filter(status="draft"))
safe_count("EVIDENCE_LOW_CONFIDENCE", Evidence.objects.filter(confidence__lt=0.5))

labels = [
 ("owner_provenance", r"owner.*provenance|provenance.*owner"),
 ("research_project", r"research.*project|project.*research"),
 ("missing_owner", r"owner.*(missing|not found|not set|none|null)|(?:missing|not found|not set).*owner"),
 ("missing_project", r"project.*(missing|not found|none|null)|(?:missing|not found|not set).*project"),
 ("auth_policy", r"approval|permission|authorization|unauthoriz"),
 ("insufficient_evidence", r"evidence|source|proof|citation"),
 ("provider", r"provider|offline|api"),
]
groups = collections.Counter()
digests = collections.Counter()
examples = {}
for t in Task.objects.filter(status="blocked").only("output_data","project_id","product_id","factory_run_id").iterator(chunk_size=200):
    body = t.output_data or {}
    msg = str(body.get("error", "") if isinstance(body, dict) else "")[:3000].lower()
    digest = hashlib.sha256(msg.encode("utf-8")).hexdigest()[:16]
    digests[digest] += 1
    for label,pat in labels:
        if re.search(pat,msg):
            groups[label] += 1
    # Emit only recognized error keywords, not raw user-controlled messages.
    if digest not in examples:
        examples[digest] = [label for label,pat in labels if re.search(pat,msg)]
print("TASK_BLOCKER_CLASS_COUNTS=" + ",".join(f"{k}:{v}" for k,v in sorted(groups.items())), flush=True)
for d, count in digests.most_common(6):
    print("TASK_ERROR_SIGNATURE="+d+" COUNT="+str(count)+" TAGS="+",".join(examples[d]), flush=True)

product_state = collections.Counter()
missing_factors = collections.Counter()
for p in Product.objects.filter(factory_managed=True).only("metadata").iterator(chunk_size=100):
    data = p.metadata or {}
    if not isinstance(data, dict): continue
    product_state[str(data.get("factory_state", "unknown"))[:50]] += 1
    validation = data.get("validation")
    if isinstance(validation, dict):
        factors = validation.get("missing_factors") or []
        if isinstance(factors, list):
            for item in factors:
                if isinstance(item,str) and re.fullmatch(r"[A-Za-z_]{2,55}",item):
                    missing_factors[item] += 1
print("FACTORY_PRODUCT_STATES=" + ",".join(f"{k}:{v}" for k,v in product_state.most_common()),flush=True)
print("VALIDATION_MISSING_FACTOR_CATEGORIES=" + ",".join(f"{k}:{v}" for k,v in missing_factors.most_common(20)),flush=True)
print("SAFE_AUDIT_COMPLETED",flush=True)
