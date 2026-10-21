#!/usr/bin/env python3
"""Public signup 403 reproduction with INVALID EMPTY registration submission only.

Does not submit a usable username, email, password or payment. Holds CSRF
cookies only in ephemeral memory; never logs tokens or session identifiers.
"""
import http.cookiejar,json,re,urllib.request,urllib.error,urllib.parse
BASES=["https://mojplaywin.com","https://www.mojplaywin.com"]
PATHS=["/accounts/register/","/accounts/login/"]
USER_AGENT="Mozilla/5.0 (Linux; Android 10; SM-A920F) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"

def emit(data):
 print("MPW_REGISTER_PUBLIC_HTTP="+json.dumps(data,sort_keys=True),flush=True)
def submit(base,path):
 jar=http.cookiejar.CookieJar()
 client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
 uri=base+path+"?mpw_csrf_external_audit=1"
 req=urllib.request.Request(uri,headers={"User-Agent":USER_AGENT,"Cache-Control":"no-cache"})
 with client.open(req,timeout=24) as r:
  html=r.read(180000).decode("utf8","replace")
  final=r.geturl()
  headers=r.headers
  get_status=r.status
 form=re.search(r"<form\b[^>]*method=['\"]post['\"][^>]*>",html,re.I)
 if not form:form=re.search(r"<form\b[^>]*>",html,re.I)
 form_action=re.search(r'action=["\x27]([^"\x27]+)',form.group(0),re.I) if form else None
 m=re.search(r'name=["\x27]csrfmiddlewaretoken["\x27][^>]*',html,re.I)
 token=re.search(r'value=["\x27]([^"\x27]+)',m.group(0),re.I).group(1) if m and re.search(r'value=["\x27]([^"\x27]+)',m.group(0),re.I) else None
 host=urllib.parse.urlparse(final).netloc
 cookie_names=[c.name for c in jar]
 h={
  "get":get_status,"requested_base":base,"path":path,
  "final_host":host,"form_action":form_action.group(1) if form_action else None,
  "csfr_cookie_issued":"csrftoken" in cookie_names,"token_present":bool(token),
  "csp_header":(headers.get("Content-Security-Policy") or "")[:1350],
  "cache_control":headers.get("Cache-Control",""),
  "referrer_policy_header":headers.get("Referrer-Policy",""),
  "referrer_meta_no_referrer":bool(re.search(r'<meta\\s+name=["\\x27]referrer["\\x27]\\s+content=["\\x27]no-referrer',html,re.I)),
  "vary":headers.get("Vary",""),
  "refresh_script_present":"mpw-csrf-fresh-submit-20261020" in html,
 }
 if not token:
  emit({**h,"failure":"csrf_token_absent"})
  return False
 # Form fields intentionally absent, so the Django validator must reject
 # the registration/login even when CSRF is valid.
 dest=urllib.parse.urljoin(final,form_action.group(1) if form_action else path)
 final_origin=urllib.parse.urlsplit(dest).scheme+"://"+urllib.parse.urlsplit(dest).netloc
 if final_origin not in ("https://mojplaywin.com","https://www.mojplaywin.com"):
  emit({**h,"failure":"unexpected_form_destination"});return False
 raw=urllib.parse.urlencode({"csrfmiddlewaretoken":token}).encode("ascii")
 hdr={"User-Agent":USER_AGENT,"Content-Type":"application/x-www-form-urlencoded",
      "Origin":final_origin,"Referer":final,"Cache-Control":"no-cache"}
 req=urllib.request.Request(dest,data=raw,headers=hdr,method="POST")
 try:
  with client.open(req,timeout=24) as res:ok=res.status
 except urllib.error.HTTPError as ex:ok=ex.code
 # Deliberately bad token/cookie should fail CSRF (test no invalid account).
 jar.clear()
 # urllib mutates Request with a Cookie header on first use. NEVER reuse it
 # after clearing cookie jar, or a false-negative CSRF test may result.
 absent=urllib.request.Request(dest,data=raw,headers=hdr,method="POST")
 assert not absent.has_header("Cookie")
 try:
  with client.open(absent,timeout=24) as res:missing=res.status
 except urllib.error.HTTPError as ex:missing=ex.code
 emit({**h,"empty_valid_csrf_POST":ok,"cookie_deleted_POST":missing,
       "valid_cookie_passes_csrf":ok!=403,"missing_cookie_fails_csrf":missing==403})
 return ok!=403 and missing==403

if __name__=="__main__":
 results=[]
 for base in BASES:
  for path in PATHS:
   try:results.append(submit(base,path))
   except Exception as e:
    emit({"base":base,"path":path,"error_class":type(e).__name__})
    results.append(False)
 if not all(results):raise SystemExit("MPW_REGISTER_PUBLIC_CSRF_GATE=FAILED")
 print("MPW_REGISTER_PUBLIC_CSRF_GATE=PASS; USERS_CREATED=0")
