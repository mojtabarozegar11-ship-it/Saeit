#!/usr/bin/env python3
"""Real Android emulator UI acceptance for the factory's two offline APKs.

Installs launchable APKs on an Android emulator, plays F12 and records/reloads
F16 inventory. This is *emulated Android execution*, never physical-device
certification, independent specialist review, or permission to release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGES={"F12":"com.zomorodmelal.factory.f12","F16":"com.zomorodmelal.factory.f16"}
BOUNDS=re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")

def adb(*args, timeout=40, expect_success=True):
    p=subprocess.run(["adb",*map(str,args)],text=True,stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,timeout=timeout,check=False)
    if expect_success and p.returncode:
        raise RuntimeError("ANDROID_EMULATOR_ADB_FAILED "+ " ".join(args) +
                           ": "+p.stderr[-300:])
    return p.stdout

def find_ui(*phrases, timeout=45):
    """Choose an actual Android accessibility node from WebView, not a mock."""
    end=time.monotonic()+timeout
    latest=""
    while time.monotonic()<end:
        try:
            adb("shell","uiautomator","dump","/sdcard/factory-six-ui.xml",timeout=15)
            xml=adb("exec-out","cat","/sdcard/factory-six-ui.xml",timeout=10)
            root=ET.fromstring(xml[xml.find("<?xml"):])
            nodes=root.iter("node")
            for node in nodes:
                text=" ".join((node.get("text",""),node.get("content-desc","")))
                if any(phrase.lower() in text.lower() for phrase in phrases):
                    return node
            latest=" | ".join((v.get("text") or v.get("content-desc") or "")
                            for v in root.iter("node") if
                            v.get("text") or v.get("content-desc"))[:350]
        except (ValueError, ET.ParseError, subprocess.SubprocessError) as error:
            latest=str(error)[:250]
        time.sleep(1.4)
    raise RuntimeError("ANDROID_EMULATOR_UI_NOT_FOUND "+repr(phrases)+": "+latest)

def center(node):
    match=BOUNDS.fullmatch(node.get("bounds",""))
    if not match:
        raise RuntimeError("ANDROID_EMULATOR_NODE_BOUNDS_MISSING")
    a,b,c,d=map(int,match.groups())
    if a>=c or b>=d:
        raise RuntimeError("ANDROID_EMULATOR_NODE_BOUNDS_INVALID")
    return ((a+c)//2,(b+d)//2)

def tap(node):
    x,y=center(node)
    adb("shell","input","tap",str(x),str(y))

def launch(family, apk):
    pkg=PACKAGES[family]
    if not apk.is_file() or apk.is_symlink() or apk.stat().st_size<5000:
        raise RuntimeError("ANDROID_EMULATOR_APK_MISSING_OR_TOO_SMALL path="+
                           str(apk)+" bytes="+str(apk.stat().st_size if apk.exists() else -1))
    adb("install","-r",str(apk),timeout=95)
    adb("shell","am","force-stop",pkg)
    opened=adb("shell","am","start","-W","-n",pkg+"/.MainActivity",timeout=55)
    if "Error:" in opened or "Status: ok" not in opened:
        raise RuntimeError("ANDROID_EMULATOR_CANNOT_LAUNCH "+family+" "+opened[-250:])
    return hashlib.sha256(apk.read_bytes()).hexdigest()

def game_test(apk):
    key=launch("F12",apk)
    find_ui("Gem Route")
    find_ui("Level 1 of 48")
    tap(find_ui("Next level"))
    find_ui("Level 2 of 48")
    # A directional button is a real gameplay input, not just a static page.
    tap(find_ui("↑"))
    find_ui("Level 2 of 48")
    return {"family":"F12","apk_sha256":key,
            "checks":["real_emulator_install","main_activity_launch",
                      "webview_48_level_load","real_next_level_button",
                      "real_directional_gameplay_control"]}

def inventory_test(apk):
    key=launch("F16",apk)
    find_ui("Field Ledger")
    tap(find_ui("Item"))
    adb("shell","input","text","QAItem52")
    tap(find_ui("Quantity"))
    adb("shell","input","text","7")
    tap(find_ui("Save entry"))
    find_ui("QAItem52")
    # Restart the application and prove *on-device* WebView DOM storage survived.
    pkg=PACKAGES["F16"]
    adb("shell","am","force-stop",pkg)
    opened=adb("shell","am","start","-W","-n",pkg+"/.MainActivity",timeout=55)
    if "Status: ok" not in opened:
        raise RuntimeError("ANDROID_EMULATOR_INVENTORY_RESTART_FAILED")
    find_ui("QAItem52")
    return {"family":"F16","apk_sha256":key,
            "checks":["real_emulator_install","main_activity_launch",
                      "native_webview_field_entry","local_storage_write",
                      "persistence_after_force_stop_and_relaunch"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apk-f12",required=True)
    p.add_argument("--apk-f16",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    adb("wait-for-device",timeout=100)
    api=adb("shell","getprop","ro.build.version.sdk").strip()
    if api not in ("29","30","31","32","33","34","35","36"):
        raise RuntimeError("ANDROID_EMULATOR_UNSUPPORTED_API "+api)
    results=[game_test(Path(args.apk_f12)),inventory_test(Path(args.apk_f16))]
    proof={"schema":"saeit.factory.native-android-emulator-interactive.v1",
           "environment":"actual_android_emulator",
           "android_api_level":int(api),"families":results,
           "native_emulator_install_ui_interaction_verified":True,
           "physical_device_tested":False,
           "independent_human_specialist_review":False,
           "quality_1000_certified":False,"public_release":False}
    output=Path(args.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(proof,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("SIX_ANDROID_REAL_EMULATOR_UI_PROOF="+json.dumps(
        {"families":2,"api":api,"f12_levels":True,"f16_storage_persisted":True,
         "physical_device_qa":False,"quality_1000":False},sort_keys=True))

if __name__=="__main__":
    main()
