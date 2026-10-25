#!/usr/bin/env python3
"""Resource-governed, zero-paid-API original leech-farm manuscript author on owner VPS.

All language-model inference runs ONLY on the owner's VPS, never GitHub runners.
No public release, customer/site writes, clinical instructions, payments or secret export.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

OPS = Path("/home/githubops/factory-runtime/operations/production-instructions")
ENGINE = OPS / "leech-offline-engine-20261025"
MODEL = ENGINE / "models/Qwen3-1.7B-Q4_K_M.gguf"
SERVER = ENGINE / "bin/llama-server"
AUTHOR = OPS / "leech-professional-author.py"
LOCK = ENGINE / "one-manuscript-writer.lock"
STATUS = ENGINE / "self-hosted-author-status.json"
PORT = 18767
SAFE_START_AVAILABLE_MIB = 2700
STOP_AVAILABLE_MIB = 1250
VIRTUAL_MEMORY_CAP_MIB = 2600


def available_memory_mib():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise RuntimeError("MEMAVAILABLE_MISSING")


def record(**data):
    ENGINE.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = {"schema": "saeit.leech.selfhosted-operator-v1",
            "order_id": "WO-26102501", "mode": "owner-vps-only",
            "paid_inference_api_cost_usd": 0,
            "scientific_quality_approved": False, "published": False,
            "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **data}
    descriptor, temporary = tempfile.mkstemp(prefix=".leech-run-", dir=str(ENGINE))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(body, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, STATUS)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("LEECH_OWNER_VPS_SELFHOSTED_STATUS=" + json.dumps(body, sort_keys=True), flush=True)


def preflight():
    if any(p.is_symlink() for p in (OPS, ENGINE, MODEL, SERVER, AUTHOR)):
        raise RuntimeError("UNSAFE_SYMLINK")
    if not (MODEL.is_file() and SERVER.is_file() and os.access(SERVER, os.X_OK) and AUTHOR.is_file()):
        raise RuntimeError("SELFHOSTED_ENGINE_OR_WRITER_MISSING")
    if not 1_200_000_000 <= MODEL.stat().st_size <= 1_450_000_000:
        raise RuntimeError("MODEL_SIZE_INVALID")
    with MODEL.open("rb") as f:
        if f.read(4) != b"GGUF":
            raise RuntimeError("MODEL_MAGIC_INVALID")
    free = os.statvfs(ENGINE)
    if free.f_bavail * free.f_frsize < 5 * 1024**3:
        raise RuntimeError("PRESERVE_DISK_5GIB")
    if available_memory_mib() < SAFE_START_AVAILABLE_MIB:
        raise RuntimeError("PRESERVE_SITE_RAM_AT_START")
    if os.getloadavg()[0] > 2.8:
        raise RuntimeError("PRESERVE_SITE_CPU_LOAD")
    with socket.socket() as sock:
        sock.settimeout(1.0)
        if sock.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError("PRIVATE_INFERENCE_PORT_BUSY")


def assignment():
    p = subprocess.run([sys.executable, "-B", str(AUTHOR), "prepare"],
                       capture_output=True, text=True, timeout=45,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=True)
    doc = json.loads(p.stdout)
    if doc.get("order_id") != "WO-26102501" and doc.get("next_chapter") is not None:
        raise RuntimeError("WRONG_PRODUCT_ORDER")
    return doc


def build_prompt(d, retry=0):
    focus_list = d.get("section_plan", [])
    if not isinstance(focus_list, list) or not focus_list:
        raise RuntimeError("MISSING_OPERATIONAL_SECTION_PLAN")
    part = int(d["part_number"])
    focus = focus_list[(part - 1 + retry) % len(focus_list)]
    angles = (
        "site layout and daily routine, with a practical operator checklist",
        "record-keeping, water testing plans, observable indicators and corrective decisions",
        "a clearly hypothetical cost, staffing or farm-capacity calculation with assumptions",
        "biosecurity workflow, veterinary escalation, quarantine decision log and responsible sourcing",
        "harvest and quality traceability, customer specifications, transport risk and compliance review",
        "a new farm equipment, procurement and husbandry scheduling case with failure diagnosis",
    )
    brief = {k: v for k, v in d.items() if k != "previous_chapter_context_tail"}
    return (
        "Continue a real vocational English handbook on establishing and operating "
        "a legally compliant commercial MEDICINAL LEECH BREEDING FARM. "
        "Do not write a general zoology essay or clinical treatment advice. "
        "Chapter " + str(d["chapter_number"]) + ": " + str(d["chapter_title"]) + ". "
        "New topic: " + str(focus) + ". Fresh distinct angle: "
        + angles[(part - 1 + 2 * retry) % len(angles)] + ". "
        "Write 650 to 950 new substantive English words, starting with a concrete "
        "descriptive subheading. Include farm SOP, realistic monitoring record "
        "fields, a worked HYPOTHETICAL example or decision, hazard signs and "
        "escalation to licensed expertise. Use original paragraphs; no padding, "
        "repeated introductions, unsourced numeric husbandry limits, invented citations, "
        "unsafe wild capture advice, human/animal blood-feeding instructions, or "
        "pathogen culture. Label assumptions and distinguish Hirudo species accurately. "
        "Use source IDs only for source-supported claims. Source-bounded research "
        "and farm-task context: " + json.dumps(brief, ensure_ascii=False)
    )


def low_priority_preexec():
    os.nice(15)
    lim = VIRTUAL_MEMORY_CAP_MIB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (lim, lim))


def call_model(doc, process, error, retry=0):
    prompt = build_prompt(doc, retry)
    payload = {
        "model": "local-owner-vps-qwen3-1.7b",
        "messages": [
            {"role": "system", "content": (
                "Produce commercially useful, source-bounded vocational leech FARM "
                "OPERATOR prose. Never invent empirical thresholds or approvals. "
                "Write ONLY substantive textbook text, without internal reasoning.")},
            {"role": "user", "content": prompt}],
        "max_tokens": 2300, "temperature": round(0.69 + retry * 0.05, 2),
        "top_p": 0.9, "chat_template_kwargs": {"enable_thinking": False},
        "stream": False,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % PORT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=820) as response:
        obj = json.load(response)
    if error:
        raise RuntimeError("LOW_MEMORY_ABORT")
    body = str(obj.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    if not body or "<think>" in body or "</think>" in body:
        raise RuntimeError("UNSAFE_MODEL_RESPONSE")
    return body


def main():
    ENGINE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with LOCK.open("a+b") as lock:
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("LEECH_SELFHOSTED_ALREADY_RUNNING=skip")
            return
        preflight()
        doc = assignment()
        if doc.get("next_chapter") is None:
            record(result="length_complete_wait_scientific_review",
                   verified_words=doc["total_verified_draft_words"])
            return
        mem_before = available_memory_mib()
        env = {**os.environ, "LD_LIBRARY_PATH": str(ENGINE / "bin"),
               "PYTHONDONTWRITEBYTECODE": "1",
               "LEECH_OFFLINE_INFERENCE_BACKEND": "owner-vps-qwen3-1.7b-q4km"}
        cmd = [str(SERVER), "-m", str(MODEL), "--host", "127.0.0.1",
               "--port", str(PORT), "-c", "4096", "-t", "1", "-ngl", "0", "--parallel", "1"]
        with open(os.devnull, "wb") as sink:
            proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=sink, stderr=sink, preexec_fn=low_priority_preexec)
            finished = threading.Event()
            pressured = []
            def watch():
                while not finished.wait(2.5):
                    try:
                        if available_memory_mib() < STOP_AVAILABLE_MIB:
                            pressured.append("LOW_MEMORY_ABORT")
                            proc.terminate()
                            return
                    except OSError:
                        proc.terminate()
                        return
            thread = threading.Thread(target=watch, daemon=True)
            thread.start()
            try:
                for _ in range(90):
                    if pressured:
                        raise RuntimeError("LOW_MEMORY_ABORT")
                    if proc.poll() is not None:
                        raise RuntimeError("MODEL_SERVER_EXITED")
                    try:
                        with urllib.request.urlopen(
                           "http://127.0.0.1:%d/health" % PORT, timeout=2) as r:
                            if r.status == 200:
                                break
                    except OSError:
                        time.sleep(2)
                else:
                    raise RuntimeError("MODEL_START_TIMEOUT")
                errors = []
                for retry in range(2):
                    body = call_model(doc, proc, pressured, retry=retry)
                    result = subprocess.run([sys.executable, "-B", str(AUTHOR), "accept"],
                        input=body + "\n", capture_output=True, text=True, timeout=90, env=env)
                    if result.returncode == 0:
                        receipt = json.loads(result.stdout)
                        if receipt.get("original_prose_accepted") is not True or receipt.get("commercial_release") is not False:
                            raise RuntimeError("UNSAFE_RECEIPT")
                        record(result="private_original_prose_accepted",
                               accepted_words=receipt["accepted_words"],
                               verified_words=receipt["total_unreviewed_original_words"],
                               next_chapter=receipt["next_chapter"],
                               next_part=receipt["next_part"],
                               start_available_mib=mem_before,
                               end_available_mib=available_memory_mib())
                        return
                    errors.append(result.stderr[-200:])
                    if "SEGMENT_DUPLICATES_PREVIOUS" not in result.stderr and "SEGMENT_REPETITIVE" not in result.stderr:
                        raise RuntimeError("STRICT_MANUSCRIPT_QC_REJECTED")
                raise RuntimeError("STRICT_DUPLICATION_QC_REJECTED_TWICE")
            finally:
                finished.set()
                proc.terminate() if proc.poll() is None else None
                try:
                    proc.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                thread.join(timeout=3)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc)[:90]
        try:
            record(result="blocked_safe", reason=msg)
        except Exception:
            pass
        print("LEECH_SELFHOSTED_SAFE_STOP=" + msg, file=sys.stderr)
        raise SystemExit(2)
