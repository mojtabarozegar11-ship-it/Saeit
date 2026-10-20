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
    source=Path(source)
    explicit=["-f","image2","-c:v","exr"] if source.suffix==".exr" else []
    proc=subprocess.run([str(ffmpeg),"-hide_banner","-loglevel","error",
         "-nostdin"]+explicit+["-i",str(source),"-f","null","-"],stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,timeout=18)
    if proc.returncode:raise ValueError("MEDIA_REVIEW_CANNOT_DECODE:"+source.name)

def check_exr(source,png):
    """Independent OpenEXR scanline parser and pixel-by-pixel consistency checks."""
    import struct
    from PIL import Image
    data=Path(source).read_bytes()
    if len(data)<100 or data[:8]!=struct.pack("<II",20000630,2):
        raise ValueError("MEDIA_REVIEW_EXR_MAGIC_OR_VERSION")
    cursor=8;attributes={}
    while True:
        end=data.find(b"\x00",cursor)
        if end<0:raise ValueError("MEDIA_REVIEW_EXR_MISSING_HEADER_END")
        if end==cursor:
            cursor+=1
            break
        name=data[cursor:end].decode("ascii")
        cursor=end+1
        end=data.find(b"\x00",cursor)
        if end<0:raise ValueError("MEDIA_REVIEW_EXR_BAD_TYPE")
        kind=data[cursor:end].decode("ascii")
        cursor=end+1
        if cursor+4>len(data):raise ValueError("MEDIA_REVIEW_EXR_BAD_ATTRIBUTE")
        size=struct.unpack_from("<I",data,cursor)[0];cursor+=4
        if size>4096 or cursor+size>len(data) or name in attributes:
            raise ValueError("MEDIA_REVIEW_EXR_BAD_ATTRIBUTE_SIZE")
        attributes[name]=(kind,data[cursor:cursor+size]);cursor+=size
    expected={
      "channels":"chlist","compression":"compression","dataWindow":"box2i",
      "displayWindow":"box2i","lineOrder":"lineOrder",
      "pixelAspectRatio":"float","screenWindowCenter":"v2f","screenWindowWidth":"float"}
    if {name:kind for name,(kind,body) in attributes.items()}!=expected:
        raise ValueError("MEDIA_REVIEW_EXR_HEADER_FIELDS")
    w=h=256
    ch=b"".join(name.encode("ascii")+b"\x00"+struct.pack("<iB3xii",2,0,1,1)
                for name in "BGR")+b"\x00"
    if (attributes["channels"][1]!=ch or
        attributes["compression"][1]!=b"\x00" or
        attributes["dataWindow"][1]!=struct.pack("<iiii",0,0,w-1,h-1) or
        attributes["displayWindow"][1]!=struct.pack("<iiii",0,0,w-1,h-1) or
        attributes["lineOrder"][1]!=b"\x00"):
        raise ValueError("MEDIA_REVIEW_EXR_WRONG_LAYOUT")
    table_end=cursor+h*8
    block_length=8+w*3*4
    if len(data)!=table_end+h*block_length:
        raise ValueError("MEDIA_REVIEW_EXR_LENGTH")
    with Image.open(png) as image:
        if image.size!=(w,h):raise ValueError("MEDIA_REVIEW_EXR_SOURCE_SIZE")
        rgb=image.convert("RGB")
        for y in range(h):
            offset=struct.unpack_from("<Q",data,cursor+y*8)[0]
            if offset!=table_end+y*block_length:
                raise ValueError("MEDIA_REVIEW_EXR_OFFSET_TABLE")
            line,size=struct.unpack_from("<ii",data,offset)
            if line!=y or size!=w*3*4:raise ValueError("MEDIA_REVIEW_EXR_SCANLINE")
            # Inspect channel planes at every tenth row and selected columns.
            if y%17==0 or y==h-1:
                for x in (0,31,127,191,255):
                    pixel=rgb.getpixel((x,y))
                    for channel,expected_value in enumerate((pixel[2],pixel[1],pixel[0])):
                        got=struct.unpack_from("<f",data,offset+8+
                            (channel*w+x)*4)[0]
                        if abs(got-expected_value/255.0)>1e-6:
                            raise ValueError("MEDIA_REVIEW_EXR_PIXEL_MISMATCH")

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
            check_exr(source,source.with_suffix(".png"))
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
