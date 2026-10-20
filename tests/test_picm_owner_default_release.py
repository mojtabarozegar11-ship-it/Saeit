"""PICM protected two-template default-mode update & rollback tests."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest
from scripts import picm_owner_default_release as rel

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def box():
    with tempfile.TemporaryDirectory() as d:
        home=Path(d)
        app=home/"Saeit-staging"
        docs=home/"mojplaywin.com"
        docs.mkdir()
        live=app/"templates/picm"
        live.mkdir(parents=True)
        stage=home/".picm-owner-default-stage-12345"/"templates/picm"
        stage.mkdir(parents=True)
        index_old=b"<html>Previously deployed protected PICM</html>"
        js_old=b"// Previous owner PICM text-to-image JavaScript"
        (live/"index.html").write_bytes(index_old)
        (live/"text_image.js").write_bytes(js_old)
        originals={"templates/picm/index.html":rel.git_blob(index_old),
                   "templates/picm/text_image.js":rel.git_blob(js_old)}
        for p in ("index.html","text_image.js"):
            (stage/p).write_bytes((ROOT/"templates/picm"/p).read_bytes())
        hashes=[rel.sha256((stage/p).read_bytes()) for p in ("index.html","text_image.js")]
        with patch.multiple(rel,HOME=home,APP=app,DOCROOT=docs,
                            BACKUP_ROOT=home/".mojplaywin-backups",EXPECTED=originals), \
             patch.object(rel,"sanity"), patch.object(rel,"restart") as restarted:
            yield home,live,hashes,restarted


def test_scoped_deploy_and_rollback_preserves_unrelated_files(box):
    home,live,hashes,restarted=box
    unrelated=home/"Saeit-staging/core/payment.py"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("payment remains unchanged")
    rel.deploy("12345",*hashes)
    assert b'value="text_image"' in (live/"index.html").read_bytes()
    assert b"form.noValidate=selected" in (live/"text_image.js").read_bytes()
    assert unrelated.read_text()=="payment remains unchanged"
    backup=home/".mojplaywin-backups/picm-owner-default-12345"
    manifest=json.loads((backup/"manifest.json").read_text())
    assert set(manifest["source"])==set(rel.EXPECTED)
    rel.rollback("12345")
    assert (live/"index.html").read_bytes()==b"<html>Previously deployed protected PICM</html>"
    assert (live/"text_image.js").read_bytes()==b"// Previous owner PICM text-to-image JavaScript"
    assert unrelated.read_text()=="payment remains unchanged"
    assert restarted.call_count==2


def test_refuses_existing_changed_live_template(box):
    home,live,hashes,_=box
    (live/"index.html").write_bytes(b"new modification by site owner")
    with pytest.raises(RuntimeError,match="PICM_LIVE_FILE_CHANGED"):
        rel.deploy("12345",*hashes)
    assert not (home/".mojplaywin-backups/picm-owner-default-12345").exists()


def test_refuses_changed_staged_script_checksum(box):
    home,live,hashes,_=box
    stage=home/".picm-owner-default-stage-12345/templates/picm/text_image.js"
    stage.write_bytes(b"not valid")
    with pytest.raises(RuntimeError,match="PICM_STAGED_FILE_CHECKSUM"):
        rel.deploy("12345",*hashes)
    assert b"Previously deployed" in (live/"index.html").read_bytes()


def test_rollback_refuses_concurrent_ownership_changes(box):
    home,live,hashes,_=box
    rel.deploy("12345",*hashes)
    (live/"text_image.js").write_bytes(b"concurrent newer changes")
    with pytest.raises(RuntimeError,match="PICM_ROLLBACK_REFUSES_NEWER"):
        rel.rollback("12345")
    assert (live/"text_image.js").read_bytes()==b"concurrent newer changes"
