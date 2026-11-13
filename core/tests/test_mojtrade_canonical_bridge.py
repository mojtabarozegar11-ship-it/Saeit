"""MojTrade research is a real canonical AgentTask, never an order executor."""
from datetime import timedelta
from io import StringIO
import json
import os

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch

from core.models import Agent, AgentTask, AuditLog
from core.mojtrade_bridge import MojTradeBridgeError, ingest_private_observation
from core.management.commands.mojtrade_market_watch_export import (
    PRIVATE_NAME, fresh_canonical_drafts, write_private_feed,
)
from core.mojtrade_signal_drafts import MarketWatchDraftError
from core.financial_brand_pages import BRANDS
from core.unified_bot_identity import (
    BOT_CODE, MOJTRADE_RESEARCH_CAPABILITY, module_for_capability,
)


@pytest.fixture
def canonical_market(tmp_path, settings):
    call_command("seed_online_income_agents", stdout=StringIO())
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    settings.MOJTRADE_PRIVATE_DIR = str(root)
    now = timezone.now().replace(microsecond=0)
    generated = now - timedelta(minutes=1)
    observed = now - timedelta(hours=1)
    payload = {
        "schema_version": 1,
        "source": "mojtrade-vps",
        "generated_at": generated.isoformat(),
        "expires_at": (now + timedelta(minutes=60)).isoformat(),
        "signals": [
            {
                "id": "a" * 24, "market": "crypto", "symbol": "BTC/USD",
                "timeframe": "1h", "stance": "watch_buy",
                "observed_at": observed.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
                "data_source": "coinbase-exchange-public-candles",
            },
            {
                "id": "b" * 24, "market": "crypto", "symbol": "ETH/USD",
                "timeframe": "1h", "stance": "neutral",
                "observed_at": observed.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
                "data_source": "bitstamp-public-ohlc",
            },
        ],
    }
    source = root / "validated-payload.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(source, 0o600)
    return root, source, payload


@pytest.mark.django_db
def test_market_receipt_is_owned_by_one_bot_and_has_no_execution(canonical_market):
    output = StringIO()
    call_command("mojtrade_research_cycle", stdout=output)
    assert "new_receipt=1" in output.getvalue()
    assert "orders=0" in output.getvalue()
    assert "execution=disabled" in output.getvalue()
    task = AgentTask.objects.get(capability_code=MOJTRADE_RESEARCH_CAPABILITY)
    assert task.agent.code == BOT_CODE
    assert task.agent.active
    assert task.action_type == MOJTRADE_RESEARCH_CAPABILITY
    assert task.status == "completed"
    assert task.attempt_count == 1
    assert task.cost == 0
    assert task.output_data["verified_effect"] is True
    assert task.output_data["execution"] == "disabled"
    assert task.output_data["orders"] == 0
    assert task.output_data["broker_connected"] is False
    assert task.output_data["published"] is False
    assert task.output_data["revenue_verified"] is False
    review = task.output_data["strategy_risk_review"]
    assert review["schema"] == "mojtrade-research-gate-v1"
    assert review["setup_candidates_not_trades"] == 1
    assert review["decisions"][0]["classification"] == "monitor_bullish"
    assert review["decisions"][1]["classification"] == "no_setup"
    assert review["risk_gate"] == "blocked_missing_broker_verified_inputs"
    assert review["executable_order_intents"] == []
    assert review["broker_connected"] is False
    assert review["orders"] == 0 and review["execution"] == "disabled"
    assert len(review["decision_digest_sha256"]) == 64
    assert len(task.output_data["market_observations"]) == 2
    assert task.output_data["market_observations"][1]["data_source"] == "bitstamp-public-ohlc"
    assert "validated-payload.json" not in json.dumps(task.input_data)
    assert not task.agent.capabilities.filter(code__in=["trade", "payment", "withdraw", "deploy"]).exists()
    # Existing Django migrations seed unrelated agent records; the bridge must
    # not create an extra MojTrade executor identity.
    assert Agent.objects.filter(code=BOT_CODE).count() == 1
    assert not Agent.objects.filter(code__startswith="mojtrade").exists()
    assert module_for_capability(MOJTRADE_RESEARCH_CAPABILITY) == "mojtrade_private_research"
    assert AuditLog.objects.filter(target_type="AgentTask", target_id=str(task.pk), action="task_claimed").count() == 1
    assert AuditLog.objects.filter(target_type="AgentTask", target_id=str(task.pk), action="task_completed").count() == 1
    assert AuditLog.objects.filter(target_type="AgentTask", target_id=str(task.pk), action="mojtrade_private_research_ingested").count() == 1


