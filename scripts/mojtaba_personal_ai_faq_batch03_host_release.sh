#!/usr/bin/env bash
# Host-only protected release. Runs exclusively inside the personal V17 app.
set -euo pipefail
umask 077
run_id="$1"
case "$run_id" in *[!0-9]*|"") echo "Invalid numeric run id" >&2; exit 1;; esac
app="/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17"
stage="/home/zomorod2/.personal-ai-faq-batch03-stage-$run_id"
installer="$stage/installer.py"
source="$stage/approved.json"
backup="/home/zomorod2/.backups/mojtaba-personal-ai-faq-batch03/$run_id"
py="/home/zomorod2/mojtaba_personal/.venv_personal_test/bin/python"
installed=0
verified=0
finish() {
  code=$?
  trap - EXIT
  if [ "$installed" -eq 1 ] && [ "$verified" -eq 0 ] && [ -f "$backup/manifest.json" ]; then
    "$py" "$installer" rollback --app "$app" --backup "$backup" &&
      echo "BATCH03_REMOTE_ROLLBACK=success" ||
      echo "BATCH03_REMOTE_ROLLBACK=manual_review_required"
  fi
  # Never remove user content or backups, only this task's private staging dir.
  if [ -d "$stage" ] && [ ! -L "$stage" ]; then
    rm -rf -- "$stage"
  fi
  exit "$code"
}
trap finish EXIT
test -f "$app/manage.py" && test ! -L "$app" && test -x "$py"
test -f "$installer" && test -f "$source" && test -f "$stage/mojtaba_personal_public_faq_safe_publish.py"
cd "$app"
"$py" "$installer" check --source "$source"
"$py" "$installer" install --app "$app" --source "$source" --backup "$backup"
installed=1
"$py" manage.py check --deploy
"$py" "$installer" verify --app "$app" --backup "$backup"
"$py" - <<'PYDJANGO'
import os,re
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django; django.setup()
from django.test import Client
from django.urls import reverse
from core.models import Post
client=Client(HTTP_HOST="mojplaywin.com")
routes=("home","about","resume","activities","memories","stories",
        "projects","posts","gallery","contact")
for name in routes:
    response=client.get(reverse("personal_site:"+name),secure=True)
    if response.status_code!=200:
        raise RuntimeError("Protected personal page failed: "+name)
    body=response.content.decode("utf-8","replace")
    batch="mpw-about-ai-questions-batch-03-20261016"
    if name!="about" and batch in body:
        raise RuntimeError("FAQ content leaked into another page")
    if name=="about":
        match=re.search(r'<section\s+id="mpw-public-personal-faq-20261016"[^>]*>.*?</section>',body,re.S)
        if not match or body.count(batch)!=1:
            raise RuntimeError("About FAQ missing")
        area=match.group()
        if len(re.findall(r'<article\b',area))!=38:
            raise RuntimeError("Expected exactly 38 English Q&A entries")
        if re.search(r"[\u0600-\u06FF]",area):
            raise RuntimeError("Non-English text in English-only FAQ")
        if area.count('data-ai-faq-id="')!=30:
            raise RuntimeError("Expected both previous batches and ten new questions")
        if ("mpw-about-ai-questions-batch-01-20261016" not in area
             or "mpw-about-ai-questions-batch-02-20261016" not in area
             or "mpw-personal-ask-question-v2-20261016" not in area
             or 'name="csrfmiddlewaretoken"' not in area):
            raise RuntimeError("Old Q&A batch or secure question form missing")
        for index in range(9,39):
            if area.count('data-ai-faq-id="'+str(index)+'"')!=1:
                raise RuntimeError("Existing or new Q&A missing: "+str(index))
    print("PERSONAL_BATCH03_DJANGO_ROUTE="+name+" HTTP=200",flush=True)
slugs=list(Post.objects.filter(published=True).values_list("slug",flat=True))
if len(slugs)<93:
    raise RuntimeError("Existing 93-article inventory missing")
for slug in slugs:
    if client.get(reverse("personal_site:post_detail",kwargs={"slug":slug}),secure=True).status_code!=200:
        raise RuntimeError("Published article inaccessible: "+slug)
print("PERSONAL_BATCH03_ARTICLE_ROUTES_PRESERVED="+str(len(slugs)),flush=True)
PYDJANGO
if [ -d "$app/tmp" ]; then touch "$app/tmp/restart.txt"; fi
"$py" - <<'PYHTTP'
import re,time
from urllib.request import Request,urlopen
url="https://mojplaywin.com/mojtaba.roozegar/about/"
for attempt in range(4):
    try:
        request=Request(url,headers={"User-Agent":"MojtabaPersonalBatch03OwnerRelease/1.0"})
        with urlopen(request,timeout=20) as response:
            text=response.read(1900000).decode("utf-8","replace")
            if response.status!=200:
                raise RuntimeError("Public response not HTTP 200")
        m=re.search(r'<section\s+id="mpw-public-personal-faq-20261016"[^>]*>.*?</section>',text,re.S)
        if not m: raise RuntimeError("About FAQ missing on live site")
        area=m.group()
        if (area.count("<article")!=38 or area.count('data-ai-faq-id="')!=30
                or "mpw-about-ai-questions-batch-02-20261016" not in area
                or "mpw-about-ai-questions-batch-02-20261016" not in area
             or "mpw-personal-ask-question-v2-20261016" not in area
                or re.search(r"[\u0600-\u06FF]",area)):
            raise RuntimeError("Live personal About FAQ not confirmed")
        print("PERSONAL_BATCH03_LIVE_HTTP=200;FAQ_COUNT=38;NEW_COUNT=10",flush=True)
        break
    except Exception as exc:
        print("PERSONAL_BATCH03_LIVE_RETRY="+type(exc).__name__+":"+str(exc)[:90],flush=True)
        if attempt==3: raise
        time.sleep(3)
PYHTTP
"$py" "$installer" verify --app "$app" --backup "$backup"
verified=1
echo "PERSONAL_BATCH03_PRODUCTION_STATUS=success"
echo "PERSONAL_BATCH03_BACKUP_PATH=$backup"
echo "MOJPLAYWIN_ROOT_ZOMOROD_OTHER_SITES_UNTOUCHED=yes"
