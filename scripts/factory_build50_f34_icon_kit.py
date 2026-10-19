#!/usr/bin/env python3
"""Build a genuinely editable 48-icon SVG+PNG kit with 50 source-bound stages.

Each of 48 distinct conceptual/visual tasks creates a separate vector icon and
a locally rendered lossless raster. No API, pre-existing stock art or downloads.
This remains private pending independent visual and commercial acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from html import escape
import shutil
import sys
import zipfile

from PIL import Image,ImageDraw

HERE=Path(__file__).resolve().parent
PRODUCT='fieldwork_ui_48_icons'
CONCEPTS=(
 'sprout','cloud','shield','package','chart','sun','database','flask',
 'globe','heart','gear','compass'
)
VARIANTS=('outline','tile','stamped','dual')
PALETTES=(
 ('#183f37','#69dbc2','#b8fff0'),
 ('#493047','#efb869','#ffe8b2'),
 ('#183747','#8bd4f1','#d3f3ff'),
 ('#4d3046','#f08d9c','#ffe1e8')
)
README='''# Fieldwork — original SVG/PNG icon kit

Original source: original vector primitives and local Pillow raster renderer.
This package was created by the F34 factory producer, not downloaded from an
existing icon library. The icons represent 12 independently described concepts
in four illustrated treatments. Each SVG is editable, self-contained, and
has an accessible title; PNGs are 256x256 true-color images.

Files: 48 SVG, 48 PNG, preview.html, catalog.json, README.md, LICENSE.txt.
Use locally or on your own website; no network connections, scripts, third-party
fonts, external SVG references, advertisements or tracking are required.

Customize SVG fills and strokes to suit your actual brand. Verify contrast and
legibility at your target size. Technical QA is automated and is NOT a human
accessibility certification, legal review, or marketing release.
'''
LICENSE='''Original icon artwork — internal factory authoring terms.

Copyright (c) 2026 Zomorod Melal. The delivered icon geometry was authored
using original vector primitives in the company's factory source.
No third-party downloaded glyphs, brand trademarks, fonts or raster
illustrations are included. This archive is a PRIVATE internal QA artifact,
not a public license offer. Commercial redistribution permissions, warranty,
final pricing and sale conditions require separate owner acceptance.
'''
def load(name,filename):
    path=HERE/filename
    if not path.is_file() or path.is_symlink():raise RuntimeError('F34_MODULE_INVALID')
    spec=importlib.util.spec_from_file_location(name,str(path))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

# Each subject uses its own hand-authored geometry and closed/open semantic shapes.
def geometry(concept):
    c={
     'sprout':[('line',[(32,52),(32,24)],4),('line',[(32,34),(20,24)],3),
       ('poly',[(32,27),(24,17),(13,15),(16,27),(27,32)],2),
       ('poly',[(31,32),(39,17),(53,13),(48,27),(34,37)],2)],
     'cloud':[('line',[(18,45),(48,45)],4),('circle',(21,33,12),3),
       ('circle',(34,27,16),3),('circle',(47,36,10),3)],
     'shield':[('poly',[(32,9),(51,17),(49,38),(43,49),(32,57),(21,49),(15,38),(13,17)],3),
       ('line',[(23,33),(29,40),(43,25)],4)],
     'package':[('poly',[(12,20),(32,10),(52,20),(52,45),(32,55),(12,45)],3),
       ('line',[(12,20),(32,31),(52,20)],3),('line',[(32,31),(32,55)],3),
       ('line',[(22,15),(43,26),(43,34)],2)],
     'chart':[('line',[(11,52),(53,52)],4),('rect',(15,33,22,52),3),
       ('rect',(28,24,35,52),3),('rect',(41,14,48,52),3)],
     'sun':[('circle',(32,32,11),3),('line',[(32,7),(32,16)],3),
       ('line',[(32,48),(32,57)],3),('line',[(7,32),(16,32)],3),
       ('line',[(48,32),(57,32)],3),('line',[(14,14),(20,20)],3),
       ('line',[(44,44),(50,50)],3),('line',[(14,50),(20,44)],3),('line',[(44,20),(50,14)],3)],
     'database':[('ellipse',(12,13,52,27),3),('line',[(12,20),(12,45)],3),
       ('line',[(52,20),(52,45)],3),('ellipse',(12,38,52,52),3),
       ('line',[(12,31),(21,36),(32,38),(43,36),(52,31)],3)],
     'flask':[('line',[(26,9),(38,9)],4),('line',[(28,9),(28,25),(14,48),(19,53),(45,53),(50,48),(36,25),(36,9)],3),
       ('line',[(20,42),(44,42)],3),('circle',(28,47,2),2)],
     'globe':[('circle',(32,32,23),3),('line',[(9,32),(55,32)],3),
       ('line',[(32,9),(32,55)],3),('ellipse',(20,9,44,55),3),
       ('line',[(13,22),(51,22)],2),('line',[(13,42),(51,42)],2)],
     'heart':[('poly',[(32,53),(15,38),(10,28),(13,18),(22,14),(32,22),(42,14),(51,18),(54,28),(49,38)],3),
       ('line',[(20,30),(27,30),(31,25),(35,37),(39,32),(46,32)],2)],
     'gear':[('poly',[(32,8),(38,13),(45,11),(49,17),(47,24),(55,29),(55,36),(47,40),(49,48),(43,53),(37,50),(32,57),(26,51),(19,53),(15,47),(18,40),(9,36),(9,29),(17,24),(15,17),(21,11),(27,13)],3),
       ('circle',(32,32,10),3)],
     'compass':[('circle',(32,32,23),3),
       ('poly',[(32,12),(39,31),(32,52),(25,32)],3),
       ('line',[(14,32),(22,32)],3),('line',[(42,32),(50,32)],3),
       ('circle',(32,32,3),2)]
    }
    if concept not in c:raise ValueError('F34_UNRECOGNIZED_CONCEPT')
    return c[concept]

def rgb(s):
    return tuple(int(s[i:i+2],16) for i in (1,3,5))

def make_icon(concept,variant):
    if concept not in CONCEPTS or variant not in VARIANTS:raise ValueError('F34_INVALID_ICON_ID')
    index=VARIANTS.index(variant);bg,stroke,light=PALETTES[index]
    title=concept.title()+' — '+variant+' icon'
    shapes=geometry(concept)
    bg_shapes=[]
    if variant=='tile':
        bg_shapes=[('rect',(3,3,61,61),1)]
    elif variant=='stamped':
        bg_shapes=[('circle',(32,32,29),1)]
    elif variant=='dual':
        bg_shapes=[('poly',[(3,13),(13,3),(51,3),(61,13),(61,51),(51,61),(13,61),(3,51)],1)]
    commands=[]
    for kind,coords,weight in shapes:
        if kind=='line':commands.append('<polyline points="'+ ' '.join('%s,%s'%p for p in coords)+'" fill="none" stroke="'+stroke+'" stroke-width="'+str(weight)+'" stroke-linecap="round" stroke-linejoin="round"/>')
        elif kind=='poly':commands.append('<polygon points="'+ ' '.join('%s,%s'%p for p in coords)+'" fill="none" stroke="'+stroke+'" stroke-width="'+str(weight)+'" stroke-linejoin="round"/>')
        elif kind=='circle':
            x,y,r=coords;commands.append('<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="%s"/>'%(x,y,r,stroke,weight))
        elif kind=='rect':
            a,b,c,d=coords;commands.append('<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="%s" stroke-width="%s"/>'%(a,b,c-a,d-b,stroke,weight))
        elif kind=='ellipse':
            a,b,c,d=coords;commands.append('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="none" stroke="%s" stroke-width="%s"/>'%((a+c)//2,(b+d)//2,(c-a)//2,(d-b)//2,stroke,weight))
    if variant=='dual':
        commands.append('<circle cx="51" cy="13" r="5" fill="'+light+'"/>')
    elif variant=='stamped':
        commands.append('<circle cx="51" cy="51" r="3" fill="'+light+'"/>')
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-labelledby="icon-title"><title id="icon-title">'+escape(title)+'</title>'
    if variant!='outline':
        if variant=='stamped':svg+='<circle cx="32" cy="32" r="29" fill="'+bg+'"/>'
        elif variant=='tile':svg+='<rect x="3" y="3" width="58" height="58" rx="12" fill="'+bg+'"/>'
        else:svg+='<polygon points="3,13 13,3 51,3 61,13 61,51 51,61 13,61 3,51" fill="'+bg+'"/>'
    svg+=''.join(commands)+'</svg>\n'
    image=Image.new('RGBA',(256,256),(0,0,0,0));draw=ImageDraw.Draw(image)
    k=4
    if variant=='tile':draw.rounded_rectangle((12,12,244,244),radius=48,fill=rgb(bg))
    elif variant=='stamped':draw.ellipse((12,12,244,244),fill=rgb(bg))
    elif variant=='dual':draw.polygon([(12,52),(52,12),(204,12),(244,52),(244,204),(204,244),(52,244),(12,204)],fill=rgb(bg))
    for kind,coords,weight in shapes:
        ink=rgb(stroke);w=weight*k
        if kind in ('line','poly'):
            pts=[(x*k,y*k) for x,y in coords]
            draw.line(pts+([pts[0]] if kind=='poly' else []),fill=ink,width=w,joint='curve')
            for x,y in pts:draw.ellipse((x-w/2,y-w/2,x+w/2,y+w/2),fill=ink)
        elif kind=='circle':
            x,y,r=coords;draw.ellipse(((x-r)*k,(y-r)*k,(x+r)*k,(y+r)*k),outline=ink,width=w)
        elif kind=='rect':
            a,b,c,d=coords;draw.rectangle((a*k,b*k,c*k,d*k),outline=ink,width=w)
        else:
            a,b,c,d=coords;draw.ellipse((a*k,b*k,c*k,d*k),outline=ink,width=w)
    if variant=='dual':draw.ellipse((184,32,224,72),fill=rgb(light))
    if variant=='stamped':draw.ellipse((192,192,216,216),fill=rgb(light))
    return svg,image

def spec(proto):
    data={'producer':proto.file_sha(__file__),
      'reviewer':proto.file_sha(HERE/'factory_f34_independent_icon_review.py'),
      'protocol':proto.file_sha(HERE/'factory_build_50.py'),
      'family':'F34','product':PRODUCT}
    tasks=[]
    for concept in CONCEPTS:
        for variant in VARIANTS:
            tasks.append({'id':'draw_'+concept+'_'+variant,
              'instruction':'Create an original '+concept+' concept using its distinct pictographic anatomy and the '+variant+' treatment; export editable SVG and pixel-tested 256px PNG with matching safe local coordinates.',
              'acceptance':['Create a distinct SVG with semantic title and no external dependencies.',
                            'Create a valid 256-by-256 raster with actual opaque pictographic pixels.']})
    return {'schema':proto.SCHEMA,'product_id':PRODUCT,'family_id':'F34',
        'producer_id':'saeit_48_icon_vector_raster_author','source_snapshot_sha256':proto.digest(data),
        'work_packages':tasks}

def worker(task,context):
    parts=task['id'].split('_');concept=parts[1];variant=parts[2]
    folder=Path(context['folder'])
    svg,image=make_icon(concept,variant)
    svg_path=folder/(concept+'_'+variant+'.svg')
    png_path=folder/(concept+'_'+variant+'.png')
    svg_path.write_text(svg,encoding='utf8')
    image.save(str(png_path),format='PNG',optimize=True)
    with Image.open(png_path) as check:
        check.load()
        if check.size!=(256,256) or check.getbbox() is None:raise ValueError('F34_NO_REAL_ICON')
    if '<title id="icon-title">' not in svg:raise ValueError('F34_INACCESSIBLE_SVG')
    return {'passed':True,'outputs':[svg_path.name,png_path.name],'successful_checks':2}

def assembler(plan,context):
    folder=Path(context['folder'])
    names=[]
    catalog=[]
    for concept in CONCEPTS:
        for variant in VARIANTS:
            key=concept+'_'+variant
            a=key+'.svg';b=key+'.png'
            for n in (a,b):
                if not (folder/n).is_file():raise ValueError('F34_MISSING_ICON_STAGE')
                names.append(n)
            catalog.append({'id':key,'concept':concept,'treatment':variant,'vector':a,'raster':b})
    assets={'README.md':README,'LICENSE.txt':LICENSE,
       'catalog.json':json.dumps({'schema':'saeit.factory.f34-icon-catalog.v1','icons':catalog},ensure_ascii=False,indent=2)}
    links=''.join('<li><span>'+escape(x['concept'].title())+' / '+escape(x['treatment'])+'</span><img src="'+x['raster']+'" width="64" height="64" alt="'+escape(x['concept'])+' '+escape(x['treatment'])+' icon"><a href="'+x['vector']+'">SVG</a></li>' for x in catalog)
    assets['preview.html']='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fieldwork original 48 SVG/PNG icons</title><style>body{font:16px system-ui;background:#edf2f2;color:#172b32;margin:2rem}ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;list-style:none;padding:0}li{display:grid;gap:.7rem;background:white;border-radius:12px;padding:1rem}a{color:#176456}img{object-fit:contain}</style></head><body><main><h1>Fieldwork — 48 original icons</h1><p>12 pictograms × 4 drawing treatments. Editable SVG and local PNG files; no external services.</p><ul>'+links+'</ul></main></body></html>'
    for name,data in assets.items():(folder/name).write_text(data,encoding='utf8')
    names+=list(assets)
    archive=folder/(PRODUCT+'-internal-qa.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted(names):
            info=zipfile.ZipInfo(PRODUCT+'/'+name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,(folder/name).read_bytes())
    return {'passed':True,'outputs':list(assets)+[archive.name],'successful_checks':5}

def build(root):
    proto=load('f34_real_protocol','factory_build_50.py')
    checker=load('f34_separate_icon_reviewer','factory_f34_independent_icon_review.py')
    root=Path(root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():raise RuntimeError('F34_PRIVATE_FACTORY_ROOT_INVALID')
    recipe=spec(proto)
    home=root/'build-50'/PRODUCT
    target=root/'digital-products'/PRODUCT
    if home.is_symlink() or target.is_symlink():raise RuntimeError('F34_UNSAFE_PRODUCT_FOLDER')
    def reviewer(plan,ctx):
        folder=Path(ctx['folder'])
        results=checker.review(folder,PRODUCT)
        if not all(results['gates'].values()):raise ValueError('F34_QUALITY_REVIEW_INCOMPLETE')
        q=folder/'independent-icon-review.json'
        q.write_text(json.dumps(results,indent=2,sort_keys=True))
        return {'passed':True,'reviewer_id':'saeit_independent_automated_icon_technical_validator',
            'critical_defects':[],'gates':results['gates'],
            'outputs':[q.name],'successful_checks':10}
    if (home/'state.json').is_file() and (target/'manufacturing_manifest.json').is_file():
        old=proto.read(home/'state.json')
        if old.get('source_snapshot_sha256')==recipe['source_snapshot_sha256'] and proto.verify_attempt(home,old,recipe['source_snapshot_sha256']):
            saved=proto.read(target/'manufacturing_manifest.json')
            arc=target/(PRODUCT+'-internal-qa.zip')
            if arc.is_file() and proto.file_sha(arc)==saved.get('artifact_sha256'):
                return {'status':'unchanged_verified_technical_product','completed_stages':50,
                        'commercial_release':False}
    state=proto.run_attempt(root,recipe,worker,assembler,reviewer)
    if state.get('status')!='awaiting_owner_acceptance' or not proto.verify_attempt(home,state,recipe['source_snapshot_sha256']):
        return {'status':'technical_rework_required','completed_stages':state.get('completed_stages',0),
            'defects':state.get('defects',[]),'commercial_release':False}
    folder=Path(state['attempt_folder'])
    archive=folder/(PRODUCT+'-internal-qa.zip')
    if target.is_symlink():raise RuntimeError('F34_UNSAFE_TARGET')
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=target/'.incoming-f34.zip'
    shutil.copyfile(archive,temp)
    os.replace(temp,target/archive.name)
    names=[x.name for x in folder.iterdir() if x.suffix in ('.svg','.png')]
    names+=['README.md','LICENSE.txt','catalog.json','preview.html']
    manifest={
       'schema_version':2,'recipe':PRODUCT,
       'name':'Fieldwork — 48 original SVG and PNG interface icons','family_id':'F34',
       'source_sha256':proto.digest({n:proto.file_sha(folder/n) for n in names}),
       'build50_source_snapshot_sha256':recipe['source_snapshot_sha256'],
       'artifact_sha256':proto.file_sha(target/archive.name),'files':names,
       'qa_status':'passed','qa_evidence':'unit_tests_passed',
       'qa_measurements':proto.read(folder/'independent-icon-review.json'),
       'commercial_status':'private_internal_qa_pass_not_published',
       'public_listing_enabled':False,'customer_order_required':False,
       'owner_publication_approval':False,'independent_human_review':False}
    proto.save(target/'manufacturing_manifest.json',manifest)
    return {'status':'technical_50_stage_build_completed','product_id':PRODUCT,
       'family_id':'F34','completed_stages':50,'icons':48,'deliverables':100,
       'bytes':(target/archive.name).stat().st_size,
       'sha256':manifest['artifact_sha256'],'commercial_release':False}

if __name__=='__main__':
    arg=argparse.ArgumentParser();arg.add_argument('--factory-private',required=True)
    a=arg.parse_args()
    outcome=build(a.factory_private)
    print('F34_BUILD50_REAL_ICON_PRODUCT='+json.dumps(outcome,sort_keys=True))
    if outcome['status']=='technical_rework_required':sys.exit(2)