@pytest.mark.django_db
def test_reprocessing_same_snapshot_is_idempotent_and_does_not_make_new_receipts(canonical_market):
    first, created = ingest_private_observation()
    second, created_again = ingest_private_observation()
    assert created is True and created_again is False
    assert first.pk == second.pk
    assert AgentTask.objects.filter(capability_code=MOJTRADE_RESEARCH_CAPABILITY).count() == 1
    assert AuditLog.objects.filter(action="mojtrade_private_research_ingested").count() == 1


@pytest.mark.django_db
def test_economic_worker_does_not_claim_or_misclassify_market_research(canonical_market):
    agent = Agent.objects.get(code=BOT_CODE)
    pending = AgentTask.objects.create(
        agent=agent, action_type=MOJTRADE_RESEARCH_CAPABILITY,
        capability_code=MOJTRADE_RESEARCH_CAPABILITY,
        risk_snapshot="low", status="queued",
    )
    output = StringIO()
    call_command("run_economic_worker", stdout=output)
    assert "IDLE: no queued economic task." in output.getvalue()
    assert "BLOCKED_UNSUPPORTED" not in output.getvalue()
    output = StringIO()
    call_command("online_income_cycle", "--dry-run", stdout=output)
    assert f"BRAIN_CONTINUE task={pending.pk}" not in output.getvalue()
    pending.refresh_from_db()
    assert pending.status == "queued" and pending.attempt_count == 0


@pytest.mark.django_db
def test_market_research_cannot_execute_concurrently_with_other_unified_work(canonical_market):
    agent = Agent.objects.get(code=BOT_CODE)
    AgentTask.objects.create(
        agent=agent, action_type="income_market_research",
        capability_code="income_market_research",
        status="running", execution_id="other-running-worker",
    )
    with pytest.raises(ValueError, match="already has a running task"):
        ingest_private_observation()
    assert AgentTask.objects.count() == 1
    assert not AuditLog.objects.filter(action="mojtrade_private_research_ingested").exists()


@pytest.mark.django_db
def test_noncompleted_duplicate_requires_reconciliation(canonical_market):
    task, _ = ingest_private_observation()
    task.status = "blocked"
    task.save(update_fields=["status"])
    with pytest.raises(MojTradeBridgeError, match="requires_reconciliation"):
        ingest_private_observation()
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("condition", ["expired", "future", "forged_method", "forged_id", "binance_usdt", "old_candle"])
def test_invalid_market_data_cannot_create_canonical_task(canonical_market, condition):
    _, source, payload = canonical_market
    if condition == "expired":
        payload["expires_at"] = (timezone.now() - timedelta(seconds=1)).isoformat()
    elif condition == "future":
        payload["generated_at"] = (timezone.now() + timedelta(minutes=3)).isoformat()
    elif condition == "forged_method":
        payload["signals"][0]["method"] = "fake_model_trade_now"
    elif condition == "forged_id":
        payload["signals"][0]["id"] = "external-order-id"
    elif condition == "binance_usdt":
        payload["signals"][0]["data_source"] = "binance-public-klines"
    else:
        payload["signals"][0]["observed_at"] = (timezone.now() - timedelta(days=2)).isoformat()
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MojTradeBridgeError):
        ingest_private_observation()
    assert not AgentTask.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("condition", ["unconfigured", "world_readable", "symlink", "public_directory"])
def test_private_source_security_is_fail_closed(canonical_market, settings, tmp_path, condition):
    root, source, payload = canonical_market
    if condition == "unconfigured":
        settings.MOJTRADE_PRIVATE_DIR = ""
    elif condition == "world_readable":
        os.chmod(source, 0o644)
    elif condition == "symlink":
        original = root / "original.json"
        source.rename(original)
        source.symlink_to(original)
    else:
        os.chmod(root, 0o755)
    with pytest.raises(MojTradeBridgeError):
        ingest_private_observation()
    assert not AgentTask.objects.exists()


