"""Import numbered management-cycle reports from the fixed public GitHub issue.

Preview by default; guarded database writes ONLY with explicit --commit and two
independent environment gates after the separate financial-office release review.
This is a GitHub *comment transcript*, not cryptographic proof of its claims.
"""
import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from enterprise_portal.github_chatgpt_reports import (
    PUBLIC_ISSUE_API, extract_receipt, AUTHOR_LOGIN,
)
from enterprise_portal.models import BusinessUnit, ChatGPTActionReport


def fetch_issue_comments(*, pages=5):
    """Only preselected GitHub repository + issue; no user-supplied URL/SSRF."""
    token = os.environ.get("ZM_GITHUB_REPORTS_READ_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Zomorod-Melal-TextReportSync/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    for page_number in range(1, pages + 1):
        request = Request(PUBLIC_ISSUE_API + "?per_page=100&page=" + str(page_number), headers=headers)
        try:
            with urlopen(request, timeout=10) as response:
                # Fail closed on excessive responses or malformed JSON.
                raw = response.read(2_000_001)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise CommandError("GITHUB_REPORT_SOURCE_UNAVAILABLE") from exc
        if len(raw) > 2_000_000:
            raise CommandError("GITHUB_REPORT_SOURCE_TOO_LARGE")
        try:
            items = json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise CommandError("GITHUB_REPORT_SOURCE_INVALID_JSON") from exc
        if not isinstance(items, list) or len(items) > 100:
            raise CommandError("GITHUB_REPORT_SOURCE_INVALID_SHAPE")
        for item in items:
            yield item
        if len(items) < 100:
            return
    raise CommandError("GITHUB_REPORT_PAGINATION_NOT_EXHAUSTIVE")


class Command(BaseCommand):
    help = "Read numbered management reports from Saeit issue #1725; --commit requires gates."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="Write after release gates")
        parser.add_argument("--unit-code", default="", help="Explicit business-unit code")
        parser.add_argument("--recorder-id", type=int, default=0, help="ID of accountable superuser")
        parser.add_argument("--pages", type=int, default=5)

    def handle(self, *args, **options):
        commit = bool(options["commit"])
        pages = options["pages"]
        if not (1 <= pages <= 10):
            raise CommandError("PAGES_OUT_OF_RANGE")

        unit = recorder = None
        if commit:
            if (os.environ.get("ZM_CHATGPT_REPORT_SYNC_ENABLED") != "1" or
                    os.environ.get("ZM_CHATGPT_REPORT_DB_ATTESTED") != "1"):
                raise CommandError("REPORT_IMPORT_RELEASE_GATE_BLOCKED")
            if not options["unit_code"] or not options["recorder_id"]:
                raise CommandError("REPORT_IMPORT_IDENTITY_REQUIRED")
            try:
                unit = BusinessUnit.objects.get(code=options["unit_code"], active=True)
                recorder = get_user_model().objects.get(
                    pk=options["recorder_id"], is_superuser=True, is_active=True, is_staff=True,
                )
            except (BusinessUnit.DoesNotExist, get_user_model().DoesNotExist) as exc:
                raise CommandError("REPORT_IMPORT_IDENTITY_INVALID") from exc

        counters = {"seen": 0, "eligible": 0, "created": 0, "duplicate": 0, "skipped": 0}
        seen_codes = {}
        eligible_receipts = []
        # Complete the bounded network fetch and validate source-number uniqueness
        # BEFORE any DB write. A late page failure must not partially import.
        for item in fetch_issue_comments(pages=pages):
            counters["seen"] += 1
            receipt = extract_receipt(item)
            if receipt is None:
                counters["skipped"] += 1
                continue
            counters["eligible"] += 1
            code, evidence = receipt["report_code"], receipt["evidence_url"]
            if code in seen_codes:
                if seen_codes[code] != evidence:
                    raise CommandError("REPORT_NUMBER_SOURCE_CONFLICT")
                counters["duplicate"] += 1
                continue
            seen_codes[code] = evidence
            if commit:
                eligible_receipts.append(receipt)

        if commit:
            # One transaction for the entire batch: a conflicting existing row,
            # validation failure or concurrent insert rolls back ALL new rows.
            # Network I/O occurs outside the transaction to avoid long DB locks.
            try:
                with transaction.atomic():
                    for receipt in eligible_receipts:
                        code, evidence = receipt["report_code"], receipt["evidence_url"]
                        existing = ChatGPTActionReport.objects.filter(report_code=code).first()
                        if existing:
                            if existing.evidence_url != evidence:
                                raise CommandError("REPORT_NUMBER_SOURCE_CONFLICT")
                            counters["duplicate"] += 1
                            continue
                        # A source comment is not independently verified delivery.
                        record = ChatGPTActionReport(
                            unit=unit, recorded_by=recorder, evidence_reviewed=False,
                            evidence_reviewed_by=None, outcome="partial", **receipt,
                        )
                        record.save()
                        counters["created"] += 1
            except IntegrityError as exc:
                raise CommandError("REPORT_IMPORT_CONCURRENT_CONFLICT") from exc

        # Never log raw reports, names, addresses or any private credentials.
        self.stdout.write(
            "ZM_REPORT_SYNC_JSON=" +
            json.dumps({"mode": "commit" if commit else "preview", **counters},
                       ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        )
