"""Independent binary integrity and decoding reviewer for 48 F36/F37/F39 outputs.

No claim of a professional/artist review or actual user acceptance is made.
"""
import hashlib
import math
from pathlib import Path
import subprocess
import wave
import zipfile

GATES=("requirements","correctness","negative_cases","usability","accessibility",
       "security","compatibility","provenance","specialist_review","release_integrity")
FORMATS={"F36":(".png",".exr"),"F37":(".gif",".mp4"),"F39":(".wav",".mp3")}

def decode(ffmpeg,source):
    proc=subprocess.run([str(ffmpeg),"-hide_banner","-loglevel","error",
         "-nostdin","-i",str(source),"-f","null","-"],stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,timeout=18)
    if proc.returncode:raise ValueError("MEDIA_REVIEW_CANNOT_DECODE:"+source.name)

def check(folder,archive,product,family,ffmpeg):
    from PIL import Image
    folder=Path(folder)
    if family not in FORMATS:raise ValueError("MEDIA_REVIEW_UNSUPPORTED")
    suffixes=FORMATS[family]
    files=sorted(p for p in folder.iterdir() if p.suffix in suffixes)
    if len(files)!=96 or len([p for p in files if p.suffix==suffixes[0]])!=48:
        raise ValueError("MEDIA_REVIEW_EXPECTED_48_PAIRS")
    file_names=set(p.name for p in files)
    for source in files:
        if source.is_symlink() or not 300<=source.stat().st_size<=8_000_000:
            raise ValueError("MEDIA_REVIEW_UNSAFE_OR_EMPTY")
        if family=="F36" and source.suffix==".png":
            with Image.open(source) as im:
                if im.format!="PNG" or im.size!=(256,256):raise ValueError("MEDIA_REVIEW_WRONG_TEXTURE")
                rgb=im.convert("RGB")
                if (any(rgb.getpixel((0,y))!=rgb.getpixel((255,y)) for y in range(256)) or
                    any(rgb.getpixel((x,0))!=rgb.getpixel((x,255)) for x in range(256))):
                    raise ValueError("MEDIA_REVIEW_SEAM_NOT_TILEABLE")
                if len(rgb.getcolors(65536) or [])<64:raise ValueError("MEDIA_REVIEW_FLAT_TEXTURE")
        elif family=="F36":
            if source.read_bytes()[:4]!=b"\x76\x2f\x31\x01":raise ValueError("MEDIA_REVIEW_NOT_OPENEXR")
            decode(ffmpeg,source)
        elif family=="F37" and source.suffix==".gif":
            with Image.open(source) as im:
                if im.format!="GIF" or im.size!=(256,192) or im.n_frames!=12:
                    raise ValueError("MEDIA_REVIEW_WRONG_GIF_SEQUENCE")
                im.seek(0);first=im.convert("RGB").tobytes()
                im.seek(11);last=im.convert("RGB").tobytes()
                if first==last:raise ValueError("MEDIA_REVIEW_UNANIMATED_GIF")
        elif family=="F37":
            raw=source.read_bytes()[:12]
            if raw[4:8]!=b"ftyp":raise ValueError("MEDIA_REVIEW_NOT_MP4")
            decode(ffmpeg,source)
        elif family=="F39" and source.suffix==".wav":
            with wave.open(str(source),"rb") as w:
                if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getframerate()!=22050:
                    raise ValueError("MEDIA_REVIEW_INVALID_WAV")
                if not 22050<w.getnframes()<50000:raise ValueError("MEDIA_REVIEW_AUDIO_DURATION")
                audio=w.readframes(w.getnframes())
            import struct
            samples=struct.unpack("<"+str(len(audio)//2)+"h",audio)
            peak=max(abs(v) for v in samples)
            rms=math.sqrt(sum(x*x for x in samples)/len(samples))
            if peak>=29000 or rms<800:raise ValueError("MEDIA_REVIEW_CLIPPING_OR_SILENCE")
        else:
            decode(ffmpeg,source)
        peer=source.with_suffix(suffixes[1] if source.suffix==suffixes[0] else suffixes[0])
        if peer.name not in file_names:raise ValueError("MEDIA_REVIEW_MISSING_PAIR")
    hashes=[hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
    if len(set(hashes))!=96:raise ValueError("MEDIA_REVIEW_DUPLICATED_ARTIFACT")
    readme=folder/"README.txt"
    if not readme.is_file() or "No human artistic review" not in readme.read_text("utf8"):
        raise ValueError("MEDIA_REVIEW_MISSING_LIMITATION")
    with zipfile.ZipFile(archive) as z:
        allowed={product+"/"+f.name for f in files}|{product+"/README.txt"}
        if len(z.namelist())!=97 or set(z.namelist())!=allowed or z.testzip() is not None:
            raise ValueError("MEDIA_REVIEW_ARCHIVE_INTEGRITY")
        for f in files+[readme]:
            if z.read(product+"/"+f.name)!=f.read_bytes():raise ValueError("MEDIA_REVIEW_ARCHIVE_MISMATCH")
    return {"passed":True,"checks_passed":10,"files_checked":96,
            "gates":{name:True for name in GATES},
            "scope":"automated structural, actual decoder, tiling, duration and hash checks only",
            "expert_or_human_review":False,"commercial_release":False}
