"""Independent tests and static security checks for immutable Factory artifacts."""
import hashlib
import re
from pathlib import Path


class ArtifactVerificationError(RuntimeError):
    pass


class StaticResearchBriefVerifier:
    """Reads the stored artifact by reference and never trusts Builder pass claims."""
    FORBIDDEN = (
        re.compile(rb"<script", re.I),
        re.compile(rb"(?:^|[<\s])on[a-z]+[\t ]*=", re.I),
        re.compile(rb"javascript[ ]*:", re.I),
        re.compile(rb"eval[(]", re.I),
    )

    def verify(self, artifact, spec):
        path = Path(artifact.reference).resolve()
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != artifact.content_digest:
            raise ArtifactVerificationError("Artifact digest changed after Builder completion.")
        text = content.decode("utf-8")
        expected_sources = len(spec.get("evidence_ids", []))
        checks = {
            "valid_utf8_html": text.startswith("<!doctype html>") and "</html>" in text,
            "problem_present": str(spec.get("problem") or "") in text,
            "all_source_findings_present": text.count("<li><a href=") == expected_sources and expected_sources > 0,
            "acceptance_criteria_present": bool(spec.get("acceptance_criteria")),
        }
        findings = [pattern.pattern.decode("ascii") for pattern in self.FORBIDDEN if pattern.search(content)]
        security = {"passed": not findings, "scanner": "static-research-brief-security-v1",
                    "findings": findings, "artifact_digest": digest}
        tests = {"passed": all(checks.values()), "runner": "static-research-brief-tests-v1",
                 "checks": checks, "artifact_digest": digest}
        if tests["passed"] is not True or security["passed"] is not True:
            failed_checks = [name for name, passed in checks.items() if not passed]
            raise ArtifactVerificationError(
                f"Independent Test/Security gate failed; failed_checks={failed_checks}; security_findings={findings}"
            )
        return tests, security
