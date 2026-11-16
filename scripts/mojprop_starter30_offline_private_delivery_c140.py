"""Prepare one buyer-specific Starter30 EDUCATIONAL HTML report OFFLINE.

Operator-only file converter. Reads a completed private journal and writes
one private HTML artifact for independent, *later* buyer verification.
Does NOT prove the case belongs to a customer, perform payment checks,
create a receipt, send mail, publish files or grant any paid entitlement.
This module does not import Django, network, wallet or e-mail libraries.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat

from scripts.mojprop_starter30_journal_csv import parse_journal_csv, MAX_BYTES
from scripts.mojprop_starter30_scorecard import render_private_scorecard, _ID


class PrivateReportRejected(ValueError):
    """No report was authorized or produced."""


def _private_directory(directory: Path) -> None:
    if not directory.is_absolute():
        raise PrivateReportRejected("absolute private directory required")
    try:
        absolute = Path(os.path.abspath(directory))
        # Refuse symlinks in any parent, not just the last path component.
        if directory.resolve(strict=True) != absolute:
            raise PrivateReportRejected("symlink in private directory ancestry")
        state = directory.lstat()
    except OSError as exc:
        raise PrivateReportRejected("private directory inaccessible") from exc
    if (not stat.S_ISDIR(state.st_mode) or state.st_uid != os.geteuid()
            or state.st_mode & 0o077):
        raise PrivateReportRejected("directory must be owned and mode 0700")


def _read_private_csv(source: Path) -> bytes:
    _private_directory(source.parent)
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise PrivateReportRejected("private CSV unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_mode & 0o077
                or not 1 <= info.st_size <= MAX_BYTES):
            raise PrivateReportRejected("unsafe private CSV file metadata")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) != info.st_size:
            raise PrivateReportRejected("private CSV changed while reading")
        return data
    finally:
        os.close(fd)


def create_private_report(*, source_csv: Path, private_output_dir: Path,
                          case_reference: str) -> Path:
    """Create a single 0600 HTML report without overwrites or customer logs.

    The case_reference must be generated and authenticated by the operator's
    separate customer/account system; its syntax is not proof of ownership.
    A complete journal is required; no placeholder/partial scorecard is
    considered a paid deliverable.
    """
    if type(case_reference) is not str or _ID.fullmatch(case_reference) is None:
        raise PrivateReportRejected("opaque MPS30 case reference required")
    if type(source_csv) is not Path or type(private_output_dir) is not Path:
        raise PrivateReportRejected("explicit trusted local Path arguments required")
    if not source_csv.is_absolute() or not private_output_dir.is_absolute():
        raise PrivateReportRejected("absolute paths required")
    _private_directory(private_output_dir)
    rows = parse_journal_csv(_read_private_csv(source_csv))
    if len(rows) != 10:
        raise PrivateReportRejected("exactly 10 journal sessions required for delivery")
    report = render_private_scorecard(rows, case_reference).encode("utf-8")
    if len(report) > 64_000:
        raise PrivateReportRejected("report exceeds reviewed private output limit")

    target = private_output_dir / (case_reference + ".html")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise PrivateReportRejected("report already exists: overwrite forbidden") from exc
    except OSError as exc:
        raise PrivateReportRejected("private report destination unavailable") from exc
    created = True
    try:
        with os.fdopen(fd, "wb", closefd=True) as file:
            file.write(report)
            file.flush()
            os.fsync(file.fileno())
        created = False
        directory_fd = os.open(private_output_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline Starter30 private educational report")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--case-ref", required=True)
    args = parser.parse_args()
    create_private_report(source_csv=args.csv,
                          private_output_dir=args.private_output_dir,
                          case_reference=args.case_ref)
    # Never reveal customer names, filenames or content in a shared runner log.
    print("STARTER30_PRIVATE_REPORT=CREATED; PAID=NOT_ASSERTED; EMAIL=NOT_SENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
