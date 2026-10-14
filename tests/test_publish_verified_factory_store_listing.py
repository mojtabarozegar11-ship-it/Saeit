"""Native free software listing respects actual publication approval and QA."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest
from django.test import override_settings
from core.models import Product, KnowledgeArticle, ApprovalRequest

ROOT = Path(__file__).resolve().parents[1] / "scripts"


def script(name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / (name + ".py")))
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


@pytest.fixture
def prepared_store(django_user_model, tmp_path):
    receiver = script("store_receiver")
    publisher = script("publish_factory_free_tool")
    owner = django_user_model.objects.create_superuser(
        username="factory-test-owner", email="", password="internal-test-only"
    )
    webroot = tmp_path / "mojplaywin.com"
    webroot.mkdir()
    app = tmp_path / "Saeit-staging"
    app.mkdir()
    (app / "manage.py").write_text("# django app")
    (webroot / "passenger_wsgi.py").write_text(
        "# Actual test app path /Saeit-staging\n"
    )
    inbox = tmp_path / ".saeit-factory-inbox"
    path = inbox / "incoming" / publisher.RECIPE
    path.mkdir(parents=True)
    zf = tmp_path / "sample.zip"
    with zipfile.ZipFile(str(zf), "w", zipfile.ZIP_DEFLATED) as arc:
        arc.writestr(publisher.RECIPE + "/calculator.py", "print('offline')")
        arc.writestr(publisher.RECIPE + "/README.md", "Synthetic examples only")
    digest = hashlib.sha256(zf.read_bytes()).hexdigest()
    (path / (digest + ".zip.partial")).write_bytes(zf.read_bytes())
    (path / (digest + ".json.partial")).write_text(json.dumps({
        "name": "Farm Enterprise Economics Toolkit",
        "recipe": publisher.RECIPE,
        "artifact_sha256": digest,
        "qa_status": "passed",
        "commercial_status": "private_internal_qa_pass_not_published",
        "public_listing_enabled": False, "owner_publication_approval": False,
        "price": None,
    }))
    receiver.finalize(inbox, publisher.RECIPE, digest)
    publisher.publish(inbox, webroot, release_authorized=True)
    product = Product.objects.create(
        title="Farm Enterprise Economics Toolkit",
        product_type="digital", active=False, price="0.00",
        currency="USD", owner=owner,
        metadata={
            "factory_origin": "saeit_vps",
            "factory_bridge_sha256": digest,
            "factory_recipe": publisher.RECIPE,
            "factory_software_qa": "passed",
            "factory_status": "needs_editorial_pricing_and_owner_approval",
        },
    )
    return inbox, app, webroot, digest, product, owner


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_authorized_release_via_approval_service_is_public_and_idempotent(prepared_store):
    inbox, app, webroot, digest, product, owner = prepared_store
    publish = script("publish_verified_factory_store_listing")
    assert publish.publish(inbox, app, webroot)["status"] == "verified_dry_run"
    assert Product.objects.filter(active=True).count() == 0
    with pytest.raises(ValueError, match="OWNER_PUBLICATION_MANDATE_REQUIRED"):
        publish.publish(inbox, app, webroot, apply=True)
    result = publish.publish(
        inbox, app, webroot, apply=True, delegated_owner_instruction=True
    )
    assert result["status"] == "activated_free"
    product.refresh_from_db()
    assert product.active is True
    assert product.price == 0
    assert product.owner == owner
    assert product.knowledge_article.published
    assert product.metadata["factory_public_url"].endswith("/index.html")
    assert ApprovalRequest.objects.filter(status="approved", target_type="Product").count() == 1
    assert ApprovalRequest.objects.filter(status="approved", target_type="KnowledgeArticle").count() == 1
    assert publish.publish(inbox, app, webroot, apply=True,
                           delegated_owner_instruction=True)["status"] == "already_active"
    assert Product.objects.count() == 1
    response = __import__("django.test", fromlist=["Client"]).Client().get("/store/")
    assert response.status_code == 200
    assert "Farm Enterprise Economics Toolkit" in response.content.decode("utf-8")


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_ambiguous_ownership_blocks_public_release(prepared_store, django_user_model):
    inbox, app, webroot, digest, product, owner = prepared_store
    django_user_model.objects.create_superuser(
        username="second-owner", password="not-used", email=""
    )
    publisher = script("publish_verified_factory_store_listing")
    with pytest.raises(RuntimeError, match="UNIQUE_ACTIVE_OWNER"):
        publisher.publish(inbox, app, webroot, apply=True,
                          delegated_owner_instruction=True)
    product.refresh_from_db()
    assert not product.active
    assert KnowledgeArticle.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_positive_price_blocks_free_release(prepared_store):
    inbox, app, webroot, digest, product, owner = prepared_store
    product.price = "15.00"
    product.save()
    publisher = script("publish_verified_factory_store_listing")
    with pytest.raises(ValueError, match="FACTORY_DRAFT_RELEASE_GATE_FAILED"):
        publisher.publish(inbox, app, webroot, apply=True,
                          delegated_owner_instruction=True)
    assert KnowledgeArticle.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_public_artifact_corruption_prevents_activation(prepared_store):
    inbox, app, webroot, digest, product, owner = prepared_store
    publisher = script("publish_verified_factory_store_listing")
    archive = webroot / "factory-releases/farm-enterprise-economics-v1/Farm_Enterprise_Economics_Toolkit_Free_v1.zip"
    archive.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="PUBLIC_FACTORY_SHA256_MISMATCH"):
        publisher.publish(inbox, app, webroot, apply=True,
                          delegated_owner_instruction=True)
    product.refresh_from_db()
    assert not product.active
