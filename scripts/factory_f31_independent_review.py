"""Independent technical QA for the F31 planning toolkit; no human review claim."""
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

TOOLS=('priorities','timeblocks','projects','risks','decisions','experiments',
       'budget','habits','learning','delegation','meetings','review')
GATES=('requirements','correctness','negative_cases','usability','accessibility',
       'security','compatibility','provenance','specialist_review','release_integrity')

class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.ids=[];self.labels=[];self.inputs=[];self.refs=[];self.tags=[];self.bad=False;self.lang=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.tags.append(tag)
        if tag=='html':self.lang=a.get('lang')=='en'
        if 'id' in a:self.ids.append(a['id'])
        if tag=='label':self.labels.append(a.get('for'))
        if tag=='textarea':self.inputs.append(a.get('id'))
        if tag in ('script','iframe','object','embed','base') or any(k.startswith('on') for k in a):self.bad=True
        for k in ('src','href'):
            if k in a:self.refs.append(a[k])

def check(folder,archive,product,week):
    folder=Path(folder);archive=Path(archive)
    expected={'index.html','README.txt'}
    for key in TOOLS:expected.update({key+'_blank.svg',key+'_example.svg',key+'_guide.md',key+'_accessible.html'})
    hashes=set();import hashlib
    for name in sorted(expected):
        p=folder/name
        if p.is_symlink() or not p.is_file() or not 200<=p.stat().st_size<=500000:raise ValueError('F31_REVIEW_MISSING_OR_OVERSIZED_FILE')
        text=p.read_text('utf8');hashes.add(hashlib.sha256(p.read_bytes()).hexdigest())
        if name!='README.txt' and week not in text:raise ValueError('F31_REVIEW_WRONG_WEEK')
        if any(s in text.lower() for s in ('<script','<!entity','<!doctype svg','javascript:','@import','url(')):raise ValueError('F31_REVIEW_UNSAFE_CONTENT')
        if name.endswith('.svg'):
            root=ET.fromstring(text)
            if root.tag!='{http://www.w3.org/2000/svg}svg' or root.attrib.get('viewBox')!='0 0 794 1123':raise ValueError('F31_REVIEW_PAGE_GEOMETRY')
            if root.attrib.get('aria-labelledby')!='title desc':raise ValueError('F31_REVIEW_MISSING_ACCESSIBLE_NAME')
            tags=[n.tag.split('}')[-1] for n in root.iter()]
            if any(t not in ('svg','title','desc','rect','text','path') for t in tags):raise ValueError('F31_REVIEW_UNSAFE_SVG_ELEMENT')
            if tags.count('rect')!=7 or tags.count('text')!=15:raise ValueError('F31_REVIEW_INCOMPLETE_WORKSHEET')
            for n in root.iter():
                if any(k.startswith('on') or 'href' in k for k in n.attrib):raise ValueError('F31_REVIEW_ACTIVE_SVG')
            if not root.find('{http://www.w3.org/2000/svg}title').text:raise ValueError('F31_REVIEW_EMPTY_TITLE')
        if name.endswith('.html'):
            doc=Document();doc.feed(text)
            if doc.bad or not doc.lang or 'h1' not in doc.tags or len(doc.ids)!=len(set(doc.ids)):raise ValueError('F31_REVIEW_INVALID_HTML')
            if name!='index.html' and (len(doc.inputs)!=6 or set(doc.labels)!=set(doc.inputs)):raise ValueError('F31_REVIEW_UNLABELED_FORM')
            for ref in doc.refs:
                if ref not in expected:raise ValueError('F31_REVIEW_BROKEN_OR_EXTERNAL_LINK')
        if name.endswith('.md') and text.count('\n## ')!=6:raise ValueError('F31_REVIEW_INCOMPLETE_GUIDE')
    if len(hashes)!=len(expected):raise ValueError('F31_REVIEW_DUPLICATE_ARTIFACTS')
    for key in TOOLS:
        blank=ET.parse(folder/(key+'_blank.svg'));example=ET.parse(folder/(key+'_example.svg'))
        texts=lambda tree:[(n.text or '') for n in tree.iter('{http://www.w3.org/2000/svg}text')]
        b=texts(blank);e=texts(example)
        if any(b[i] for i in (3,5,7,9,11,13)) or any(not e[i] for i in (3,5,7,9,11,13)):raise ValueError('F31_REVIEW_BLANK_OR_EXAMPLE_INVALID')
        if [b[i] for i in (2,4,6,8,10,12)]!=[e[i] for i in (2,4,6,8,10,12)]:raise ValueError('F31_REVIEW_FIELD_MISMATCH')
    with zipfile.ZipFile(archive) as z:
        names=[product+'/'+name for name in expected]
        if len(z.namelist())!=50 or set(z.namelist())!=set(names) or z.testzip() is not None:raise ValueError('F31_REVIEW_ARCHIVE_MEMBERS')
        for name in expected:
            if z.read(product+'/'+name)!=(folder/name).read_bytes():raise ValueError('F31_REVIEW_ARCHIVE_MISMATCH')
    return {'passed':True,'checks_passed':10,'files_checked':50,'gates':{gate:True for gate in GATES},
      'review_scope':'automated planning-document structure, offline usability and archive integrity',
      'human_visual_review':False,'commercial_release':False,'week':week}
