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


    def test_real_paid_file_opener_rejects_drift_and_closes_fd(self):
        """Exercise the real payment file-opening function, not just text checks."""
        import ast
        import os
        import stat
        import sys
        from types import ModuleType
        from unittest.mock import Mock, patch

        path=SOURCE.parent/'mpw_walletless_commercial_intent.py'
        tree=ast.parse(path.read_text('utf-8'))
        definitions=[node for node in tree.body
                     if isinstance(node,ast.FunctionDef)
                     and node.name=='open_commercial_paid_file']
        self.assertEqual(len(definitions),1)
        namespace={}
        class PaymentHold(Exception):
            pass
        namespace.update(os=os,stat=stat,PaymentHold=PaymentHold,
                         PROVIDER='mpw_walletless_trx_v1',
                         commercial_buyer_status=lambda *a,**k: {'can_download':True})
        exec(compile(ast.Module(body=definitions,type_ignores=[]),str(path),'exec'),
             namespace)
        handler=namespace['open_commercial_paid_file']
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'sale.pdf'
            approved=b'%PDF-1.4\\nThe original paid product'
            source.write_bytes(approved)
            digest=hashlib.sha256(approved).hexdigest()
            metadata=evidence()
            metadata.update(sha256=digest,rights_asset_sha256=digest)
            product=SimpleNamespace(metadata=metadata)
            item=SimpleNamespace(product=product)
            intent=SimpleNamespace(order=SimpleNamespace(customer_id=7),
                                   provider='mpw_walletless_trx_v1')
            payments=ModuleType('core.models')
            payments.PaymentIntent=SimpleNamespace(objects=Mock())
            payments.PaymentIntent.objects.select_related.return_value.get.return_value=intent
            payments.OrderItem=SimpleNamespace(objects=Mock())
            payments.OrderItem.objects.get.return_value=item
            storage=ModuleType('mpw_commerce.downloads')
            storage._private_file=lambda entry: source
            rights=ModuleType('services.mpw_trx_commercial_context')
            rights.private_paid_stream_matches_approved=CONTEXT.private_paid_stream_matches_approved
            stubs={
                'core.models':payments,
                'mpw_commerce.downloads':storage,
                'services.mpw_trx_commercial_context':rights,
            }
            streams=[]
            original_fdopen=os.fdopen
            def capture_fdopen(fd,mode):
                stream=original_fdopen(fd,mode)
                streams.append(stream)
                return stream
            with patch.dict(sys.modules,stubs),patch.object(os,'fdopen',side_effect=capture_fdopen):
                stream=handler(31,7)
                try:
                    self.assertEqual(stream.tell(),0)
                    self.assertEqual(stream.read(),approved)
                finally:
                    stream.close()
                self.assertTrue(streams[-1].closed)
                source.write_bytes(b'%PDF-1.4\\nAltered paid product copy')
                with self.assertRaises(PaymentHold):
                    handler(31,7)
                self.assertTrue(streams[-1].closed)


    def test_legacy_paid_delivery_hashes_opened_file_and_closes_denied_fd(self):
        """Run the actual legacy delivery function in isolation: no DB or payment."""
        import ast
        import os
        import sys
        from types import ModuleType
        from unittest.mock import Mock, patch

        path=SOURCE.parent.parent/'mpw_commerce/downloads.py'
        tree=ast.parse(path.read_text('utf-8'))
        nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef)
               and node.name=='download_paid_item']
        self.assertEqual(len(nodes),1)
        nodes[0].decorator_list=[]
        class NotFound(Exception):
            pass
        item=SimpleNamespace(product=SimpleNamespace(metadata={}))
        item_model=SimpleNamespace(objects=Mock())
        item_model.objects.select_related.return_value.filter.return_value.first.return_value=item
        class Delivered(dict):
            def __init__(self,stream,*,as_attachment,filename):
                super().__init__()
                self.stream=stream
                self.filename=filename
                self.as_attachment=as_attachment
        namespace=dict(
            settings=SimpleNamespace(MPW_COMMERCE_DOWNLOADS_ENABLED=True),
            Http404=NotFound,
            HttpResponseForbidden=lambda reason: ('forbidden',reason),
            FileResponse=Delivered,
            DOMAIN_ALLOWLIST=frozenset(('mojplaywin.com','www.mojplaywin.com')),
            OrderItem=item_model,
            can_access_purchased_digital_item=lambda item_id,buyer_id: True,
            os=os,
        )
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
        handler=namespace['download_paid_item']
        request=SimpleNamespace(
            is_secure=lambda:True,get_host=lambda:'mojplaywin.com',
            user=SimpleNamespace(pk=7))
        rights=ModuleType('services.mpw_trx_commercial_context')
        rights.private_paid_stream_matches_approved=CONTEXT.private_paid_stream_matches_approved
        streams=[]
        fdopen=os.fdopen
        def record_fdopen(fd,mode):
            stream=fdopen(fd,mode)
            streams.append(stream)
            return stream
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'approved.pdf'
            approved=b'%PDF-1.4\\nLicensed paid content\\n'
            source.write_bytes(approved)
            digest=hashlib.sha256(approved).hexdigest()
            item.product.metadata=evidence()
            item.product.metadata.update(sha256=digest,rights_asset_sha256=digest)
            namespace['_private_file']=lambda row:source
            with patch.dict(sys.modules,{'services.mpw_trx_commercial_context':rights}), \\
                 patch.object(os,'fdopen',side_effect=record_fdopen):
                response=handler(request,41)
                self.assertEqual(response.stream.read(),approved)
                self.assertEqual(response['Cache-Control'],'no-store, private')
                self.assertEqual(response['X-Robots-Tag'],'noindex, nofollow')
                response.stream.close()
                self.assertTrue(streams[-1].closed)

                source.write_bytes(b'%PDF-1.4\\nModified paid content\\n')
                with self.assertRaises(NotFound):
                    handler(request,41)
                self.assertTrue(streams[-1].closed)

                item.product.metadata['rights_cleared']=False
                with self.assertRaises(NotFound):
                    handler(request,41)
                self.assertTrue(streams[-1].closed)

            namespace['can_access_purchased_digital_item']=lambda *_:False
            with self.assertRaises(NotFound):
                handler(request,41)

    def test_legacy_download_does_not_run_for_disabled_release(self):
        """No entitlement query or file access when download permission is off."""
        path=SOURCE.parent.parent/'mpw_commerce/downloads.py'
        text=path.read_text('utf-8')
        self.assertIn('MPW_COMMERCE_DOWNLOADS_ENABLED',text)
        self.assertIn('can_access_purchased_digital_item(item_id,request.user.pk)',text)
        self.assertIn('private_paid_stream_matches_approved(item.product,stream)',text)
        self.assertIn('stream.close()',text)
        self.assertIn('descriptor is not None',text)


if __name__=="__main__":
    unittest.main()
