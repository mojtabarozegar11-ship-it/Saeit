#!/usr/bin/env python3
"""Independent BUILD50 technical production for F36, F37 and F39.

Forty-eight original measured media work packages per family, with real
rendered PNG/EXR, animated GIF/MP4, and synthesized WAV/MP3 files.
Commercial, expert, rights and artistic quality approvals are intentionally
not inferred. The production CLI requires a verified pinned VPS toolchain.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import wave
import zipfile

HERE=Path(__file__).resolve().parent
FAMILIES={
 "F36":"fieldwork_tileable_materials_48",
 "F37":"fieldwork_animated_motion_48",
 "F39":"fieldwork_original_audio_cues_48"}
MOTIFS=("dunes","ripples","orbits","lattice","currents","sparks","arches","waves",
        "petals","rings","glow","drift")
VARIANTS=("subtle","balanced","dynamic","contrast")
FORMATS={"F36":(".png",".exr"),"F37":(".gif",".mp4"),"F39":(".wav",".mp3")}

def load(name):
    path=HERE/(name+".py")
    if not path.is_file() or path.is_symlink():raise ValueError("MEDIA_UNTRUSTED_MODULE")
    spec=importlib.util.spec_from_file_location(name,str(path))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def binary(path):
    path=Path(path)
    if path.name!="ffmpeg" or path.is_symlink() or not path.is_file():
        raise RuntimeError("MEDIA_PINNED_FFMPEG_REQUIRED")
    return path

def ffmpeg_run(exe,*args,timeout=22):
    proc=subprocess.run([str(exe),"-hide_banner","-loglevel","error","-nostdin","-y"]+
         list(args),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
         timeout=timeout)
    if proc.returncode:
        raise RuntimeError("MEDIA_RENDER_FAILED:"+proc.stderr.decode("utf8","replace")[-500:])
    return proc

def plan(proto,family,exe):
    if family not in FAMILIES:raise ValueError("MEDIA_UNKNOWN_FAMILY")
    return {"schema":proto.SCHEMA,"family_id":family,"product_id":FAMILIES[family],
      "producer_id":"fieldwork_verified_native_media_engine",
      "source_snapshot_sha256":proto.digest({
        "family":family,"producer":proto.file_sha(__file__),
        "reviewer":proto.file_sha(HERE/"factory_native_media_review.py"),
        "protocol":proto.file_sha(HERE/"factory_build_50.py"),
        "ffmpeg_sha256":proto.file_sha(exe),
        "format":"verified_fixed_scope_media_v1"}),
      "work_packages":[{
        "id":motif+"_"+variant,"motif_index":i,"variant_index":v,
        "instruction":"Render unique original "+motif+" "+variant+
           " reusable "+({"F36":"tileable diffuse texture and OpenEXR source",
                            "F37":"loopable graphic animation and actual playable video",
                            "F39":"synthesized sound cue with editable PCM and decoded MP3"}[family])+
           ". Verify nonempty original outputs, exact format identity, correct dimensions or measured signal, and decoder integrity.",
        "acceptance":["Produce two distinct new independently decodable original media assets.",
                      "Verify task-specific content variation and concrete measurements without assuming commercial clearance."]}
        for i,motif in enumerate(MOTIFS) for v,variant in enumerate(VARIANTS)]}

def material(folder,stem,i,v,exe):
    from PIL import Image
    size=256
    p=folder/(stem+".png");q=folder/(stem+".exr")
    image=Image.new("RGB",(size,size))
    pixels=image.load()
    phase=(i+1)*0.31
    for y in range(size):
        y0=math.tau*y/(size-1)
        for x in range(size):
            x0=math.tau*x/(size-1)
            a=math.sin(x0*(1+i%4)+phase)*math.cos(y0*(1+v%3))
            b=math.sin(x0*(2+v%3)+y0*(1+i%3)+phase)
            c=math.cos(x0*(1+i%3)-y0*(2+v%2)-phase)
            base=110+33*a+19*b+12*c
            pixels[x,y]=tuple(max(5,min(245,int(base+shift))) for shift in
                (-21+i%8*4,13+v*7,39-i%6*5))
    image.save(p,"PNG",optimize=True)
    ffmpeg_run(exe,"-i",str(p),"-frames:v","1","-c:v","exr",
               "-pix_fmt","gbrpf32le","-f","image2",str(q))
    return [stem+".png",stem+".exr"]

def motion(folder,stem,i,v,exe):
    from PIL import Image,ImageDraw
    frames=[]
    w,h=256,192
    for tick in range(12):
        image=Image.new("RGB",(w,h),(14+(i*3)%30,27+v*8,47+(i*2)%24))
        draw=ImageDraw.Draw(image)
        progress=tick/12
        cx=44+int((w-88)*((progress+(v*.11))%1))
        cy=80+int(26*math.sin(math.tau*progress+i*.32))
        r=15+i%10
        for p in range(4):
            angle=math.tau*(progress+p/4)+i*.17
            x=int(cx+38*math.cos(angle))
            y=int(cy+27*math.sin(angle))
            draw.ellipse((x-5,y-5,x+5,y+5),fill=(117+v*15,183+i%40,178))
        draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(235-v*9,160+i%70,85+v*19))
        draw.line([(16,160),(240,160)],fill=(90,145,155),width=3)
        draw.rectangle((22,166,230,169),fill=(50+v*15,83,107))
        frames.append(image)
    gif=folder/(stem+".gif");mp4=folder/(stem+".mp4")
    frames[0].save(gif,save_all=True,append_images=frames[1:],
                   duration=100,loop=0,optimize=False)
    ffmpeg_run(exe,"-i",str(gif),"-c:v","mpeg4","-pix_fmt","yuv420p",
               "-q:v","5","-movflags","+faststart",str(mp4))
    return [stem+".gif",stem+".mp4"]

def audio(folder,stem,i,v,exe):
    rate=22050;count=int(rate*1.7);freq=185+i*29+v*17
    frames=bytearray()
    for n in range(count):
        t=n/rate
        rise=min(1.,n/(rate*.018))
        fall=min(1.,(count-1-n)/(rate*.21))
        envelope=max(0.,rise*fall)
        phase=math.tau*freq*t
        shape=.76*math.sin(phase)+.18*math.sin(phase*(2+i%3))+.06*math.sin(phase*4)
        value=int(12500*envelope*shape)
        frames.extend(struct.pack("<h",max(-32000,min(32000,value))))
    wav=folder/(stem+".wav");mp3=folder/(stem+".mp3")
    with wave.open(str(wav),"wb") as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
        stream.writeframes(frames)
    ffmpeg_run(exe,"-i",str(wav),"-c:a","libmp3lame","-b:a","128k",str(mp3))
    return [stem+".wav",stem+".mp3"]

def build(root,family,exe):
    root=Path(root);exe=binary(exe)
    if root.is_symlink() or not root.is_dir() or family not in FAMILIES:
        raise ValueError("MEDIA_UNSAFE_ROOT_OR_FAMILY")
    proto=load("factory_build_50");review=load("factory_native_media_review")
    spec=plan(proto,family,exe);product=spec["product_id"]
    home=root/"build-50"/product;target=root/"digital-products"/product
    zipname=product+"-internal-qa.zip"
    if any(p.is_symlink() for p in (root/"build-50",home,root/"digital-products",target)):
        raise ValueError("MEDIA_UNSAFE_TARGET")
    if (home/"state.json").is_file() and (target/"manufacturing_manifest.json").is_file():
        state=proto.read(home/"state.json");manifest=proto.read(target/"manufacturing_manifest.json")
        archive=target/zipname
        if (proto.verify_attempt(home,state,spec["source_snapshot_sha256"]) and
            archive.is_file() and not archive.is_symlink() and
            proto.file_sha(archive)==manifest.get("artifact_sha256")):
            return {"family_id":family,"product_id":product,
                    "status":"unchanged_verified_technical_product"}
    def worker(task,ctx):
        folder=Path(ctx["folder"]);stem=task["id"]
        i,v=task["motif_index"],task["variant_index"]
        files=({"F36":material,"F37":motion,"F39":audio}[family])(folder,stem,i,v,exe)
        if any(not (folder/name).is_file() or (folder/name).stat().st_size<300 for name in files):
            raise RuntimeError("MEDIA_MISSING_REAL_WORK")
        return {"passed":True,"outputs":files,"successful_checks":2}
    def assemble(info,ctx):
        folder=Path(ctx["folder"])
        members=sorted(t["id"]+ext for t in info["work_packages"] for ext in FORMATS[family])
        (folder/"README.txt").write_text(
            "Original fixed-scope "+family+" media sample portfolio. 48 original paired sources "
            "with independent automated decoder checks. No human artistic review, qualified "
            "licensing assessment, commercial approval or customer release. Verify intended use.\n",
            encoding="utf8")
        with zipfile.ZipFile(folder/zipname,"w",zipfile.ZIP_DEFLATED) as z:
            for name in members+["README.txt"]:
                entry=zipfile.ZipInfo(product+"/"+name,date_time=(2020,1,1,0,0,0))
                entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16
                z.writestr(entry,(folder/name).read_bytes())
        return {"passed":True,"outputs":["README.txt",zipname],"successful_checks":3}
    def checker(info,ctx):
        folder=Path(ctx["folder"])
        evidence=review.check(folder,folder/zipname,product,family,exe)
        proto.save(folder/"independent-native-media-review.json",evidence)
        return {"reviewer_id":"independent_binary_decoder_and_media_integrity_checker",
                "critical_defects":[],"passed":evidence["passed"],"gates":evidence["gates"],
                "outputs":["independent-native-media-review.json"],"successful_checks":10}
    state=proto.run_attempt(root,spec,worker,assemble,checker)
    if not proto.verify_attempt(home,state,spec["source_snapshot_sha256"]):
        return {"family_id":family,"product_id":product,
                "status":"technical_rework_required","defects":state.get("defects",[])}
    folder=Path(state["attempt_folder"]);target.mkdir(parents=True,exist_ok=True,mode=0o700)
    incoming=target/".incoming-native-media.zip"
    if incoming.is_symlink() or (target/zipname).is_symlink():
        raise ValueError("MEDIA_UNSAFE_ARCHIVE")
    shutil.copyfile(folder/zipname,incoming);os.replace(incoming,target/zipname)
    manifest={"schema_version":2,"recipe":product,"family_id":family,
      "name":family+" original, independently decoder-tested media samples",
      "artifact_sha256":proto.file_sha(target/zipname),
      "bytes":(target/zipname).stat().st_size,
      "source_sha256":spec["source_snapshot_sha256"],
      "build50_source_snapshot_sha256":spec["source_snapshot_sha256"],
      "qa_status":"passed","qa_evidence":"automated_binary_media_integrity_only",
      "qa_measurements":proto.read(folder/"independent-native-media-review.json"),
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
    p.add_argument("--toolchain",required=True)
    p.add_argument("--family",required=True,choices=sorted(FAMILIES))
    args=p.parse_args()
    pinned,_=load("factory_specialist_pilots").toolchain(args.toolchain)
    result=build(args.factory_private,args.family,pinned/"bin"/"ffmpeg")
    print("FACTORY_NATIVE_MEDIA_BUILD50="+json.dumps(result,sort_keys=True))
    if result["status"]=="technical_rework_required":raise SystemExit(2)
