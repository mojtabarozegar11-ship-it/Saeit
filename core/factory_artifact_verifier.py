"""Independent tests and static security checks for immutable Factory artifacts."""
import hashlib
import json
import re
from pathlib import Path


class ArtifactVerificationError(RuntimeError):
    pass


class StaticResearchBriefVerifier:
    """Independent read-only test/security verifier for immutable build artifacts."""
    FORBIDDEN = (
        re.compile(rb"<script", re.I),
        re.compile(rb"(?:^|[<\\s])on[a-z]+[\\t ]*=", re.I),
        re.compile(rb"javascript[ ]*:", re.I),
        re.compile(rb"eval[(]", re.I),
        re.compile(rb"(?:api[_-]?key|secret|password|token)[\\t ]*[:=][\\t ]*['\"][^'\"]{8,}", re.I),
    )

    @staticmethod
    def _content(artifact):
        path = Path(artifact.reference).resolve()
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != artifact.content_digest:
            raise ArtifactVerificationError("Artifact digest changed after Builder completion.")
        return content, digest

    def test(self, artifact, spec, *, task, authorization, authorization_check):
        if not callable(authorization_check) or not authorization_check(authorization, task, "product_test"):
            raise ArtifactVerificationError("Independent Tester requires current ToolGateway authorization.")
        content, digest = self._content(artifact)
        text = content.decode("utf-8")
        expected_sources = len(spec.get("evidence_references", []))
        checks = {
            "valid_utf8_html": text.startswith("<!doctype html>") and "</html>" in text,
            "problem_present": str(spec.get("problem") or "") in text,
            "all_source_findings_present": text.count("<li><a href=") == expected_sources and expected_sources > 0,
            "acceptance_criteria_present": bool(spec.get("acceptance_criteria")),
        }
        result = {"passed": all(checks.values()), "suite": "static-research-brief-tests-v2",
                  "checks": checks, "build_digest": digest, "spec_digest": spec.get("digest"),
                  "tester": "factory-independent-test-agent", "execution_id": task.execution_id}
        result["attestation_digest"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        if not result["passed"]:
            raise ArtifactVerificationError(f"Independent Test failed: {[k for k,v in checks.items() if not v]}")
        return result

    def security(self, artifact, spec, *, task, authorization, authorization_check):
        if not callable(authorization_check) or not authorization_check(authorization, task, "product_security"):
            raise ArtifactVerificationError("Independent Security verifier requires current ToolGateway authorization.")
        content, digest = self._content(artifact)
        findings = [pattern.pattern.decode("ascii") for pattern in self.FORBIDDEN if pattern.search(content)]
        result = {"passed": not findings, "scanner": "static-research-brief-security-v2",
                  "findings": findings, "severity": "HIGH" if findings else "NONE",
                  "build_digest": digest, "spec_digest": spec.get("digest"),
                  "verifier": "factory-independent-security-agent", "execution_id": task.execution_id}
        result["attestation_digest"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        if not result["passed"]:
            raise ArtifactVerificationError(f"Independent Security failed; blocking findings={findings}")
        return result

    def verify(self, artifact, spec, *, task, authorization, authorization_check):
        """Compatibility helper; new autonomous lifecycle uses separate specialists."""
        tests = self.test(artifact, spec, task=task, authorization=authorization, authorization_check=authorization_check)
        security = self.security(artifact, spec, task=task, authorization=authorization, authorization_check=authorization_check)
        return tests, security

