"""Exact private receipt -> inactive draft, without inventing 1000 clearance."""
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
def test_unreviewed_receipt_can_only_enter_inactive_draft(django_user_model, tmp_path,
                                                         monkeypatch):
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

    with pytest.raises(RuntimeError, match="EXACT_FACTORY_RECIPE_REQUIRED"):
        importer.import_receipts(root, app, docroot, "09175814408")
    report = importer.import_receipts(
        root, app, docroot, "09175814408", recipe=recipe, digest=digest
    )
    assert report["examined"] == 1
    assert report["created"] == 0
    assert report["commercial_quality_approved"] is False
    assert Product.objects.count() == 0

    # cPanel must separately attest that the live Passenger app is the same
    # Django directory. Only the importer fixture bypasses the UAPI call.
    monkeypatch.setattr(importer, "verify_live_passenger_mapping", lambda app: True)
    report = importer.import_receipts(
        root, app, docroot, "09175814408", apply=True, recipe=recipe, digest=digest
    )
    assert report["created"] == 1
    product = Product.objects.get()
    assert product.active is False
    assert product.price == 0
    assert product.metadata["factory_publication_permission"] is False
    assert product.metadata["factory_commercial_release"] is False
    assert product.metadata["factory_objective_release_readiness"] == "pending"
    assert product.metadata["factory_chatgpt_final_review"] == "pending_independent_review"
    assert product.metadata["factory_software_qa_scope"] == "private_archive_integrity_only"

    repeat = importer.import_receipts(
        root, app, docroot, "09175814408", apply=True, recipe=recipe, digest=digest
    )
    assert repeat["created"] == 0
    assert repeat["already_present"] == 1
    assert Product.objects.count() == 1
    assert Product.objects.filter(active=True).count() == 0

    with pytest.raises(RuntimeError, match="SELECTED_PRIVATE_RECEIPT_NOT_FOUND"):
        importer.import_receipts(
            root, app, docroot, "09175814408", apply=True,
            recipe=recipe, digest="f" * 64
        )
    assert Product.objects.count() == 1


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
    receipt_dir = inbox / "receipts" / "farm_enterprise_economics"
    receipt_dir.mkdir(parents=True)
    (receipt_dir / ("a" * 64 + ".json")).write_text("{}")
    with pytest.raises(RuntimeError, match="IDENTIFIED_STORE_OWNER_NOT_PRESENT"):
        importer.import_receipts(inbox, app, docroot, "09175814408", apply=True,
                                 recipe="farm_enterprise_economics", digest="a" * 64)
    assert Product.objects.count() == 0


def test_exact_selector_rejects_invalid_versions_and_links(tmp_path):
    importer = module("import_factory_store_drafts")
    root = tmp_path / "private"
    (root / "receipts" / "farm_enterprise_economics").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="EXACT_FACTORY_SHA256_REQUIRED"):
        importer.selected_receipt(root, "farm_enterprise_economics", "not-a-hash")
    with pytest.raises(RuntimeError, match="EXACT_FACTORY_RECIPE_REQUIRED"):
        importer.selected_receipt(root, "../other", "a" * 64)
    with pytest.raises(RuntimeError, match="SELECTED_PRIVATE_RECEIPT_NOT_FOUND"):
        importer.selected_receipt(root, "farm_enterprise_economics", "a" * 64)
    poisoned = root / "receipts" / "farm_enterprise_economics" / ("a" * 64 + ".json")
    poisoned.symlink_to(tmp_path / "outside")
    with pytest.raises(RuntimeError, match="SELECTED_PRIVATE_RECEIPT_NOT_FOUND"):
        importer.selected_receipt(root, "farm_enterprise_economics", "a" * 64)


def test_live_passenger_mapping_blocks_wrong_django_database(tmp_path):
    importer = module("import_factory_store_drafts")
    app = tmp_path / "Saeit-staging"
    wrong = tmp_path / "mojplaywin.com"
    payload = {"result": {"status": 1, "data": [{
        "domain": "mojplaywin.com", "base_uri": "/", "app_root": str(wrong)
    }]}}
    with pytest.raises(RuntimeError, match="LIVE_PASSENGER_MAPPING_DOES_NOT_MATCH_TARGET_APP"):
        importer.verify_live_passenger_mapping(app, payload=payload)
    payload["result"]["data"][0]["app_root"] = str(app)
    assert importer.verify_live_passenger_mapping(app, payload=payload) is True
    payload["result"]["data"].append(dict(payload["result"]["data"][0]))
    with pytest.raises(RuntimeError, match="LIVE_PASSENGER_MAPPING_DOES_NOT_MATCH_TARGET_APP"):
        importer.verify_live_passenger_mapping(app, payload=payload)
