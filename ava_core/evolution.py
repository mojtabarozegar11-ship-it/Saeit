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
import re
from typing import Callable, Mapping, Protocol


class CodeProposalError(ValueError):
    """A generated code proposal violates the bounded review contract."""


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


class CodeEvolutionDirector:
    """One owner-scoped control plane for model-generated code review.

    Only paths in the deliberately narrow AVA Python source/test namespace are
    accepted. Callers pass trusted file snapshots; proposals cannot fetch
    files or command the host. AST parsing checks syntax, not safety or quality.
    """

    _ALLOWED_PATH = re.compile(
        r"(?:ava_core/[a-z_][a-z0-9_]*|tests/test_ava[a-z0-9_]*)\.py\Z"
    )
    _MAX_EDITS = 5
    _MAX_FILE_BYTES = 64 * 1024
    _MAX_TOTAL_BYTES = 160 * 1024

    def __init__(self, *, owner_id: str, proposer: CodeProposer | None = None) -> None:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("Authenticated owner_id is required")
        if proposer is not None and not callable(proposer):
            raise TypeError("proposer must be callable")
        self.owner_id = owner_id
        self._proposer = proposer
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
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 500:
            raise CodeProposalError("Goal must be 1-500 characters")

    def _validate_snapshot(self, files: Mapping[str, str]) -> None:
        if not isinstance(files, Mapping):
            raise TypeError("Trusted file snapshot must be a mapping")
        for path, contents in files.items():
            if not isinstance(path, str) or not self._ALLOWED_PATH.fullmatch(path):
                raise CodeProposalError("Snapshot path is outside AVA source/test boundary")
            if not isinstance(contents, str):
                raise CodeProposalError("Snapshot must contain source text only")

    def stage(self, proposal: CodeProposal, *, trusted_files: Mapping[str, str]) -> CodeReview:
        """Compile the proposed change *to AST only* in memory, never execute."""
        if not isinstance(proposal, CodeProposal):
            raise CodeProposalError("Expected a typed CodeProposal")
        self._validate_goal(proposal.goal)
        self._validate_snapshot(trusted_files)
        if not isinstance(proposal.rationale, str) or not proposal.rationale.strip() or len(proposal.rationale) > 2000:
            raise CodeProposalError("A bounded explanation is required")
        if not isinstance(proposal.edits, tuple) or not 1 <= len(proposal.edits) <= self._MAX_EDITS:
            raise CodeProposalError("One to five file edits are allowed")

        seen: set[str] = set()
        changed: list[ReviewedFile] = []
        total_bytes = 0
        for edit in proposal.edits:
            if not isinstance(edit, CodeEdit):
                raise CodeProposalError("Every edit must be a CodeEdit")
            if not isinstance(edit.path, str) or not self._ALLOWED_PATH.fullmatch(edit.path):
                raise CodeProposalError("Unsafe or unrelated file path")
            if edit.path in seen:
                raise CodeProposalError("Repeated file path")
            seen.add(edit.path)
            if not isinstance(edit.new_source, str):
                raise CodeProposalError("Code must be UTF-8 text")
            size = len(edit.new_source.encode("utf-8"))
            total_bytes += size
            if not 0 < size <= self._MAX_FILE_BYTES or total_bytes > self._MAX_TOTAL_BYTES:
                raise CodeProposalError("Code exceeds bounded review size")

            old_source = trusted_files.get(edit.path)
            expected = self.digest(old_source) if old_source is not None else None
            if edit.expected_sha256 != expected:
                raise CodeProposalError("Source version mismatch; refresh the trusted snapshot")
            if old_source == edit.new_source:
                raise CodeProposalError("Empty change is not a self-improvement")
            try:
                ast.parse(edit.new_source, filename=edit.path, mode="exec")
            except (SyntaxError, ValueError, RecursionError) as exc:
                raise CodeProposalError(f"Python syntax invalid for {edit.path}") from exc

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
            rationale=proposal.rationale, files=tuple(changed), syntax_checked=True,
        )
        self._reviews[review_id] = review
        return review

    def get_review(self, review_id: str) -> CodeReview | None:
        return self._reviews.get(review_id)

    def review_count(self) -> int:
        return len(self._reviews)

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
