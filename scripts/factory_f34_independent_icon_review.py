#!/usr/bin/env python3
"""Separate automated technical review for 48 distinct SVG/PNG original icons.

Never certifies human-level visual quality, originality under copyright law,
or commercial suitability; it rejects malformed, duplicated and offsite assets.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
from PIL import Image
from io import BytesIO

CONCEPTS=('sprout','cloud','shield','package','chart','sun','database',
          'flask','globe','heart','gear','compass')
VARIANTS=('outline','tile','stamped','dual')
GATES=('requirements','correctness','negative_cases','usability','accessibility',
       'security','compatibility','provenance','specialist_review','release_integrity')
PNG_SIGNATURE=b'\x89PNG\r\n\x1a\n'
def review(folder,product):
    folder=Path(folder)
    labels=[a+'_'+b for a in CONCEPTS for b in VARIANTS]
    files=[label+suffix for label in labels for suffix in ('.svg','.png')]
    others=['README.md','LICENSE.txt','catalog.json','preview.html']
    full=files+others
    for name in full:
        p=folder/name
        if p.is_symlink() or not p.is_file() or not p.stat().st_size:
            raise ValueError('F34_MISSING_REAL_ASSET:'+name)
    catalog=json.loads((folder/'catalog.json').read_text('utf8'))
    records=catalog.get('icons')
    if not isinstance(records,list) or len(records)!=48:raise ValueError('F34_BAD_CATALOG')
    id_list=[x.get('id') for x in records if isinstance(x,dict)]
    requirements=len(id_list)==48 and set(id_list)==set(labels) and len(files)==96
    src_hashes=set();raster_hashes=set();valid_svg=0;valid_png=0
    alpha_count=0
    no_unsafe=True
    title_count=0
    try:
        for label in labels:
            svg=(folder/(label+'.svg')).read_text('utf8')
            forbidden=('<script','<foreignobject','javascript:','onload=','onclick=',
                       'http:','https:','xlink:','data:','@import','<image','<use')
            checked=svg.lower().replace('xmlns="http://www.w3.org/2000/svg"','',1)
            if any(bad in checked for bad in forbidden):no_unsafe=False
            root=ET.fromstring(svg)
            tags=[elem.tag.rsplit('}',1)[-1] for elem in root.iter()]
            if set(tags)-{'svg','title','rect','polygon','polyline','circle','ellipse'}:
                no_unsafe=False
            if root.get('viewBox')=='0 0 64 64' and root.get('role')=='img':
                valid_svg+=1
            if len([x for x in root.iter() if x.tag.endswith('title') and x.text and label.split('_')[0].lower() in x.text.lower()])==1:
                title_count+=1
            src_hashes.add(hashlib.sha256(svg.encode()).hexdigest())
            data=(folder/(label+'.png')).read_bytes()
            if not data.startswith(PNG_SIGNATURE):raise ValueError('F34_BAD_PNG_SIGNATURE')
            with Image.open(BytesIO(data)) as im:
                im.load()
                if im.format=='PNG' and im.mode=='RGBA' and im.size==(256,256):valid_png+=1
                if im.getbbox() and im.getbbox()[2]-im.getbbox()[0]>40:alpha_count+=1
            raster_hashes.add(hashlib.sha256(data).hexdigest())
    except (ET.ParseError,OSError,ValueError) as error:
        raise ValueError('F34_INVALID_VECTOR_OR_RASTER:'+type(error).__name__)
    preview=(folder/'preview.html').read_text('utf8')
    readme=(folder/'README.md').read_text('utf8')
    terms=(folder/'LICENSE.txt').read_text('utf8')
    links_correct=all((label+'.svg' in preview and label+'.png' in preview) for label in labels)
    negative_cases=no_unsafe and not any(word in preview.lower() for word in ('<script','<iframe','<form','http:','https:','onload='))
    usability=links_correct and '<main>' in preview and '<h1>' in preview and len(readme)>450
    accessibility=title_count==48 and all('alt=' in line for line in preview.split('<img')[1:])
    security=negative_cases and all('href="' + label+'.svg"' in preview for label in labels)
    compatibility=valid_svg==valid_png==48 and alpha_count==48 and 'viewport' in preview
    provenance=('Original source' in readme and 'Zomorod Melal' in terms and
                 'PRIVATE internal QA' in terms and len(terms)>200)
    # Independent checks reject duplicate artwork across all 48 work packages.
    specialist_review=(len(src_hashes)==48 and len(raster_hashes)==48 and
                       len({x.get('concept') for x in records if isinstance(x,dict)})==12)
    archive=folder/(product+'-internal-qa.zip')
    if not archive.is_file() or archive.is_symlink():raise ValueError('F34_ARCHIVE_MISSING')
    with zipfile.ZipFile(archive) as z:
        present=z.namelist()
        expected=[product+'/'+x for x in full]
        release_integrity=(sorted(present)==sorted(expected) and z.testzip() is None)
        if release_integrity:
            for item in full:
                if z.read(product+'/'+item)!=(folder/item).read_bytes():
                    release_integrity=False;break
    checks=dict(zip(GATES,(requirements,valid_svg==valid_png==48,negative_cases,
                   usability,accessibility,security,compatibility,provenance,
                   specialist_review,release_integrity)))
    if not all(checks.values()):
        raise ValueError('F34_INDEPENDENT_GATES_FAILED:'+','.join(k for k,v in checks.items() if not v))
    return {'gates':checks,'critical_defects':[],
        'review_kind':'separate_automated_technical_verification',
        'human_visual_review':False,'legal_review':False,'commercial_license_approved':False,
        'original_pictogram_concepts':12,'distinct_vector_raster_pairs':48,
        'validated_archive_members':len(full),
        'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
