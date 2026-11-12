"""Contract: one specially titled protected push can invoke only read-only audit."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / ".github/workflows/mojtaba-live-topology-readonly.yml"
ONESHOT = ROOT / ".github/workflows/mojtaba-one-shot-readonly-dispatch.yml"
EXPECTED_COMMIT = "audit: run one-time read-only VPS and cPanel inventory"


def test_underlying_workflow_is_reusable_and_still_manual_without_auto_push():
    content = AUDIT.read_text(encoding="utf-8")
    events = content.split("on:\n", 1)[1].split("permissions:", 1)[0]
    assert "  workflow_dispatch:" in events
    assert "  workflow_call:" in events
    assert "  push:" not in events
    assert "  pull_request:" not in events
    assert "  schedule:" not in events
    assert "    runs-on: ubuntu-22.04" in content
    assert "StrictHostKeyChecking yes" in content
    assert "Reconcile both observations" in content
    assert "deactivation" not in content.split("jobs:", 1)[0].lower()


def test_one_shot_push_event_is_exactly_one_protected_path_only():
    content = ONESHOT.read_text(encoding="utf-8")
    events = content.split("on:\n", 1)[1].split("permissions:", 1)[0]
    assert "  push:" in events
    assert "    branches: [main]" in events
    assert '      - ".github/workflows/mojtaba-one-shot-readonly-dispatch.yml"' in events
    assert "  workflow_dispatch:" not in events
    assert "  pull_request:" not in events
    assert "  schedule:" not in events
    assert "  issue_comment:" not in events


def test_only_expected_commit_on_main_can_call_existing_readonly_workflow():
    text = ONESHOT.read_text(encoding="utf-8")
    assert "github.repository == 'mojtabarozegar11-ship-it/Saeit'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert f"github.event.head_commit.message == '{EXPECTED_COMMIT}'" in text
    assert "    uses: ./.github/workflows/mojtaba-live-topology-readonly.yml" in text
    assert "    secrets: inherit" in text
    assert "  contents: read" in text
    assert "  cancel-in-progress: false" in text
    assert "deploy" not in text.lower()
    assert "delete" not in text.lower()
