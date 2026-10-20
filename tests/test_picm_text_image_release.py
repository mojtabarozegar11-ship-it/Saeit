"""PICM two-template deployment and rollback safety, without real server writes."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest
from scripts import picm_text_image_release as release

ROOT = Path(__file__).resolve().parents[1]
RUN = "123456789"


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def scoped_install():
    with tempfile.TemporaryDirectory() as dir:
        home = Path(dir)
        app = home/"Saeit-staging"
        docroot=home/"mojplaywin.com"
        backups=home/".mojplaywin-backups"
        index=app/"templates/picm/index.html"
        target_js=app/"templates/picm/text_image.js"
        stage=home/(".picm-text-image-stage-"+RUN)
        index.parent.mkdir(parents=True)
        docroot.mkdir()
        stage_tpl=stage/"templates/picm"
        stage_tpl.mkdir(parents=True)
        old=b"<html>ORIGINAL PRIVATE PICM PAGE</html>"
        index.write_bytes(old)
        target_index=(ROOT/"templates/picm/index.html").read_bytes()
        target_script=(ROOT/"templates/picm/text_image.js").read_bytes()
        (stage_tpl/"index.html").write_bytes(target_index)
        (stage_tpl/"text_image.js").write_bytes(target_script)
        with patch.multiple(release, HOME=home, APP=app, DOCROOT=docroot, BACKUPS=backups,
                            BASE_INDEX_BLOB=release.blob_sha(old)), \
             patch.object(release,"sanity"), patch.object(release,"restart") as restarted:
            yield {
                "home":home, "index":index, "javascript":target_js,
                "original":old, "html_bytes":target_index,
                "js_bytes":target_script, "restart":restarted,
                "backups":backups,
            }


def test_install_and_rollback_change_only_picm_files(scoped_install):
    x=scoped_install
    untouched=x["home"]/"Saeit-staging/core/authentication.py"
    untouched.parent.mkdir(parents=True)
    untouched.write_text("do-not-touch",encoding="utf-8")
    release.deploy(RUN,digest(x["html_bytes"]),digest(x["js_bytes"]))
    assert x["index"].read_bytes()==x["html_bytes"]
    assert x["javascript"].read_bytes()==x["js_bytes"]
    assert untouched.read_text()=="do-not-touch"
    b=x["backups"]/("picm-text-image-"+RUN)
    assert (b/"templates/picm/index.html").read_bytes()==x["original"]
    assert json.loads((b/"manifest.json").read_text())["run_id"]==RUN
    release.rollback(RUN)
    assert x["index"].read_bytes()==x["original"]
    assert not x["javascript"].exists()
    assert untouched.read_text()=="do-not-touch"
    assert x["restart"].call_count==2


def test_refuses_to_clobber_changed_live_template(scoped_install):
    x=scoped_install
    x["index"].write_bytes(b"Someone else updated this live PICM template")
    with pytest.raises(RuntimeError,match="PICM_LIVE_TEMPLATE_CHANGED"):
        release.deploy(RUN,digest(x["html_bytes"]),digest(x["js_bytes"]))
    assert not x["javascript"].exists()


def test_refuses_wrong_candidate_hash_before_any_changes(scoped_install):
    x=scoped_install
    with pytest.raises(RuntimeError,match="PICM_BAD_CANDIDATE_DIGEST"):
        release.deploy(RUN,"0"*64,digest(x["js_bytes"]))
    assert x["index"].read_bytes()==x["original"]
    assert not x["javascript"].exists()


def test_rollback_cannot_delete_other_concurrent_picm_changes(scoped_install):
    x=scoped_install
    release.deploy(RUN,digest(x["html_bytes"]),digest(x["js_bytes"]))
    x["javascript"].write_text("Unrelated new owner edits",encoding="utf-8")
    with pytest.raises(RuntimeError,match="PICM_ROLLBACK_REFUSES_CHANGED_SCRIPT"):
        release.rollback(RUN)
    assert x["index"].read_bytes()==x["html_bytes"]
    assert x["javascript"].read_text()=="Unrelated new owner edits"
