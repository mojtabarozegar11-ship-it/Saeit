"""UAPI Version get can exit 0 and still return an unsupported-module error."""
import json

import pytest
from scripts.cpanel_readonly_uapi_gate import check_version_result


def test_missing_cpanel_api_module_is_not_a_false_green():
    raw = {"result": {"status": 0, "errors": ["module not found"]}}
    with pytest.raises(ValueError, match="uapi_rejected"):
        check_version_result(json.dumps(raw).encode())


def test_rejected_result_does_not_echo_or_parse_secret_text():
    raw = {"result": {"status": "0", "errors": ["secret private API key ABC"]}}
    with pytest.raises(ValueError, match="uapi_rejected") as err:
        check_version_result(json.dumps(raw).encode())
    assert "ABC" not in str(err.value)


@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b"null", b"{}",
                                     b"x" * 500001])
def test_empty_malformed_or_oversized_uapi_fails(raw):
    with pytest.raises(ValueError):
        check_version_result(raw)


def test_success_only_with_explicit_status_and_no_errors():
    good = {"result": {"status": 1, "errors": None, "data": {}}}
    assert check_version_result(json.dumps(good).encode()) == {
        "uapi": "Version get", "status": "success", "release_authorized": False,
    }


def test_both_bridge_paths_check_api_status_not_just_process_code():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] /
              "deploy/cpanel_direct_command.sh").read_text()
    assert source.count("scripts/cpanel_readonly_uapi_gate.py") == 2
    assert source.count("uapi --output=json Version get") == 2
