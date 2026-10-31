#!/usr/bin/env python3
"""Private MojPlayWin backup TAR member classifier; no file names or content logged.

Used in-memory on the backup VPS with its existing GPG verifier. It does not
extract, write, upload or print archive contents. The classifier only reports
coarse categories required to investigate the 2026-10-22 unsafe_member abort.
"""
from __future__ import annotations

from collections import Counter
import json
import os
import posixpath
import tarfile
import threading
from pathlib import PurePosixPath

ROOTS = frozenset(("Saeit-staging", "mojplaywin.com"))
MAX_ENTRIES = 150_000


def member_category(name):
    """Match the safe extractor's rejection gate without revealing the path."""
    if not isinstance(name, str) or not name:
        return "empty_or_invalid"
    if name.startswith("/"):
        return "absolute"
    if name.startswith("./"):
        return "dot_prefix"
    parts = PurePosixPath(name).parts
    if not parts:
        return "empty_or_invalid"
    if ".." in parts or "" in parts:
        return "parent_traversal"
    if parts[0] not in ROOTS:
        return "outside_approved_roots"
    return "approved_root"



def link_category(name, target, is_symlink):
    """Mirror extractor link-target normalization, never return a path."""
    if not isinstance(target, str):
        return "invalid_link_target"
    parts = PurePosixPath(name).parts
    if target.startswith("/"):
        if not is_symlink:
            return "absolute_hardlink_rejected"
        try:
            relative = PurePosixPath(target).relative_to("/home/zomorod2")
        except ValueError:
            return "unbacked_absolute_symlink"
        candidate = str(relative)
    elif is_symlink:
        candidate = posixpath.normpath(posixpath.join(*parts[:-1], target))
    else:
        candidate = posixpath.normpath(target)
    category = member_category(candidate)
    return ("inside_approved_roots" if category == "approved_root"
            else category)

def classify_tar(stream):
    """Consume archive headers, not payload content, then drain to GPG EOF."""
    counts = Counter()
    link_counts = Counter()
    entries = 0
    tar_status = "PASS"
    try:
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            for member in archive:
                entries += 1
                if entries > MAX_ENTRIES:
                    tar_status = "MEMBER_LIMIT"
                    break
                counts[member_category(member.name)] += 1
                if member.issym() or member.islnk():
                    kind = 'symlink' if member.issym() else 'hardlink'
                    link_counts[kind + '_' + link_category(member.name, member.linkname, member.issym())] += 1
    except (tarfile.TarError, OSError, ValueError, UnicodeError):
        tar_status = "TAR_PARSE_FAILURE"
    # The encrypted source has an authenticated footer after the tar end.
    # Drain everything so GPG and the source SHA/footer check reach EOF.
    while stream.read(131072):
        pass
    return {"member_count_capped": min(entries, MAX_ENTRIES),
            "categories": dict(sorted(counts.items())),
            "link_target_categories": dict(sorted(link_counts.items())),
            "tar_read_status": tar_status}


def main(recovery):
    """The caller injects the trusted existing recovery module, not a path."""
    stems = recovery.discover()
    reader_fd, writer_fd = os.pipe()
    producer_errors = []

    def produce():
        try:
            with os.fdopen(writer_fd, "wb", buffering=0) as output:
                recovery.decrypt_to_stdout(
                    "files", out=output, stem=stems["files"])
        except BaseException:
            producer_errors.append("VERIFICATION_FAILED")

    producer = threading.Thread(target=produce, name="archive-decrypt", daemon=True)
    producer.start()
    try:
        with os.fdopen(reader_fd, "rb", buffering=0) as input_file:
            result = classify_tar(input_file)
    finally:
        producer.join(timeout=15)
    result.update({
        "classification": "PRIVATE_ARCHIVE_MEMBER_CATEGORIES_ONLY",
        "source_integrity_verified": not producer.is_alive() and not producer_errors,
        "production_modified": False,
        "archive_extracted": False,
        "sql_rows_read": False,
        "member_names_logged": False,
    })
    print("MPW_PRIVATE_ARCHIVE_MEMBER_DIAG=" + json.dumps(result, sort_keys=True))
    return 0 if result["source_integrity_verified"] and result["tar_read_status"] == "PASS" else 1
