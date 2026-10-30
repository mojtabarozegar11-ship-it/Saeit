#!/usr/bin/env python3
"""S-01 -> G-01: offline, rights-gated Ramadan Web package builder.

Reads only a supplied local game source directory. No SSH, deploy, network,
payment, factory, database, or GitHub action. Does not assert licensing or
commercial release. ZIP stays on the operator's private filesystem.
"""
import argparse
import ast
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import stat
import zipfile
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

MAX_FILE = 40 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
REQUIRED = {"index.html", "game.js", "tactical-map.mjs",
            "objective-navigation.mjs", "campaign-backup.mjs",
            "THREE-LICENSE.txt", "ASSET-CREDITS.md"}


def safe_read(root, relative):
    path = PurePosixPath(relative)
    if (path.is_absolute() or not path.parts or
            any(part in ("", ".", "..") for part in path.parts) or
            str(path) != relative):
        raise ValueError("unsafe asset path")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_fd = os.open(root, flags)
    try:
        for part in path.parts[:-1]:
            next_fd = os.open(part, flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=parent_fd)
        try:
            before = os.fstat(file_fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_size < 1 or before.st_size > MAX_FILE):
                raise ValueError("unsafe asset type or size")
            with os.fdopen(os.dup(file_fd), "rb") as stream:
                data = stream.read(MAX_FILE + 1)
            after = os.fstat(file_fd)
            signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
            if len(data) != before.st_size or signature(before) != signature(after):
                raise ValueError("asset changed during read")
            return data
        finally:
            os.close(file_fd)
    finally:
        os.close(parent_fd)


def assets_from_deploy(source):
    tree = ast.parse(source.decode("utf-8"))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "ASSETS"
                           for t in node.targets)]
    if len(assignments) != 1:
        raise ValueError("exactly one static ASSETS list required")
    names = ast.literal_eval(assignments[0].value)
    if (not isinstance(names, list) or not 5 <= len(names) <= 80
            or any(not isinstance(name, str) for name in names)
            or len(names) != len(set(names)) or not REQUIRED.issubset(names)):
        raise ValueError("invalid or incomplete release asset contract")
    for name in names:
        p = PurePosixPath(name)
        if (p.is_absolute() or str(p) != name or
                any(part in ("", ".", "..") for part in p.parts)):
            raise ValueError("release path escape")
    return names


class _EntrypointReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "base":
            raise ValueError("base URL forbidden in offline game package")
        # Source, responsive image and video-poster dependencies must be
        # present in the signed asset list; otherwise a private ZIP may look
        # complete while its real browser entrypoint requests missing files.
        if tag in ("script", "img", "source", "audio", "video", "track") and values.get("src"):
            self.refs.append(values["src"])
        if tag == "video" and "poster" in values:
            self.refs.append(values["poster"])
        if tag in ("img", "source") and "srcset" in values:
            candidates = values["srcset"].split(",")
            for candidate in candidates:
                tokens = candidate.strip().split()
                if (not tokens or len(tokens) > 2 or
                        (len(tokens) == 2 and not re.fullmatch(
                            r"(?:[1-9][0-9]*w|(?:[1-9][0-9]*(?:\\.[0-9]+)?)x)",
                            tokens[1]))):
                    raise ValueError("unsafe responsive game dependency")
                self.refs.append(tokens[0])
        if tag == "link" and "stylesheet" in (values.get("rel") or "").lower():
            self.refs.append(values.get("href", ""))


def validate_entrypoint_references(html, asset_names):
    """Fail closed on missing/off-origin HTML dependencies before private ZIP."""
    parser = _EntrypointReferences()
    parser.feed(html.decode("utf-8"))
    found = set()
    for raw in parser.refs:
        if not raw or raw.startswith("//") or "\\" in raw:
            raise ValueError("unsafe game entrypoint dependency")
        url = urlsplit(raw)
        if url.scheme or url.netloc or url.fragment:
            raise ValueError("remote or fragment game dependency")
        name = unquote(url.path)
        if "%" in name or not name.startswith("./"):
            raise ValueError("ambiguous or nonlocal game dependency")
        rel = name[2:]
        path = PurePosixPath(rel)
        if (path.is_absolute() or str(path) != rel or
                any(part in ("", ".", "..") for part in path.parts) or
                rel not in asset_names):
            raise ValueError("missing or escaping game dependency")
        found.add(rel)
    if not {"game.js", "game.css"}.issubset(found):
        raise ValueError("game entrypoint missing required script or stylesheet")
    return len(found)


def build(source_dir, output_zip):
    root = Path(source_dir)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe source root")
    assets = assets_from_deploy(safe_read(root, "deploy.py"))
    files = {}
    total = 0
    for name in assets + [".htaccess"]:
        data = safe_read(root, name)
        total += len(data)
        if total > MAX_TOTAL:
            raise ValueError("release exceeds private package limit")
        files[name] = data
    validate_entrypoint_references(files["index.html"], set(files))
    if files[".htaccess"] != b"PassengerEnabled off\nDirectoryIndex index.html\n":
        raise ValueError("game route configuration changed")
    if (b"./tactical-map.mjs" not in files["game.js"]
            or b"./objective-navigation.mjs" not in files["game.js"]
            or b"./campaign-backup.mjs" not in files["game.js"]
            or b"relativeDirection" not in files["tactical-map.mjs"]
            or b"objectiveWaypoint" not in files["objective-navigation.mjs"]
            or b"makeCampaignBackup" not in files["campaign-backup.mjs"]
            or b"The MIT License" not in files["THREE-LICENSE.txt"]
            or b"CC BY 4.0" not in files["ASSET-CREDITS.md"]):
        raise ValueError("game dependency or attribution contract incomplete")
    manifest = {
        "scope": "G01_RAMADAN_OFFLINE_CANDIDATE",
        "asset_count": len(files),
        "total_source_bytes": total,
        "assets_sha256": {name: hashlib.sha256(data).hexdigest()
                          for name, data in sorted(files.items())},
        "commercial_rights_verified": False,
        "independent_backup_restore_verified": False,
        "deployment_authorized": False,
        "live_verified": False,
    }
    output = Path(output_zip)
    if output.is_symlink() or output.parent.is_symlink() or not output.parent.is_dir():
        raise ValueError("unsafe output location")
    parent_info = output.parent.stat()
    if parent_info.st_uid != os.getuid() or stat.S_IMODE(parent_info.st_mode) & 0o077:
        raise ValueError("output must be inside an owner-only private directory")
    # ZIP must be private from its first byte, not chmod'ed after creation:
    # permissive caller umask must not expose an unpublished game candidate.
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as archive:
            for name, data in sorted(files.items()):
                archive.writestr(name, data)
            archive.writestr("S01_PRIVATE_RELEASE_MANIFEST.json",
                             json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    with zipfile.ZipFile(output, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("release archive CRC verification failed")
        if set(archive.namelist()) != set(files) | {"S01_PRIVATE_RELEASE_MANIFEST.json"}:
            raise ValueError("release archive membership mismatch")
        for name, expected in manifest["assets_sha256"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("release archive readback mismatch")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", help="private local games/ramadan-war directory")
    parser.add_argument("output_zip", help="new private output ZIP (never overwritten)")
    args = parser.parse_args()
    manifest = build(args.source_dir, args.output_zip)
    print(json.dumps({"scope": manifest["scope"],
                      "asset_count": manifest["asset_count"],
                      "zip_verified": True, "deployment_authorized": False},
                     sort_keys=True))


if __name__ == "__main__":
    main()
