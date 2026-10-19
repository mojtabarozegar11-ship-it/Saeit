"""Offline client transport checks for PICM GPU worker (no network and no GPU)."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "ops" / "picm-gpu"
sys.path.insert(0, str(ROOT))
import video_worker_client as client


class GPUVideoWorkerClientTests(unittest.TestCase):
    def test_refuse_external_gpu_host_and_token_leak(self):
        with self.assertRaisesRegex(RuntimeError, "ORIGIN_MUST_MATCH"):
            client.Transport("X" * 64, origin="https://gpu-provider.example")
        transport = client.Transport("X" * 64)
        with self.assertRaisesRegex(RuntimeError, "INVALID_API_ROUTE"):
            transport.request("GET", "//evil.example/private")
        with self.assertRaisesRegex(RuntimeError, "INVALID_API_ROUTE"):
            transport.request("GET", "/other/api")

    def test_token_must_be_private_regular_file(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "gpu-token"
            file.write_text("X" * 64)
            file.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, "TOKEN_MUST_BE_0600"):
                client._token(file)
            file.chmod(0o600)
            self.assertEqual(client._token(file), "X" * 64)
            other = Path(d) / "external"
            other.write_text("X" * 64)
            file.unlink()
            file.symlink_to(other)
            with self.assertRaisesRegex(RuntimeError, "TOKEN_MUST_BE_0600"):
                client._token(file)

    def test_non_private_worker_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            p.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, "PRIVATE_WORK_DIRECTORY"):
                client._private_dir(p)
            p.chmod(0o700)
            self.assertEqual(client._private_dir(p), p)

    def test_chunk_upload_ack_and_finish_is_required(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "story.mp4"
            payload = b"sample-only-" * 400
            file.write_bytes(payload)
            ident = "a" * 32
            lease = "b" * 32
            digest = hashlib.sha256(payload).hexdigest()
            receipt = {"job_id": ident, "sha256": digest, "bytes": len(payload),
                       "duration": 5, "state": "real_mp4_rendered_and_ffprobed"}
            class FakeTransport:
                def __init__(self):
                    self.offset = 0
                    self.calls = 0
                def json(self, method, route, *, lease=None, payload=None):
                    if "progress" in route:
                        return {"offset": self.offset}
                    if "finish" in route:
                        if self.offset != len(payload_data):
                            raise RuntimeError("incomplete")
                        return {"state": "done", "id": ident}
                    raise RuntimeError("unexpected request")
                def request(self, method, route, *, lease=None, data=None, headers=None):
                    self.calls += 1
                    if self.offset != int(headers["X-PICM-Offset"]):
                        raise RuntimeError("offset invalid")
                    self.offset += len(data)
                    return ('{"offset": %d}' % self.offset).encode()
            payload_data = payload
            fake = FakeTransport()
            reply = client.upload_rendered(fake, ident, lease, file, receipt)
            self.assertEqual(reply["state"], "done")
            self.assertEqual(fake.offset, len(payload))
            self.assertGreater(fake.calls, 0)
            modified = dict(receipt, sha256="0" * 64)
            with self.assertRaisesRegex(RuntimeError, "CHANGED_MP4"):
                client.upload_rendered(fake, ident, lease, file, modified)

    def test_preflight_denies_job_claim_when_no_real_gpu(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d)
            private.chmod(0o700)
            token = private / "gpu-token"
            token.write_text("X" * 64)
            token.chmod(0o600)
            with self.assertRaises(Exception):
                client.deliver_once(private, token, private / "absent.json",
                                    private / "absent_nodes.json")
            self.assertEqual(set(private.iterdir()), {token})


if __name__ == "__main__":
    unittest.main()
