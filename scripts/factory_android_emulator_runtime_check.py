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
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

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



def tap_visible_app_control(family):
    """Use accessibility UI bounds, never guessed screen coordinates."""
    for attempt in range(2):
        raw = run("exec-out", "uiautomator", "dump", "/dev/tty", timeout=45)
        start = raw.find("<?xml")
        if start < 0:
            raise RuntimeError("EMULATOR_ACCESSIBILITY_TREE_MISSING")
        finish = raw.find("</hierarchy>", start)
        if finish < 0:
            raise RuntimeError("EMULATOR_ACCESSIBILITY_TREE_INCOMPLETE")
        hierarchy = ET.fromstring(raw[start:finish + len("</hierarchy>")])
        for node in hierarchy.iter("node"):
            attrs = node.attrib
            label = (attrs.get("text", "") + " " +
                     attrs.get("content-desc", "")).lower()
            matching = (
                "next level" in label if family == "F12" else
                attrs.get("class") == "android.widget.EditText"
            )
            if not matching:
                continue
            match = re.fullmatch(
                r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                attrs.get("bounds", ""))
            if not match:
                continue
            x1, y1, x2, y2 = map(int, match.groups())
            if x2 <= x1 or y2 <= y1:
                continue
            run("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
            return True
        if attempt == 0:
            run("shell", "input", "swipe", "400", "800", "400", "300", "300")
            time.sleep(1)
    raise RuntimeError("EMULATOR_APP_CONTROL_NOT_EXPOSED_IN_UI_TREE")

class DebugWebView:
    """Inspects the actual running debug APK over the emulator's local CDP socket."""
    def __init__(self, pid):
        self.pid = str(pid).split()[0]
        if not self.pid.isdigit():
            raise RuntimeError("EMULATOR_WEBVIEW_PID_INVALID")
        self.connection = None
        self.port = "9223"

    def __enter__(self):
        from websocket import create_connection
        result = subprocess.run(
            ["adb", "forward", "tcp:" + self.port,
             "localabstract:webview_devtools_remote_" + self.pid],
            capture_output=True, text=True, timeout=12)
        if result.returncode:
            raise RuntimeError("EMULATOR_WEBVIEW_DEBUG_FORWARD_FAILED")
        try:
            url = None
            for _ in range(30):
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:" + self.port + "/json", timeout=3
                    ) as response:
                        pages = json.load(response)
                    url = next(
                        row["webSocketDebuggerUrl"] for row in pages
                        if row.get("type") == "page"
                        and "appassets.androidplatform.net" in row.get("url", "")
                        and row.get("webSocketDebuggerUrl")
                    )
                    break
                except (OSError, ValueError, KeyError, StopIteration):
                    time.sleep(1)
            if not url:
                raise RuntimeError("EMULATOR_REAL_WEBVIEW_PAGE_NOT_FOUND")
            self.connection = create_connection(
                url, timeout=12, suppress_origin=True)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        subprocess.run(["adb", "forward", "--remove", "tcp:" + self.port],
                       capture_output=True, text=True, timeout=12)

    def evaluate(self, expression):
        self.connection.send(json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True
            }
        }))
        for _ in range(20):
            message = json.loads(self.connection.recv())
            if message.get("id") != 1:
                continue
            result = message.get("result", {})
            if result.get("exceptionDetails"):
                raise RuntimeError("EMULATOR_WEBVIEW_JAVASCRIPT_EXCEPTION")
            value = result.get("result", {})
            if value.get("type") == "undefined":
                raise RuntimeError("EMULATOR_WEBVIEW_UNDEFINED_RESULT")
            return value.get("value")
        raise RuntimeError("EMULATOR_WEBVIEW_NO_CDP_RESULT")