@pytest.mark.django_db
def test_unseeded_bot_does_not_autocreate_agents_or_approve_trade(canonical_market):
    Agent.objects.filter(code=BOT_CODE).update(active=False)
    with pytest.raises(MojTradeBridgeError, match="canonical_bot_is_not_active"):
        ingest_private_observation()
    assert not AgentTask.objects.exists()



@pytest.mark.django_db
def test_private_trilingual_signal_feed_exports_one_canonical_receipt(canonical_market):
    root, source, _ = canonical_market
    task, created = ingest_private_observation()
    assert created is True
    out = StringIO()
    call_command("mojtrade_market_watch_export", stdout=out)
    feed = root / PRIVATE_NAME
    assert feed.is_file()
    assert os.stat(feed).st_mode & 0o077 == 0
    document = json.loads(feed.read_text(encoding="utf-8"))
    assert document == task.output_data["market_watch_drafts"]
    assert document["canonical_owner"] == BOT_CODE
    assert document["status"] == "private_owner_review_only"
    assert document["languages"] == ["fa", "en", "ar"]
    assert document["publication_authorized"] is False
    assert document["trade_execution_authorized"] is False
    assert document["executed_orders"] == 0
    assert all(row["entry_price"] is None for row in document["alerts"])
    assert "publications=0 orders=0" in out.getvalue()
    assert source.is_file()
    before = feed.read_bytes()
    call_command("mojtrade_market_watch_export", stdout=StringIO())
    assert feed.read_bytes() == before
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
def test_private_signal_feed_refuses_expired_canonical_receipt(canonical_market):
    task, _ = ingest_private_observation()
    with pytest.raises(MarketWatchDraftError, match="expired"):
        fresh_canonical_drafts(now=timezone.now() + timedelta(days=2))


@pytest.mark.django_db
def test_private_signal_feed_refuses_modified_or_unfinished_receipt(canonical_market):
    task, _ = ingest_private_observation()
    output = dict(task.output_data)
    changed = dict(output["market_watch_drafts"])
    changed["publication_authorized"] = True
    output["market_watch_drafts"] = changed
    task.output_data = output
    task.save(update_fields=["output_data"])
    with pytest.raises(MarketWatchDraftError, match="stored_draft_differs"):
        fresh_canonical_drafts()
    task.status = "blocked"
    task.save(update_fields=["status"])
    with pytest.raises(MarketWatchDraftError, match="no_completed"):
        fresh_canonical_drafts()


@pytest.mark.django_db
def test_private_export_does_not_create_feed_without_source_task(canonical_market):
    root, _, _ = canonical_market
    with pytest.raises(CommandError, match="no_completed"):
        call_command("mojtrade_market_watch_export")
    assert not (root / PRIVATE_NAME).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("condition", ["symlink_file", "public_directory", "symlink_directory"])
def test_signal_feed_export_refuses_unsafe_target(canonical_market, tmp_path, settings, condition):
    root, _, _ = canonical_market
    ingest_private_observation()
    if condition == "symlink_file":
        outside = tmp_path / "unmodified.txt"
        outside.write_text("private original", encoding="utf-8")
        (root / PRIVATE_NAME).symlink_to(outside)
    elif condition == "public_directory":
        os.chmod(root, 0o755)
    else:
        replacement = tmp_path / "linked"
        replacement.symlink_to(root, target_is_directory=True)
        settings.MOJTRADE_PRIVATE_DIR = str(replacement)
    with pytest.raises(CommandError, match="PRIVATE_WATCH_EXPORT_REJECTED"):
        call_command("mojtrade_market_watch_export")
    if condition == "symlink_file":
        assert outside.read_text(encoding="utf-8") == "private original"



@pytest.mark.django_db
def test_private_watch_api_denies_anonymous_and_regular_staff(client, canonical_market):
    url = reverse("mojtrade-private-watch")
    response = client.get(url)
    assert response.status_code == 403
    assert response.json() == {"detail": "owner_access_required"}
    assert "no-store" in response["Cache-Control"]
    assert "noindex" in response["X-Robots-Tag"]
    assert "Cookie" in response["Vary"]
    for label, is_staff in (("normal-watch", False), ("staff-watch", True)):
        user = get_user_model().objects.create_user(
            username=label, is_staff=is_staff,
        )
        client.force_login(user)
        assert client.get(url).status_code == 403
        client.logout()


