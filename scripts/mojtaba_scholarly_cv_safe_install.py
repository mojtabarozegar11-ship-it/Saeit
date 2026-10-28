#!/usr/bin/env python3
"""Add a source-honest scholarly CV to Mojtaba Roozegar's existing personal resume.

Only modifies templates/personal_site/core/resume.html on the private Django V17
installation. Repeated installs update only our own marked block. Backups are
mandatory, unique and losslessly reversible.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil

DEFAULT_APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
RELATIVE_TEMPLATE = Path("templates/personal_site/core/resume.html")
START = "<!-- MR-SCHOLARLY-CV-20261024:START -->"
END = "<!-- MR-SCHOLARLY-CV-20261024:END -->"
EXISTING_MARKERS = (
    'id="mpw-academic-profile-20261016"',
    'id="mpw-new-originals-20261015-b"',
    'id="mpw-fifty-editorials-20261015"',
)
CSS = """<style>
.mr-scholar{width:min(1180px,calc(100% - 28px));margin:36px auto;padding:clamp(22px,3.4vw,46px);border-radius:20px;border:1px solid #c9b98b;background:linear-gradient(138deg,#fffdf7,#f4f5ef);box-shadow:0 14px 50px #061d1925;color:#1e313b;font:16px/1.8 system-ui,-apple-system,Segoe UI,sans-serif}
.mr-scholar *{box-sizing:border-box}.mr-scholar .mr-eyebrow{color:#866338;font-weight:750;font-size:12px;letter-spacing:.16em;text-transform:uppercase}
.mr-scholar h2{font:600 clamp(29px,4vw,44px)/1.2 Georgia,serif;color:#18313b;margin:9px 0 12px}
.mr-scholar h3{font:600 clamp(22px,2.3vw,29px)/1.3 Georgia,serif;color:#213e4a;margin:28px 0 10px}
.mr-scholar p{margin:0 0 13px;color:#3e5260;max-width:920px}
.mr-scholar .mr-intro{font-size:clamp(17px,2vw,21px);line-height:1.65;color:#2c444f}
.mr-scholar .mr-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:24px 0}
.mr-scholar .mr-card{padding:18px;border-radius:10px;background:#fff;border:1px solid #dedac9;border-top:3px solid #b18a4b}
.mr-scholar .mr-label{display:block;font-size:12px;font-weight:750;letter-spacing:.05em;text-transform:uppercase;color:#806843;margin-bottom:7px}
.mr-scholar .mr-card strong{display:block;font-size:15px;line-height:1.5;color:#203c47}
.mr-scholar .mr-badges{display:flex;flex-wrap:wrap;gap:8px;margin:13px 0}
.mr-scholar .mr-badge{display:inline-block;border:1px solid #d4c9ab;border-radius:30px;background:#fdfbf4;padding:6px 11px;font-size:13px;color:#3f5560}
.mr-scholar .mr-note{border-left:3px solid #a78448;background:#f4f0e4;padding:14px 16px;font-size:14px}
.mr-scholar .mr-record{padding:17px 20px;margin-top:12px;background:white;border:1px solid #dedac9;border-radius:12px}
.mr-scholar .mr-record strong{display:block;font-size:17px;color:#1a3340;line-height:1.5}
.mr-scholar .mr-record small{display:block;font-size:13px;color:#637682}
.mr-scholar .mr-links a{display:inline-block;margin:5px 18px 0 0;color:#20556c;text-decoration:underline;text-underline-offset:3px}
@media(max-width:740px){.mr-scholar .mr-cards{grid-template-columns:1fr}.mr-scholar{padding:22px 17px}}
</style>"""

def escape(v: object) -> str:
    return html.escape(str(v), quote=True)

def load_data(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing trusted JSON source")
    d = json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema_version") != 2:
        raise ValueError("Unsupported scientific CV schema")
    if d.get("identity", {}).get("display_name") != "Mojtaba Roozegar":
        raise ValueError("Author byline is not the owner-approved name")
    for field in ("identity", "education", "research_interests", "researcher_ids",
                  "verified_peer_reviewed_publications", "verified_journal_submissions",
                  "research_pipeline", "accuracy_policy", "professional_profile", "seo"):
        if field not in d:
            raise ValueError("Missing required section: " + field)
    if not isinstance(d["education"], list) or not d["education"]:
        raise ValueError("Education source missing")
    if not isinstance(d["verified_peer_reviewed_publications"], list) or not isinstance(d["verified_journal_submissions"], list):
        raise ValueError("Scientific records must be arrays")
    seen = set()
    for p in d["verified_peer_reviewed_publications"]:
        if not (p.get("title") and p.get("journal") and re.fullmatch(r"10\.\d{4,9}/\S+", p.get("doi", ""))):
            raise ValueError("A publication requires actual title, journal and DOI evidence")
    for p in d["verified_journal_submissions"]:
        if not (p.get("title") and p.get("journal") and p.get("manuscript_id")):
            raise ValueError("A submission requires real publisher manuscript ID")
    for entry in d["research_pipeline"]:
        if not (entry.get("id") and entry.get("title") and entry.get("status")):
            raise ValueError("Incomplete working research record")
        if entry["id"] in seen:
            raise ValueError("Duplicate manuscript tracking ID")
        seen.add(entry["id"])
        if "submitted" in entry["status"].lower() or "accepted" in entry["status"].lower():
            raise ValueError("Working pipeline cannot self-certify submission or acceptance")
    professional = d["professional_profile"]
    for field in ("residence", "summary", "current_roles", "previous_experience",
                  "specializations", "teaching", "writing", "official_links", "evidence_note"):
        if not professional.get(field):
            raise ValueError("Incomplete professional resume: " + field)
    if len(professional["current_roles"]) < 2 or len(professional["official_links"]) < 2:
        raise ValueError("Current executive roles and official links required")
    for role in professional["current_roles"]:
        if not all(role.get(k) for k in ("title", "organization", "scope", "description")):
            raise ValueError("Incomplete current role")
    allowed_origins = ("https://mojplaywin.com/", "https://zomorodmelal.ir/")
    for link in professional["official_links"]:
        if not link.get("label") or not any(link.get("url", "").startswith(o) for o in allowed_origins):
            raise ValueError("Official CV links restricted to known sites")
    if not d["seo"].get("title") or not d["seo"].get("description"):
        raise ValueError("Resume title and description required")
    return d

def render_professional(data: dict) -> str:
    """Render owner-reported roles without manufacturing dates or credentials."""
    p = data["professional_profile"]
    out = [
        '<div class="mr-professional" id="mr-professional-resume-20261028">',
        '<span class="mr-eyebrow">Vancouver · Research · Executive leadership</span>',
        '<h3>Professional profile and current roles</h3>',
        '<p class="mr-intro">' + escape(p["summary"]) + '</p>',
        '<p><strong>Current residence:</strong> ' + escape(p["residence"]) + '</p>',
        '<div class="mr-cards">',
    ]
    for role in p["current_roles"]:
        out.append('<article class="mr-card"><span class="mr-label">' +
                   escape(role["scope"]) + '</span><strong>' +
                   escape(role["title"]) + '</strong><span>' +
                   escape(role["organization"]) + '</span><p>' +
                   escape(role["description"]) + '</p></article>')
    out += [
        '</div><h3>Previous executive and business experience</h3>',
        '<p>' + escape(p["previous_experience"]) + '</p>',
        '<h3>Core specializations</h3><div class="mr-badges">',
    ]
    out += ['<span class="mr-badge">' + escape(s) + '</span>'
            for s in p["specializations"]]
    out += [
        '</div><h3>Teaching, workshops and knowledge sharing</h3>',
        '<p>' + escape(p["teaching"]) + '</p>',
        '<h3>Books, articles and scientific writing</h3>',
        '<p>' + escape(p["writing"]) + '</p>',
        '<p class="mr-note">' + escape(p["evidence_note"]) + '</p>',
        '<h3>Official professional links</h3><p class="mr-links">',
    ]
    out += ['<a href="' + escape(link["url"]) +
            '" rel="noopener">' + escape(link["label"]) + '</a>'
            for link in p["official_links"]]
    # A distinct CV WebPage references the same authoritative Person @id.
    graph = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": "https://mojplaywin.com/mojtaba.roozegar/resume/#webpage",
        "url": "https://mojplaywin.com/mojtaba.roozegar/resume/",
        "name": data["seo"]["title"],
        "description": data["seo"]["description"],
        "inLanguage": "en",
        "about": {"@id": "https://mojplaywin.com/mojtaba.roozegar/#person"},
        "isPartOf": {"@id": "https://mojplaywin.com/mojtaba.roozegar/#webpage"}
    }
    structured = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    out += ['</p><script type="application/ld+json">' + structured +
            '</script></div>']
    return "\n".join(out)


def replace_resume_meta(template: str, data: dict) -> str:
    """Only update page-local Django title/description blocks, if present."""
    for name, value in (("title", data["seo"]["title"]),
                        ("description", data["seo"]["description"])):
        pat = re.compile(r"({%\s*block\s+" + name +
                         r"\s*%})(.*?)({%\s*endblock\s*%})", re.S)
        matches = list(pat.finditer(template))
        if len(matches) > 1:
            raise ValueError("Ambiguous SEO block: " + name)
        if matches:
            m = matches[0]
            template = template[:m.start()] + m.group(1) + escape(value) + m.group(3) + template[m.end():]
    return template

def render(data: dict) -> str:
    ident = data["identity"]
    degree = data["education"][0]
    out = [START, '<section id="mr-scholarly-cv-20261024" class="mr-scholar" aria-labelledby="mr-scholar-title">',
           CSS, '<span class="mr-eyebrow">Official scholarly record · Research portfolio</span>',
           '<h2 id="mr-scholar-title">' + escape(ident["display_name"]) + ' — Scientific CV</h2>',
           '<p class="mr-intro">Research interests, academic background, and a transparent register of international journal publications and submissions.</p>',
           '<div class="mr-cards">',
           '<div class="mr-card"><span class="mr-label">Academic background · self-reported</span><strong>' +
           escape(degree["degree"]) + '</strong><span>' + escape(degree["institution"]) + '</span></div>',
           '<div class="mr-card"><span class="mr-label">Research specialization</span><strong>' +
           escape(degree["concentration"]) + '</strong></div>',
           '<div class="mr-card"><span class="mr-label">Professional affiliation</span><strong>' +
           escape(ident["affiliation"]) + '</strong><span>' + escape(ident["role"]) + '</span></div>',
           '</div>',
           '<p class="mr-note">Academic degree and professional background above are owner-reported. No graduation date, university verification, journal acceptance or citation count is asserted without supporting evidence.</p>',
           render_professional(data),
           '<h3>Research interests</h3><div class="mr-badges">']
    out += ['<span class="mr-badge">' + escape(s) + '</span>' for s in data["research_interests"]]
    out += ['</div><h3>Researcher identifiers</h3><div class="mr-cards">']
    for k in ("ORCID", "Scopus Author ID", "Web of Science ResearcherID"):
        v = data["researcher_ids"].get(k)
        out.append('<div class="mr-card"><span class="mr-label">' + escape(k) + '</span><strong>' +
                   (escape(v) if v else "Not linked or verified") + '</strong></div>')
    out += ['</div><h3>Peer-reviewed journal publications</h3>']
    pubs = data["verified_peer_reviewed_publications"]
    if not pubs:
        out.append('<p class="mr-record">No independently verified peer-reviewed journal article has yet been entered in this public record. This is not a claim that the researcher has no other works.</p>')
    else:
        for p in pubs:
            doi = escape(p["doi"])
            out.append('<article class="mr-record"><strong>' + escape(p["title"]) + '</strong><small>' +
                       escape(p["journal"]) + '</small><a href="https://doi.org/' + doi + '" rel="noopener">Publisher DOI: ' +
                       doi + '</a></article>')
    out += ['<h3>Verified journal submissions</h3>']
    submissions = data["verified_journal_submissions"]
    if not submissions:
        out.append('<p class="mr-record">No journal-submission receipt or manuscript ID has been verified for this page yet.</p>')
    else:
        for p in submissions:
            out.append('<article class="mr-record"><strong>' + escape(p["title"]) + '</strong><small>Journal: ' +
                       escape(p["journal"]) + ' · Manuscript ID: ' + escape(p["manuscript_id"]) + '</small></article>')
    out += ['<h3>Research in preparation</h3>']
    for p in data["research_pipeline"]:
        out.append('<article class="mr-record"><strong>' + escape(p["title"]) + '</strong><small>' +
                   escape(p["id"]) + ' · ' + escape(p["type"]) + ' · ' + escape(p["status"]) +
                   '</small><p>Next evidence gate: ' + escape(p["next_gate"]) + '</p></article>')
    out += ['<p class="mr-note">Editorial transparency: personal website articles and drafts are not represented as peer-reviewed journal publications. A manuscript is "submitted" only after journal acknowledgement; "published" only after publisher confirmation.</p>',
            '<p class="mr-links"><a href="https://orcid.org/register" rel="noopener">Create or link ORCID</a>',
            '<a href="https://mjl.clarivate.com/" rel="noopener">Check journal indexing</a>',
            '<a href="/mojtaba.roozegar/blog/">Personal research journal (non-peer-reviewed)</a></p>',
            '</section>', END]
    return "\n".join(out)

def patch(template: str, data: dict) -> str:
    if template.count("{% block content %}") != 1:
        raise ValueError("Django resume content block missing or ambiguous")
    for marker in EXISTING_MARKERS:
        if template.count(marker) != 1:
            raise ValueError("Existing published resume content must remain intact: " + marker)
    block = render(data)
    if START in template or END in template:
        if template.count(START) != 1 or template.count(END) != 1:
            raise ValueError("Scientific CV marker pair corrupt")
        a = template.index(START)
        b = template.index(END, a) + len(END)
        updated = template[:a] + block + template[b:]
    else:
        marker = "{% block content %}"
        idx = template.index(marker) + len(marker)
        updated = template[:idx] + "\n" + block + "\n" + template[idx:]
    if updated.count(START) != 1 or updated.count(END) != 1:
        raise ValueError("Idempotency postcondition failed")
    for marker in EXISTING_MARKERS:
        if updated.count(marker) != 1:
            raise ValueError("Existing content preservation failed")
    return replace_resume_meta(updated, data)

def execute(mode: str, data_path: Path | None, app: Path, backup: Path | None) -> None:
    if app.is_symlink() or not (app / "manage.py").is_file():
        raise ValueError("Personal Django app not found")
    target = app / RELATIVE_TEMPLATE
    if not target.is_file() or target.is_symlink():
        raise ValueError("Target resume template invalid")
    if mode == "rollback":
        if not backup or not (backup / "resume.html").is_file() or (backup / "resume.html").is_symlink():
            raise ValueError("Rollback backup absent")
        temp = target.with_name("resume.html.scholar-rollback")
        if temp.exists():
            raise ValueError("Unexpected temp file")
        shutil.copy2(backup / "resume.html", temp)
        os.replace(temp, target)
        print("MR_SCHOLARLY_CV_ROLLBACK=yes")
    else:
        if data_path is None:
            raise ValueError("Content JSON required")
        data = load_data(data_path)
        old = target.read_text(encoding="utf-8")
        new = patch(old, data)
        print("MR_SCHOLARLY_CV_PRECHECK=yes")
        if mode == "check":
            return
        if not backup or backup.exists():
            raise ValueError("A fresh unique backup directory is mandatory")
        backup.mkdir(parents=True, mode=0o700)
        (backup / "resume.html").write_text(old, encoding="utf-8")
        (backup / "resume.html").chmod(0o600)
        temp = target.with_name("resume.html.scholar-install")
        if temp.exists():
            raise ValueError("Unexpected temp file")
        try:
            temp.write_text(new, encoding="utf-8")
            os.chmod(temp, target.stat().st_mode & 0o777)
            os.replace(temp, target)
        finally:
            if temp.exists():
                temp.unlink()
        print("MR_SCHOLARLY_CV_INSTALLED=yes")
    restart = app / "tmp/restart.txt"
    if restart.parent.is_dir():
        restart.touch()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["check", "install", "rollback"])
    parser.add_argument("--content", type=Path)
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--backup", type=Path)
    opts = parser.parse_args()
    execute(opts.mode, opts.content, opts.app, opts.backup)
