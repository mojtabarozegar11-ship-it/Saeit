"""Rights metadata linkage must be fail-closed; no DB or customer records."""
import importlib.util
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


SOURCE=Path(__file__).resolve().parents[1]/"services/mpw_trx_commercial_context.py"
SPEC=importlib.util.spec_from_file_location("mpw_rights_context",SOURCE)
CONTEXT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTEXT)


def evidence():
    sha="abc123"*10+"abcd"
    return {"rights_cleared":True,"publication_approved":True,
            "sha256":sha,"rights_asset_sha256":sha,
            "rights_document_sha256":"f"*64}


class RightsMetadataContract(unittest.TestCase):
    def test_exact_document_and_artifact_linkage(self):
        fields=evidence()
        self.assertTrue(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))
        fields["rights_asset_sha256"]=fields["sha256"].upper()
        self.assertTrue(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))

    def test_unverified_rights_or_publication_cannot_pass(self):
        for key in ("rights_cleared","publication_approved"):
            for bad in (False,"true",1,None):
                with self.subTest(key=key,value=bad):
                    fields=evidence()
                    fields[key]=bad
                    self.assertFalse(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))

    def test_missing_malformed_or_mismatched_hash_fails_closed(self):
        for key in ("sha256","rights_asset_sha256","rights_document_sha256"):
            for value in (None,"", "f"*63,"z"*64,123):
                with self.subTest(key=key,value=value):
                    fields=evidence()
                    fields[key]=value
                    self.assertFalse(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))
        fields=evidence()
        fields["rights_asset_sha256"]="1"*64
        self.assertFalse(CONTEXT.rights_cleared_for_sale(SimpleNamespace(metadata=fields)))

    def test_non_dict_metadata_and_missing_product_do_not_pass(self):
        for product in (None,SimpleNamespace(metadata=None),SimpleNamespace(metadata=[]),
                        SimpleNamespace(metadata={})):
            self.assertFalse(CONTEXT.rights_cleared_for_sale(product))

    def test_real_private_file_digest_must_equal_approved_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / 'product.pdf'
            original = b'%PDF-1.4\nOwner approved version\n'
            artifact.write_bytes(original)
            digest = hashlib.sha256(original).hexdigest()
            metadata = evidence()
            metadata.update(sha256=digest, rights_asset_sha256=digest)
            product = SimpleNamespace(metadata=metadata)
            self.assertTrue(CONTEXT.private_artifact_sha_matches_approved(product, artifact))
            artifact.write_bytes(b'%PDF-1.4\nSubstituted after approval\n')
            self.assertFalse(CONTEXT.private_artifact_sha_matches_approved(product, artifact))

    def test_missing_empty_and_symlink_private_file_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = evidence()
            product = SimpleNamespace(metadata=metadata)
            missing = Path(tmp) / 'missing.pdf'
            empty = Path(tmp) / 'empty.pdf'
            empty.write_bytes(b'')
            symlink = Path(tmp) / 'link.pdf'
            symlink.symlink_to(empty)
            for artifact in (missing, empty, symlink):
                with self.subTest(artifact=artifact.name):
                    self.assertFalse(CONTEXT.private_artifact_sha_matches_approved(product, artifact))

    def test_symlink_to_matching_approved_file_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            approved = Path(tmp) / 'approved.pdf'
            payload = b'%PDF-1.4\nApproved exact content\n'
            approved.write_bytes(payload)
            metadata = evidence()
            metadata.update(sha256=hashlib.sha256(payload).hexdigest(),
                            rights_asset_sha256=hashlib.sha256(payload).hexdigest())
            product = SimpleNamespace(metadata=metadata)
            self.assertTrue(CONTEXT.private_artifact_sha_matches_approved(product, approved))
            shortcut = Path(tmp) / 'shortcut.pdf'
            shortcut.symlink_to(approved)
            self.assertFalse(CONTEXT.private_artifact_sha_matches_approved(product, shortcut))

    def test_hardlinked_approved_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            approved = Path(tmp) / 'approved.zip'
            payload = b'ZIP test fixture bytes, not a production archive'
            approved.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            metadata = evidence()
            metadata.update(sha256=digest, rights_asset_sha256=digest)
            second = Path(tmp) / 'second-link.zip'
            import os
            os.link(approved, second)
            self.assertFalse(CONTEXT.private_artifact_sha_matches_approved(
                SimpleNamespace(metadata=metadata), approved))


    def test_paid_stream_matches_exact_approved_bytes_and_resets_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload=b'%PDF-1.4\\nExact purchased private content\\n'
            path=Path(tmp)/'paid.pdf'
            path.write_bytes(payload)
            digest=hashlib.sha256(payload).hexdigest()
            metadata=evidence()
            metadata.update(sha256=digest,rights_asset_sha256=digest)
            product=SimpleNamespace(metadata=metadata)
            with path.open('rb') as stream:
                stream.read(6)
                self.assertTrue(CONTEXT.private_paid_stream_matches_approved(product,stream))
                self.assertEqual(stream.tell(),0)
                self.assertEqual(stream.read(),payload)

    def test_paid_stream_denies_modified_content_even_when_size_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            approved=b'%PDF-1.4\\nOriginal file content\\n'
            altered=approved.replace(b'Original',b'Altered!')
            self.assertEqual(len(approved),len(altered))
            path=Path(tmp)/'paid.pdf'
            path.write_bytes(altered)
            digest=hashlib.sha256(approved).hexdigest()
            metadata=evidence()
            metadata.update(sha256=digest,rights_asset_sha256=digest)
            with path.open('rb') as stream:
                self.assertFalse(CONTEXT.private_paid_stream_matches_approved(
                    SimpleNamespace(metadata=metadata),stream))

    def test_paid_stream_rejects_revoked_rights_even_with_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload=b'valid licensed file bytes'
            path=Path(tmp)/'private.zip'
            path.write_bytes(payload)
            digest=hashlib.sha256(payload).hexdigest()
            metadata=evidence()
            metadata.update(sha256=digest,rights_asset_sha256=digest,
                            rights_cleared=False)
            with path.open('rb') as stream:
                self.assertFalse(CONTEXT.private_paid_stream_matches_approved(
                    SimpleNamespace(metadata=metadata),stream))

    def test_paid_stream_rejects_hardlinked_open_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload=b'merchant approved stream'
            path=Path(tmp)/'asset.pdf'
            path.write_bytes(payload)
            import os
            os.link(path,Path(tmp)/'hardlink.pdf')
            digest=hashlib.sha256(payload).hexdigest()
            metadata=evidence()
            metadata.update(sha256=digest,rights_asset_sha256=digest)
            with path.open('rb') as stream:
                self.assertFalse(CONTEXT.private_paid_stream_matches_approved(
                    SimpleNamespace(metadata=metadata),stream))

    def test_paid_stream_rejects_removed_inode_after_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload=b'approved original'
            path=Path(tmp)/'paid.pdf'
            path.write_bytes(payload)
            digest=hashlib.sha256(payload).hexdigest()
            metadata=evidence()
            metadata.update(sha256=digest,rights_asset_sha256=digest)
            with path.open('rb') as stream:
                path.unlink()
                self.assertFalse(CONTEXT.private_paid_stream_matches_approved(
                    SimpleNamespace(metadata=metadata),stream))

    def test_paid_delivery_source_uses_open_fd_verifier_and_cleanup(self):
        source=(SOURCE.parent/'mpw_walletless_commercial_intent.py').read_text('utf-8')
        paid=source.split('def open_commercial_paid_file(',1)[1]
        self.assertIn('private_paid_stream_matches_approved(item.product,stream)',paid)
        self.assertIn('getattr(os,"O_NOFOLLOW",0)',paid)
        self.assertIn('stream.close()',paid)
        self.assertIn('return stream',paid)


if __name__=="__main__":
    unittest.main()
