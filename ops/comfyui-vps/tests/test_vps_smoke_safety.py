"""Static safety checks for the isolated CPU smoke test and portable build."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "vps_smoke.py"
BUILD = ROOT.parents[1] / ".github/workflows/comfyui-cpu-sse2-build.yml"

class CPUSmokeSafety(unittest.TestCase):
    def test_python_compiles_and_is_not_executed_on_import(self):
        source = SCRIPT.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('if __name__ == "__main__"', source)

    def test_private_cpu_and_factory_guards(self):
        content = SCRIPT.read_text(encoding="utf-8")
        for phrase in ('sd-cpp-runtime-sse2/bin', 'qa.lock', 'factory_ok()',
                       'available_kib() < 975_000', 'RLIMIT_DATA',
                       'os.killpg(proc.pid, signal.SIGTERM)', 'start_new_session=True',
                       'sha256', 'VPS_CPU_REAL_PNG_VERIFIED'):
            self.assertIn(phrase, content)
        self.assertNotIn('shell=True', content)

    def test_model_is_pinned(self):
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72', content)

    def test_build_explicitly_disables_extensions_absent_on_vps(self):
        content = BUILD.read_text(encoding="utf-8")
        for option in ('-DGGML_NATIVE=OFF','-DGGML_SSE42=OFF','-DGGML_AVX=OFF',
                       '-DGGML_AVX2=OFF','-DGGML_FMA=OFF','-DGGML_F16C=OFF',
                       '-DGGML_BMI2=OFF','-march=x86-64','sd-cpp-runtime-sse2'):
            self.assertIn(option, content)

if __name__ == "__main__":
    unittest.main()
