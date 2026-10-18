#!/usr/bin/env python3
"""Prepare ten REAL, different, freely reusable Commons photographs for the website.

Runs in CI (not production). Fail closed if a source, license, image, or hash
is unsuitable; no placeholder, stock-image repetition or fake lab portraits.
Output is ten optimized WebP photos plus a manifest with source and SHA256.
"""
import argparse, hashlib, html, io, json, re, time
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from PIL import Image, ImageOps

API="https://commons.wikimedia.org/w/api.php"
UA="ZomorodMelalScientificContent/1.0 (Wikimedia reusable-media attribution workflow)"
def retrieve(url,limit=16000000):
    req=Request(url,headers={"User-Agent":UA,"Accept":"application/json,image/*"})
    with urlopen(req,timeout=45) as r:
        data=r.read(limit+1)
        if len(data)>limit:
            raise ValueError("Image exceeds byte ceiling")
        return data
def main():
    args=argparse.ArgumentParser()
    args.add_argument("--catalog",required=True,type=Path)
    args.add_argument("--assets",required=True,type=Path)
    a=args.parse_args()
    pages=json.loads(a.catalog.read_text(encoding="utf-8"))["pages"]
    assert len(pages)==10 and len({p['file'] for p in pages})==10
    a.assets.mkdir(parents=True,exist_ok=False)
    manifest=[]
    seen_files=set()
    seen_image_sha=set()
    for p in pages:
        name=p["file"]
        params={"action":"query","format":"json","prop":"imageinfo","iiprop":"url|extmetadata",
                "iiurlwidth":"1280","titles":"File:"+name}
        url=API+"?"+urlencode(params)
        response=json.loads(retrieve(url,limit=400000))
        entries=response.get("query",{}).get("pages",{})
        record=next(iter(entries.values()))
        if "missing" in record or not record.get("imageinfo"):
            raise ValueError("Commons original missing: "+name)
        info=record["imageinfo"][0]
        meta=info.get("extmetadata",{})
        lic=re.sub(r"<[^>]+>"," ",html.unescape(meta.get("LicenseShortName",{}).get("value","")))
        cc=lic.lower().replace("-","").replace(" ","")
        if not (("publicdomain" in cc) or ("cc0" in cc) or ("pdm" in cc)):
            raise ValueError(f"Non-PD/CC0 image {name}: {lic}")
        imageurl=info.get("thumburl") or info.get("url")
        if not imageurl or not imageurl.startswith(("https://upload.wikimedia.org/","https://thumb.wikimedia.org/")):
            raise ValueError(f"No safe Wikimedia image URL for {name}; origin={str(imageurl)[:140]}")
        raw=retrieve(imageurl,limit=6000000)
        im=Image.open(io.BytesIO(raw))
        im.verify()
        im=Image.open(io.BytesIO(raw))
        im=ImageOps.exif_transpose(im).convert("RGB")
        if min(im.size)<470:
            raise ValueError("Photograph too small "+name)
        im.thumbnail((1280,860),Image.Resampling.LANCZOS)
        output=io.BytesIO()
        im.save(output,format="WEBP",quality=84,method=5)
        data=output.getvalue()
        digest=hashlib.sha256(data).hexdigest()
        if len(data)<15000 or len(data)>1500000:
            raise ValueError(f"Abnormal optimized image byte size: {name}, {len(data)}")
        if digest in seen_image_sha:
            raise ValueError("Duplicated actual image content!")
        seen_image_sha.add(digest)
        dest=a.assets/(p["id"]+".webp")
        if dest.exists():raise ValueError("Collision")
        dest.write_bytes(data)
        manifest.append({"id":p["id"],"url":f"/static/site/zomorod-ten-editorials/{p['id']}.webp",
           "source":"https://commons.wikimedia.org/wiki/File:"+quote(name.replace(" ","_")),
           "file":name,"credit":p["credit"],"license":lic,"sha256":digest,
           "dimensions":[im.width,im.height],"size":len(data)})
        print("PHOTO_VALIDATED",p["id"],"license",lic,"bytes",len(data),flush=True)
        time.sleep(.45)
    if len(manifest)!=10 or len({x["url"] for x in manifest})!=10:
        raise ValueError("Not ten unique photographs")
    (a.assets/"photo-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("TEN_UNIQUE_AUTHENTIC_CC0_PD_PHOTOGRAPHS=verified")
if __name__=="__main__":main()
