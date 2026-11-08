"""No-dependency tests for the read-only factory source contract preflight."""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_source_contract_audit.py"
SPEC = importlib.util.spec_from_file_location("factory_source_contract_audit", SCRIPT)
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


class FactorySourceContractAuditTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        command = root / "core/management/commands/factory_product_step.py"
        command.parent.mkdir(parents=True)
        command.write_text("from core.factory_agent_runtime import FactoryAgentRuntime\n"
                           "from core.factory_tool_pack import build_factory_gateway\n",
                           encoding="utf-8")
        worker = root / "core/factory_worker_compat.py"
        worker.write_text("from .factory_contracts import GatewayToolResult\n"
                          "from .factory_governance import FactoryTaskVerifier\n",
                          encoding="utf-8")
        models = root / "core/models.py"
        models.write_text("class AgentTask:\n"
                          "    factory_run = None\n"
                          "    product = None\n"
                          "    environment = None\n"
                          "    next_retry_at = None\n"
                          "class Product:\n"
                          "    metadata = None\n", encoding="utf-8")
        return root

    def test_missing_dependencies_are_blockers(self):
        result = audit_module.audit(self.fixture())
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(item["component"] == "core.factory_agent_runtime"
                            for item in result["blockers"]))
        self.assertFalse(result["live_vps_verified"])
        self.assertFalse(result["production_ready"])

    def test_missing_model_bindings_are_reported(self):
        root = self.fixture()
        (root / "core/models.py").write_text("class AgentTask:\n    status = None\n"
                                               "class Product:\n    metadata = None\n",
                                               encoding="utf-8")
        result = audit_module.audit(root)
        found = {item["component"] for item in result["blockers"]}
        self.assertTrue({"AgentTask.factory_run", "AgentTask.product",
                         "AgentTask.environment", "AgentTask.next_retry_at"} <= found)

    def test_source_contract_can_pass_without_claiming_live_readiness(self):
        root = self.fixture()
        for relative in ("factory_agent_runtime.py", "factory_tool_pack.py",
                         "factory_contracts.py", "factory_governance.py"):
            (root / "core" / relative).write_text("# fixture\n", encoding="utf-8")
        result = audit_module.audit(root)
        self.assertEqual(result["status"], "source_contract_present")
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["production_ready"])

    def test_malformed_file_fails_closed(self):
        root = self.fixture()
        (root / "core/models.py").write_text("class AgentTask(:\n", encoding="utf-8")
        result = audit_module.audit(root)
        self.assertTrue(any(item["code"] == "SOURCE_UNREADABLE" for item in result["blockers"]))

    def test_cli_reports_blockers_with_nonzero_exit(self):
        root = self.fixture()
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = audit_module.main(["--root", str(root)])
        self.assertEqual(code, 2)
        self.assertIn('"status": "blocked"', captured.getvalue())


if __name__ == "__main__":
    unittest.main()
