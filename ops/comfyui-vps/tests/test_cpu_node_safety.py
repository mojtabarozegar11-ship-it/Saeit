"""Static safety invariants for private ComfyUI CPU bridge."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / "saeit_cpu_node" / "__init__.py"
RUNNER = ROOT / "render_sd_cpp.py"
INSTALLER = ROOT / "install_tiny_model.sh"


class CPUBridgeSafetyTests(unittest.TestCase):
    def test_node_is_parseable_and_exposes_image(self):
        source = NODE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn("RETURN_TYPES = (\"IMAGE\",)", source)
        self.assertIn("SaeitSafeCPURender", source)
        self.assertTrue(any(isinstance(x, ast.ClassDef) and x.name == "SaeitSafeCPURender" for x in tree.body))

    def test_cpu_process_has_no_shell_invocation(self):
        tree = ast.parse(NODE.read_text(encoding="utf-8"))
        invocations = [node for node in ast.walk(tree)
                       if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                       and node.func.attr == "Popen"]
        self.assertEqual(len(invocations), 1)
        self.assertFalse(any(k.arg == "shell" and isinstance(k.value, ast.Constant)
                             and k.value.value for k in invocations[0].keywords))

    def test_factory_and_memory_watchdog_are_present(self):
        src = NODE.read_text(encoding="utf-8")
        self.assertIn("factory_running()", src)
        self.assertIn("RLIMIT_DATA", src)
        self.assertIn("LOCK_EX | fcntl.LOCK_NB", src)
        self.assertIn("available_kib() < 950_000", src)
        self.assertIn("os.killpg(child.pid, signal.SIGTERM)", src)

    def test_checkpoint_integrity_pin_is_consistent(self):
        import re
        a = NODE.read_text(encoding="utf-8")
        b = INSTALLER.read_text(encoding="utf-8")
        ha = re.search(r'EXPECTED_SHA256 = "([a-f0-9]{64})"', a)
        hb = re.search(r'sha="([a-f0-9]{64})"', b)
        self.assertIsNotNone(ha)
        self.assertIsNotNone(hb)
        self.assertEqual(ha.group(1), hb.group(1))

    def test_output_is_png_and_limited(self):
        s = RUNNER.read_text(encoding="utf-8")
        self.assertIn('"-W", "512", "-H", "512"', s)
        self.assertIn('"--steps", "4"', s)
        self.assertIn("resource.RLIMIT_DATA", s)
        self.assertIn("CPU_COMPANION_REAL_PNG_VERIFIED", s)


if __name__ == "__main__":
    unittest.main()
