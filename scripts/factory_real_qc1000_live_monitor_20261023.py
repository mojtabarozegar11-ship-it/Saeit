#!/usr/bin/env python3
"""Private live QC1000: independently validate *executed* scenario evidence.

One hundred rubric groups worth ten points each are not 1,000 executed tests.
This monitor never converts a score, a synthetic fixture, or a signature alone
into scientific certification. It accepts only 1,000 distinct, version-bound,
integrity-checked execution receipts signed by a separately trusted runner.
Human domain/rights review and release authorization remain independent gates.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

SCHEMA = "saeit.factory.qc1000.live-monitor.v1"
SUITE_SCHEMA = "saeit.factory.qc1000.real-executions.v1"
CASE_SCHEMA = "saeit.factory.qc1000.case-execution.v1"
SHA = re.compile(r"[a-f0-9]{64}\Z")
ORDER_FILE = re.compile(r"WO-[0-9]{8}--r[0-9]{3}\.json\Z")
CASE_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{7,100}\Z")
GROUPS = {"Q%03d" % n for n in range(1, 101)}
MAX_SUITE = 2_000_000
MAX_CASE = 16_384
MAX_ARCHIVE = 12_000_000


class QCFault(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise QCFault(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path, limit):
    require(path.is_file() and not path.is_symlink(), "EVIDENCE_FILE_MISSING_OR_LINK")
    require(0 < path.stat().st_size <= limit, "EVIDENCE_FILE_SIZE_INVALID")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise QCFault("EVIDENCE_JSON_INVALID") from exc


def bounded_child(root, relative, max_size):
    require(isinstance(relative, str) and 1 <= len(relative) <= 230,
            "EVIDENCE_PATH_INVALID")
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts,
            "EVIDENCE_PATH_TRAVERSAL")
    path = root
    for element in part.parts:
        path = path / element
        require(not path.is_symlink(), "EVIDENCE_SYMLINK")
    require(path.is_file() and root in path.parents, "EVIDENCE_BYTES_MISSING")
    require(0 < path.stat().st_size <= max_size, "EVIDENCE_BYTES_SIZE_INVALID")
    return path


def verify_artifact(area, receipt):
    require(receipt.get("ready_for_paid_store") is False
            and receipt.get("scientific_quality_certified") is False
            and receipt.get("public_distribution_allowed") is False,
            "ARTIFACT_ALREADY_CLAIMS_UNVERIFIED_RELEASE")
    digest = receipt.get("zip_sha256")
    require(isinstance(digest, str) and SHA.fullmatch(digest),
            "ARTIFACT_HASH_MISSING")
    path = bounded_child(area, receipt.get("archive_relative_path"), MAX_ARCHIVE)
    raw = path.read_bytes()
    require(sha(raw) == digest, "ARTIFACT_HASH_MISMATCH")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()
            require(0 < len(members) <= 256, "ARTIFACT_ZIP_MEMBER_COUNT")
            require(sum(m.file_size for m in members) <= 32_000_000,
                    "ARTIFACT_ZIP_EXPANSION_UNBOUNDED")
            for member in members:
                require(member.file_size <= 8_000_000 and not (member.flag_bits & 1),
                        "ARTIFACT_ZIP_MEMBER_UNSAFE")
                require(not member.filename.startswith("/")
                        and ".." not in Path(member.filename).parts,
                        "ARTIFACT_ZIP_TRAVERSAL")
                mode = (member.external_attr >> 16) & 0o170000
                require(mode in (0, 0o100000, 0o040000),
                        "ARTIFACT_ZIP_SYMLINK_OR_DEVICE")
            require(archive.testzip() is None, "ARTIFACT_ZIP_CRC_INVALID")
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise QCFault("ARTIFACT_ZIP_UNREADABLE") from exc
    return digest


def verify_runner_signature(document, pubkey):
    require(pubkey.is_file() and not pubkey.is_symlink()
            and 0 < pubkey.stat().st_size < 8192,
            "NO_PINNED_TRUSTED_RUNNER")
    signature = document.get("signature_hex")
    require(isinstance(signature, str)
            and re.fullmatch(r"[a-f0-9]{768}", signature) is not None,
            "RUNNER_SIGNATURE_MISSING")
    payload = dict(document)
    payload.pop("signature_hex", None)
    try:
        with tempfile.TemporaryDirectory(prefix="qc1000-verifier-") as tmp:
            base = Path(tmp)
            # RSA-3072/PSS-SHA256 is supported by OpenSSL 1.1.1 and 3.x.
            # Domain separation prevents cross-protocol signature reuse.
            (base / "payload").write_bytes(
                b"SAEIT_REAL_QC1000_RSA_PSS_V1\x00" + canonical(payload))
            (base / "signature").write_bytes(bytes.fromhex(signature))
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(pubkey),
                 "-sigopt", "rsa_padding_mode:pss",
                 "-sigopt", "rsa_pss_saltlen:digest",
                 "-signature", str(base / "signature"), str(base / "payload")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=10)
        require(result.returncode == 0, "UNTRUSTED_RUNNER_SIGNATURE")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QCFault("RUNNER_SIGNATURE_CHECK_UNAVAILABLE") from exc


def parse_time(value):
    require(isinstance(value, str), "EXECUTION_TIME_MISSING")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QCFault("EXECUTION_TIME_INVALID") from exc


def verify_real_suite(suite_path, artifact_sha, pubkey):
    """Verifies authentic runner attestation and 1,000 distinct evidence bytes.

    Never claims that signed measurements substitute for scientific review.
    """
    suite = read_json(suite_path, MAX_SUITE)
    require(isinstance(suite, dict) and suite.get("schema") == SUITE_SCHEMA,
            "WRONG_REAL1000_SUITE_SCHEMA")
    require(suite.get("artifact_sha256") == artifact_sha,
            "REAL1000_SUITE_WRONG_ARTIFACT")
    cases = suite.get("cases")
    require(isinstance(cases, list) and len(cases) == 1000,
            "REAL1000_REQUIRES_1000_EXECUTIONS")
    seen_ids, seen_spec, counts = set(), set(), Counter()
    for item in cases:
        require(isinstance(item, dict), "CASE_INVALID")
        cid = item.get("scenario_id")
        group = item.get("criterion_id")
        spec = item.get("scenario_spec_sha256")
        receipt_hash = item.get("execution_receipt_sha256")
        require(isinstance(cid, str) and CASE_ID.fullmatch(cid),
                "CASE_ID_INVALID")
        require(cid not in seen_ids, "DUPLICATE_SCENARIO_ID")
        require(group in GROUPS, "CASE_CRITERION_INVALID")
        require(isinstance(spec, str) and SHA.fullmatch(spec),
                "CASE_SPEC_HASH_MISSING")
        require(spec not in seen_spec, "DUPLICATE_SCENARIO_DEFINITION")
        require(isinstance(receipt_hash, str) and SHA.fullmatch(receipt_hash),
                "CASE_RECEIPT_HASH_INVALID")
        require(item.get("result") == "PASSED", "CASE_NOT_PASSED")
        seen_ids.add(cid)
        seen_spec.add(spec)
        counts[group] += 1
    require(set(counts) == GROUPS and all(counts[g] == 10 for g in GROUPS),
            "REAL1000_REQUIRES_TEN_DISTINCT_CASES_PER_CRITERION")
    verify_runner_signature(suite, pubkey)
    for item in cases:
        cid = item["scenario_id"]
        relative = item.get("execution_receipt_path")
        raw = bounded_child(suite_path.parent, relative, MAX_CASE).read_bytes()
        require(sha(raw) == item["execution_receipt_sha256"],
                "CASE_EVIDENCE_HASH_MISMATCH")
        try:
            evidence = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise QCFault("CASE_EVIDENCE_INVALID_JSON") from exc
        require(isinstance(evidence, dict)
                and evidence.get("schema") == CASE_SCHEMA
                and evidence.get("scenario_id") == cid
                and evidence.get("criterion_id") == item["criterion_id"]
                and evidence.get("scenario_spec_sha256") == item["scenario_spec_sha256"]
                and evidence.get("artifact_sha256") == artifact_sha,
                "CASE_EVIDENCE_WRONG_VERSION_OR_ID")
        require(evidence.get("execution_mode") == "real_executed_test"
                and evidence.get("status") == "PASSED"
                and type(evidence.get("exit_code")) is int
                and evidence["exit_code"] == 0,
                "CASE_EXECUTION_NOT_VERIFIED")
        for key in ("input_sha256", "expected_sha256", "observed_sha256",
                    "test_program_sha256"):
            require(isinstance(evidence.get(key), str)
                    and SHA.fullmatch(evidence[key]),
                    "CASE_EXECUTION_EVIDENCE_INCOMPLETE")
        started, finished = parse_time(evidence.get("started_utc")), parse_time(
            evidence.get("finished_utc"))
        require(started.tzinfo is not None and finished.tzinfo is not None
                and started <= finished, "CASE_EXECUTION_INTERVAL_INVALID")
    return {"verified_distinct_scenarios": 1000,
            "criteria_with_ten_scenarios": 100,
            "runner_signature_verified": True,
            "professionally_quality_certified": False,
            "independent_domain_and_rights_attestation_required": True}


def atomic_json(path, obj):
    require(not path.is_symlink() and not path.parent.is_symlink(),
            "QC_STATUS_UNSAFE_LINK")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".qc1000-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(canonical(obj) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def scan(root, pubkey, limit=20):
    """Bounded one-tick QC-only scan; no production or storefront writes."""
    area = Path(root).resolve() / "production-instructions"
    require(area.is_dir() and not area.is_symlink(), "QC_FACTORY_PRIVATE_ROOT_MISSING")
    receipts = area / "stage-05/downloadable-receipts"
    stage = area / "stage-06"
    require(receipts.is_dir() and not receipts.is_symlink()
            and stage.is_dir() and not stage.is_symlink(), "QC_PRIVATE_LANES_MISSING")
    lock = stage / ".real-qc1000-monitor.lock"
    require(not lock.is_symlink(), "QC_LOCK_UNSAFE")
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(), 0o600)
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"schema": SCHEMA, "already_running": True}
        names = sorted(p.name for p in receipts.iterdir()
                       if p.is_file() and not p.is_symlink()
                       and ORDER_FILE.fullmatch(p.name))
        require(len(names) <= 20000, "QC_CANDIDATE_LIST_UNBOUNDED")
        state_file = stage / "real-qc1000-health.json"
        prev = read_json(state_file, 30000) if state_file.is_file() else {}
        position = prev.get("next_cursor", 0)
        require(type(position) is int and position >= 0, "QC_CURSOR_INVALID")
        start = position % len(names) if names else 0
        chosen = [names[(start+i) % len(names)]
                  for i in range(min(limit, len(names)))]
        verdicts = Counter()
        verified_cases = 0
        for filename in chosen:
            reason = "UNKNOWN"
            details = {}
            try:
                receipt = read_json(receipts / filename, 150000)
                artifact = verify_artifact(area, receipt)
                suite = stage / "real-qc1000-executions" / filename[:-5] / artifact / "suite.json"
                require(not any(p.is_symlink() for p in
                                (suite, suite.parent, suite.parent.parent,
                                 suite.parent.parent.parent)),
                        "QC_SUITE_SYMLINK")
                require(suite.is_file(), "NO_REAL1000_EXECUTION_SUITE")
                details = verify_real_suite(suite, artifact, Path(pubkey))
                verified_cases += details["verified_distinct_scenarios"]
                reason = "MEASURED_1000_PENDING_AUTHENTIC_INDEPENDENT_REVIEW"
            except (QCFault, TypeError, KeyError, OSError, zipfile.BadZipFile) as exc:
                reason = str(exc) if isinstance(exc, QCFault) else type(exc).__name__
                reason = "BLOCKED_" + re.sub(r"[^A-Za-z0-9_]", "_", reason)[:90]
            verdicts[reason] += 1
            # Dedicated QC-only file; version bound, no original receipt mutation.
            result_path = stage / "real-qc1000-verdicts" / filename
            atomic_json(result_path, {
                "schema": SCHEMA, "order_file": filename, "verdict": reason,
                "execution_verification": details,
                "scientific_certification": False,
                "professional_quality_1000_approved": False,
                "commercial_release_allowed": False,
                "public_sites_modified": False})
        result = {
            "schema": SCHEMA, "updated_utc": datetime.now(timezone.utc).isoformat(),
            "scanner_health": "RUNNING", "indexed_candidates": len(names),
            "trusted_execution_runner_enrolled": Path(pubkey).is_file()
                and not Path(pubkey).is_symlink(),
            "inspected_this_tick": len(chosen),
            "next_cursor": (start + len(chosen)) % len(names) if names else 0,
            "actual_execution_scenarios_evidence_verified_this_tick": verified_cases,
            "verdict_counts": dict(sorted(verdicts.items())),
            "professional_quality_1000_certifications_created": 0,
            "public_products_released": 0, "public_sites_modified": False,
            "hard_gate": "1000 distinct signed execution receipts, 10 per 100 rubric criteria; no P0; separate authentic experts",
            "health_not_equivalent_to_product_pass": True,
        }
        atomic_json(state_file, result)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--trusted-runner-pubkey", required=True)
    parser.add_argument("--batch", type=int, default=20)
    a = parser.parse_args()
    require(1 <= a.batch <= 250, "QC_BATCH_RANGE")
    print(json.dumps(scan(a.factory_private, a.trusted_runner_pubkey, a.batch),
                     ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("QC1000_HEALTH_FAILURE:" + type(exc).__name__ + ":" + str(exc)[:120],
              file=sys.stderr)
        raise SystemExit(1)
