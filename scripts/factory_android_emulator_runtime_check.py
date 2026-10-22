#!/usr/bin/env python3
"""Probe actual Android emulator launches for the F12/F16 private APKs.

This is virtual device evidence; it is NOT physical-device approval, formal
usability testing, production release signing, or quality-1000 certification.
No arbitrary app/package can be tested: only the two named factory families.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import time

FAMILIES={"F12":"com.zomorodmelal.factory.f12",
          "F16":"com.zomorodmelal.factory.f16"}

def run(*args, timeout=30):
    result=subprocess.run(["adb",*args],text=True,capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError("EMULATOR_ADB_COMMAND_FAILED:"+str(args[:3])+":"+result.stderr[:300])
    return result.stdout.strip()

def screenshot():
    result=subprocess.run(["adb","exec-out","screencap","-p"],
                          capture_output=True,timeout=40)
    if result.returncode or not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("EMULATOR_SCREENSHOT_NOT_PNG")
    return result.stdout

def execute(family,apk,destination):
    if family not in FAMILIES:
        raise RuntimeError("EMULATOR_UNSUPPORTED_FAMILY")
    apk=Path(apk)
    destination=Path(destination)
    if apk.is_symlink() or not apk.is_file() or apk.stat().st_size<10000:
        raise RuntimeError("EMULATOR_REAL_APK_REQUIRED")
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("EMULATOR_OUTPUT_MUST_BE_NEW")
    pkg=FAMILIES[family]
    sdk=run("shell","getprop","ro.build.version.sdk")
    is_virtual=run("shell","getprop","ro.kernel.qemu")
    if sdk!="35" or is_virtual!="1":
        raise RuntimeError("EMULATOR_EXPECTED_ANDROID_35_VIRTUAL_DEVICE")
    run("wait-for-device",timeout=90)
    run("install","-r",str(apk),timeout=160)
    if not run("shell","pm","path",pkg).startswith("package:"):
        raise RuntimeError("EMULATOR_PACKAGE_NOT_INSTALLED")
    permissions=run("shell","dumpsys","package",pkg,timeout=40)
    if "android.permission.INTERNET: granted=true" in permissions:
        raise RuntimeError("EMULATOR_UNEXPECTED_INTERNET_PERMISSION")
    run("shell","am","force-stop",pkg)
    run("logcat","-c")
    launch=run("shell","am","start","-W","-n",pkg+"/.MainActivity",timeout=65)
    if "Status: ok" not in launch:
        raise RuntimeError("EMULATOR_ACTIVITY_START_NOT_OK")
    time.sleep(5)
    first_pid=run("shell","pidof",pkg)
    if not first_pid:
        raise RuntimeError("EMULATOR_APP_PROCESS_NOT_ALIVE")
    # Real Android input dispatch; safety: local synthetic emulator only.
    run("shell","input","tap","200","360")
    run("shell","input","swipe","280","390","120","390","270")
    time.sleep(2)
    after_pid=run("shell","pidof",pkg)
    if not after_pid:
        raise RuntimeError("EMULATOR_APP_CRASHED_AFTER_TOUCH")
    active=run("shell","dumpsys","activity","activities",timeout=35)
    if pkg not in active:
        raise RuntimeError("EMULATOR_APP_NOT_IN_ACTIVITY_STACK")
    png=screenshot()
    if len(png)<3000:
        raise RuntimeError("EMULATOR_SCREEN_BLANK_OR_TOO_SMALL")
    from PIL import Image
    img=Image.open(io.BytesIO(png)).convert("RGB")
    img.thumbnail((120,120))
    unique=len(set(img.getdata()))
    if unique<5:
        raise RuntimeError("EMULATOR_SCREEN_NO_VISIBLE_CONTENT")
    logcat=run("logcat","-d","-v","brief","AndroidRuntime:E","*:S",timeout=45)
    if "FATAL EXCEPTION" in logcat and pkg in logcat:
        raise RuntimeError("EMULATOR_APP_CRASH_IN_ANDROID_RUNTIME")
    destination.mkdir(parents=True,mode=0o700)
    (destination/"emulator-screen.png").write_bytes(png)
    report={
        "schema":"saeit.factory.android-emulated-runtime-check.v1",
        "family":family,
        "package":pkg,
        "android_sdk":int(sdk),
        "virtual_device":True,
        "actual_install_verified":True,
        "actual_activity_start_verified":True,
        "real_emulated_touch_and_swipe_dispatched":True,
        "app_alive_after_interaction":True,
        "no_app_fatal_crash_observed":True,
        "distinct_screen_colors":unique,
        "apk_sha256":hashlib.sha256(apk.read_bytes()).hexdigest(),
        "screenshot_sha256":hashlib.sha256(png).hexdigest(),
        "emulator_screen_size_bytes":len(png),
        "physical_device_tested":False,
        "independent_professional_review":False,
        "release_signing_verified":False,
        "quality_1000_certified":False,
        "commercial_release":False
    }
    (destination/"emulator-proof.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print("ANDROID_ACTUAL_EMULATOR_TEST="+json.dumps(
        {"family":family,"sdk":int(sdk),"touch":True,"screen_colors":unique,
         "physical_device":False,"quality1000":False},sort_keys=True))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--family",required=True,choices=tuple(FAMILIES))
    p.add_argument("--apk",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    execute(a.family,a.apk,a.out)
