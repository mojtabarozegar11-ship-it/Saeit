"""Read-only audit of newsroom exclusions and their publication exposure."""

from collections import Counter

from .editorial_policy import blocked_story_reason
from .editorial_signature import has_final_signature


PUBLIC_STATES = frozenset({"approved", "scheduled", "published"})


def summarize_editorial_stories(stories, *, max_ids: int = 50) -> dict:
    """Build a non-destructive, privacy-limited evidence snapshot.

    The caller must provide all stories in scope, or mark the result partial.
    No titles, summaries, or source URLs are included in audit output.
    """
    scanned = 0
    blocked = Counter()
    blocked_states = Counter()
    exposed_ids = []
    unsigned_published_ids = []
    unsigned_published_total = 0
    all_blocked_ids = []
    for story in stories:
        scanned += 1
        if story.status == "published" and not has_final_signature(getattr(story, "body", "")):
            unsigned_published_total += 1
            if len(unsigned_published_ids) < max_ids:
                unsigned_published_ids.append(story.pk)
        reason = blocked_story_reason(story)
        if not reason:
            continue
        blocked[reason] += 1
        blocked_states[str(story.status)] += 1
        all_blocked_ids.append(story.pk)
        if story.status in PUBLIC_STATES and len(exposed_ids) < max_ids:
            exposed_ids.append(story.pk)
    return {
        "scanned": scanned,
        "blocked_total": sum(blocked.values()),
        "blocked_by_reason": dict(blocked),
        "blocked_by_state": dict(blocked_states),
        "public_or_scheduled_blocked_total": sum(blocked_states[s] for s in PUBLIC_STATES),
        "public_or_scheduled_blocked_ids_sample": exposed_ids,
        "published_missing_final_signature_total": unsigned_published_total,
        "published_missing_final_signature_ids_sample": unsigned_published_ids,
        "blocked_ids": all_blocked_ids,
        "read_only": True,
        "semantic_manual_review_still_required": True,
    }
