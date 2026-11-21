"""Provider-neutral, no-execution self-coding review pipeline for AVA.

An injected proposer may write code. AVA only creates immutable in-memory
review bundles; an authenticated host must arrange sandbox checks and any
subsequent release. This module never reads/writes project files or runs code.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import difflib
import hashlib
import json
from typing import Callable, Mapping, Protocol


class CodeProposalError(ValueError):
    """A generated code proposal violates its review contract."""


@dataclass(frozen=True)
class DevelopmentScope:
    """Host-configurable creative workspace, not an authorization to deploy.

    By default AVA can propose edits in any ordinary source subdirectory, not
    just its own package. The trusted host still decides which file snapshots
    to provide. Prefixes can narrow access for an individual work session.
    """

    project_roots: tuple[str, ...] = ("",)
    max_edits: int = 128
    max_file_bytes: int = 2 * 1024 * 1024
    max_total_bytes: int = 32 * 1024 * 1024

    _SUFFIXES = frozenset({
        ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
        ".html", ".css", ".scss", ".json", ".yaml", ".yml",
        ".toml", ".md", ".rst", ".txt", ".sql", ".sh", ".bash",
        ".go", ".rs", ".java", ".kt", ".swift", ".c", ".h",
        ".cpp", ".hpp", ".cs", ".php", ".rb", ".xml", ".svg",
    })
    _PLAIN_NAMES = frozenset({"Dockerfile", "Makefile", "Containerfile", "Justfile"})
    _SENSITIVE_NAMES = frozenset({
        "id_rsa", "id_ed25519", "credentials", "secrets", "token",
        "authorized_keys", "known_hosts", "passwd", "shadow",
    })

    def __post_init__(self) -> None:
        if not isinstance(self.project_roots, tuple) or not self.project_roots:
            raise ValueError("project_roots must be a nonempty tuple")
        for root in self.project_roots:
            if root != "" and not self._safe_segments(root):
                raise ValueError("Unsafe development project root")
        for bound in (self.max_edits, self.max_file_bytes, self.max_total_bytes):
            if type(bound) is not int or bound < 1:
                raise ValueError("Development review resource bounds must be positive integers")

    @staticmethod
    def _safe_segments(path: str) -> bool:
        if not isinstance(path, str) or not path or "\\" in path or ":" in path:
            return False
        segments = path.split("/")
        return all(
            segment not in ("", ".", "..")
            and not segment.startswith(".")
            and not any(ord(c) < 32 or ord(c) == 127 for c in segment)
            for segment in segments
        )

    def allows(self, path: str) -> bool:
        if not self._safe_segments(path):
            return False
        leaf = path.rsplit("/", 1)[-1]
        if leaf.casefold() in self._SENSITIVE_NAMES:
            return False
        suffix = "." + leaf.rsplit(".", 1)[-1].lower() if "." in leaf else ""
        if suffix not in self._SUFFIXES and leaf not in self._PLAIN_NAMES:
            return False
        return any(not root or path.startswith(root + "/") for root in self.project_roots)


@dataclass(frozen=True)
class CodeEdit:
    path: str
    expected_sha256: str | None
    new_source: str


@dataclass(frozen=True)
class CodeProposal:
    goal: str
    rationale: str
    edits: tuple[CodeEdit, ...]


class CodeProposer(Protocol):
    """Trusted-host-injected code author, possibly backed by a model."""

    def __call__(self, goal: str, files: Mapping[str, str]) -> CodeProposal: ...


@dataclass(frozen=True)
class ReviewedFile:
    path: str
    old_sha256: str | None
    new_sha256: str
    new_source: str
    unified_diff: str


@dataclass(frozen=True)
class CodeReview:
    review_id: str
    owner_id: str
    goal: str
    rationale: str
    files: tuple[ReviewedFile, ...]
    syntax_checked: bool


@dataclass(frozen=True)
class CheckEvidence:
    """Attestation produced by an authenticated external isolated test runner."""

    review_id: str
    passed: bool
    isolated: bool
    tests_run: int
    runner: str
    details: str


@dataclass(frozen=True)
class ApprovedCodeBundle:
    """Approved handoff only: *not* a commit, merge, deployment or execution."""

    review: CodeReview
    evidence: CheckEvidence


@dataclass(frozen=True)
class RollbackFile:
    """Restore a prior source file or remove a file added by this review."""

    path: str
    action: str  # 'restore' or 'remove'
    expected_current_sha256: str
    previous_sha256: str | None
    previous_source: str | None


@dataclass(frozen=True)
class CodeRollbackPlan:
    """Verified source-state handoff only; never modifies any filesystem."""

    review_id: str
    owner_id: str
    files: tuple[RollbackFile, ...]
    plan_sha256: str


class CodeEvolutionDirector:
    """One owner-scoped control plane for model-generated code review.

    Paths and review size are configured per trusted host, with broadly useful
    defaults. Callers pass trusted file snapshots; proposals cannot fetch files
    or command the host. Python AST parsing checks syntax, not safety or quality.
    """

    def __init__(self, *, owner_id: str, proposer: CodeProposer | None = None,
                 scope: DevelopmentScope | None = None) -> None:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("Authenticated owner_id is required")
        if proposer is not None and not callable(proposer):
            raise TypeError("proposer must be callable")
        if scope is not None and not isinstance(scope, DevelopmentScope):
            raise TypeError("scope must be a DevelopmentScope")
        self.owner_id = owner_id
        self._proposer = proposer
        self.scope = scope if scope is not None else DevelopmentScope()
        self._reviews: dict[str, CodeReview] = {}

    @staticmethod
    def digest(source: str) -> str:
        if not isinstance(source, str):
            raise TypeError("Source must be text")
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def propose(self, goal: str, *, trusted_files: Mapping[str, str]) -> CodeReview:
        """Ask configured code author to propose text; stage without execution."""
        if self._proposer is None:
            raise PermissionError("No approved code proposer was configured")
        self._validate_goal(goal)
        self._validate_snapshot(trusted_files)
        proposal = self._proposer(goal, dict(trusted_files))
        return self.stage(proposal, trusted_files=trusted_files)

    @staticmethod
    def _validate_goal(goal: str) -> None:
        if not isinstance(goal, str) or not goal.strip():
            raise CodeProposalError("Goal must be nonempty")

    def _validate_snapshot(self, files: Mapping[str, str]) -> None:
        if not isinstance(files, Mapping):
            raise TypeError("Trusted file snapshot must be a mapping")
        for path, contents in files.items():
            if not self.scope.allows(path):
                raise CodeProposalError("Snapshot path is outside the configured source scope")
            if not isinstance(contents, str):
                raise CodeProposalError("Snapshot must contain source text only")

    def stage(self, proposal: CodeProposal, *, trusted_files: Mapping[str, str]) -> CodeReview:
        """Compile the proposed change *to AST only* in memory, never execute."""
        if not isinstance(proposal, CodeProposal):
            raise CodeProposalError("Expected a typed CodeProposal")
        self._validate_goal(proposal.goal)
        self._validate_snapshot(trusted_files)
        if not isinstance(proposal.rationale, str) or not proposal.rationale.strip():
            raise CodeProposalError("An explanation is required")
        if not isinstance(proposal.edits, tuple) or not 1 <= len(proposal.edits) <= self.scope.max_edits:
            raise CodeProposalError("Edit count exceeds the configured review budget")

        seen: set[str] = set()
        changed: list[ReviewedFile] = []
        total_bytes = 0
        for edit in proposal.edits:
            if not isinstance(edit, CodeEdit):
                raise CodeProposalError("Every edit must be a CodeEdit")
            if not self.scope.allows(edit.path):
                raise CodeProposalError("Unsafe file path or outside configured project scope")
            if edit.path in seen:
                raise CodeProposalError("Repeated file path")
            seen.add(edit.path)
            if not isinstance(edit.new_source, str):
                raise CodeProposalError("Code must be UTF-8 text")
            size = len(edit.new_source.encode("utf-8"))
            total_bytes += size
            if not 0 < size <= self.scope.max_file_bytes or total_bytes > self.scope.max_total_bytes:
                raise CodeProposalError("Code exceeds the configured review budget")

            old_source = trusted_files.get(edit.path)
            expected = self.digest(old_source) if old_source is not None else None
            if edit.expected_sha256 != expected:
                raise CodeProposalError("Source version mismatch; refresh the trusted snapshot")
            if old_source == edit.new_source:
                raise CodeProposalError("Empty change is not a self-improvement")
            if edit.path.endswith((".py", ".pyi")):
                try:
                    ast.parse(edit.new_source, filename=edit.path, mode="exec")
                except (SyntaxError, ValueError, RecursionError) as exc:
                    raise CodeProposalError(f"Python syntax invalid for {edit.path}") from exc
            elif edit.path.endswith(".json"):
                try:
                    json.loads(edit.new_source)
                except (ValueError, RecursionError) as exc:
                    raise CodeProposalError(f"JSON syntax invalid for {edit.path}") from exc

            diff = "".join(difflib.unified_diff(
                (old_source or "").splitlines(keepends=True),
                edit.new_source.splitlines(keepends=True),
                fromfile=f"a/{edit.path}" if old_source is not None else "/dev/null",
                tofile=f"b/{edit.path}",
            ))
            changed.append(ReviewedFile(
                path=edit.path, old_sha256=expected,
                new_sha256=self.digest(edit.new_source),
                new_source=edit.new_source, unified_diff=diff,
            ))

        # Canonical digest permits replay-safe staging of identical proposals.
        canonical = json.dumps({
            "owner_id": self.owner_id, "goal": proposal.goal,
            "rationale": proposal.rationale,
            "files": [(f.path, f.old_sha256, f.new_sha256) for f in changed],
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        review_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        review = CodeReview(
            review_id=review_id, owner_id=self.owner_id, goal=proposal.goal,
            rationale=proposal.rationale, files=tuple(changed),
            syntax_checked=all(f.path.endswith((".py", ".pyi")) for f in changed),
        )
        self._reviews[review_id] = review
        return review

    def get_review(self, review_id: str) -> CodeReview | None:
        return self._reviews.get(review_id)

    def review_count(self) -> int:
        return len(self._reviews)

    def prepare_rollback(
        self, review_id: str, *, trusted_before: Mapping[str, str],
        trusted_current: Mapping[str, str],
    ) -> CodeRollbackPlan:
        """Prepare a no-write reversal only if current code matches this review.

        The caller must independently authenticate both source snapshots. The
        returned plan is not permission to delete, restore, merge or deploy.
        """
        review = self.get_review(review_id)
        if review is None:
            raise CodeProposalError("Unknown review_id")
        self._validate_snapshot(trusted_before)
        self._validate_snapshot(trusted_current)
        rollback: list[RollbackFile] = []
        for changed in review.files:
            current = trusted_current.get(changed.path)
            if current is None or self.digest(current) != changed.new_sha256:
                raise CodeProposalError("Current source does not match this release candidate")
            previous = trusted_before.get(changed.path)
            if changed.old_sha256 is None:
                if previous is not None:
                    raise CodeProposalError("New file unexpectedly exists in baseline")
                action = "remove"
            else:
                if previous is None or self.digest(previous) != changed.old_sha256:
                    raise CodeProposalError("Original source version is unavailable")
                action = "restore"
            rollback.append(RollbackFile(
                path=changed.path, action=action,
                expected_current_sha256=changed.new_sha256,
                previous_sha256=changed.old_sha256,
                previous_source=previous,
            ))
        canonical = json.dumps({
            "review_id": review.review_id, "owner_id": review.owner_id,
            "files": [(f.path, f.action, f.expected_current_sha256, f.previous_sha256)
                      for f in rollback],
        }, sort_keys=True, separators=(",", ":"))
        return CodeRollbackPlan(
            review_id=review.review_id, owner_id=self.owner_id,
            files=tuple(rollback),
            plan_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        )

    def approve_handoff(
        self, review_id: str, *, evidence: CheckEvidence,
        authorize: Callable[[str, CodeReview], bool] | None = None,
    ) -> ApprovedCodeBundle:
        """Emit a handoff only after host-attested isolated tests and permission.

        This does not apply the patch, write files, publish a PR or deploy.
        Authorization must be obtained outside generated model text.
        """
        review = self.get_review(review_id)
        if review is None:
            raise CodeProposalError("Unknown review_id")
        if not isinstance(evidence, CheckEvidence) or evidence.review_id != review.review_id:
            raise CodeProposalError("Evidence is missing or belongs to a different revision")
        if (evidence.passed is not True or evidence.isolated is not True
                or type(evidence.tests_run) is not int or evidence.tests_run < 1
                or not isinstance(evidence.runner, str) or not evidence.runner.strip()
                or not isinstance(evidence.details, str) or not evidence.details.strip()):
            raise PermissionError("Authenticated isolated test evidence is required")
        if authorize is None or not callable(authorize) or authorize(self.owner_id, review) is not True:
            raise PermissionError("Independent host authorization required")
        return ApprovedCodeBundle(review=review, evidence=evidence)
