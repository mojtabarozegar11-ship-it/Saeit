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
    if name == "publish_verified_factory_store_listing":
        # Isolate the store workflow from absent production-only signed QA
        # artifacts; the dedicated release-gate suite verifies those separately.
        from types import SimpleNamespace
        original_loaded = instance.loaded
        def loaded(module_name, filename):
            if module_name == "factory_premium_commercial_guard":
                return SimpleNamespace(require_quality_clearance=lambda *args: {
                    "status": "VERIFIED_SIGNED_PREMIUM_1000",
                    "1000_quality_verified": True,
                    "chatgpt_final_review": "CHATGPT_FINAL_REVIEW_VERIFIED",
                })
            return original_loaded(module_name, filename)
        instance.loaded = loaded
    return instance


def simulate_shared_release_gate(monkeypatch, *, count=1, complete=True):
    """A narrow fake for the production-only gate model absent in local CI.

    This simulates schema presence; it is NOT a QA approval or a manifest.
    The actual production ApprovalRequest.save enforces the signed manifest.
    """
    from django.apps import apps
    from types import SimpleNamespace

    real_get_model = apps.get_model

    class Query:
        def count(self):
            return count

        def first(self):
            return SimpleNamespace(
                run_id=1, artifact_id=1,
                manifest_id=1 if complete else None
            )

    simulated_model = SimpleNamespace(
        objects=SimpleNamespace(filter=lambda **kwargs: Query())
    )

    def overridden_get_model(app_label, model_name=None, **kwargs):
        if app_label == "core" and model_name == "FactoryReleaseGate":
            return simulated_model
        return real_get_model(app_label, model_name, **kwargs)

    monkeypatch.setattr(apps, "get_model", overridden_get_model)


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
    release = webroot / "factory-releases" / publisher.PUBLIC_SLUG
    release.mkdir(parents=True)
    (release / publisher.PUBLIC_FILENAME).write_bytes(zf.read_bytes())
    (release / "index.html").write_text(publisher.landing_page(digest), encoding="utf-8")
    (release / "SHA256SUMS.txt").write_text(
        digest + "  " + publisher.PUBLIC_FILENAME + "\\n", encoding="utf-8"
    )
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
def test_authorized_release_via_approval_service_is_public_and_idempotent(prepared_store, monkeypatch):
    simulate_shared_release_gate(monkeypatch)
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

@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_runtime_shared_release_gate_blocks_even_dry_run_without_db_writes(
    prepared_store, monkeypatch
):
    """Production may require a gate absent from the simpler local Product class.

    The preflight must discover that requirement before creating an article,
    an ApprovalRequest, or mutating the product in the live database.
    """
    from django.core.exceptions import ValidationError

    inbox, app, webroot, digest, product, owner = prepared_store
    original_clean = Product.clean

    def deployed_clean(self):
        original_clean(self)
        if self.active and self.metadata.get("factory_status") == "published_free":
            raise ValidationError(
                "Factory Product approval requires its shared Release Gate."
            )

    simulate_shared_release_gate(monkeypatch)
    monkeypatch.setattr(Product, "clean", deployed_clean)
    publisher = script("publish_verified_factory_store_listing")
    for apply in (False, True):
        with pytest.raises(ValueError, match="RUNTIME_RELEASE_GATE_NOT_READY"):
            publisher.publish(
                inbox, app, webroot, apply=apply,
                delegated_owner_instruction=True,
            )
        product.refresh_from_db()
        assert product.active is False
        assert product.knowledge_article_id is None
        assert product.metadata["factory_status"] == "needs_editorial_pricing_and_owner_approval"
        assert KnowledgeArticle.objects.count() == 0
        assert ApprovalRequest.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_dry_run_on_an_unsaved_candidate_cannot_change_product_state(prepared_store, monkeypatch):
    simulate_shared_release_gate(monkeypatch)
    inbox, app, webroot, digest, product, owner = prepared_store
    publisher = script("publish_verified_factory_store_listing")
    assert publisher.publish(inbox, app, webroot)["status"] == "verified_dry_run"
    product.refresh_from_db()
    assert product.active is False
    assert product.metadata["factory_status"] == "needs_editorial_pricing_and_owner_approval"
    assert product.metadata.get("factory_publication_permission") is None
    assert Product.objects.count() == 1
    assert KnowledgeArticle.objects.count() == 0
    assert ApprovalRequest.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_missing_deployed_release_gate_model_fails_closed(prepared_store):
    inbox, app, webroot, digest, product, owner = prepared_store
    publisher = script("publish_verified_factory_store_listing")
    with pytest.raises(ValueError, match="FACTORY_SHARED_RELEASE_GATE_MODEL_MISSING"):
        publisher.publish(inbox, app, webroot, apply=True,
                          delegated_owner_instruction=True)
    product.refresh_from_db()
    assert not product.active
    assert ApprovalRequest.objects.count() == 0
    assert KnowledgeArticle.objects.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_no_gate_row_or_missing_manifest_blocks_publish(prepared_store, monkeypatch):
    inbox, app, webroot, digest, product, owner = prepared_store
    publisher = script("publish_verified_factory_store_listing")
    simulate_shared_release_gate(monkeypatch, count=0)
    with pytest.raises(ValueError, match="FACTORY_SHARED_RELEASE_GATE_MISSING_OR_AMBIGUOUS"):
        publisher.publish(inbox, app, webroot, apply=True,
                          delegated_owner_instruction=True)
    simulate_shared_release_gate(monkeypatch, count=1, complete=False)
    with pytest.raises(ValueError, match="FACTORY_RELEASE_EVIDENCE_CHAIN_INCOMPLETE"):
        publisher.publish(inbox, app, webroot, apply=True,
                          delegated_owner_instruction=True)
    product.refresh_from_db()
    assert product.active is False
    assert KnowledgeArticle.objects.count() == 0
    assert ApprovalRequest.objects.count() == 0
