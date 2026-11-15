#!/usr/bin/env python3
"""Safely deploy the Moj Prop public-intake backend to the pinned Passenger app."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path("/home/zomorod2/Saeit-staging")
DOCROOT = Path("/home/zomorod2/mojplaywin.com")
BACKUP_ROOT = Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
FILES = (
    Path("config/urls.py"),
    Path("core/models.py"),
    Path("core/admin.py"),
    Path("core/mojprop_views.py"),
    Path("core/migrations/0041_mojprop_request.py"),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_run_id(value: str) -> str:
    if not value.isdigit() or len(value) > 20:
        raise ValueError("invalid workflow run id")
    return value


def validate_commit(value: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("invalid source commit")
    return value


def assert_regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} is missing or unsafe: {path}")


def assert_safe_parent(path: Path, root: Path) -> None:
    current = path.parent
    while current != root:
        if current == Path("/"):
            raise RuntimeError(f"unsafe parent chain: {path}")
        if current.is_symlink():
            raise RuntimeError(f"symlink parent refused: {current}")
        current = current.parent


def compile_python(path: Path) -> None:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def selftest(repo_root: Path) -> None:
    for relative in FILES:
        source = repo_root / relative
        assert_regular(source, "source")
        if source.suffix == ".py":
            compile_python(source)
    view = (repo_root / "core/mojprop_views.py").read_text(encoding="utf-8")
    urls = (repo_root / "config/urls.py").read_text(encoding="utf-8")
    model = (repo_root / "core/models.py").read_text(encoding="utf-8")
    required = (
        ("mojprop_intake", view),
        ("MojPropRequest", model),
        ('path("api/moj-prop/intake/"', urls),
        ("get_token", view),
        ("_ip_hash", view),
    )
    missing = [marker for marker, text in required if marker not in text]
    if missing:
        raise RuntimeError(f"backend selftest missing markers: {missing}")
    print("MOJ_PROP_BACKEND_SELFTEST=PASS")


def choose_python() -> Path:
    candidates = (
        Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"),
        Path("/home/zomorod2/virtualenv/Saeit/3.11/bin/python"),
        ROOT / ".venv/bin/python",
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError("verified Django Python runtime not found")


def backup_target(target: Path, backup: Path, manifest: dict, relative: Path) -> None:
    if target.exists():
        assert_regular(target, "live target")
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
        manifest[str(relative)] = {
            "existed": True,
            "sha256": digest(target),
            "mode": stat.S_IMODE(target.stat().st_mode),
        }
    else:
        manifest[str(relative)] = {"existed": False}


def atomic_replace(source: Path, target: Path, mode: int) -> None:
    assert_regular(source, "staged source")
    assert_safe_parent(target, ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.mojprop-", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def restore(backup: Path) -> None:
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError("backend backup manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in FILES:
        entry = manifest[str(relative)]
        target = ROOT / relative
        assert_safe_parent(target, ROOT)
        if entry["existed"]:
            saved = backup / relative
            assert_regular(saved, "backend backup")
            atomic_replace(saved, target, int(entry["mode"]))
        elif target.exists():
            assert_regular(target, "unexpected target")
            target.unlink()
    restart = DOCROOT / "tmp" / "restart.txt"
    if restart.is_symlink():
        raise RuntimeError("Passenger restart path is a symlink")
    restart.parent.mkdir(parents=True, exist_ok=True)
    restart.touch()
    print("MOJ_PROP_BACKEND_ROLLBACK=PASS")


def run_checked(command: list[str], cwd: Path) -> None:
    print("RUNNING=" + " ".join(command[:3]))
    subprocess.run(command, cwd=str(cwd), check=True, timeout=300)


def deploy(run_id: str, commit: str, staged_root: Path) -> None:
    run_id = validate_run_id(run_id)
    commit = validate_commit(commit)
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("Passenger application root is missing or redirected")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    assert_regular(DOCROOT / "passenger_wsgi.py", "Passenger routing file")
    if "Saeit-staging" not in (DOCROOT / "passenger_wsgi.py").read_text(
        encoding="utf-8", errors="replace"
    ):
        raise RuntimeError("Passenger routing file no longer points to Saeit-staging")
    if staged_root.is_symlink() or not staged_root.is_dir():
        raise RuntimeError("backend staging root is missing or unsafe")
    for relative in FILES:
        assert_regular(staged_root / relative, "backend staged file")

    backup = BACKUP_ROOT / run_id
    if backup.exists():
        raise RuntimeError(f"refusing to reuse backend backup: {backup}")
    backup.mkdir(parents=True, mode=0o700)
    manifest = {"run_id": run_id, "commit": commit, "files": [str(item) for item in FILES]}
    for relative in FILES:
        backup_target(ROOT / relative, backup, manifest, relative)
    (backup / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    try:
        for relative in FILES:
            target = ROOT / relative
            current_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o640
            atomic_replace(staged_root / relative, target, current_mode)
            if digest(target) != digest(staged_root / relative):
                raise RuntimeError(f"post-copy hash mismatch: {relative}")

        python = choose_python()
        run_checked([str(python), "manage.py", "check", "--deploy"], ROOT)
        run_checked([str(python), "manage.py", "migrate", "--noinput"], ROOT)
        run_checked([str(python), "manage.py", "collectstatic", "--noinput"], ROOT)

        restart = DOCROOT / "tmp" / "restart.txt"
        if restart.is_symlink():
            raise RuntimeError("Passenger restart path is a symlink")
        restart.parent.mkdir(parents=True, exist_ok=True)
        restart.touch()
        print("MOJ_PROP_BACKEND_DEPLOY=PASS")
        print("MOJ_PROP_BACKEND_COMMIT=" + commit)
        print("MOJ_PROP_BACKUP=" + str(backup))
    except Exception:
        restore(backup)
        raise


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: script.py selftest [repo_root] | deploy RUN_ID COMMIT STAGED_ROOT | rollback RUN_ID")
    action = argv[1]
    if action == "selftest":
        selftest(Path(argv[2]).resolve() if len(argv) > 2 else Path.cwd())
        return 0
    if action == "deploy" and len(argv) == 5:
        deploy(argv[2], argv[3], Path(argv[4]).resolve())
        return 0
    if action == "rollback" and len(argv) == 3:
        restore(BACKUP_ROOT / validate_run_id(argv[2]))
        return 0
    raise SystemExit("invalid arguments")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
