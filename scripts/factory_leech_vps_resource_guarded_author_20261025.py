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
    """Source-scoped short-context leech SOP prompt for very slow old SSE2 VPS."""
    focus_list = d.get("section_plan", [])
    if not isinstance(focus_list, list) or not focus_list:
        raise RuntimeError("MISSING_OPERATIONAL_SECTION_PLAN")
    part = int(d["part_number"])
    focus = " ".join(str(focus_list[(part - 1 + retry) % len(focus_list)]).split())[:125]
    angles = (
        "layout and daily staff duties", "water-monitoring records and response",
        "hypothetical operating costs", "quarantine and veterinary referral",
        "traceable harvest and buyer specification", "equipment failure response")
    refs = []
    for row in d.get("foundational_source_records", [])[:5]:
        if isinstance(row, dict) and row.get("id"):
            scope = str(row.get("limitation") or row.get("title") or "")
            scope = " ".join(scope.split())[:65]
            refs.append(str(row["id"])[:20] + ":" + scope)
    return (
        "/no_think\n"
        "Write 335-460 ORIGINAL English vocational textbook words about "
        "OPERATING a lawful medicinal-leech breeding FARM. No clinical advice. "
        "Chapter %s, %s. Section: %s. Angle: %s. "
        "Explain a practical SOP, named monitoring-log fields, decision thresholds "
        "only if sourced, one explicitly HYPOTHETICAL operational calculation, "
        "staff responsibility, biosecurity hazard, and licensed specialist referral. "
        "Distinguish Hirudo medicinalis, H. verbana and H. orientalis. "
        "No wild capture, human/animal feeding protocol, pathogen culture, "
        "fake citations, unsourced fixed limits or padding. "
        "Bound evidence by these source IDs and scopes: %s. "
        "Acknowledge unknowns; use a concrete section heading and fresh prose."
    ) % (d["chapter_number"], str(d["chapter_title"])[:72],
         focus, angles[(part - 1 + retry) % len(angles)], " | ".join(refs)[:620])


def low_priority_preexec():
    os.nice(15)
    lim = VIRTUAL_MEMORY_CAP_MIB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (lim, lim))


def call_model(doc, process, error, retry=0):
    """Stream owner-VPS text and stop at a complete, substantial paragraph.

    On very old SSE2-only CPUs full 1500+ token responses can exceed the safe
    execution window. Streaming lets us preserve substantive original prose
    as soon as a self-contained segment passes diversity/length checks.
    """
    import re
    prompt = build_prompt(doc, retry)
    payload = {
        "model": "local-owner-vps-qwen3-1.7b",
        "messages": [
            {"role": "system", "content": (
                "Produce commercially useful, source-bounded vocational leech FARM "
                "OPERATOR prose. Never invent empirical thresholds or approvals. "
                "Write ONLY substantive textbook text, without internal reasoning. /no_think")},
            {"role": "user", "content": prompt}],
        "max_tokens": 900, "temperature": round(0.69 + retry * 0.05, 2),
        "top_p": 0.9, "chat_template_kwargs": {"enable_thinking": False},
        "stream": True,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % PORT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    chunks = []
    last_checked_bytes = 0
    start = time.monotonic()
    last_progress = start
    content_events = 0
    reasoning_events = 0
    stream_event_lines = 0
    content_chars = 0
    token_word = re.compile(r"[A-Za-z][A-Za-z'-]*")

    def good_segment(body, minimum):
        prose_lines = [line.strip() for line in body.splitlines()
                       if line.strip() and not line.lstrip().startswith(("#", "|"))]
        word_list = token_word.findall(" ".join(prose_lines))
        return (len(word_list) >= minimum and
                len({w.casefold() for w in word_list}) >= 135 and
                body.rstrip().endswith((".", "!", "?")))

    with urllib.request.urlopen(req, timeout=300) as response:
        if response.status != 200:
            raise RuntimeError("INFERENCE_HTTP_NOT_OK")
        for line in response:
            now = time.monotonic()
            if error or process.poll() is not None:
                raise RuntimeError("LOW_MEMORY_OR_MODEL_EXIT_ABORT")
            if now - last_progress >= 100:
                record(result="private_original_prose_stream_progress",
                       verified_words=doc["global_verified_draft_words"],
                       next_chapter=doc["next_chapter"],
                       next_part=doc["next_part"],
                       stream_elapsed_seconds=int(now - start),
                       stream_content_chars=content_chars,
                       stream_content_events=content_events,
                       stream_reasoning_events=reasoning_events,
                       stream_event_lines=stream_event_lines)
                last_progress = now
            if now - start > 775:
                break
            if not line.startswith(b"data: "):
                continue
            stream_event_lines += 1
            raw = line[6:].strip()
            if raw == b"[DONE]":
                break
            try:
                event = json.loads(raw)
                delta_obj = event.get("choices", [{}])[0].get("delta", {})
                delta = delta_obj.get("content", "")
                reasoning = delta_obj.get("reasoning_content", "")
            except (ValueError, IndexError, KeyError, TypeError, AttributeError):
                continue
            if isinstance(reasoning, str) and reasoning:
                reasoning_events += 1
            if not isinstance(delta, str) or not delta:
                continue
            content_events += 1
            content_chars += len(delta)
            chunks.append(delta)
            if sum(map(len, chunks)) - last_checked_bytes < 120:
                continue
            body = "".join(chunks).strip()
            last_checked_bytes = len(body)
            if good_segment(body, 300):
                return body
    if error:
        raise RuntimeError("LOW_MEMORY_ABORT")
    body = "".join(chunks).strip()
    if not body:
        raise RuntimeError("EMPTY_MODEL_CONTENT_STREAM")
    if "<think>" in body or "</think>" in body:
        raise RuntimeError("MODEL_REASONING_LEAK_BLOCKED")
    if not good_segment(body, 300):
        raise RuntimeError("STREAMED_SEGMENT_BELOW_QC_SUBSTANCE")
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
               "--port", str(PORT), "-c", "4096", "-t", "2", "-ngl", "0", "--parallel", "1", "--reasoning", "off"]
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
                record(result="private_original_prose_generation_running", next_chapter=doc["next_chapter"], next_part=doc["next_part"], verified_words=doc["global_verified_draft_words"], start_available_mib=mem_before)
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
