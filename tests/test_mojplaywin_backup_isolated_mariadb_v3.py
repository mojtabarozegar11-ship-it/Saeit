"""Synthetic-only MariaDB container recovery after GZIP/GPG authentication.

No real source data, SSH credentials, customer data, backups or production
database are read. MariaDB is a temporary, network-disabled CI container.
"""
import hashlib
import io
import os
import pathlib
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zlib

from scripts import mojplaywin_backup_encrypt_vps_gpg as encrypt
from scripts import mojplaywin_backup_gzip_recovery_v3 as recovery

STEM = "mojplaywin_20261020"
FIXTURE_SCHEMA = "v3_synthetic_restore_only"


def pack(payload):
    compressor = zlib.compressobj(level=1, wbits=31)
    return compressor.compress(payload) + compressor.flush() + encrypt.MARKER


def restore_fixture_tar(encoded, directory):
    """Safely extract verified TAR bytes; explicitly forbid traversal/links/devices."""
    directory = pathlib.Path(directory).resolve(strict=True)
    digest = {}
    with tarfile.open(fileobj=io.BytesIO(encoded), mode="r:") as bundle:
        seen = set()
        for member in bundle:
            if not (member.isfile() or member.isdir()):
                raise ValueError("unsupported tar member type")
            path = pathlib.PurePosixPath(member.name)
            if (not member.name or path.is_absolute() or
                ".." in path.parts or "." in path.parts or
                "\x00" in member.name or member.name.startswith("./")):
                raise ValueError("unsafe tar path")
            target = directory.joinpath(*path.parts)
            if not target.is_relative_to(directory) or str(path) in seen:
                raise ValueError("unsafe or duplicate tar entry")
            seen.add(str(path))
            if member.isdir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                payload = bundle.extractfile(member)
                if payload is None:
                    raise ValueError("missing tar payload")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                with os.fdopen(os.open(target, flags, 0o600), "wb") as out:
                    checksum = hashlib.sha256()
                    written = 0
                    while True:
                        block = payload.read(131072)
                        if not block:
                            break
                        out.write(block)
                        checksum.update(block)
                        written += len(block)
                if written != member.size:
                    raise ValueError("tar member length mismatch")
                digest[str(path)] = checksum.hexdigest()
    return digest


@unittest.skipUnless(bool(os.getenv("MPW_RESTORE_FIXTURE_CONTAINER")),
                     "Only run on the isolated fixture MariaDB job")
@unittest.skipUnless(shutil.which("docker") and shutil.which("gpg"),
                     "Docker and GPG required for the isolated synthetic proof")
class DisposableMariaDBRestore(unittest.TestCase):
    def test_gpg_decrypt_sql_import_and_safe_tar_recovery(self):
        container = os.environ["MPW_RESTORE_FIXTURE_CONTAINER"]
        self.assertEqual(container, "mpw-v3-synthetic-restore-ci")
        sql = (
            f"CREATE DATABASE IF NOT EXISTS \`{FIXTURE_SCHEMA}\`;\n"
            f"USE \`{FIXTURE_SCHEMA}\`;\n"
            "CREATE TABLE recovery_marker (id INT PRIMARY KEY, note VARCHAR(100));\n"
            "INSERT INTO recovery_marker VALUES (1, 'test-only'), (2, 'isolated');\n"
        ).encode() * 10
        # Make CREATE and INSERT idempotency explicit for the fixture replay.
        sql = (
            f"CREATE DATABASE \`{FIXTURE_SCHEMA}\`;\n"
            f"USE \`{FIXTURE_SCHEMA}\`;\n"
            "CREATE TABLE recovery_marker (id INT PRIMARY KEY, note VARCHAR(100));\n"
            "INSERT INTO recovery_marker VALUES (1,'test-only'),(2,'isolated');\n"
        ).encode()
        self.assertGreater(len(sql), 128)
        with tempfile.TemporaryDirectory(prefix="mpw-v3-synthetic-recovery-") as tmp:
            root = pathlib.Path(tmp)
            result = encrypt.store(io.BytesIO(pack(sql)), "mysql", root=root,
                                   keyroot=root, minimum_free=0, stem=STEM,
                                   source_encoding="gzip-with-footer-v1")
            self.assertTrue(result["decryption_verified"])
            sql_buffer = io.BytesIO()
            self.assertEqual(recovery.decode_archive("mysql", home=root, stem=STEM,
                                                      out=sql_buffer), len(sql))
            restored_sql = sql_buffer.getvalue()
            self.assertEqual(restored_sql, sql)
            command = ["docker", "exec", "-i", container, "mariadb", "-uroot"]
            run = subprocess.run(command, input=restored_sql, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=30, check=False)
            self.assertEqual(run.returncode, 0, msg="synthetic SQL import did not succeed")
            query = subprocess.run(
                ["docker","exec", container, "mariadb","-uroot","-N","-B",
                 "-e", f"SELECT COUNT(*), SUM(id) FROM \`{FIXTURE_SCHEMA}\`.recovery_marker"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
            self.assertEqual(query.returncode, 0)
            self.assertEqual(query.stdout.decode().strip(), "2\t3")
            source_files = root / "synthetic_site"
            source_files.mkdir()
            (source_files / "main.txt").write_bytes(b"synthetic private root content\n" * 120)
            tar_blob = io.BytesIO()
            with tarfile.open(fileobj=tar_blob, mode="w") as bundle:
                bundle.add(source_files / "main.txt", arcname="main-site/main.txt")
            encoded = tar_blob.getvalue()
            encrypt.store(io.BytesIO(pack(encoded)), "files", root=root,
                          keyroot=root, minimum_free=0, stem=STEM,
                          source_encoding="gzip-with-footer-v1")
            self.assertTrue(recovery.both_ready(home=root, stem=STEM))
            files_buffer = io.BytesIO()
            self.assertEqual(recovery.decode_archive("files", home=root, stem=STEM,
                                                      out=files_buffer), len(encoded))
            destination = root / "isolated_destination"
            destination.mkdir()
            checksums = restore_fixture_tar(files_buffer.getvalue(), destination)
            self.assertEqual(checksums["main-site/main.txt"],
                             hashlib.sha256((source_files / "main.txt").read_bytes()).hexdigest())
            self.assertEqual((destination / "main-site" / "main.txt").read_bytes(),
                             (source_files / "main.txt").read_bytes())
            self.assertFalse(result["release_permitted"])
            print("MPW_V3_ISOLATED_SYNTHETIC_MYSQL_AND_TAR_RESTORE=PASS")
            print("MPW_V3_LIVE_RESTORE_COMPLETED=false")

    def test_reject_tar_path_traversal_without_outside_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            malicious = io.BytesIO()
            with tarfile.open(fileobj=malicious, mode="w") as bundle:
                bad = tarfile.TarInfo("../outside.txt")
                bad.size = 7
                bundle.addfile(bad, io.BytesIO(b"unsafe!"))
            with self.assertRaises(ValueError):
                restore_fixture_tar(malicious.getvalue(), root)
            self.assertFalse((root.parent / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
