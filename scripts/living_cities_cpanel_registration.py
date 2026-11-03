#!/usr/bin/env python3
"""Scoped cPanel PassengerApps registration for Living Cities only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HOME=Path("/home/zomorod2")
SOURCE_SHA="b3fe1b772368f3f0874481ab88ad82862bd24de2"
RELEASE=HOME/".private/living-cities-app/releases"/SOURCE_SHA
DOCROOT=HOME/"public_html"
ROOT_HTACCESS=DOCROOT/".htaccess"
STATE=HOME/".private/living-cities-app/state"
APP_NAME="zomorod_living_cities_b3fe"
MARKER=STATE/"cpanel-passenger-app-registration.json"
APP_PATH=".private/living-cities-app/releases/"+SOURCE_SHA

def require(c,m):
    if not c:raise RuntimeError(m)
def uapi(function,*args):
    bin="/usr/local/cpanel/bin/uapi"
    require(Path(bin).is_file(),"uapi_unavailable")
    p=subprocess.run([bin,"--output=json","PassengerApps",function,*args],
       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=90)
    require(p.returncode==0,"uapi_transport_error")
    try:out=json.loads(p.stdout)
    except ValueError as exc:raise RuntimeError("uapi_response_invalid_json") from exc
    require(isinstance(out,dict),"uapi_unexpected_result_shape")
    return out
def check_ok(obj):
    result=obj.get("result",obj)
    require(isinstance(result,dict) and result.get("status")==1,
            "uapi_registration_rejected:"+",".join(map(str,(result.get("errors") or [])[:2]))[:180])
    return result
def all_apps():
    obj=check_ok(uapi("list_applications"))
    items=obj.get("data",[])
    if isinstance(items,dict):items=items.get("applications",items.get("app",[]))
    return items if isinstance(items,list) else []
def by_name():
    return [a for a in all_apps() if isinstance(a,dict) and a.get("name")==APP_NAME]
def preflight():
    require(os.geteuid()==HOME.stat().st_uid,"unexpected_user")
    require(ROOT_HTACCESS.is_file() and not ROOT_HTACCESS.is_symlink(),"root_config_not_regular")
    require(RELEASE.is_dir() and (RELEASE/"LC_VALIDATED.json").is_file(),"private_release_not_ready")
    require((DOCROOT/"living-cities").is_dir() and
            (DOCROOT/"living-cities/LC-OWNER.txt").read_text().strip()=="LC-OWNER-PINNED-"+SOURCE_SHA,
            "unmanaged_public_route")
    require(STATE.is_dir(),"missing_private_state")
def register():
    preflight()
    require(not MARKER.exists() and not MARKER.is_symlink(),"already_registered_marker")
    require(not by_name(),"app_name_conflict")
    digest=hashlib.sha256(ROOT_HTACCESS.read_bytes()).hexdigest()
    obj=uapi("register_application","name="+APP_NAME,"path="+APP_PATH,
       "domain=zomorodmelal.ir","base_uri=/living-cities",
       "deployment_mode=production","enabled=1")
    check_ok(obj)
    require(by_name(),"registered_app_not_listed")
    current=hashlib.sha256(ROOT_HTACCESS.read_bytes()).hexdigest()
    require(current==digest,"root_htaccess_changed_by_registration")
    tmp=MARKER.with_suffix(".pending")
    with tmp.open("x") as file:
        json.dump({"name":APP_NAME,"source":SOURCE_SHA,"path":APP_PATH,
           "base_uri":"/living-cities","root_htaccess_sha":digest},file)
    tmp.chmod(0o600);tmp.replace(MARKER)
    print("CPANEL_PASSENGER_APP_REGISTERED=PASS")
def unregister():
    require(MARKER.is_file() and not MARKER.is_symlink(),"registration_ownership_marker_missing")
    obj=json.loads(MARKER.read_text())
    require(obj["name"]==APP_NAME and obj["source"]==SOURCE_SHA,"registration_marker_mismatch")
    matching=by_name()
    require(len(matching)<2,"ambiguous_registered_app")
    if matching:
        r=uapi("unregister_application","name="+APP_NAME)
        check_ok(r)
    require(not by_name(),"registered_app_still_present")
    MARKER.rename(STATE/("unregistered-"+SOURCE_SHA+".json"))
    print("CPANEL_SCOPED_APP_UNREGISTERED=PASS")
if __name__=="__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("register","unregister"),"invalid_mode")
    {"register":register,"unregister":unregister}[sys.argv[1]]()
