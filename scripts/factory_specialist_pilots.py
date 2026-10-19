#!/usr/bin/env python3
"""Evidence-gated, private, resource-bounded specialist product pilots.

Builds ORIGINAL usable editable artifacts with the separately verified VPS
toolchain. One new family pilot per tick. Never declares a 40-family release,
human review, code self-upgrade, ownership, or commercial approval.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

FAMILIES = {"F27": ("budget.xlsx",), "F29": ("project_brief.docx",),
            "F30": ("kickoff.pptx",), "F34": ("icon.png", "icon.svg"),
            "F10": ("assessment.pdf", "assessment.json"),
            "F14": ("mini_game.html", "game.js", "browser_game.zip"),
            "F19": ("landing.html", "landing.css", "website_template.zip"),
            "F31": ("weekly_planner.pdf", "weekly_planner.svg"),
            "F33": ("landscape.png", "landscape.svg"),
            "F37": ("motion.gif", "motion.mp4"),
            "F39": ("sound_effect.wav", "sound_effect.mp3")}
REQUIRED = {"images", "documents", "video", "office_render_and_recalculation",
            "blender_cpu_render", "local_language_model"}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def toolchain(manifest):
    path = Path(manifest)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise RuntimeError("PILOT_TOOLCHAIN_MANIFEST_MISSING_OR_UNSAFE")
    item = json.loads(path.read_text(encoding="utf-8"))
    if item.get("schema") != "saeit.factory.toolchain.v1":
        raise RuntimeError("PILOT_TOOLCHAIN_SCHEMA_INVALID")
    checks = item.get("checks")
    if not isinstance(checks, dict) or not REQUIRED.issubset(checks):
        raise RuntimeError("PILOT_TOOLCHAIN_PROOFS_MISSING")
    if any(checks[k].get("passed") is not True for k in REQUIRED):
        raise RuntimeError("PILOT_TOOLCHAIN_NOT_VERIFIED")
    root = Path(item["root"])
    if (root.is_symlink() or not root.is_dir()
            or not re.fullmatch(r"[a-f0-9]{40}", root.name)
            or root.parent != path.parent / "versions"):
        raise RuntimeError("PILOT_TOOLCHAIN_ROOT_NOT_VERSION_PINNED")
    python = root / "venv" / "bin" / "python"
    if Path(item.get("python", "")) != python or not python.is_file():
        raise RuntimeError("PILOT_TOOLCHAIN_PYTHON_INVALID")
    if not (root / "proof.json").is_file():
        raise RuntimeError("PILOT_TOOLCHAIN_LOCAL_PROOF_MISSING")
    return root, python


def render(family, folder):
    folder = Path(folder)
    if family in ("F10","F14","F19","F31","F33","F37","F39"):
        source = Path(__file__).resolve().parent / "factory_specialist_formats.py"
        spec = importlib.util.spec_from_file_location("factory_specialist_formats", str(source))
        if spec is None or spec.loader is None:
            raise RuntimeError("SPECIALIST_RENDERER_SOURCE_MISSING")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.render(family, folder)
    elif family == "F27":
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font, PatternFill
        w = Workbook()
        s = w.active
        s.title = "Illustrative budget"
        s.append(["Month", "Revenue (example)", "Costs (example)", "Net (formula)"])
        for n in range(1, 13):
            row = n + 1
            s.append([n, 1200 + n * 70, 680 + n * 25, "=B%d-C%d" % (row, row)])
        s.append(["TOTAL", "=SUM(B2:B13)", "=SUM(C2:C13)", "=SUM(D2:D13)"])
        s.freeze_panes = "A2"
        s.column_dimensions["A"].width = 22
        for name in "BCD":
            s.column_dimensions[name].width = 25
        for cell in s[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="19385A")
        w.save(str(folder / "budget.xlsx"))
        check = load_workbook(str(folder / "budget.xlsx"), data_only=False)
        assert check.active["D2"].value == "=B2-C2"
        assert check.active["D14"].value == "=SUM(D2:D13)"
    elif family == "F29":
        from docx import Document
        d = Document()
        d.add_heading("Project brief — editable template", 0)
        for heading, text in (
            ("Outcome", "Define one verifiable result and its acceptance criteria."),
            ("Scope", "List included deliverables, exclusions and assumptions."),
            ("Milestones", "Record milestone, accountable owner, due date and evidence."),
            ("Risks", "Log the likelihood, impact, mitigation and escalation owner."),
            ("Quality gate", "Verify factual accuracy, rights and accessibility.")):
            d.add_heading(heading, level=1)
            d.add_paragraph(text)
        d.save(str(folder / "project_brief.docx"))
        verify = Document(str(folder / "project_brief.docx"))
        assert len(verify.paragraphs) >= 10
    elif family == "F30":
        from pptx import Presentation
        from pptx.util import Inches, Pt
        p = Presentation()
        p.slide_width, p.slide_height = Inches(13.333), Inches(7.5)
        slides = [
            ("Project kick-off", "An editable delivery plan template"),
            ("Objectives and evidence", "Define measurable outcomes, users and acceptance checks"),
            ("Timeline and risks", "Milestones • ownership • assumptions • mitigation")]
        for title, subtitle in slides:
            slide = p.slides.add_slide(p.slide_layouts[6])
            for top, content, size in ((1.15, title, 34), (2.75, subtitle, 21)):
                shape = slide.shapes.add_textbox(Inches(0.95), Inches(top),
                                                  Inches(11.4), Inches(2.0))
                paragraph = shape.text_frame.paragraphs[0]
                paragraph.text = content
                paragraph.font.size = Pt(size)
        p.save(str(folder / "kickoff.pptx"))
        assert len(Presentation(str(folder / "kickoff.pptx")).slides) == 3
    elif family == "F34":
        from PIL import Image, ImageDraw
        image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((64, 64, 448, 448), radius=110, fill=(25, 56, 90, 255))
        draw.polygon([(256, 112), (390, 256), (256, 400), (122, 256)],
                     fill=(236, 190, 92, 255))
        image.save(str(folder / "icon.png"), "PNG", optimize=True)
        (folder / "icon.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            '<rect x="64" y="64" width="384" height="384" rx="110" fill="#19385a"/>'
            '<path d="M256 112 390 256 256 400 122 256Z" fill="#ecbe5c"/></svg>',
            encoding="utf-8")
        assert Image.open(str(folder / "icon.png")).size == (512, 512)
        assert ET.parse(str(folder / "icon.svg")).getroot().tag.endswith("svg")
    else:
        raise ValueError("PILOT_UNSUPPORTED_FAMILY")
    output = {}
    for name in FAMILIES[family]:
        path = folder / name
        if not path.is_file() or path.stat().st_size < 100:
            raise RuntimeError("PILOT_OUTPUT_INVALID:" + name)
        output[name] = sha(path)
    return output


def atomic(path, data):
    if path.parent.is_symlink():
        raise RuntimeError('SELF_UPGRADE_BLOCKED_SYMLINK_PARENT')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temp = tempfile.mkstemp(prefix=".pilot-", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def verified_receipt(folder, family, source_key):
    receipt = folder / "technical-receipt.json"
    if not receipt.is_file() or receipt.is_symlink():
        return False
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
        return (data.get("source_key") == source_key
                and data.get("family") == family
                and data.get("commercial_release") is False
                and set(data.get("files", {})) == set(FAMILIES[family])
                and all((folder / name).is_file()
                        and not (folder / name).is_symlink()
                        and sha(folder / name) == data["files"][name]
                        for name in FAMILIES[family]))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def cycle(output, manifest):
    output = Path(output)
    if output.is_symlink():
        raise RuntimeError("PILOT_UNSAFE_ROOT")
    root = output / "family-pilots"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        toolroot, executable = toolchain(manifest)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
        status = {"status": "awaiting_verified_toolchain", "reason": str(error)[:180],
                  "commercial_release": False, "fully_verified_families": 0}
        atomic(root / "status.json", status)
        return status
    source = Path(__file__).resolve().parent / "factory_specialist_formats.py"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("PILOT_SPECIALIST_FORMAT_MODULE_MISSING")
    source_key = hashlib.sha256((sha(__file__) + sha(source) + toolroot.name + "v2").encode()).hexdigest()[:20]
    failures = []
    for family in FAMILIES:
        version = root / family / source_key
        if verified_receipt(version, family, source_key):
            continue
        family_dir = version.parent
        family_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # The previous damaged revision is never deleted. Keep evidence and rebuild.
        if version.exists():
            if version.is_symlink():
                raise RuntimeError("PILOT_UNSAFE_VERSION")
            quarantine = family_dir / ("retained-damaged-" + source_key + "-" + str(time.time_ns()))
            version.rename(quarantine)
        stage = Path(tempfile.mkdtemp(prefix=".pilot-build-", dir=str(family_dir)))
        try:
            process = subprocess.run(
                [str(executable), "-B", str(Path(__file__).resolve()), "--render", family,
                 "--destination", str(stage)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                timeout=50, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                    FACTORY_TOOLCHAIN_BIN=str(toolroot / "bin")))
            if process.returncode:
                raise RuntimeError("PILOT_RENDER_FAILURE:" + process.stderr[-350:])
            outputs = json.loads(process.stdout.strip())
            if not isinstance(outputs, dict) or set(outputs) != set(FAMILIES[family]):
                raise RuntimeError("PILOT_RENDER_PROOF_INVALID")
            if any(sha(stage / name) != digest for name, digest in outputs.items()):
                raise RuntimeError("PILOT_ARTIFACT_HASH_MISMATCH")
            atomic(stage / "technical-receipt.json", {
                "schema": "saeit.factory.specialist-pilot.v1",
                "family": family, "source_key": source_key, "files": outputs,
                "technical_quality_passed": True, "commercial_release": False,
                "independent_specialist_review_completed": False,
                "distribution_enabled": False, "owner_approval_recorded": False,
                "toolchain_version": toolroot.name})
            stage.rename(version)
            result = {"status": "pilot_built", "family": family,
                      "source_key": source_key, "technical_files": list(outputs),
                      "independent_approval": False, "fully_verified_families": 0}
            atomic(root / "status.json", result)
            return result
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            # Preserve the defect indefinitely, retry on a later minute.
            ticket_path = family_dir / "rework.json"
            try:
                previous = json.loads(ticket_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                previous = {}
            prior = previous.get("attempts", 0)
            if isinstance(prior, bool) or not isinstance(prior, int) or prior < 0:
                prior = 0
            ticket = {"family": family, "status": "needs_rework",
                      "last_failure": str(error)[:400], "source_key": source_key,
                      "attempts": prior + 1, "retry_on_next_tick": True,
                      "last_attempt_epoch_ns": time.time_ns(),
                      "commercial_release": False,
                      "history_tail": (previous.get("history_tail", [])
                          if isinstance(previous.get("history_tail"), list) else [])[-30:]}
            ticket["history_tail"].append({"attempt": prior + 1,
                                           "reason": str(error)[:200]})
            atomic(ticket_path, ticket)
            # Do not let one broken family starve every other independent line.
            failures.append({"family": family, "reason": ticket["last_failure"]})
            continue
        finally:
            if stage.exists():
                shutil.rmtree(str(stage))
    if failures:
        status = {"status": "needs_rework", "failed_families": failures,
                  "retry_on_next_tick": True, "fully_verified_families": 0,
                  "commercial_release": False, "distribution_enabled": False}
        atomic(root / "status.json", status)
        return status
    status = {"status": "technical_pilots_verified", "families": list(FAMILIES),
              "fully_verified_families": 0, "commercial_release": False,
              "distribution_enabled": False}
    atomic(root / "status.json", status)
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out")
    p.add_argument("--manifest")
    p.add_argument("--render", choices=sorted(FAMILIES))
    p.add_argument("--destination")
    args = p.parse_args()
    if args.render:
        if not args.destination:
            raise ValueError("PILOT_DESTINATION_REQUIRED")
        print(json.dumps(render(args.render, args.destination), sort_keys=True))
        return
    if not args.out or not args.manifest:
        raise ValueError("PILOT_OUTPUT_AND_MANIFEST_REQUIRED")
    print("FACTORY_SPECIALIST_PILOT=" + json.dumps(cycle(args.out, args.manifest), sort_keys=True))


if __name__ == "__main__":
    main()