@pytest.mark.django_db
def test_private_watch_api_active_superuser_sees_only_fresh_canonical_draft(client, canonical_market):
    task, created = ingest_private_observation()
    assert created is True
    owner = get_user_model().objects.create_superuser(
        username="watch-owner", email="watch-owner@example.com",
        password="local-test-only",
    )
    client.force_login(owner)
    response = client.get(reverse("mojtrade-private-watch"))
    assert response.status_code == 200
    document = response.json()
    assert document["owner"] == BOT_CODE
    assert document["task_id"] == task.pk
    assert document["private_research_only"] is True
    assert document["watch"] == task.output_data["market_watch_drafts"]
    assert document["watch"]["languages"] == ["fa", "en", "ar"]
    assert document["watch"]["publication_authorized"] is False
    assert document["watch"]["trade_execution_authorized"] is False
    assert all(card["entry_price"] is None for card in document["watch"]["alerts"])
    assert "no-store" in response["Cache-Control"]
    assert "noarchive" in response["X-Robots-Tag"]
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "Cookie" in response["Vary"]
    assert response["Content-Type"].startswith("application/json")
    assert AgentTask.objects.count() == 1
    assert not AuditLog.objects.filter(action="signal_published").exists()


@pytest.mark.django_db
def test_private_watch_api_refuses_missing_stale_or_incomplete_task(client, canonical_market):
    owner = get_user_model().objects.create_superuser(
        username="watch-missing-owner", email="missing@example.com",
        password="local-test-only",
    )
    client.force_login(owner)
    url = reverse("mojtrade-private-watch")
    empty = client.get(url)
    assert empty.status_code == 503
    assert "watch" not in empty.json()
    task, _ = ingest_private_observation()
    task.status = "blocked"
    task.save(update_fields=["status"])
    blocked = client.get(url)
    assert blocked.status_code == 503
    task.status = "completed"
    task.save(update_fields=["status"])
    original = dict(task.output_data)
    saved = dict(original["market_watch_drafts"])
    saved["publication_authorized"] = True
    original["market_watch_drafts"] = saved
    task.output_data = original
    task.save(update_fields=["output_data"])
    tampered = client.get(url)
    assert tampered.status_code == 503
    assert "watch" not in tampered.json()
    assert tampered.json()["trade_execution_authorized"] is False


@pytest.mark.django_db
def test_private_watch_api_disabled_superuser_denied(client, canonical_market):
    user = get_user_model().objects.create_superuser(
        username="deactivated-watch-owner", email="disabled@example.com",
        password="local-test-only",
    )
    user.is_active = False
    user.save(update_fields=["is_active"])
    client.force_login(user)
    response = client.get(reverse("mojtrade-private-watch"))
    assert response.status_code == 403
    assert "watch" not in response.json()


@pytest.mark.django_db
def test_private_watch_api_post_does_not_trigger_market_ingest(client, canonical_market):
    owner = get_user_model().objects.create_superuser(
        username="post-watch-owner", email="post@example.com",
        password="local-test-only",
    )
    client.force_login(owner)
    response = client.post(reverse("mojtrade-private-watch"), data={"trade": "buy"})
    assert response.status_code == 405
    assert AgentTask.objects.count() == 0



@pytest.mark.django_db
def test_private_watch_api_expires_even_after_a_previously_successful_get(client, canonical_market):
    task, _ = ingest_private_observation()
    user = get_user_model().objects.create_superuser(
        username="watch-expired-owner", email="watch-expired@example.com",
        password="local-test-only",
    )
    client.force_login(user)
    url = reverse("mojtrade-private-watch")
    assert client.get(url).status_code == 200
    with patch(
        "core.management.commands.mojtrade_market_watch_export.timezone.now",
        return_value=timezone.now() + timedelta(days=1),
    ):
        expired = client.get(url)
    assert expired.status_code == 503
    assert "watch" not in expired.json()
    assert "no-store" in expired["Cache-Control"]
    assert task.status == "completed"


