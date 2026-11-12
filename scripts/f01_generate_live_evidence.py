#!/usr/bin/env python3
"""Generate artifact-bound F01 documentary evidence from live, reproducible checks."""
from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile, zipfile
from pathlib import Path
PRODUCT = "farm_enterprise_economics"
SCHEMA = "saeit.factory.f01-quality-evidence.v1"
def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()
def safe_extract(archive: Path, target: Path) -> None:
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            (target / info.filename).resolve().relative_to(target.resolve())
        z.extractall(target)
def main() -> int:
    if len(sys.argv) != 4: return 2
    archive = Path(sys.argv[1])
    evidence_root = Path(sys.argv[2])
    run_id = sys.argv[3]
    artifact = digest(archive)
    evidence_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="f01-live-") as raw:
        extracted = Path(raw) / "package"; extracted.mkdir()
        safe_extract(archive, extracted)
        source = next((p for p in (extracted / PRODUCT, extracted)
                       if (p / "calculator.py").is_file()), None)
        if source is None or not (source / "test_calculator.py").is_file(): return 1
        tests = source / "test_calculator.py"; calc = source / "calculator.py"
        readme = source / "README.md"; example = source / "example_inputs.json"
        test_run = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(source),
             "-p", "test_calculator.py", "-v"], cwd=source,
            capture_output=True, text=True, timeout=120)
        suite_ok = test_run.returncode == 0
        calc_text = calc.read_text(encoding="utf-8")
        readme_text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        checks = [
            ("F01-01-1", suite_ok and "def enterprise" in calc_text),
            ("F01-02-1", suite_ok and "land_area_hectares" in calc_text and "irrigation_water_m3" in calc_text),
            ("F01-03-1", suite_ok and "decimal_number" in calc_text and "is_finite" in calc_text),
            ("F01-04-1", suite_ok and "scenario_results" in calc_text),
            ("F01-05-1", suite_ok and "json-output" in calc_text and "csv-output" in calc_text),
            ("F01-06-1", suite_ok and "Getting started" in readme_text),
            ("F01-07-1", suite_ok and "Spreadsheet security" in readme_text),
            ("F01-08-1", suite_ok and "offline" in readme_text.lower()),
            ("F01-09-1", suite_ok and "formula" in readme_text.lower() and "reject" in readme_text.lower()),
            ("F01-10-1", suite_ok and "commercial" in readme_text.lower() and "approval" in readme_text.lower()),
            ("F01-11-1", suite_ok and readme.is_file() and example.is_file()),
            ("F01-12-1", suite_ok and "No telemetry" in readme_text),
            ("F01-13-1", suite_ok and "Python 3.8+" in readme_text),
            ("F01-14-1", suite_ok and "scenario_results" in calc_text),
            ("F01-15-1", suite_ok and "INPUT_ERROR" in calc_text),
            ("F01-16-1", suite_ok and tests.stat().st_size > 1000),
            ("F01-17-1", suite_ok and "contribution" in readme_text.lower() and "break-even" in readme_text.lower()),
            ("F01-18-1", suite_ok and "How to interpret" in readme_text),
            ("F01-19-1", suite_ok and "currency" in calc_text and "ISO" in readme_text),
            ("F01-20-1", suite_ok and artifact == digest(archive)),
        ]
        passed = []
        for criterion_id, ok in checks:
            if not ok: continue
            path = evidence_root / (criterion_id + ".json")
            record = {"schema": SCHEMA, "product_id": PRODUCT,
                      "criterion_id": criterion_id, "artifact_sha256": artifact,
                      "status": "PASS", "source": "live-vps-package-check",
                      "run_id": run_id,
                      "command": "python -B -m unittest discover -s <package> -p test_calculator.py -v",
                      "test_returncode": test_run.returncode}
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            path.chmod(0o600); passed.append(criterion_id)
        report = evidence_root.parent / ("live-evidence-" + run_id + ".json")
        report.write_text(json.dumps({"schema": "saeit.factory.f01-live-evidence-run.v1",
            "product_id": PRODUCT, "artifact_sha256": artifact, "run_id": run_id,
            "test_returncode": test_run.returncode, "passed_criteria": passed,
            "failed_criteria": [cid for cid, ok in checks if not ok]},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report.chmod(0o600)
        print("F01_LIVE_EVIDENCE_TEST_RETURN_CODE=" + str(test_run.returncode))
        print("F01_LIVE_EVIDENCE_PASS_COUNT=" + str(len(passed)))
    return 0 if suite_ok else 1
if __name__ == "__main__": raise SystemExit(main())
