from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "mojtaba-live-topology-readonly.yml"


def test_vps_diagnostic_stage_is_emitted_without_private_stderr():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'MOJTABA_VPS_FAILURE_STAGE=$vps_failure_stage' in text
    assert 'MOJTABA_VPS_SSH_EXIT_CODE=$ssh_status' in text
    assert 'cat "$d/vps.err"' not in text
    assert 'echo "$(<"$d/vps.err")"' not in text
