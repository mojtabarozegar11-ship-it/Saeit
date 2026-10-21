#!/usr/bin/env python3
"""Safe public MojPlayWin CSRF check using nonexistent credentials; no real logins or orders."""
import urllib.request,urllib.error,http.cookiejar,urllib.parse,re,json
BASE='https://mojplaywin.com'
PATH='/accounts/login/'
def report(tag,item):print(tag+'='+json.dumps(item,sort_keys=True),flush=True)
def probe(label,origin,with_cookie):
    cj=http.cookiejar.CookieJar()
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req=urllib.request.Request(BASE+PATH,headers={'User-Agent':'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/127 Mobile Safari/537.36','Cache-Control':'no-cache'})
    with client.open(req,timeout=20) as resp:
        html=resp.read(150000).decode('utf8','replace')
        get_status=resp.status
        get_url=resp.geturl()
    m=re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)',html)
    if not m:m=re.search(r'value=["\']([^"\']+)["\']\s+name=["\']csrfmiddlewaretoken["\']',html)
    if not m:raise RuntimeError('Login token missing')
    body=urllib.parse.urlencode({'username':'mpw_csrf_probe_nouser_oct2026','password':'this-is-not-a-real-password','csrfmiddlewaretoken':m.group(1)}).encode()
    if not with_cookie:cj.clear()
    post=urllib.request.Request(BASE+PATH,data=body,headers={
      'Content-Type':'application/x-www-form-urlencoded',
      'User-Agent':'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/127 Mobile Safari/537.36',
      'Origin':origin,'Referer':origin+PATH,
    },method='POST')
    try:
        with client.open(post,timeout=20) as resp:status=resp.status;final=resp.geturl()
    except urllib.error.HTTPError as e:status=e.code;final=e.geturl()
    report('MPW_CSRF_PUBLIC_POST',{'scenario':label,'login_page_get':get_status,
      'get_canonical_host':urllib.parse.urlparse(get_url).netloc,'result':status,'final_host':urllib.parse.urlparse(final).netloc})
    return status
if __name__=='__main__':
    scenarios=[('same-origin-cookie-preserved','https://mojplaywin.com',True),
      ('www-origin-cookie-preserved','https://www.mojplaywin.com',True),
      ('same-origin-cookie-missing','https://mojplaywin.com',False)]
    result=[probe(*case) for case in scenarios]
    # Nonexistent credentials must never authenticate; cookie-bearing CSRF POST must
    # reach the login validator, while a missing CSRF cookie must be rejected.
    if result[0] not in (200,400,401,302):
        raise RuntimeError('Standard mobile-style login POST failed (CSRF or server error): '+str(result[0]))
    if result[2]!=403:
        raise RuntimeError('Cookie-free login POST unexpectedly bypassed CSRF protection: '+str(result[2]))
    print('MPW_CSRF_PUBLIC_POST_SAFE_DIAGNOSTIC=PASS')
