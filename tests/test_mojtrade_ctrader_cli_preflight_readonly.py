"""No-cost, no-credentials contract tests of the cTrader CLI read-only gate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from deploy.mojtrade_ctrader_cli_preflight_readonly import (
    PreflightError, SCHEMA, read_config, run_readonly,
)


@pytest.fixture
def private_cli(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    password = root / "ctrader-cli.pwd"
    password.write_text("PRIVATE_PASSWORD_NOT_PRINTABLE", encoding="utf-8")
    password.chmod(0o600)
    config = root / "config.json"
    content = {
        "schema_version": 1,
        "ctid": "safe.owner@example.com",
        "demo_account": "12345678",
        "account_alias": "LITE_DEMO_1",
        "broker": "LiteFinance",
        "password_file": "ctrader-cli.pwd",
    }
    config.write_text(json.dumps(content), encoding="utf-8")
    config.chmod(0o600)
    return config, password, content


def runner_factory(*, account=None, cbots=None, positions=None, orders=None,
                   retcode=0, commands=None):
    account = account if account is not None else {"accounts": [{
        "accountId": 12345678,
        "brokerName": "LiteFinance",
        "isLive": False,
    }]}
    cbots = cbots if cbots is not None else {"cbots": [{
        "instanceId": "first-demo-instance",
    }]}
    positions = positions if positions is not None else {"positions": []}
    orders = orders if orders is not None else {"orders": []}
    def fake(argv, *, capture_output, text, timeout, check):
        assert capture_output is True and text is True
        assert timeout == 25 and check is False
        assert argv[1] in {"accounts", "cbots", "positions", "orders"}
        assert not any(
            item in argv for item in (
                "run", "stop", "order", "place-market", "place-limit",
                "cancel", "position", "modify", "close", "--full-access",
            )
        )
        if commands is not None:
            commands.append(tuple(argv))
        body = {
            "accounts": account, "cbots": cbots, "positions": positions,
            "orders": orders,
        }[argv[1]]
        return subprocess.CompletedProcess(argv, retcode, json.dumps(body), "")
    return fake


def test_read_only_cli_produces_redacted_account_and_cbot_evidence(private_cli):
    config, password, values = private_cli
    commands = []
    report = run_readonly(
        config, cli_binary=sys.executable, runner=runner_factory(commands=commands),
    )
    assert report["schema"] == SCHEMA
    assert report["owner"] == "mojtaba-bot-ai"
    assert report["read_only"] is True
    assert report["cli_demo_account_identity_confirmed"] is True
    assert report["observed_running_cbot_count"] == 1
    assert report["multiple_cli_cbot_instances_detected"] is False
    assert report["single_runtime_instance_independently_attested"] is False
    assert report["cloud_and_external_process_census_verified"] is False
    assert report["trading_release_authorized"] is False
    assert report["orders_placed_by_this_probe"] == 0
    assert report["real_revenue_verified"] is False
    assert len(commands) == 4
    assert [cmd[1] for cmd in commands] == [
        "accounts", "cbots", "positions", "orders",
    ]
    assert "-q" not in commands[0]
    assert all("-q" in command for command in commands[1:])
    for command in commands:
        assert "--pwd-file=" + str(password) in command
        assert "--account=" + values["demo_account"] in command
        assert "--ctid=" + values["ctid"] in command
    safe = json.dumps(report)
    assert values["ctid"] not in safe
    assert values["demo_account"] not in safe
    assert password.read_text(encoding="utf-8") not in safe
    assert "first-demo-instance" not in safe
    assert report["observed_open_position_count"] == 0
    assert report["observed_pending_order_count"] == 0
    assert report["account_exposure_reconciled_for_new_order"] is False
    assert set(report["redacted_source_sha256"]) == {
        "accounts", "cbots", "positions", "orders",
    }
    assert all(len(digest) == 64 for digest in report["redacted_source_sha256"].values())


@pytest.mark.parametrize("accounts", [
    {"accounts": [{"accountId": 12345678, "brokerName": "LiteFinance", "isLive": True}]},
    {"accounts": [{"accountId": 12345678, "brokerName": "LiteFinance"}]},
    {"accounts": [{"accountId": 12345678, "brokerName": "OTHER", "isLive": False}]},
    {"accounts": [{"accountId": 9, "brokerName": "LiteFinance", "isLive": False}]},
    {"accounts": [
        {"accountId": 12345678, "brokerName": "LiteFinance", "isLive": False},
        {"accountId": 12345678, "brokerName": "LiteFinance", "isLive": False},
    ]},
    {"accounts": "bad-type"},
    {"records": [{"accountId": 12345678, "brokerName": "LiteFinance", "isLive": False}]},
])
def test_demo_preflight_refuses_live_wrong_broker_ambiguous_or_unrecognized_identity(
    private_cli, accounts,
):
    config, *_ = private_cli
    with pytest.raises(PreflightError):
        run_readonly(config, cli_binary=sys.executable,
                     runner=runner_factory(account=accounts))


@pytest.mark.parametrize("cbots", [
    {"cbots": [{"instanceId": "first"}, {"instanceId": "first"}]},
    {"cbots": [{"status": "running"}]},
    {"cbots": [None]},
    {"cbots": "not-a-list"},
    {"list": [{"instanceId": "first"}]},
])
def test_cbot_preflight_rejects_invalid_or_unparseable_runtime_inventory(
    private_cli, cbots,
):
    config, *_ = private_cli
    with pytest.raises(PreflightError):
        run_readonly(config, cli_binary=sys.executable,
                     runner=runner_factory(cbots=cbots))


def test_multiple_visible_bots_are_not_misreported_as_single_executor(private_cli):
    config, *_ = private_cli
    report = run_readonly(config, cli_binary=sys.executable,
        runner=runner_factory(cbots={"cbots": [
            {"instanceId": "first"}, {"instanceId": "second"},
        ]}))
    assert report["observed_running_cbot_count"] == 2
    assert report["multiple_cli_cbot_instances_detected"] is True
    assert report["single_runtime_instance_independently_attested"] is False
    assert report["trading_release_authorized"] is False


def test_zero_visible_bots_is_not_equivalent_to_verified_retirement(private_cli):
    config, *_ = private_cli
    report = run_readonly(config, cli_binary=sys.executable,
        runner=runner_factory(cbots={"cbots": []}))
    assert report["observed_running_cbot_count"] == 0
    assert report["cloud_and_external_process_census_verified"] is False


@pytest.mark.parametrize("tamper", ["world_dir", "world_config", "world_pwd", "symlink_config",
                                     "symlink_pwd", "path_traversal", "unknown_field", "raw_password_field"])
def test_private_config_cannot_expose_account_secrets(private_cli, tmp_path, tamper):
    config, password, content = private_cli
    if tamper == "world_dir":
        config.parent.chmod(0o755)
    elif tamper == "world_config":
        config.chmod(0o644)
    elif tamper == "world_pwd":
        password.chmod(0o644)
    elif tamper == "symlink_config":
        original = config.with_name("original.json")
        config.rename(original)
        config.symlink_to(original)
    elif tamper == "symlink_pwd":
        original = password.with_name("original.pwd")
        password.rename(original)
        password.symlink_to(original)
    else:
        if tamper == "path_traversal":
            content["password_file"] = "../stolen.pwd"
        elif tamper == "unknown_field":
            content["allow_live_trades"] = True
        else:
            content["password"] = "NEVER_PUT_PASSWORD_HERE"
        config.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(PreflightError):
        read_config(config)


def test_failed_cli_call_is_not_misreported_as_broker_authentication(private_cli):
    config, *_ = private_cli
    with pytest.raises(PreflightError, match="accounts_cli_rejected"):
        run_readonly(config, cli_binary=sys.executable,
                     runner=runner_factory(retcode=1))


def test_unknown_binary_fails_before_any_broker_call(private_cli):
    config, *_ = private_cli
    with pytest.raises(PreflightError, match="ctrader_cli_not_installed"):
        run_readonly(config, cli_binary="/nonexistent/never-installed-ctrader")


def test_timeout_blocks_without_raw_credential_error(private_cli):
    config, *_ = private_cli
    def timed_out(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
    with pytest.raises(PreflightError, match="accounts_cli_unavailable"):
        run_readonly(config, cli_binary=sys.executable, runner=timed_out)



def test_open_positions_and_pending_orders_are_counted_not_executed(private_cli):
    config, *_ = private_cli
    called = []
    report = run_readonly(config, cli_binary=sys.executable,
        runner=runner_factory(
            positions={"positions": [{"positionId": 1}, {"positionId": 2}]},
            orders={"orders": [{"orderId": 3}]}, commands=called,
        ))
    assert report["observed_open_position_count"] == 2
    assert report["observed_pending_order_count"] == 1
    assert report["account_exposure_reconciled_for_new_order"] is False
    assert report["trading_release_authorized"] is False
    assert {command[1] for command in called} == {
        "accounts", "cbots", "positions", "orders",
    }


@pytest.mark.parametrize("kind", ["positions", "orders"])
def test_unknown_open_exposure_schema_fails_closed(private_cli, kind):
    config, *_ = private_cli
    fake = runner_factory(**{kind: {kind: "not-a-list"}})
    with pytest.raises(PreflightError, match=kind + "_output_schema_unrecognized"):
        run_readonly(config, cli_binary=sys.executable, runner=fake)


def test_live_identity_blocks_all_followup_account_commands(private_cli):
    config, *_ = private_cli
    calls = []
    fake = runner_factory(
        account={"accounts": [{
            "accountId": 12345678, "brokerName": "LiteFinance",
            "isLive": True,
        }]},
        commands=calls,
    )
    with pytest.raises(PreflightError, match="demo_identity_not_explicit"):
        run_readonly(config, cli_binary=sys.executable, runner=fake)
    assert [command[1] for command in calls] == ["accounts"]



@pytest.mark.parametrize("account_data", [
    {
        "accounts": [{
            "accountId": 12345678, "traderLogin": 999999,
            "brokerName": "LiteFinance", "isLive": False,
        }],
    },
    {
        "accounts": [{
            "traderLogin": 12345678,
            "brokerName": "LiteFinance", "broker": "DifferentBroker",
            "isLive": False,
        }],
    },
    {
        "accounts": [{
            "traderLogin": 12345678,
            "brokerName": "LiteFinance",
            "brokerTitleShort": "DifferentBroker", "isLive": False,
        }],
    },
])
def test_account_aliases_must_not_contradict_broker_or_login(private_cli, account_data):
    config, *_ = private_cli
    with pytest.raises(PreflightError):
        run_readonly(
            config, cli_binary=sys.executable,
            runner=runner_factory(account=account_data),
        )


def test_documented_trader_login_can_differ_from_internal_account_identifier(private_cli):
    config, *_ = private_cli
    evidence = run_readonly(
        config, cli_binary=sys.executable,
        runner=runner_factory(account={"accounts": [{
            "accountId": 887766554433,
            "traderLogin": 12345678,
            "brokerName": "LiteFinance",
            "isLive": False,
        }]}),
    )
    assert evidence["cli_demo_account_identity_confirmed"] is True
    assert evidence["trading_release_authorized"] is False


@pytest.mark.parametrize("payload", [
    '{"accounts":[{"accountId":12345678,"brokerName":"LiteFinance","isLive":false}],"accounts":[]}',
    '{"accounts":[{"accountId":12345678,"accountId":12345678,"brokerName":"LiteFinance","isLive":false}]}',
    '{"accounts":[{"accountId":12345678,"brokerName":"LiteFinance","isLive":false}],"success":false}',
    '{"accounts":[{"accountId":12345678,"brokerName":"LiteFinance","isLive":false}],"error":"not-authorized"}',
    '{"accounts":[{"accountId":12345678,"brokerName":"LiteFinance","isLive":false}],"ok":false}',
    '{"accounts":[{"accountId":12345678,"brokerName":"LiteFinance","isLive":false}],"success":"false"}',
    '{"accounts":[{"accountId":12345678,"brokerName":"LiteFinance","isLive":false}],"ok":0}',
    '{"accounts":[{"accountId":12345678,"brokerName":"LiteFinance","isLive":false,"equity":NaN}]}',
])
def test_reject_duplicate_json_keys_and_cli_errors_before_any_trade_read(
    private_cli, payload,
):
    config, *_ = private_cli
    commands = []

    def malicious_cli(argv, *, capture_output, text, timeout, check):
        commands.append(argv[1])
        return subprocess.CompletedProcess(argv, 0, payload, "")

    with pytest.raises(PreflightError):
        run_readonly(config, cli_binary=sys.executable, runner=malicious_cli)
    assert commands == ["accounts"]
