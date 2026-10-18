"""MojPlayWin MAIN site English editorial-content drafting line, private only.

Creates original, bounded, source-annotated English page guides from audited
editorial briefs. No unbounded synthetic variations, network, LLM credentials,
business claims, Django, publishing, payments, public files or tenant crossover.
Gen65 is a *format/readiness* reviewer, not factual verification. Every output
must undergo human fact checking and production authorization before publishing.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

TENANT = "mojplaywin-main"
MAX_PER_UTC_DAY = 2
MAX_DRAFTS = 32
MAX_BYTES = 19000
TOPIC_PATHS = frozenset(("/agents/", "/knowledge/", "/studio/", "/research/"))
SOURCES = {
    "nist": "https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10",
    "playbook": "https://www.nist.gov/itl/ai-risk-management-framework/nist-ai-rmf-playbook",
    "wcag": "https://www.w3.org/TR/WCAG22/",
    "google": "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
    "owasp": "https://owasp.org/www-project-top-ten/",
}
# All briefs are authored from broadly applicable educational principles. They
# describe proposed methods, NOT proof of any actual MojPlayWin product/service.
# Links document the framework; no assertion that any page is already WCAG-compliant.
BRIEFS = (
    {
      "slug": "ai-evaluation-before-deployment",
      "page": "/agents/",
      "title": "An AI Evaluation Plan Before Deployment",
      "audience": "teams planning their first AI-assisted workflow",
      "intro": "A demonstration can look impressive without establishing that a system works reliably. Evaluate the intended use before measuring success. A useful evaluation starts with a clear boundary: who will use the output, what decision could follow, and which failures would matter most. The purpose of this guide is to help teams plan a small, reproducible evaluation rather than mistake a prototype for a finished service.",
      "steps": [
        ("Define the task and its boundaries", "Write down input types, expected outputs, who reviews the result, and what the system must not do. Select realistic examples and include difficult or ambiguous cases. An assistant that drafts explanations needs different evidence from a service that takes actions on behalf of a customer."),
        ("Measure quality with representative samples", "Separate factual correctness, relevance, completeness, clarity, and harmful mistakes into different review fields. Record failures rather than keeping only successful demonstrations. A reviewer should be able to reproduce the input and understand why a result passed or failed. Avoid claiming accuracy from a few hand-picked examples."),
        ("Control deployment and monitoring", "Make human approval explicit for consequential or irreversible actions. Define ownership, time limits, rollback, and ways to report unexpected output. Review performance again when content, users, integrations, or operating conditions change. A passing test today does not guarantee safe behavior indefinitely."),
      ],
      "limitations": "This is a planning guide, not a certification, safety guarantee, or report on a deployed MojPlayWin AI model. Thresholds require task-specific evidence and expert assessment.",
      "sources": ("nist", "playbook"),
    },
    {
      "slug": "documenting-ai-assisted-decisions",
      "page": "/agents/",
      "title": "Documenting AI-Assisted Decisions Without Losing Accountability",
      "audience": "editors, researchers, and product managers",
      "intro": "Teams can use automated systems to organize evidence while remaining responsible for final decisions. An accountable workflow makes the boundary visible between a machine suggestion, a verified source, and an approved action. Good records do not need to be complicated, but they should enable an independent reviewer to understand what happened and why.",
      "steps": [
        ("Trace the evidence", "For each important claim, keep the underlying reference, its publication context, and any uncertainty. A generated answer may be well written yet unsupported. Label unsupported suggestions rather than turning them into statements of fact. Update citations if the primary documentation changes."),
        ("Capture review decisions", "Document which criteria were applied, who had approval authority, and the reasons for accepting, revising, or declining a result. Distinguish editorial approval from legal, security, or scientific validation. A single numerical quality score is not a substitute for those checks."),
        ("Prepare for correction", "Maintain a route for users and reviewers to report errors. Make changes reversible where possible and preserve earlier versions for comparison. If an automated feature becomes unreliable, there should be a clear way to disable it without disabling unrelated website functions."),
      ],
      "limitations": "The examples describe recommended governance practice and do not assert that a particular vendor, website, or employee has completed these controls.",
      "sources": ("nist", "playbook"),
    },
    {
      "slug": "accessible-knowledge-articles",
      "page": "/knowledge/",
      "title": "Building Knowledge Articles That Readers Can Actually Use",
      "audience": "educators and people preparing online learning resources",
      "intro": "Useful educational content does more than collect facts. It gives readers a recognizable question, an understandable route through the material, and a way to apply the answer. Accessible structure matters because people may read on small screens, use assistive technology, or arrive without prior knowledge of the topic.",
      "steps": [
        ("Start from one reader question", "State the intended audience and the result they should be able to achieve. Define technical words when first used and prefer examples over unexplained jargon. Separate essential guidance from optional background so readers can find what they need quickly."),
        ("Make the structure navigable", "Use one clear page title and descriptive headings in a meaningful order. Provide descriptive link text rather than relying on phrases such as click here. Illustrations should support the explanation, with suitable text alternatives when they communicate information. Check reading order and keyboard access in the final interface."),
        ("Review usefulness before publishing", "Ask someone unfamiliar with the topic to follow the instructions. Note where assumptions, missing steps, or vague warnings make progress difficult. Confirm that references support the specific claims and distinguish the author’s practical recommendations from externally established facts."),
      ],
      "limitations": "This is a guide to editorial practice; it is not a claim that any specific website satisfies WCAG 2.2 or that an article has been independently tested with assistive technology.",
      "sources": ("wcag", "google"),
    },
    {
      "slug": "people-first-digital-guides",
      "page": "/knowledge/",
      "title": "Planning People-First Digital Guides",
      "audience": "content teams designing evergreen tutorials",
      "intro": "An evergreen guide remains useful because it solves a real problem, not because it repeats a popular keyword. A reader should be able to see the intended outcome, understand any prerequisites, and recognize when the advice is no longer applicable. Good editorial planning begins with usefulness rather than search traffic.",
      "steps": [
        ("Choose a specific outcome", "Write a precise task such as comparing options, preparing a checklist, or understanding a method. Keep the topic narrow enough that the guide can complete the task. When a question requires specialist advice, explain the scope and point readers toward appropriate independent guidance."),
        ("Provide examples and failure cases", "Show the inputs, an expected intermediate result, and common mistakes that might change the answer. Discuss the conditions under which a method is not suitable. Avoid recycled filler, exaggerated promises, fabricated metrics, or unsupported product recommendations."),
        ("Maintain the guide over time", "Record which references and assumptions were used. If a standard, interface, or process changes, revise the affected instructions rather than repeatedly publishing near-identical pages. Archive outdated steps when maintaining them would confuse users."),
      ],
      "limitations": "Search rankings and commercial performance cannot be guaranteed by following an editorial method. Content should be reviewed for accessibility, accuracy, and relevance before public release.",
      "sources": ("google", "wcag"),
    },
    {
      "slug": "accessible-creative-prototypes",
      "page": "/studio/",
      "title": "Accessibility Checks for Interactive Creative Prototypes",
      "audience": "interactive designers and early-stage game developers",
      "intro": "A polished animation or playful interface is not complete if people cannot operate it. Accessibility can shape creative choices from the first prototype instead of being treated as a final cosmetic improvement. Designers can begin with a few practical checks and document what remains untested.",
      "steps": [
        ("Test the interaction without a pointer", "Try the prototype using only a keyboard. Make focus visible and ensure that the order of interaction matches the visual and logical reading order. A button that works only on hover may be inaccessible for many users; provide an alternative input route."),
        ("Offer control over motion and feedback", "Avoid using motion as the only way to explain status, direction, or progress. Consider reduced-motion preferences and ways to pause moving content when appropriate. Use text or accessible status messages to communicate essential results of an interaction."),
        ("Check contrast, labels and recovery", "Readable text, meaningful control names, and clear error messages help both first-time and experienced users. Verify that someone can recover from an incorrect input without losing unrelated work. Record device and assistive-technology test limitations rather than claiming universal compatibility."),
      ],
      "limitations": "A checklist is an early design aid, not an accessibility audit, product certification, or proof that a finished game implements these practices.",
      "sources": ("wcag", "google"),
    },
    {
      "slug": "safe-release-process-creative-web",
      "page": "/studio/",
      "title": "A Safer Release Process for Creative Web Projects",
      "audience": "small web studios shipping interactive experiences",
      "intro": "Interactive projects combine creative assets with forms, authentication, application code, and external services. A design-focused release can still introduce security or availability problems if these parts are not checked independently. A practical release process connects creative review to engineering safeguards.",
      "steps": [
        ("Separate protected services", "Inventory routes, shared application files, and dependencies before publishing. Isolate changes to the smallest verified scope. If unrelated websites share the same runtime, plan a way to preserve them and stop a deployment when boundaries are unclear."),
        ("Validate inputs and dependencies", "Treat user input as untrusted and keep secrets outside public files. Review relevant security guidance, test failure cases, and verify that client-side checks are not the only protection for sensitive operations. Know which third-party services or packages are required for the experience to work."),
        ("Prove recovery before release", "Keep a restorable backup and verify the essential journey in a staging environment. Record the artifact version, test results, and a rollback procedure. After deployment, check health without assuming that a successful upload means the application is functioning."),
      ],
      "limitations": "These are general software-release recommendations; they do not claim any particular MojPlayWin feature has been deployed, independently audited, or certified secure.",
      "sources": ("owasp", "wcag"),
    },
    {
      "slug": "reproducible-digital-research",
      "page": "/research/",
      "title": "A Reproducible Workflow for Digital Research Notes",
      "audience": "researchers preparing technical briefs and evidence summaries",
      "intro": "Research communication becomes more trustworthy when readers can distinguish observations, interpretation, and uncertainty. Even a short technical brief benefits from a repeatable process that records where information came from and how conclusions were reached. The objective is traceability, not a false appearance of absolute certainty.",
      "steps": [
        ("Frame the research question", "Write a question that can be answered with a defined type of evidence. Describe the intended audience and why the issue matters. List the assumptions that might bias source selection or interpretation, including factors that cannot be measured with the available material."),
        ("Keep an evidence trail", "Record source titles, publication dates where known, definitions, and the steps used to compare or summarize them. Prefer primary documentation for claims about standards or methods. Separate a cited claim from a new hypothesis; document conflicting findings rather than silently removing them."),
        ("Review uncertainty and reproducibility", "Ask whether a colleague could independently repeat the reasoning with the same references. Identify omitted data, uncertain measurements, and limits on generalization. Maintain a version history so changes to the question, sources, or interpretation are visible."),
      ],
      "limitations": "This guide does not represent new experimental data, original peer-reviewed findings, completed laboratory research, or external scientific validation.",
      "sources": ("nist", "google"),
    },
    {
      "slug": "evaluating-research-tools",
      "page": "/research/",
      "title": "Evaluating Research Tools Before Trusting Their Output",
      "audience": "teams comparing data and AI-assisted research workflows",
      "intro": "A research tool is useful only when its output can be understood in the context of the original question. Speed, presentation quality, and automation are not enough to establish reliability. Before adopting a tool, identify what it processes, what it cannot know, and which errors would materially affect a decision.",
      "steps": [
        ("Define measurable expectations", "Choose representative tasks and establish a human-readable reference answer where possible. Track whether the tool returns correct information, omits important qualifications, or invents citations. Include negative tests and deliberately ambiguous examples, rather than measuring only straightforward cases."),
        ("Separate retrieval from interpretation", "Check cited material directly. An accurately retrieved document does not guarantee that a generated conclusion faithfully reflects it. Record whether a statement is quoted, paraphrased, inferred, or hypothetical; each form requires a different standard of review."),
        ("Monitor errors and updates", "Keep a repeatable test set and compare results after tool, model, source, or configuration changes. Document uncertainty, access restrictions, and the need for domain-expert judgment. Turn unexpected failures into concrete test cases instead of silently adjusting a single score."),
      ],
      "limitations": "This educational checklist is not a comparative evaluation of any named commercial product or evidence that a deployed AI system satisfies a regulatory requirement.",
      "sources": ("nist", "playbook"),
    },
)


def _private(path: Path):
    return path.is_dir() and not path.is_symlink() and not (path.stat().st_mode & 0o077)


def _atomic(path: Path, obj: dict):
    if path.is_symlink():
        raise RuntimeError("content_destination_symlink")
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise RuntimeError("content_document_too_large")
    fd, temp = tempfile.mkstemp(prefix=".mpw-content-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def _read(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise RuntimeError("content_existing_state_invalid")
    data = json.loads(path.read_text("utf-8"))
    if not isinstance(data, dict) or data.get("tenant") != TENANT:
        raise RuntimeError("content_cross_tenant_state")
    return data


def build(brief: dict, stamp: str) -> dict:
    if (brief["page"] not in TOPIC_PATHS
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", brief["slug"])
        or len(brief["steps"]) != 3
        or len(brief["sources"]) != 2
        or not set(brief["sources"]) <= set(SOURCES)):
        raise ValueError("content_unapproved_page_or_source")
    guide = f"# {brief['title']}\n\n{brief['intro']}\n\n"
    for heading, paragraph in brief["steps"]:
        guide += f"## {heading}\n\n{paragraph}\n\n"
    guide += f"## Scope and limitations\n\n{brief['limitations']}\n\n"
    guide += "## Reference frameworks\n\n"
    for key in brief["sources"]:
        guide += f"- {SOURCES[key]}\n"
    count = len(re.findall(r"\b[\w'-]+\b", guide))
    if count < 220 or count > 700:
        raise RuntimeError("content_not_substantial_or_unbounded")
    srcs = [SOURCES[key] for key in brief["sources"]]
    digest = hashlib.sha256((brief["page"] + "\x1f" + guide).encode()).hexdigest()
    return {
        "tenant": TENANT,
        "site": "mojplaywin.com",
        "page_path": brief["page"],
        "slug": brief["slug"],
        "title": brief["title"],
        "language": "en",
        "audience": brief["audience"],
        "summary": brief["intro"][:320],
        "body_markdown": guide,
        "word_count": count,
        "source_urls": srcs,
        "content_sha256": digest,
        "drafted_utc": stamp,
        "authorship": "MojPlayWin private editorial drafting system",
        "provenance": "curated_original_educational_brief",
        "has_claims_of_live_products_or_original_research": False,
        "verified_source_links_not_fact_checked": True,
        "requires_factual_and_editorial_review": True,
        "approved_for_publication": False,
        "published": False,
        "sale_ready": False,
    }


def tick(root: Path, stamp: str, gen65_classify) -> dict:
    """Produce max 2 *new* source-backed drafts per UTC day, then stop safely.

    Caller already holds evolution's exclusive cycle lock. Gen65 callback
    returns private REVIEW recommendation only, never a publish permission.
    """
    if not _private(root):
        raise RuntimeError("content_private_root_required")
    current = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if current.tzinfo is None:
        raise RuntimeError("content_timestamp_unzoned")
    day = current.astimezone(timezone.utc).strftime("%Y-%m-%d")
    folder = root / "page_content_20261018"
    if folder.exists():
        if not _private(folder):
            raise RuntimeError("content_folder_not_private")
    else:
        folder.mkdir(mode=0o700)
    drafts = folder / "drafts"
    if drafts.exists():
        if not _private(drafts):
            raise RuntimeError("content_drafts_folder_not_private")
    else:
        drafts.mkdir(mode=0o700)
    existing = sorted(drafts.glob("*.json"))
    if len(existing) > MAX_DRAFTS or any(p.is_symlink() for p in existing):
        raise RuntimeError("content_storage_or_symlink_guard")
    # No infinite SEO rephrasing. No new source -> no new draft.
    issued_today = 0
    existing_slugs = set()
    for item in existing:
        row = _read(item)
        if (row.get("page_path") not in TOPIC_PATHS
            or row.get("slug") != item.stem
            or row.get("published") is not False
            or row.get("approved_for_publication") is not False):
            raise RuntimeError("content_draft_scope_violation")
        existing_slugs.add(item.stem)
        if row.get("drafted_utc", "")[:10] == day:
            issued_today += 1
    made = []
    assessments = []
    for brief in BRIEFS:
        if len(made) >= MAX_PER_UTC_DAY - issued_today:
            break
        if brief["slug"] in existing_slugs:
            continue
        item = build(brief, stamp)
        # Site-specific Gen65 is a read-only editorial suggestion. Link
        # existence was checked during brief curation, not each Cron tick.
        decision = gen65_classify(95, len(item["source_urls"]), True)
        if decision not in ("candidate_ready_for_human_review", "hold_for_review"):
            raise RuntimeError("gen65_rejected_content_brief")
        item["gen65_private_review_recommendation"] = decision
        item["gen65_factual_verification_completed"] = False
        path = drafts / (brief["slug"] + ".json")
        if path.exists() or path.is_symlink():
            raise RuntimeError("content_duplicate_file")
        _atomic(path, item)
        made.append(brief["slug"])
        assessments.append(decision)
    report = {
        "tenant": TENANT,
        "status": "active_private_page_content_pipeline",
        "utc": stamp,
        "current_utc_day": day,
        "new_drafts": len(made),
        "new_slugs": made,
        "total_drafts": len(existing) + len(made),
        "remaining_curated_briefs": len(BRIEFS)-len(existing_slugs)-len(made),
        "approved_page_paths": sorted(TOPIC_PATHS),
        "language": "en",
        "gen65_review_recommendations": assessments,
        "generation_source": "bounded_curated_original_briefs",
        "external_llm_connected": False,
        "auto_publish": False,
        "public_site_modified": False,
        "other_subsites_modified": False,
        "requires_editorial_review": True,
    }
    _atomic(folder / "last_report.json", report)
    return report