@pytest.mark.django_db
def test_private_watch_api_does_not_revert_to_old_completed_snapshot(client, canonical_market):
    earlier, _ = ingest_private_observation()
    user = get_user_model().objects.create_superuser(
        username="watch-no-fallback-owner", email="no-fallback@example.com",
        password="local-test-only",
    )
    client.force_login(user)
    latest = AgentTask.objects.create(
        agent=earlier.agent,
        action_type=MOJTRADE_RESEARCH_CAPABILITY,
        capability_code=MOJTRADE_RESEARCH_CAPABILITY,
        risk_snapshot="low",
        status="queued",
        input_data={"source_sha256": "d" * 64},
    )
    with patch(
        "core.management.commands.mojtrade_market_watch_export.timezone.now",
        return_value=timezone.now(),
    ):
        response = client.get(reverse("mojtrade-private-watch"))
    assert latest.pk > earlier.pk
    assert response.status_code == 503
    assert "watch" not in response.json()
    assert AgentTask.objects.count() == 2



@pytest.mark.django_db
@pytest.mark.parametrize("tamper", ["missing", "digest", "source_binding", "duplicated"])
def test_private_watch_requires_exact_canonical_audit_trail(canonical_market, tamper):
    from core.mojtrade_signal_drafts import MarketWatchDraftError

    task, _ = ingest_private_observation()
    receipt = AuditLog.objects.get(
        action="mojtrade_private_research_ingested", target_id=str(task.pk),
    )
    if tamper == "missing":
        receipt.delete()
    elif tamper == "digest":
        receipt.after_state = {**receipt.after_state, "source_sha256": "d" * 64}
        receipt.save(update_fields=["after_state"])
    elif tamper == "source_binding":
        output = dict(task.output_data)
        output["evidence"] = {"source_sha256": "d" * 64}
        task.output_data = output
        task.save(update_fields=["output_data"])
    else:
        AuditLog.objects.create(
            actor_type="agent", actor_id=str(task.agent_id),
            action="mojtrade_private_research_ingested",
            target_type="AgentTask", target_id=str(task.pk),
            after_state=dict(receipt.after_state),
            trace_id="duplicate-receipt-proof-must-fail",
        )
    with pytest.raises(MarketWatchDraftError, match="audit"):
        fresh_canonical_drafts()


@pytest.mark.django_db
def test_mojtrade_readiness_api_denies_public_and_non_superusers(client, canonical_market):
    url = reverse("mojtrade-private-readiness")
    anonymous = client.get(url)
    assert anonymous.status_code == 403
    assert "gates" not in anonymous.json()
    assert "no-store" in anonymous["Cache-Control"]

    user = get_user_model().objects.create_user(
        username="staff-readiness-not-owner", is_staff=True,
    )
    client.force_login(user)
    denied = client.get(url)
    assert denied.status_code == 403
    assert "gates" not in denied.json()


@pytest.mark.django_db
def test_mojtrade_readiness_api_proves_only_fresh_private_watch(client, canonical_market):
    owner = get_user_model().objects.create_superuser(
        username="readiness-owner", email="readiness@example.com",
        password="local-test-only",
    )
    client.force_login(owner)
    url = reverse("mojtrade-private-readiness")
    before = client.get(url)
    assert before.status_code == 200
    gates = before.json()["gates"]
    assert gates["canonical_bot_active_in_current_database"] is True
    assert gates["fresh_canonical_private_watch_receipt"] is False
    task, _ = ingest_private_observation()
    after = client.get(url)
    assert after.status_code == 200
    evidence = after.json()
    assert evidence["market_watch_task_id"] == task.pk
    assert evidence["gates"]["fresh_canonical_private_watch_receipt"] is True
    assert evidence["gates"]["local_demo_closed_deal_log_audited"] is False
    assert evidence["gates"]["broker_authenticated_demo_execution_and_account"] is False
    assert evidence["gates"]["canonical_approved_demo_order_control"] is False
    assert evidence["gates"]["verified_customer_signal_delivery"] is False
    assert evidence["gates"]["settled_real_revenue_verified"] is False
    assert evidence["operational_completion_percent"] is None
    assert evidence["public_signal_publication_authorized"] is False
    assert evidence["live_account_orders_authorized"] is False
    assert evidence["real_revenue_verified"] is False
    assert "no-store" in after["Cache-Control"]
    assert "noindex" in after["X-Robots-Tag"]
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
def test_mojtrade_readiness_api_disallows_post_or_data_mutation(client, canonical_market):
    owner = get_user_model().objects.create_superuser(
        username="readiness-post-owner", email="readiness-post@example.com",
        password="local-test-only",
    )
    client.force_login(owner)
    assert client.post(reverse("mojtrade-private-readiness"), {"trade": "buy"}).status_code == 405
    assert not AgentTask.objects.exists()



