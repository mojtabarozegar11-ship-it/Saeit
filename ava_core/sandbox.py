"""Fail-closed, disposable local evaluator for AVA code-review bundles.

Linux-only. An empty network namespace is created by ``unshare -Urn`` before
``bwrap`` constructs a read-only, allowlisted filesystem. Generated code is
never executed directly by the host Python process. No implicit fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import tempfile
import time
from typing import Mapping

from .evolution import CheckEvidence, CodeEvolutionDirector, CodeProposalError, CodeReview, DevelopmentScope


class IsolationUnavailable(RuntimeError):
    """A verified isolated runner is unavailable; code is not executed."""


@dataclass(frozen=True)
class SandboxResult:
    review_id: str
    evidence: CheckEvidence
    exit_code: int
    stdout_excerpt: str
    stderr_excerpt: str
    staged_files_removed: bool


class IsolatedReviewRunner:
    """Execute AVA regression tests only inside a disposable Linux namespace.

    The trusted host supplies a complete allowlisted source/test snapshot.
    No project worktree, secrets, sockets, /home or application data is mounted
    into the sandbox. This is a local defense-in-depth boundary, not a claim of
    security certification against kernel exploits.
    """

    MAX_FILES = 150
    MAX_SOURCE_BYTES = 2 * 1024 * 1024
    MAX_RESULT_BYTES = 256 * 1024

    def __init__(self, *, owner_id: str, timeout_seconds: int = 20,
                 memory_limit_mb: int = 512,
                 scope: DevelopmentScope | None = None,
                 max_files: int = MAX_FILES,
                 max_source_bytes: int = MAX_SOURCE_BYTES) -> None:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id is required")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be in [1, 60]")
        if type(memory_limit_mb) is not int or not 256 <= memory_limit_mb <= 2048:
            raise ValueError("memory_limit_mb must be in [256, 2048]")
        if scope is not None and not isinstance(scope, DevelopmentScope):
            raise TypeError("scope must be a DevelopmentScope")
        if type(max_files) is not int or max_files < 1:
            raise ValueError("max_files must be positive")
        if type(max_source_bytes) is not int or max_source_bytes < 1:
            raise ValueError("max_source_bytes must be positive")
        self.owner_id = owner_id
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.scope = scope if scope is not None else DevelopmentScope()
        self.max_files = max_files
        self.max_source_bytes = max_source_bytes

    @staticmethod
    def _limits(cpu_seconds: int, memory_bytes: int, output_bytes: int) -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes, output_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    @staticmethod
    def _validate_runner() -> None:
        for executable in ("/usr/bin/unshare", "/usr/bin/bwrap", "/usr/bin/python3"):
            if not Path(executable).is_file() or not os.access(executable, os.X_OK):
                raise IsolationUnavailable(f"Required isolation tool is unavailable: {executable}")
        if not Path("/usr/lib").is_dir() or not Path("/usr/lib64").is_dir():
            raise IsolationUnavailable("Required readonly Python libraries are unavailable")

    def _validate_source(self, review: CodeReview, source_tree: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(review, CodeReview) or review.owner_id != self.owner_id:
            raise PermissionError("Review owner mismatch")
        if review.syntax_checked is not True:
            raise CodeProposalError("Only syntax-checked reviews may be evaluated")
        if not isinstance(source_tree, Mapping) or not 1 <= len(source_tree) <= self.max_files:
            raise CodeProposalError("Source tree exceeds the isolated review file budget")
        clean = {}
        total = 0
        for path, source in source_tree.items():
            if not self.scope.allows(path):
                raise CodeProposalError("Unsafe source-tree path")
            if not isinstance(source, str):
                raise CodeProposalError("Source-tree values must be text")
            total += len(source.encode("utf-8"))
            if total > self.max_source_bytes:
                raise CodeProposalError("Source-tree size limit exceeded")
            clean[path] = source
        if not any(path.startswith("tests/test_ava") for path in clean):
            raise CodeProposalError("A trusted AVA regression suite is required")
        for changed in review.files:
            if not self.scope.allows(changed.path):
                raise CodeProposalError("Reviewed path is outside the isolated evaluation scope")
            if not (changed.path.startswith("ava_core/") or changed.path.startswith("tests/test_ava")):
                raise CodeProposalError("A different project needs its own verified isolated test runner")
            if changed.path in clean:
                if CodeEvolutionDirector.digest(clean[changed.path]) != changed.old_sha256:
                    raise CodeProposalError("Stale code snapshot: cannot run a different version")
            elif changed.old_sha256 is not None:
                raise CodeProposalError("Missing baseline source file")
            if CodeEvolutionDirector.digest(changed.new_source) != changed.new_sha256:
                raise CodeProposalError("Staged source digest mismatch")
            clean[changed.path] = changed.new_source
        return clean

    def evaluate(self, review: CodeReview, *, trusted_tree: Mapping[str, str]) -> SandboxResult:
        """Apply a proposal to temporary files, run isolated tests, discard all.

        A failing run returns negative CheckEvidence, which cannot authorize
        a handoff. A failure to establish isolation raises, never runs code.
        """
        clean = self._validate_source(review, trusted_tree)
        self._validate_runner()
        began = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="ava-isolated-review-") as stage:
            root = Path(stage)
            for path, source in clean.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source, encoding="utf-8")

            # unshare provides an empty network namespace without invoking
            # bwrap's blocked loopback-network configuration path.
            command = [
                "/usr/bin/unshare", "-Urn", "/usr/bin/bwrap",
                "--share-net", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
                "--die-with-parent", "--new-session",
                "--ro-bind", "/usr", "/usr",
                "--symlink", "usr/lib", "/lib",
                "--symlink", "usr/lib64", "/lib64",
                "--symlink", "usr/bin", "/bin",
                "--ro-bind", stage, "/work",
                "--proc", "/proc", "--dev", "/dev",
                "--tmpfs", "/tmp", "--tmpfs", "/scratch",
                "--chdir", "/work", "--clearenv",
                "--setenv", "PATH", "/usr/bin",
                "--setenv", "HOME", "/tmp",
                "--setenv", "PYTHONPATH", "/work",
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                "--setenv", "PYTHONNOUSERSITE", "1",
                "/usr/bin/python3", "-B", "-m", "unittest", "discover",
                "-s", "tests", "-p", "test_ava*.py", "-q",
            ]
            stdout_file = root / "stdout.log"
            stderr_file = root / "stderr.log"
            try:
                with stdout_file.open("wb") as out, stderr_file.open("wb") as err:
                    process = subprocess.Popen(
                        command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                        cwd=stage, env={"PATH": "/usr/bin", "HOME": "/tmp"},
                        start_new_session=True,
                        preexec_fn=lambda: self._limits(
                            self.timeout_seconds + 1, self.memory_limit_mb * 1024 * 1024,
                            self.MAX_RESULT_BYTES,
                        ),
                    )
                    try:
                        exit_code = process.wait(timeout=self.timeout_seconds)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        exit_code = 124
            except OSError as exc:
                raise IsolationUnavailable("Isolated subprocess could not be started") from exc

            stdout = stdout_file.read_bytes()[:self.MAX_RESULT_BYTES]
            stderr = stderr_file.read_bytes()[:self.MAX_RESULT_BYTES]
            report = stderr.decode("utf-8", errors="replace")
            matched = re.search(r"^Ran (\d+) tests? in ", report, flags=re.MULTILINE)
            test_count = int(matched.group(1)) if matched else 0
            isolated = not ("unshare: " in report or "bwrap: " in report)
            if not isolated:
                raise IsolationUnavailable("Namespace setup failed; no valid isolated result")
            passed = exit_code == 0 and test_count > 0 and re.search(r"^OK\s*$", report, re.MULTILINE) is not None
            duration_ms = round((time.monotonic() - began) * 1000)
            evidence = CheckEvidence(
                review_id=review.review_id, passed=passed, isolated=True,
                tests_run=test_count, runner="linux-unshare-bwrap-v1",
                details=(f"exit={exit_code}; elapsed_ms={duration_ms}; "
                         f"stdout_sha256={hashlib.sha256(stdout).hexdigest()}; "
                         f"stderr_sha256={hashlib.sha256(stderr).hexdigest()}"),
            )
            output_out = stdout.decode("utf-8", errors="replace")[:1200]
            output_err = report[:1200]
        return SandboxResult(
            review_id=review.review_id, evidence=evidence, exit_code=exit_code,
            stdout_excerpt=output_out, stderr_excerpt=output_err,
            staged_files_removed=not Path(stage).exists(),
        )
