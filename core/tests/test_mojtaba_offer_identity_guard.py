"""Commercial lifecycle integrity for the existing Mojtaba.bot.ai economic gateway.

All fixtures are internal Django test data. No buyers, payments, outbound
messages, listings or production source are modified by these tests.
"""
import pytest

from core.economic_tool_pack import (
    OFFER_TITLE, offer_design, mvp_build, growth_experiment,
)
from core.models import Product


def seeded(status, *, title=OFFER_TITLE, kind="service", active=False):
    return Product.objects.create(
        title=title, product_type=kind, price="0.00",
        currency="USD", active=active,
        metadata={"commercial_status": status, "pricing_status": "requires_market_evidence"},
    )


@pytest.mark.django_db
def test_first_offer_creates_only_one_inactive_private_service_draft():
    first = offer_design({})
    row = Product.objects.get()
    assert first["verified_effect"] is True
    assert first["next_action"] == "income_mvp_build"
    assert row.title == OFFER_TITLE and row.product_type == "service"
    assert row.active is False and row.price == 0
    assert row.metadata["commercial_status"] == "offer_designed"


@pytest.mark.django_db
@pytest.mark.parametrize("stage,next_action", [
    ("offer_designed", "income_mvp_build"),
    ("mvp_built", "income_growth_experiment"),
    ("growth_ready", "await_external_acquisition"),
])
def test_repeated_offer_design_does_not_create_another_product(stage, next_action):
    row = seeded(stage)
    before = dict(row.metadata)
    first = offer_design({})
    second = offer_design({})
    assert Product.objects.count() == 1
    row.refresh_from_db()
    assert row.metadata == before
    assert first["verified_effect"] is False
    assert second["verified_effect"] is False
    assert first["next_action"] == second["next_action"] == next_action


@pytest.mark.django_db
def test_existing_book_cannot_be_hijacked_as_an_automation_service():
    book = seeded("growth_ready", kind="book")
    first = offer_design({})
    book.refresh_from_db()
    assert Product.objects.count() == 2
    assert book.product_type == "book" and book.metadata["commercial_status"] == "growth_ready"
    assert first["verified_effect"] is True


@pytest.mark.django_db
def test_duplicate_private_services_fail_closed_without_rewriting_either():
    older = seeded("offer_designed")
    newer = seeded("mvp_built")
    with pytest.raises(ValueError, match="DUPLICATE_OFFER_REQUIRES_RECONCILIATION"):
        offer_design({})
    assert Product.objects.count() == 2
    older.refresh_from_db()
    newer.refresh_from_db()
    assert older.metadata["commercial_status"] == "offer_designed"
    assert newer.metadata["commercial_status"] == "mvp_built"


@pytest.mark.django_db
def test_unrelated_commercial_draft_is_not_converted_to_mojtaba_deliverable():
    unrelated = seeded("offer_designed", title="Another client's separate audit")
    with pytest.raises(ValueError, match="No designed offer exists"):
        mvp_build({})
    unrelated.refresh_from_db()
    assert unrelated.metadata["commercial_status"] == "offer_designed"


@pytest.mark.django_db
def test_unrelated_mvp_is_not_auto_promoted_to_growth_ready():
    unrelated = seeded("mvp_built", title="A different client's workbook")
    with pytest.raises(ValueError, match="No built MVP exists"):
        growth_experiment({})
    unrelated.refresh_from_db()
    assert unrelated.metadata["commercial_status"] == "mvp_built"


@pytest.mark.django_db
def test_active_unreviewed_service_is_not_private_mvp_builder_input():
    row = seeded("offer_designed", active=True)
    with pytest.raises(ValueError, match="No designed offer exists"):
        mvp_build({})
    row.refresh_from_db()
    assert row.active is True and row.metadata["commercial_status"] == "offer_designed"


@pytest.mark.django_db
def test_active_service_is_not_silently_reclassified_as_growth_ready():
    row = seeded("mvp_built", active=True)
    with pytest.raises(ValueError, match="No built MVP exists"):
        growth_experiment({})
    row.refresh_from_db()
    assert row.metadata["commercial_status"] == "mvp_built"


@pytest.mark.django_db
def test_growth_needs_a_genuine_private_deliverable_not_only_metadata():
    row = seeded("mvp_built")
    with pytest.raises(ValueError, match="MVP_ASSET_ATTESTATION_MISSING"):
        growth_experiment({})
    row.refresh_from_db()
    assert row.metadata["commercial_status"] == "mvp_built"


@pytest.mark.django_db
def test_growth_advances_only_after_original_private_asset_is_verified(tmp_path):
    from unittest.mock import patch
    row = seeded("offer_designed")
    with patch("core.economic_tool_pack.Path.home", return_value=tmp_path):
        mvp = mvp_build({})
        assert mvp["verified_effect"] is True
        result = growth_experiment({})
    row.refresh_from_db()
    assert result["verified_effect"] is True
    assert row.metadata["commercial_status"] == "growth_ready"
    assert row.metadata["commercial_release"] == "not_published"


@pytest.mark.django_db
@pytest.mark.parametrize("tamper", ["bytes", "digest", "location"])
def test_growth_rejects_modified_or_repointed_asset(tmp_path, tamper):
    from pathlib import Path
    from unittest.mock import patch
    row = seeded("offer_designed")
    with patch("core.economic_tool_pack.Path.home", return_value=tmp_path):
        mvp_build({})
        row.refresh_from_db()
        asset = row.metadata["artifact"]
        path = Path(asset["relative_path"])
        if tamper == "bytes":
            path.write_bytes(path.read_bytes() + b"tampered")
        elif tamper == "digest":
            asset["sha256"] = "0" * 64
        else:
            asset["relative_path"] = str(tmp_path / "outside-customer-file.html")
        row.save(update_fields=["metadata"])
        with pytest.raises(ValueError, match="MVP_ASSET_"):
            growth_experiment({})
    row.refresh_from_db()
    assert row.metadata["commercial_status"] == "mvp_built"
