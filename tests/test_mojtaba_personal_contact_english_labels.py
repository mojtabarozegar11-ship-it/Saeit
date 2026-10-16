"""Safety regression tests for narrow personal contact label translation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mojtaba_personal_contact_english_labels.py"
spec = importlib.util.spec_from_file_location("personal_contact_translation", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ORIGINAL = """from django import forms
class ContactForm(forms.Form):
    name = forms.CharField(label="نام فرستنده", widget=forms.TextInput(attrs={"placeholder": "Your name"}))
    email = forms.EmailField(label="ایمیل", widget=forms.EmailInput(attrs={"placeholder": "Email address"}))
    subject = forms.CharField(label="موضوع", widget=forms.TextInput(attrs={"placeholder": "Subject"}))
    message = forms.CharField(label="متن پیام", widget=forms.Textarea(attrs={"placeholder": "Write your message"}))
"""


class ContactLabelSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.file = self.root / "core" / "forms.py"
        self.file.parent.mkdir(parents=True)
        self.file.write_text(ORIGINAL, encoding="utf-8")
        self.backup = self.root / "backup"

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_labels_changed_and_all_form_fields_preserved(self):
        rel, before, after = module.plan(self.root)
        self.assertEqual(rel, "core/forms.py")
        self.assertEqual(before, ORIGINAL)
        self.assertEqual(after.count("Subject"), 2)  # one placeholder already existed
        module.install(self.root, self.backup)
        updated = self.file.read_text(encoding="utf-8")
        self.assertEqual(updated, after)
        for name in ("name", "email", "subject", "message"):
            self.assertIn(name + " =", updated)
        for fa in module.LABELS:
            self.assertNotIn(fa, updated)
        module.rollback(self.root, self.backup)
        self.assertEqual(self.file.read_text(encoding="utf-8"), ORIGINAL)

    def test_partial_source_fails_without_modification(self):
        self.file.write_text(ORIGINAL.replace("نام فرستنده", "Your Name"), encoding="utf-8")
        with self.assertRaises(ValueError):
            module.plan(self.root)
        self.assertFalse(self.backup.exists())

    def test_duplicate_label_fails(self):
        self.file.write_text(ORIGINAL + '\nextra = "موضوع"\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            module.plan(self.root)

    def test_other_application_untouched(self):
        unrelated = self.root / "unrelated" / "forms.py"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text(ORIGINAL, encoding="utf-8")
        module.install(self.root, self.backup)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), ORIGINAL)

    def test_refuses_to_restore_when_source_changed_after_install(self):
        module.install(self.root, self.backup)
        self.file.write_text("externally changed", encoding="utf-8")
        with self.assertRaises(ValueError):
            module.rollback(self.root, self.backup)
        self.assertEqual(self.file.read_text(encoding="utf-8"), "externally changed")


if __name__ == "__main__":
    unittest.main()
