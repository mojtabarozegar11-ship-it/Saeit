#!/usr/bin/env python3
import urllib.request,urllib.error,re,html,os
base="https://zomorodmelal.ir"
paths=["/topics/zm-r25/game-development/","/farm-wars/","/","/topics/zm-r25/"]
for path in paths:
 try:
  request=urllib.request.Request(base+path,headers={"User-Agent":"ZomorodExistingGameCardPageAudit/1","Cache-Control":"no-cache"})
  with urllib.request.urlopen(request,timeout=28) as r:
   raw=r.read(2500000);status=r.status;u=r.url;ctype=r.headers.get("content-type","")
  text=raw.decode("utf-8","replace")
  print("PAGE",path,"HTTP",status,"FINAL",u,"MIME",ctype,"BYTES",len(raw),flush=True)
  for tag in ["title","h1","main","iframe","footer"]:
   tags=re.findall(r"<"+tag+r"\b[^>]*>.*?</"+tag+r">",text,re.I|re.S)
   clean=[re.sub(r"\s+"," ",re.sub(r"<[^>]*>"," ",x)).strip()[:240] for x in tags[:2]]
   print(" ",tag,"count",len(tags),"texts",clean,flush=True)
  for term in ["ZOMOROD_ORBIT_DATA","FarmDominionDebug","farm-wars","game-development","ساخت بازی","بازی‌سازی","بازی","نمایش"]:
   i=text.find(term)
   if i>=0:print(" TERM",term,"OFFSET",i,"AROUND",re.sub(r"\s+"," ",text[max(0,i-190):i+350])[:550],flush=True)
 except Exception as e:print("PAGE_ERROR",path,str(e),flush=True)
