"""Crash-resumable source-job research with strict evidence gates.

Scaffold only: integrate with the deployed Factory after code reconciliation.
No HTTP fetch occurs in this module; a separately audited fetcher must enforce
pinned public-IP connections (protecting against DNS rebinding and SSRF).
"""
from datetime import timedelta
import hashlib
from urllib.parse import urlsplit
import ipaddress
import re

from django.db import transaction
from django.utils import timezone

from .models import FactorySourceJob, FactoryEvidenceSnapshot


def acceptable_discovery_url(url):
    """Fail closed on malformed or obviously unsafe discovery URLs.

    This is an admission filter, NOT a substitute for pinned-IP checks at
    connection time in the future HTTP fetcher.
    """
    if not isinstance(url, str) or len(url) > 1800:
        return False
    if re.search(r"[\\x00-\\x20\\x7f]", url):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if (parts.scheme != "https" or not host or parts.username is not None
                or parts.password is not None or parts.fragment
                or parts.port not in (None, 443)):
            return False
        normalized = host.rstrip(".").lower()
        if normalized in ("localhost", "localhost.localdomain") or normalized.endswith(
                (".localhost", ".local", ".internal", ".test", ".invalid")
        ):
            return False
        try:
            ipaddress.ip_address(normalized.strip("[]"))
        except ValueError:
            return bool(re.fullmatch(r"[a-z0-9.-]+", normalized)) and "." in normalized
        return False  # Reject IP literals; connection-time DNS pinning remains mandatory.
    except ValueError:
        return False


@transaction.atomic
def schedule(project, urls):
    """Persist discoveries idempotently; discovery failure cannot destroy evidence."""
    created = 0
    for url in list(urls)[:16]:
        if not acceptable_discovery_url(url):
            continue
        _, added = FactorySourceJob.objects.get_or_create(
            project=project, url=url, defaults={"status": "queued"}
        )
        created += int(added)
    return created


@transaction.atomic
def claim(project, stale_after_seconds=180):
    """Claim one bounded unit, without consuming the parent AgentTask retry."""
    cutoff = timezone.now() - timedelta(seconds=stale_after_seconds)
    FactorySourceJob.objects.filter(
        project=project, status="running", leased_at__lt=cutoff
    ).update(status="queued", leased_at=None)
    job = (FactorySourceJob.objects.select_for_update()
           .filter(project=project, status="queued", attempts__lt=3)
           .order_by("id").first())
    if not job:
        return None
    job.attempts += 1
    job.status = "running"
    job.leased_at = timezone.now()
    job.save(update_fields=["attempts", "status", "leased_at", "updated_at"])
    return job


def finish(job, *, body, content_type, source_verified=False):
    """Store successful bytes and provenance atomically; never auto-approve relevance."""
    if not isinstance(body, bytes) or not 100 <= len(body) <= 256_000:
        raise ValueError("Source payload outside accepted bounds")
    if not any(t in content_type.lower() for t in ("text/html", "text/plain")):
        raise ValueError("Source must be HTML or plain text")
    digest = hashlib.sha256(body).hexdigest()
    with transaction.atomic():
        fresh = FactorySourceJob.objects.select_for_update().get(pk=job.pk)
        if fresh.status != "running" or fresh.attempts != job.attempts:
            raise ValueError("Stale claim cannot finish a source")
        FactoryEvidenceSnapshot.objects.update_or_create(
            source_job=fresh,
            defaults={
                "sha256": digest, "body": body.decode("utf-8", "replace"),
                "content_type": content_type[:100],
                "fetched_at": timezone.now(),
                "verified_relevant": bool(source_verified),
            },
        )
        fresh.status = "done"
        fresh.last_error = ""
        fresh.save(update_fields=["status", "last_error", "updated_at"])
    return digest


@transaction.atomic
def fail(job, error):
    """A failing URL never fails the parent research task."""
    fresh = FactorySourceJob.objects.select_for_update().get(pk=job.pk)
    if fresh.status != "running" or fresh.attempts != job.attempts:
        return False
    fresh.status = "failed" if fresh.attempts >= 3 else "queued"
    fresh.leased_at = None
    fresh.last_error = str(error)[:500]
    fresh.save(update_fields=["status", "leased_at", "last_error", "updated_at"])
    return True


def evidence_ready(project, minimum=2):
    """Different hostname is a minimum gate, not proof of actual independence."""
    domains = {
        urlsplit(row.source_job.url).hostname
        for row in FactoryEvidenceSnapshot.objects
          .filter(source_job__project=project, verified_relevant=True)
          .select_related("source_job")
    }
    return len(domains) >= minimum