def deep_application_acceptance(family, package, pid):
    """Prove application-specific state in the REAL installed APK, not in source."""
    if family == "F12":
        with DebugWebView(pid) as dev:
            first = dev.evaluate("""(() => ({
              count: levels.length, index,
              cells: document.querySelectorAll('#board button').length,
              message: document.querySelector('#message').textContent
            }))()""")
            if (first.get("count") != 48 or first.get("index") != 0
                    or first.get("cells") != 36
                    or first.get("message") != "Level 1 of 48"):
                raise RuntimeError("EMULATOR_F12_REAL_LEVELS_NOT_LOADED")
            moved = dev.evaluate("""(() => {
              document.getElementById('next').click();
              const switched = index === 1 &&
                  document.getElementById('message').textContent === 'Level 2 of 48';
              let changed = false;
              for (const [key, delta] of [
                ['ArrowUp', -6], ['ArrowDown', 6],
                ['ArrowLeft', -1], ['ArrowRight', 1]
              ]) {
                const before = player;
                document.dispatchEvent(new KeyboardEvent('keydown',
                     {key, bubbles: true, cancelable: true}));
                if (player !== before) { changed = true; break; }
              }
              return {switched, changed, cells:
                document.querySelectorAll('#board button').length};
            })()""")
            if (moved.get("switched") is not True
                    or moved.get("changed") is not True
                    or moved.get("cells") != 36):
                raise RuntimeError("EMULATOR_F12_APK_GAMEPLAY_NOT_CONFIRMED")
        return {"webview_dom_runtime_verified": True,
                "actual_48_levels_loaded": True,
                "next_level_transition_verified": True,
                "keyboard_player_movement_verified": True}

    token = "qa_apk_" + package.replace(".", "_")[-12:]
    with DebugWebView(pid) as dev:
        created = dev.evaluate("""(() => {
          const name = """ + json.dumps(token) + """;
          document.getElementById('name').value = name;
          document.getElementById('quantity').value = '7';
          document.getElementById('f').dispatchEvent(
              new Event('submit', {bubbles: true, cancelable: true}));
          const rows = JSON.parse(localStorage.getItem('field_ledger_local_v1') || '[]');
          return {saved: rows.some(x => x.name === name && x.quantity === 7),
                  visible: document.getElementById('items').textContent.includes(name)};
        })()""")
        if created != {"saved": True, "visible": True}:
            raise RuntimeError("EMULATOR_F16_APK_STORAGE_NOT_WRITTEN")

    run("shell", "am", "force-stop", package)
    launch = run("shell", "am", "start", "-W", "-n",
                 package + "/.MainActivity", timeout=65)
    if "Status: ok" not in launch:
        raise RuntimeError("EMULATOR_F16_REOPEN_FAILED")
    time.sleep(3)
    new_pid = run("shell", "pidof", package)
    if not new_pid:
        raise RuntimeError("EMULATOR_F16_REOPEN_NO_PROCESS")
    with DebugWebView(new_pid) as dev:
        persisted = dev.evaluate("""(() => {
          const name = """ + json.dumps(token) + """;
          const rows = JSON.parse(localStorage.getItem('field_ledger_local_v1') || '[]');
          return {saved: rows.some(x => x.name === name && x.quantity === 7),
                  visible: document.getElementById('items').textContent.includes(name)};
        })()""")
        if persisted != {"saved": True, "visible": True}:
            raise RuntimeError("EMULATOR_F16_APK_STORAGE_NOT_PERSISTED")
    return {"webview_dom_runtime_verified": True,
            "inventory_entry_written_in_apk": True,
            "inventory_storage_persisted_after_relaunch": True}

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
    # Verify app-specific state first, then dispatch real accessibility-derived touch.
    deep=deep_application_acceptance(family,pkg,first_pid)
    tap_visible_app_control(family)
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
        "commercial_release":False,
        **deep
    }
    (destination/"emulator-proof.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print("ANDROID_ACTUAL_EMULATOR_TEST="+json.dumps(
        {"family":family,"sdk":int(sdk),"touch":True,"screen_colors":unique,
         "physical_device":False,"quality1000":False,
         "deep_apk_dom_qa":True},sort_keys=True))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--family",required=True,choices=tuple(FAMILIES))
    p.add_argument("--apk",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    execute(a.family,a.apk,a.out)