@pytest.mark.django_db
@pytest.mark.parametrize("locale", ["fa", "en", "ar"])
@pytest.mark.parametrize("brand", [row[0] for row in BRANDS])
def test_all_17_brand_signal_previews_are_owner_only_source_bound_and_unpublished(
    client, canonical_market, brand, locale,
):
    task, _ = ingest_private_observation()
    owner = get_user_model().objects.create_superuser(
        username="brand-preview-owner", email="brand-preview@example.com",
        password="test-password-only",
    )
    url = reverse("mojtrade-private-brand-preview", kwargs={
        "brand": brand, "locale": locale,
    })
    public = client.get(url)
    assert public.status_code == 403
    assert "alerts" not in public.json()
    client.force_login(owner)
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_owner"] == BOT_CODE
    assert data["brand"] == brand and data["locale"] == locale
    assert data["task_id"] == task.pk
    assert data["status"] == "private_owner_preview_only"
    assert data["source_sha256"] == task.input_data["source_sha256"]
    assert data["draft_sha256"] == task.output_data["market_watch_drafts"]["draft_sha256"]
    assert data["publication_authorized"] is False
    assert data["external_delivery_receipts"] == []
    assert data["trade_execution_authorized"] is False
    assert data["broker_connected"] is False
    assert data["orders"] == 0 and data["revenue_verified"] is False
    assert [row["symbol"] for row in data["alerts"]] == ["BTC/USD", "ETH/USD"]
    for row in data["alerts"]:
        assert row["market_watch_text"]
        assert row["entry_price"] is None and row["stop_loss"] is None
        assert row["take_profit"] is None and row["order_intent"] is None
        assert "content" not in row
    assert "no-store" in response["Cache-Control"]
    assert "noindex" in response["X-Robots-Tag"]
    assert response["X-Frame-Options"] == "DENY"
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
def test_brand_signal_preview_denies_unrecognized_brands_locales_and_staff(
    client, canonical_market,
):
    task, _ = ingest_private_observation()
    staff = get_user_model().objects.create_user(
        username="brand-staff-only", is_staff=True,
    )
    route = reverse("mojtrade-private-brand-preview", kwargs={
        "brand": "saman", "locale": "en",
    })
    client.force_login(staff)
    assert client.get(route).status_code == 403
    owner = get_user_model().objects.create_superuser(
        username="brand-owning-user", email="owning@example.com",
        password="test-password-only",
    )
    client.force_login(owner)
    for unknown in [
        reverse("mojtrade-private-brand-preview", kwargs={"brand": "unknown", "locale": "fa"}),
        reverse("mojtrade-private-brand-preview", kwargs={"brand": "saman", "locale": "ru"}),
    ]:
        response = client.get(unknown)
        assert response.status_code == 404
        assert "alerts" not in response.json()
    assert client.post(route, {"order": "buy"}).status_code == 405
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
def test_brand_preview_never_replays_expired_or_corrupted_watch(
    client, canonical_market,
):
    task, _ = ingest_private_observation()
    owner = get_user_model().objects.create_superuser(
        username="brand-expiry-owner", email="expiry@example.com",
        password="test-password-only",
    )
    client.force_login(owner)
    url = reverse("mojtrade-private-brand-preview", kwargs={
        "brand": "mojtaba", "locale": "fa",
    })
    assert client.get(url).status_code == 200
    with patch(
        "core.management.commands.mojtrade_market_watch_export.timezone.now",
        return_value=timezone.now() + timedelta(days=1),
    ):
        old = client.get(url)
    assert old.status_code == 503 and "alerts" not in old.json()
    receipt = AuditLog.objects.get(
        action="mojtrade_private_research_ingested", target_id=str(task.pk),
    )
    receipt.delete()
    corrupted = client.get(url)
    assert corrupted.status_code == 503 and "alerts" not in corrupted.json()
    assert corrupted.json()["publication_authorized"] is False
