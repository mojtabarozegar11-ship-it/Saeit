"""Compile every inline Python heredoc before site-changing workflow execution."""
import ast
from pathlib import Path
import re
import textwrap

WORKFLOW=(Path(__file__).resolve().parents[1]/
          ".github/workflows/mojplaywin-about-company-consolidated-20261019.yml")

def test_all_inline_python_in_workflow_compiles():
    content=WORKFLOW.read_text(encoding="utf-8")
    blocks=re.findall(r"^\s*python3 - <<'PY'\s*\n(.*?)^\s*PY\s*$",
                      content,flags=re.M|re.S)
    assert len(blocks)==2, f"Expected pre-release and live-smoke Python blocks; found {len(blocks)}"
    for index,raw in enumerate(blocks,1):
        code=textwrap.dedent(raw)
        ast.parse(code,filename=f"inline-workflow-script-{index}")
    assert "MPW_CONSOLIDATED_ROLLBACK" not in content  # emitted by the host script
    assert "python3 - rollback" in content
    assert "failure() && steps.publish.outcome == 'success'" in content
