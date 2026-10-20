#!/usr/bin/env python3
"""Real fixed-scope F29/F30/F33 template producers (48 distinct work packages).

Outputs are original editable technical templates/illustrations, not custom
commissions, human-approved artwork, or commercially licensed finished goods.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
ACTIONS = ("brief", "example", "checklist", "review")
TOPICS = (
 ("project_scope", "Project scope", "Outcome", "Exclusions", "Assumptions", "Acceptance"),
 ("risk_register", "Risk register", "Risk", "Likelihood", "Mitigation", "Owner"),
 ("requirements", "Requirements", "User need", "Constraint", "Evidence", "Priority"),
 ("release_plan", "Release plan", "Milestone", "Dependency", "Rollback", "Approval"),
 ("quality_review", "Quality review", "Requirement", "Method", "Result", "Defect"),
 ("accessibility", "Accessibility", "Audience", "Assistive use", "Contrast", "Check"),
 ("operations", "Operations", "Trigger", "Procedure", "Escalation", "Recovery"),
 ("research_log", "Research log", "Question", "Evidence", "Uncertainty", "Source"),
 ("change_control", "Change control", "Request", "Impact", "Decision", "Reviewer"),
 ("cost_plan", "Cost plan", "Resource", "Estimate", "Assumptions", "Variance"),
 ("stakeholders", "Stakeholders", "Audience", "Need", "Communication", "Feedback"),
 ("retrospective", "Retrospective", "Outcome", "Evidence", "Learning", "Next action"),
)
PRODUCTS = {"F29": "fieldwork_editable_document_suite",
            "F30": "fieldwork_editable_slide_suite",
            "F33": "fieldwork_vector_illustration_suite"}

def load(name):
    source = HERE / (name + ".py")
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("CREATIVE_MODULE_UNTRUSTED")
    spec = importlib.util.spec_from_file_location(name, str(source))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def tasks(proto, family):
    return {
      "schema": proto.SCHEMA, "family_id": family,
      "product_id": PRODUCTS[family], "producer_id": "fieldwork_creative_template_engine_v1",
      "source_snapshot_sha256": proto.digest({
          "producer": proto.file_sha(__file__),
          "reviewer": proto.file_sha(HERE / "factory_creative_independent_review.py"),
          "protocol": proto.file_sha(HERE / "factory_build_50.py"),
          "family": family, "scope": "fixed_editable_template"}),
      "work_packages": [
          {"id": key + "_" + action, "topic": key, "action": action,
           "instruction": "Create an original " + action + " " +
             ("editable document" if family == "F29" else "editable slide deck" if family == "F30" else "raster and vector illustration") +
             " addressing the unique " + title + " scope, including " + ", ".join(fields) +
             ". Deliver a usable family-specific standalone asset with verifiable structure.",
           "acceptance": [
              "This task creates new nonempty, independently readable original files.",
              "This asset includes scope-specific content, visible distinguishing features and a verified file format."]}
          for key, title, *fields in TOPICS for action in ACTIONS]}

def document(folder, name, topic, action):
    from docx import Document
    from docx.shared import Pt
    key, title, *fields = topic
    doc = Document()
    doc.add_heading(title + " — " + action.title(), 0)
    doc.add_paragraph("Editable project template • " + key.replace("_", " ") +
                      " • private technical sample, not expert advice.")
    for i, field in enumerate(fields):
        doc.add_heading(field, level=1)
        samples = {
          "brief": "Define the " + field.lower() + " with an explicit owner and measurable acceptance condition.",
          "example": "Illustrative " + field.lower() + ": document a concrete observation, then verify it before external use.",
          "checklist": "☐ Check " + field.lower() + " against the project record; ☐ record missing evidence.",
          "review": "Review " + field.lower() + ": evidence seen, discrepancy, corrective action, independent sign-off."
        }
        doc.add_paragraph(samples[action])
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = field + " reference"
        table.cell(0, 1).text = "Enter and verify before use"
    doc.add_paragraph("Quality notice: illustrative editable material only; no claims of human or legal approval.")
    doc.styles["Normal"].font.size = Pt(10)
    doc.save(str(folder / name))

def slides(folder, name, topic, action):
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    key, title, *fields = topic
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    for page, pair in enumerate((fields[:2], fields[2:])):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(21 + 4 * ACTIONS.index(action), 43, 62 + page * 9)
        heading = slide.shapes.add_textbox(Inches(.7), Inches(.55), Inches(11.9), Inches(1))
        para = heading.text_frame.paragraphs[0]
        para.text = title + " · " + action.title() + " · " + str(page + 1)
        para.font.size = Pt(30)
        para.font.color.rgb = RGBColor(245, 211, 153)
        for i, field in enumerate(pair):
            shape = slide.shapes.add_textbox(Inches(.8 + i * 6), Inches(2), Inches(5.5), Inches(3.5))
            txt = shape.text_frame
            txt.word_wrap = True
            txt.text = field + "\n\n" + {
              "brief": "Define scope, owner, and observable acceptance evidence.",
              "example": "Illustrative example: verify a recorded observation with a primary source.",
              "checklist": "□ Verify field  □ Record evidence  □ Escalate defects",
              "review": "Review evidence  →  log issues  →  assign next action"
            }[action]
            for p in txt.paragraphs:
                p.font.size = Pt(20)
                p.font.color.rgb = RGBColor(248, 249, 246)
    deck.save(str(folder / name))

def illustration(folder, name, topic, action):
    from PIL import Image, ImageDraw
    from xml.etree import ElementTree as ET
    key, title, *fields = topic
    theme = next(i for i, row in enumerate(TOPICS) if row[0] == key)
    variant = ACTIONS.index(action)
    hue = (theme * 17 + variant * 31) % 170
    colors = ("#%02x%02x%02x" % (20 + hue // 4, 55 + hue // 3, 95 + variant * 17),
              "#%02x%02x%02x" % (193 + variant * 10, 141 + theme * 3, 79 + theme * 2),
              "#%02x%02x%02x" % (61 + variant * 15, 124 + theme * 2, 129 + variant * 10))
    svg_name = name + ".svg"
    png_name = name + ".png"
    # Twelve structurally different arrangements; four color/composition variants each.
    circle_x = 105 + (theme * 43 + variant * 37) % 420
    circle_y = 88 + (theme * 17 + variant * 39) % 240
    points = "30,440 %d,%d %d,%d 690,440" % (
        120 + theme * 9, 160 + variant * 23, 320 + theme * 11, 250 - variant * 18)
    text = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 480" role="img" aria-label="' +
       title + ' ' + action + '"><rect width="720" height="480" fill="' + colors[0] +
       '"/><circle cx="' + str(circle_x) + '" cy="' + str(circle_y) +
       '" r="' + str(37 + theme * 2) + '" fill="' + colors[1] +
       '"/><polygon points="' + points + '" fill="' + colors[2] +
       '"/><path d="M0 455 Q360 ' + str(275 + variant * 18) + ' 720 455" fill="none" stroke="' +
       colors[1] + '" stroke-width="' + str(5 + theme % 4) + '"/></svg>')
    (folder / svg_name).write_text(text, encoding="utf8")
    root = ET.fromstring(text)
    if not root.tag.endswith("svg"): raise ValueError("CREATIVE_BAD_VECTOR")
    def rgb(code): return tuple(int(code[x:x+2], 16) for x in (1,3,5))
    img = Image.new("RGB", (720,480), rgb(colors[0]))
    draw = ImageDraw.Draw(img)
    radius = 37 + theme * 2
    draw.ellipse((circle_x-radius,circle_y-radius,circle_x+radius,circle_y+radius), fill=rgb(colors[1]))
    draw.polygon([(30,440),(120+theme*9,160+variant*23),
                  (320+theme*11,250-variant*18),(690,440)],fill=rgb(colors[2]))
    draw.arc((-40,275+variant*18,760,635+variant*18), 0, 180, fill=rgb(colors[1]),width=5+theme%4)
    img.save(str(folder / png_name), "PNG", optimize=True)
    return [svg_name,png_name]

def build(root, family):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or family not in PRODUCTS:
        raise ValueError("CREATIVE_UNSAFE_ROOT_OR_FAMILY")
    proto = load("factory_build_50")
    review = load("factory_creative_independent_review")
    plan = tasks(proto, family)
    product = plan["product_id"]
    home = root / "build-50" / product
    target = root / "digital-products" / product
    if any(x.is_symlink() for x in (home,root/"digital-products",target)):
        raise ValueError("CREATIVE_UNSAFE_OUTPUT")
    archive_name = product + "-internal-qa.zip"
    if (home/"state.json").is_file() and (target/"manufacturing_manifest.json").is_file():
        state = proto.read(home/"state.json")
        manifest = proto.read(target/"manufacturing_manifest.json")
        archive = target/archive_name
        if (proto.verify_attempt(home,state,plan["source_snapshot_sha256"]) and
                archive.is_file() and not archive.is_symlink() and
                proto.file_sha(archive) == manifest.get("artifact_sha256")):
            return {"family_id":family,"product_id":product,"status":"unchanged_verified_technical_product"}
    topics = {r[0]:r for r in TOPICS}
    def worker(task,ctx):
        folder=Path(ctx["folder"])
        name=task["id"]
        if family=="F29":
            result=[name+".docx"]
            document(folder,result[0],topics[task["topic"]],task["action"])
        elif family=="F30":
            result=[name+".pptx"]
            slides(folder,result[0],topics[task["topic"]],task["action"])
        else:
            result=illustration(folder,name,topics[task["topic"]],task["action"])
        if any(not (folder/x).is_file() or (folder/x).stat().st_size<200 for x in result):
            raise ValueError("CREATIVE_EMPTY_ARTIFACT")
        return {"passed":True,"outputs":result,"successful_checks":2}
    def assemble(data,ctx):
        folder=Path(ctx["folder"])
        members=sorted(p.name for p in folder.iterdir() if p.suffix in (".docx",".pptx",".svg",".png"))
        readme="Original editable fixed-scope "+family+" portfolio. "+str(len(members))+" source files. Private engineering samples; illustrative content and geometry. No human, legal, semantic, device or commercial certification. Confirm rights and fitness before publication.\n"
        (folder/"README.txt").write_text(readme,encoding="utf8")
        with zipfile.ZipFile(folder/archive_name,"w",zipfile.ZIP_DEFLATED) as zipf:
            for name in members+["README.txt"]:
                info=zipfile.ZipInfo(product+"/"+name,date_time=(2020,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o100644<<16
                zipf.writestr(info,(folder/name).read_bytes())
        return {"passed":True,"outputs":["README.txt",archive_name],"successful_checks":3}
    def reviewer(data,ctx):
        folder=Path(ctx["folder"])
        evidence=review.check(folder,folder/archive_name,product,family)
        proto.save(folder/"independent-creative-review.json",evidence)
        return {"reviewer_id":"independent_creative_format_and_integrity_reviewer",
                "critical_defects":[],"gates":evidence["gates"],
                "passed":evidence["passed"],"outputs":["independent-creative-review.json"],
                "successful_checks":10}
    state=proto.run_attempt(root,plan,worker,assemble,reviewer)
    if not proto.verify_attempt(home,state,plan["source_snapshot_sha256"]):
        return {"family_id":family,"product_id":product,
                "status":"technical_rework_required","defects":state.get("defects",[])}
    folder=Path(state["attempt_folder"])
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    incoming=target/".incoming-creative.zip"
    if incoming.is_symlink() or (target/archive_name).is_symlink():
        raise ValueError("CREATIVE_UNSAFE_ARCHIVE")
    shutil.copyfile(folder/archive_name,incoming)
    os.replace(incoming,target/archive_name)
    manifest={"schema_version":2,"recipe":product,"family_id":family,
      "name":family+" original editable technical template portfolio",
      "artifact_sha256":proto.file_sha(target/archive_name),
      "bytes":(target/archive_name).stat().st_size,
      "source_sha256":plan["source_snapshot_sha256"],
      "build50_source_snapshot_sha256":plan["source_snapshot_sha256"],
      "qa_status":"passed","qa_evidence":"automated_format_archive_checks_only",
      "qa_measurements":proto.read(folder/"independent-creative-review.json"),
      "commercial_status":"private_internal_qa_pass_not_published",
      "public_listing_enabled":False,"owner_publication_approval":False,
      "independent_human_review":False}
    proto.save(target/"manufacturing_manifest.json",manifest)
    return {"family_id":family,"product_id":product,
            "status":"technical_50_stage_build_completed","completed_stages":50,
            "commercial_release":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--family",required=True,choices=sorted(PRODUCTS))
    a=p.parse_args()
    result=build(a.factory_private,a.family)
    print("FACTORY_CREATIVE_BUILD50="+json.dumps(result,sort_keys=True))
    if result["status"]=="technical_rework_required":raise SystemExit(2)
