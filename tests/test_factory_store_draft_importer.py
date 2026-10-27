"""End-to-end verified private receipt -> inactive Django product draft tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

import pytest
from django.test import override_settings
from core.models import Product

REPO = Path(__file__).resolve().parents[1]


def module(name):
    path = REPO / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, str(path))
    x = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(x)
    return x


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_unreviewed_receipt_cannot_enter_store_as_a_draft(django_user_model, tmp_path):
    receiver = module("store_receiver")
    importer = module("import_factory_store_drafts")
    owner = django_user_model.objects.create_superuser(
        username="09175814408", email="", password="not-used-here"
    )
    app = tmp_path / "Saeit-staging"
    app.mkdir()
    (app / "manage.py").write_text("pass", encoding="utf-8")
    docroot = tmp_path / "mojplaywin.com"
    docroot.mkdir()
    (docroot / "passenger_wsgi.py").write_text("# /home/sample/Saeit-staging", encoding="utf-8")
    root = tmp_path / ".saeit-factory-inbox"
    recipe = "farm_enterprise_economics"
    incoming = root / "incoming" / recipe
    incoming.mkdir(parents=True)
    sample = tmp_path / "example.zip"
    with zipfile.ZipFile(str(sample), "w") as zipped:
        zipped.writestr(recipe + "/calculator.py", "print('safe')")
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()
    (incoming / (digest + ".zip.partial")).write_bytes(sample.read_bytes())
    (incoming / (digest + ".json.partial")).write_text(json.dumps({
        "name": "Farm Enterprise Economics Toolkit",
        "recipe": recipe, "artifact_sha256": digest, "qa_status": "passed",
        "commercial_status": "private_internal_qa_pass_not_published",
        "price": None, "owner_publication_approval": False, "public_listing_enabled": False
    }), encoding="utf-8")
    receiver.finalize(root, recipe, digest)

    with pytest.raises(RuntimeError, match="STORE_BLOCKED_UNTIL_CHATGPT_AND_QC1000_APPROVE"):
        importer.import_receipts(root, app, docroot, "09175814408")
    with pytest.raises(RuntimeError, match="STORE_BLOCKED_UNTIL_CHATGPT_AND_QC1000_APPROVE"):
        importer.import_receipts(root, app, docroot, "09175814408", apply=True)
    assert Product.objects.count() == 0
    assert Product.objects.filter(active=True).count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_rejects_unverified_owner_and_wrong_docroot(django_user_model, tmp_path):
    importer = module("import_factory_store_drafts")
    django_user_model.objects.create_superuser(username="other", email="", password="unused")
    app = tmp_path / "Saeit-staging"
    app.mkdir()
    (app / "manage.py").write_text("pass")
    docroot = tmp_path / "mojplaywin.com"
    docroot.mkdir()
    (docroot / "passenger_wsgi.py").write_text("other project")
    inbox = tmp_path / "private"
    inbox.mkdir()
    with pytest.raises(RuntimeError, match="STOREFRONT_TARGET_MISMATCH"):
        importer.import_receipts(inbox, app, docroot, "09175814408", apply=True)
    (docroot / "passenger_wsgi.py").write_text("Saeit-staging")
    with pytest.raises(RuntimeError, match="IDENTIFIED_STORE_OWNER_NOT_PRESENT"):
        importer.import_receipts(inbox, app, docroot, "09175814408", apply=True)
    assert Product.objects.count() == 0
