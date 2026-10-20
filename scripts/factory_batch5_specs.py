"""Original stdlib product specifications for five distinct engineering families.

No remote services, invented research, personal records or API dependencies.
"""
FAMILIES=('F20','F21','F22','F25','F28')
SLUGS={'F20':'validation_plugins','F21':'developer_text_tools','F22':'record_workflows','F25':'synthetic_edge_fixtures','F28':'engineering_calculators'}
# Every tool has a distinct implementation, demonstration input and expected result.
SPECS={
'F20':[
 ('email','Email syntax guard',"isinstance(v,str) and len(v)<=254 and len(v.split('@')[0])<=64 and bool(re.fullmatch(r'[A-Za-z0-9_%+-]+(?:\\.[A-Za-z0-9_%+-]+)*@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\.)+[A-Za-z]{2,63}',v))",'a@example.org',True),
 ('identifier','Portable identifier',"isinstance(v,str) and bool(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',v))",'valid_name',True),
 ('positive_integer','Positive integer excluding bool',"type(v) is int and v>0",4,True),
 ('finite_number','Finite numeric value excluding bool',"type(v) in (int,float) and math.isfinite(v)",3.5,True),
 ('iso_date','Gregorian ISO date',"isinstance(v,str) and bool(re.fullmatch(r'\\d{4}-\\d{2}-\\d{2}',v)) and date.fromisoformat(v).isoformat()==v",'2026-10-20',True),
 ('sha256','Lowercase SHA256 hex syntax',"isinstance(v,str) and bool(re.fullmatch(r'[a-f0-9]{64}',v))",'a'*64,True),
 ('currency_code','Supported accounting currency code',"isinstance(v,str) and v in ('USD','EUR','GBP','CAD','AUD','JPY','CHF','AED')",'USD',True),
 ('nonempty_text','Nonblank bounded text',"isinstance(v,str) and 1<=len(v.strip())<=1000",' note ',True),
 ('string_list','Unique nonblank string list',"isinstance(v,list) and len(v)>0 and all(isinstance(x,str) and x.strip() for x in v) and len(v)==len(set(v))",['one','two'],True),
 ('record_id','Positive record identifier',"isinstance(v,dict) and type(v.get('id')) is int and v['id']>0",{'id':8},True),
 ('unit_interval','Inclusive unit interval',"type(v) in (int,float) and math.isfinite(v) and 0<=v<=1",0.5,True),
 ('safe_filename','Portable leaf filename',"isinstance(v,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',v)) and not v.endswith('.') and v.split('.')[0].upper() not in ('CON','PRN','AUX','NUL','COM1','COM2','COM3','COM4','COM5','COM6','COM7','COM8','COM9','LPT1','LPT2','LPT3','LPT4','LPT5','LPT6','LPT7','LPT8','LPT9')",'report.json',True),
],
'F21':[
 ('json_pretty','Canonical readable JSON',"json.dumps(json.loads(v),sort_keys=True,indent=2,ensure_ascii=False)",'{"b":2,"a":1}','{\n  "a": 1,\n  "b": 2\n}'),
 ('json_compact','Compact canonical JSON',"json.dumps(json.loads(v),sort_keys=True,separators=(',',':'),ensure_ascii=False)",'{"b": 2, "a": 1}','{"a":1,"b":2}'),
 ('text_sha256','UTF8 SHA256 digest',"hashlib.sha256(v.encode('utf8')).hexdigest()",'abc','ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'),
 ('base64_encode','UTF8 Base64 encoder',"base64.b64encode(v.encode('utf8')).decode('ascii')",'hello','aGVsbG8='),
 ('base64_decode','Strict UTF8 Base64 decoder',"base64.b64decode(v,validate=True).decode('utf8')",'aGVsbG8=','hello'),
 ('slug','ASCII slug builder',"re.sub(r'[^a-z0-9]+','-',v.lower()).strip('-')",'Hello, World!','hello-world'),
 ('unique_lines','Stable unique text lines',"'\\n'.join(dict.fromkeys(v.splitlines()))",'b\na\nb','b\na'),
 ('sorted_lines','Sorted case-sensitive text lines',"'\\n'.join(sorted(v.splitlines()))",'b\na','a\nb'),
 ('word_count','Whitespace token counter',"len(v.split())",'one  two\nthree',3),
 ('utf8_bytes','UTF8 encoded byte count',"len(v.encode('utf8'))",'café',5),
 ('html_escape','HTML text escaper',"html.escape(v,quote=True)",'<a>','&lt;a&gt;'),
 ('line_numbers','Number text lines',"'\\n'.join(str(i)+': '+s for i,s in enumerate(v.splitlines(),1))",'x\ny','1: x\n2: y'),
],
'F22':[
 ('active_records','Select explicitly active records',"[r for r in v if r.get('active') is True]",[{'id':1,'active':True},{'id':2,'active':False}],[{'id':1,'active':True}]),
 ('drop_empty','Drop empty-valued fields',"[{k:x for k,x in r.items() if x is not None and x!=''} for r in v]",[{'id':1,'name':'','n':0}],[{'id':1,'n':0}]),
 ('normalize_email','Trim and lowercase email fields',"[dict(r,email=r.get('email','').strip().lower()) for r in v]",[{'email':' A@EXAMPLE.ORG '}],[{'email':'a@example.org'}]),
 ('trim_names','Trim name fields',"[dict(r,name=r.get('name','').strip()) for r in v]",[{'name':' Ada '}],[{'name':'Ada'}]),
 ('sort_ids','Sort numeric identifiers',"sorted(v,key=lambda r:r['id'])",[{'id':2},{'id':1}],[{'id':1},{'id':2}]),
 ('unique_ids','Keep first record per identifier',"list({r['id']:next(x for x in v if x['id']==r['id']) for r in v}.values())",[{'id':1,'n':2},{'id':1,'n':3}],[{'id':1,'n':2}]),
 ('sum_amounts','Sum integer minor-unit amounts',"sum(r['amount_cents'] for r in v)",[{'amount_cents':10},{'amount_cents':20}],30),
 ('count_status','Count records per status',"{s:sum(r.get('status','unknown')==s for r in v) for s in sorted(set(r.get('status','unknown') for r in v))}",[{'status':'new'},{'status':'new'}],{'new':2}),
 ('redact_email','Remove email fields',"[{k:x for k,x in r.items() if k!='email'} for r in v]",[{'id':1,'email':'a@example.org'}],[{'id':1}]),
 ('rename_identifier','Rename id to record_id',"[dict({k:x for k,x in r.items() if k!='id'},record_id=r['id']) for r in v]",[{'id':2,'name':'Ada'}],[{'record_id':2,'name':'Ada'}]),
 ('flatten_tags','Produce sorted unique tags',"sorted(set(t for r in v for t in r.get('tags',[])))",[{'tags':['b','a']},{'tags':['a']}],['a','b']),
 ('public_fields','Select declared public fields',"[{k:r[k] for k in ('id','name','status') if k in r} for r in v]",[{'id':1,'name':'Ada','secret':'x'}],[{'id':1,'name':'Ada'}]),
],
'F28':[
 ('celsius_fahrenheit','Celsius to Fahrenheit',"v[0]*9/5+32",[100],212),
 ('fahrenheit_celsius','Fahrenheit to Celsius',"(v[0]-32)*5/9",[32],0),
 ('km_miles','Kilometres to international miles',"v[0]/1.609344",[1.609344],1),
 ('litres_gallons','Litres to US liquid gallons',"v[0]/3.785411784",[3.785411784],1),
 ('rectangle_area','Rectangle area in squared input units',"v[0]*v[1]",[3,4],12),
 ('triangle_area','Triangle area from base and altitude',"v[0]*v[1]/2",[3,4],6),
 ('circle_area','Circle area from radius',"math.pi*v[0]**2",[1],3.141592653589793),
 ('cylinder_volume','Cylinder volume from radius and height',"math.pi*v[0]**2*v[1]",[1,2],6.283185307179586),
 ('speed','Average speed from distance and positive elapsed time',"v[0]/v[1]",[100,2],50),
 ('density','Density from mass and positive volume',"v[0]/v[1]",[10,2],5),
 ('ohms_voltage','Voltage from current and resistance',"v[0]*v[1]",[2,4],8),
 ('electric_energy','Energy in kWh from watts and elapsed hours',"v[0]*v[1]/1000",[500,2],1),
]}
# JSON fixtures contain declared synthetic edge cases, not collected/training facts.
FIXTURES=[
 ('email_cases','Conservative email syntax',[('a@example.org',True),('bad',False),('',False),('b+tag@example.org',True)]),
 ('identifier_cases','Portable identifiers',[('alpha',True),('_item',True),('2bad',False),('a b',False)]),
 ('positive_integer_cases','Integer versus bool and zero',[(1,True),(0,False),(-1,False),(True,False)]),
 ('finite_number_cases','Numeric versus string cases',[(1.5,True),('1.5',False),(False,False),(0,True)]),
 ('date_cases','Leap dates and calendar edges',[('2024-02-29',True),('2025-02-29',False),('2026-13-01',False),('2026-10-20',True)]),
 ('sha_cases','Digest length and hex case',[('a'*64,True),('A'*64,False),('z'*64,False),('a'*63,False)]),
 ('currency_cases','Supported code allowlist',[('USD',True),('usd',False),('EUR',True),('XXX',False)]),
 ('text_cases','Blank and unicode text',[('hello',True),(' ',False),('café',True),('line\nvalue',True)]),
 ('string_list_cases','List uniqueness and blank items',[(['a','b'],True),(['a','a'],False),([],False),([' '],False)]),
 ('record_cases','Record identity boundaries',[({'id':1},True),({'id':True},False),({'id':0},False),({},False)]),
 ('interval_cases','Closed interval boundaries',[(0,True),(1,True),(-0.01,False),(1.01,False)]),
 ('filename_cases','Portable filename and traversal',[('report.csv',True),('../report.csv',False),('a/b',False),('a,b',False)]),
]
