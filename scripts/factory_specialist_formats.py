#!/usr/bin/env python3
"""Real private specialized pilot artifact renderers; not a commercial release.

These are small, reproducible technical products. They do not substitute for
research validity, buyer fit, artistic expert review, app-store builds or rights.
"""
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import wave
import zipfile

FAMILIES = {
    "F10": ("assessment.pdf", "assessment.json"),
    "F14": ("mini_game.html", "game.js", "browser_game.zip"),
    "F19": ("landing.html", "landing.css", "website_template.zip"),
    "F31": ("weekly_planner.pdf", "weekly_planner.svg"),
    "F33": ("landscape.png", "landscape.svg"),
    "F37": ("motion.gif", "motion.mp4"),
    "F39": ("sound_effect.wav", "sound_effect.mp3"),
}


def package(folder, archive, names):
    with zipfile.ZipFile(str(folder / archive), "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(str(folder / name), arcname=name)
    with zipfile.ZipFile(str(folder / archive)) as z:
        assert z.testzip() is None and sorted(z.namelist()) == sorted(names)


def media_bin():
    prefix = Path(os.environ.get("FACTORY_TOOLCHAIN_BIN", ""))
    if not prefix.is_absolute() or prefix.name != "bin":
        raise RuntimeError("MEDIA_PREFIX_REQUIRED")
    executable = prefix / "ffmpeg"
    if executable.is_symlink() or not executable.is_file():
        raise RuntimeError("MEDIA_BINARY_UNAVAILABLE")
    return str(executable)


def ffmpeg(*args):
    result = subprocess.run([media_bin(), "-hide_banner", "-loglevel", "error", "-y"] + list(args),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=36, universal_newlines=True)
    if result.returncode:
        raise RuntimeError("MEDIA_RENDER_FAILED:" + result.stderr[-260:])


def render(family, folder):
    folder = Path(folder)
    if family == "F10":
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        bank = []
        for i in range(1, 13):
            a, b, c = i * 4 + 3, i * 3 + 2, i
            bank.append({"id": i, "question": "{} + {} - {} = ?".format(a, b, c),
                         "answer": a+b-c, "difficulty": "introductory",
                         "explanation": "Add the first two values, then subtract the third."})
        (folder/"assessment.json").write_text(json.dumps(
            {"schema": "factory.original.assessment.v1", "questions": bank,
             "scope": "Original illustrative arithmetic with machine-computed answer key"},
            indent=2), encoding="utf-8")
        pdf = canvas.Canvas(str(folder/"assessment.pdf"), pagesize=A4)
        pdf.setTitle("Arithmetic assessment — sample")
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawString(48, 780, "Arithmetic Assessment — example")
        pdf.setFont("Helvetica", 12)
        for n, item in enumerate(bank):
            pdf.drawString(48, 739-36*n, item["question"])
        pdf.drawString(48, 250, "Answer key and explanations are supplied in assessment.json.")
        pdf.save()
        assert len(json.loads((folder/"assessment.json").read_text())["questions"]) == 12
    elif family == "F14":
        (folder/"mini_game.html").write_text("""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orbit Collect — playable demo</title>
<style>body{background:#142330;color:#f8e5c4;font:20px system-ui;text-align:center}
canvas{width:min(90vw,420px);background:#233e4d;border:2px solid #e7b65a}
button{padding:12px;margin:7px;background:#e7b65a;border:0;border-radius:8px}</style>
<h1>Orbit Collect</h1><p>Collect the gold sparks; avoid red hazards.</p>
<canvas id="board" width="400" height="400" role="img" aria-label="Orbit Collect game field. Use Left and Right buttons or arrow keys to collect gold sparks and avoid red hazards."></canvas><p id="score" role="status" aria-live="polite" aria-atomic="true">Score: 0</p>
<button data-d="-1">Left</button><button data-d="1">Right</button>
<button id="restart">Restart</button><script src="game.js"></script></html>""",encoding="utf-8")
        (folder/"game.js").write_text("""'use strict';
const c=document.getElementById('board'),ctx=c.getContext('2d');
let x=200,items=[],score=0,tick=0,over=false;
function reset(){x=200;items=[];score=0;tick=0;over=false;document.getElementById('score').textContent='Score: 0';}
function move(d){if(!over)x=Math.max(18,Math.min(382,x+d*31));}
document.querySelectorAll('[data-d]').forEach(b=>b.addEventListener('click',()=>move(Number(b.dataset.d))));
document.getElementById('restart').addEventListener('click',reset);
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')move(-1);if(e.key==='ArrowRight')move(1);});
function frame(){ctx.clearRect(0,0,400,400);tick++;
if(!over&&tick%26===0)items.push({x:22+Math.random()*356,y:0,bad:Math.random()<.3});
items.forEach(o=>{if(!over)o.y+=2.4+score*.06;ctx.beginPath();ctx.arc(o.x,o.y,10,0,Math.PI*2);
ctx.fillStyle=o.bad?'#f15f67':'#ffd46c';ctx.fill();if(Math.abs(o.x-x)<22&&o.y>352&&o.y<392){
if(o.bad)over=true;else score+=1;o.y=999;}});items=items.filter(o=>o.y<410);
ctx.fillStyle='#91e1ce';ctx.fillRect(x-17,365,34,26);const status=document.getElementById('score');const next=(over?'Game over — ':'')+'Score: '+score;if(status.textContent!==next)status.textContent=next;
requestAnimationFrame(frame);}reset();requestAnimationFrame(frame);""",encoding="utf-8")
        package(folder, "browser_game.zip", ["mini_game.html","game.js"])
    elif family == "F19":
        (folder/"landing.html").write_text("""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Independent Studio — editable demo</title><link rel="stylesheet" href="landing.css">
<header><span>Independent Studio</span><nav><a href="#work">Work</a> <a href="#contact">Contact</a></nav></header>
<main><section class="hero"><h1>Create something useful.</h1><p>A responsive, lightweight starter page; replace demo wording before publishing.</p><a class="cta" href="#contact">Get in touch</a></section>
<section id="work"><h2>What we deliver</h2><div class="grid"><article>Clarity</article><article>Quality</article><article>Reliability</article></div></section>
<section id="contact"><h2>Contact</h2><p>Replace this placeholder with your verified business contact information.</p></section></main>
<footer>Original editable demonstration layout — no commercial claims.</footer></html>""",encoding="utf-8")
        (folder/"landing.css").write_text("""*{box-sizing:border-box}body{margin:0;background:#101c30;color:#f1e7d5;font:16px/1.6 system-ui,sans-serif}a{color:#efbf6f}
header{display:flex;justify-content:space-between;align-items:center;padding:1rem 5vw;border-bottom:1px solid #43516b}
header span{font-weight:700;font-size:1.3rem}.hero{padding:7vw 5vw;max-width:960px}.hero h1{font-size:clamp(2rem,6vw,4rem)}
.cta{display:inline-block;background:#ebbc66;color:#132437;border-radius:9px;padding:.65rem 1.2rem}
section:not(.hero){padding:2rem 5vw}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}
article{padding:2rem;border:1px solid #5c687b;border-radius:12px;background:#1d2c43}
footer{padding:2rem 5vw}@media(max-width:650px){.grid{grid-template-columns:1fr}header{flex-wrap:wrap}}
""",encoding="utf-8")
        package(folder, "website_template.zip", ["landing.html","landing.css"])
    elif family == "F31":
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from xml.etree import ElementTree as ET
        pdf=canvas.Canvas(str(folder/"weekly_planner.pdf"), pagesize=A4)
        pdf.setTitle("Weekly planner — blank printable")
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(42,790,"Weekly Planner")
        for i,name in enumerate(("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")):
            y=726-i*95
            pdf.setFont("Helvetica-Bold",12);pdf.drawString(47,y,name)
            pdf.setLineWidth(.7);pdf.rect(42,y-66,507,76,stroke=1,fill=0)
        pdf.save()
        parts=['<svg xmlns="http://www.w3.org/2000/svg" width="595" height="842" viewBox="0 0 595 842">',
               '<rect width="595" height="842" fill="#ffffff"/>',
               '<text x="42" y="46" font-family="sans-serif" font-size="25">Weekly Planner</text>']
        for i,name in enumerate(("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")):
            y=84+i*103
            parts.append('<rect x="42" y="{}" width="507" height="87" fill="none" stroke="#152c40"/>'.format(y))
            parts.append('<text x="52" y="{}" font-family="sans-serif" font-size="17">{}</text>'.format(y+23,name))
        (folder/"weekly_planner.svg").write_text("".join(parts)+"</svg>",encoding="utf-8")
        assert ET.parse(str(folder/"weekly_planner.svg")).getroot().tag.endswith("svg")
    elif family == "F33":
        from PIL import Image, ImageDraw
        from xml.etree import ElementTree as ET
        img=Image.new("RGB",(720,480),(27,54,83));d=ImageDraw.Draw(img)
        d.ellipse((485,55,625,195),fill=(251,200,111))
        d.polygon([(0,330),(180,165),(355,335)],fill=(89,136,139))
        d.polygon([(190,345),(510,120),(720,347)],fill=(56,105,129))
        d.rectangle((0,344,720,480),fill=(30,83,99))
        img.save(str(folder/"landscape.png"),"PNG",optimize=True)
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 480"><rect width="720" height="480" fill="#1b3653"/><circle cx="555" cy="125" r="70" fill="#fbc86f"/><path d="M0 330 180 165 355 335Z" fill="#59888b"/><path d="M190 345 510 120 720 347Z" fill="#386981"/><rect y="344" width="720" height="136" fill="#1e5363"/></svg>'
        (folder/"landscape.svg").write_text(svg,encoding="utf-8")
        assert Image.open(str(folder/"landscape.png")).size==(720,480)
        assert ET.parse(str(folder/"landscape.svg")).getroot().tag.endswith("svg")
    elif family == "F37":
        from PIL import Image, ImageDraw
        frames=[]
        for i in range(12):
            im=Image.new("RGB",(320,240),(21,35,52))
            d=ImageDraw.Draw(im)
            xx=35+i*22
            d.ellipse((xx,80,xx+55,135),fill=(243,190,85))
            d.line((20,180,300,180),fill=(97,164,160),width=3)
            frames.append(im)
        frames[0].save(str(folder/"motion.gif"),save_all=True,append_images=frames[1:],
                       duration=130,loop=0,optimize=True)
        ffmpeg("-i",str(folder/"motion.gif"),"-c:v","mpeg4","-pix_fmt","yuv420p",
               "-q:v","4",str(folder/"motion.mp4"))
        assert Image.open(str(folder/"motion.gif")).n_frames==12
    elif family == "F39":
        rate=22050
        samples=[]
        notes=((440,0.4),(554.37,0.4),(659.25,0.4),(880,0.6),(440,0.35))
        for frequency,duration in notes:
            for n in range(int(rate*duration)):
                t=n/rate
                envelope=min(1.,n/(rate*.025))*min(1.,(duration-t)/.12)
                val=int(11000*envelope*math.sin(2*math.pi*frequency*t))
                samples.append(struct.pack("<h",max(-32767,min(32767,val))))
        with wave.open(str(folder/"sound_effect.wav"),"wb") as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b"".join(samples))
        ffmpeg("-i",str(folder/"sound_effect.wav"),"-c:a","libmp3lame",
               "-b:a","128k",str(folder/"sound_effect.mp3"))
        with wave.open(str(folder/"sound_effect.wav"),"rb") as verify:
            assert verify.getnframes()>rate
    else:
        raise ValueError("NOT_A_SUPPORTED_SPECIALIST_FORMAT:"+family)
    for filename in FAMILIES[family]:
        path=folder/filename
        if not path.is_file() or path.stat().st_size<100:
            raise RuntimeError("SPECIALIST_FORMAT_MISSING_OR_EMPTY:"+filename)
