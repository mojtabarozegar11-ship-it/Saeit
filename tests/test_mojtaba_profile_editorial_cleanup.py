import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("editorial_cleanup",ROOT/"scripts/mojtaba_remove_unwanted_profile_disclaimers.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
catalog=importlib.util.spec_from_file_location("protected",ROOT/"scripts/mojtaba_twenty_photo_essays_safe_publish.py")
c=importlib.util.module_from_spec(catalog);catalog.loader.exec_module(c)

PROFILE='''{% extends 'personal_site/base.html' %}
{% block content %}
<section id="mpw-primary-personal-profile-20261016">
<figure><img src="/static/personal_site/official_profile_20261016/avatar.webp" alt="Profile image"/>
<figcaption>Official owner-selected profile photograph</figcaption></figure>
<p style="font:14px/1.8 system-ui,sans-serif">
 This is a personal photograph selected by the profile owner. It is not presented as
 evidence of a Vancouver office or a completed client project.
</p>
<a href="/mojtaba.roozegar/contact/">Contact</a>
</section>
<div id="mpw-new-originals-20261015-b">Photos</div>
<div id="mpw-mojtaba-twenty-image-essays-20261016">Articles</div>
{% endblock %}'''

class ProfileEditorialCorrection(unittest.TestCase):
    def test_exact_screenshot_phrase_removed_without_harming_portrait(self):
        out=m.cleanup_template(PROFILE)
        self.assertNotIn("It is not presented as",out)
        self.assertNotIn("This is a personal photograph",out)
        self.assertNotIn("Official owner-selected",out)
        self.assertIn("Mojtaba Roozegar",out)
        self.assertIn('id="mpw-primary-personal-profile-20261016"',out)
        self.assertIn('src="/static/personal_site/official_profile_20261016/avatar.webp"',out)
        self.assertIn("/mojtaba.roozegar/contact/",out)
        self.assertEqual(PROFILE.count("<img"),out.count("<img"))

    def test_other_unwanted_promotional_disclaimers_replaced_with_useful_copy(self):
        src="""<p>The following are proposed pilot formats, not completed client contracts, a claimed Canadian office, fixed offers or guaranteed results.</p>
<p>This is an invitation, not an existing Vancouver project or guaranteed service.</p>
<p>Images document editorial themes, not client contracts.</p>
<figcaption>Conceptual visualization · not an actual client installation</figcaption>"""
        out=m.cleanup_template(src)
        for phrase in m.NO_TOKENS:self.assertNotIn(phrase,out)
        self.assertIn("clearly scoped technical pilot",out)
        self.assertIn("requirements and a defined pilot",out)
        self.assertIn("Technology and engineering illustration",out)

    def test_repetitive_image_contract_boilerplate_removed_from_article(self):
        text=(
            "Professional Collaboration\n"
            + "A clear requirements plan helps an enterprise choose valuable features. "*7
            + "The photograph is personal editorial material, not proof of a signed Vancouver contract. "
            + "A good prototype tests the initial workflow and respects user access rules.\n\n"
            + "Editorial note: This photograph is not evidence of a Canadian office or completed project.\n\n"
            + "The pilot should define a technical objective and a realistic test plan. "*7
        )
        out=m.cleanup_article(text)
        self.assertNotIn("not proof of a signed",out)
        self.assertNotIn("Editorial note:",out)
        self.assertIn("prototype tests",out)
        self.assertIn("requirements plan",out)

    def test_keep_scientific_limits_and_security_cautions(self):
        text=(
            "Research validation\n"
            + "A dashboard is not proof that an intervention increased actual profitability. "*8
            + "A scenario chart does not prove that the prediction is reliable. "*4
            + "Input data should be accurate and reviewed by a qualified specialist. "*6
        )
        out=m.cleanup_article(text)
        self.assertIn("dashboard is not proof",out)
        self.assertIn("does not prove",out)
        self.assertIn("qualified specialist",out)

    def test_catalog_representative_existing_93_no_large_deletions(self):
        content=ROOT/"content"
        old=[]
        for f in c.OLD_FILES:
            d=json.loads((content/f).read_text())
            old.extend(d["articles"])
        new=c.load_articles(content)
        self.assertEqual(len(old),73)
        self.assertEqual(len(new),20)
        for row in old+new:
            txt=row["content"]
            with self.subTest(article=row["slug"]):
                edited=m.cleanup_article(txt)
                self.assertGreater(len(edited),0)
                self.assertGreaterEqual(len(edited),int(len(txt)*0.68))
                self.assertNotIn("Editorial note:",edited)
                self.assertNotIn("It is not presented as evidence of a Vancouver office",edited)

    def test_guardrails_do_not_change_unrelated_apps(self):
        script=(ROOT/"scripts/mojtaba_remove_unwanted_profile_disclaimers.py").read_text()
        self.assertIn("mojtaba_personal/mojtaba_roozegar_personal_v17",script)
        self.assertIn("transaction.atomic()",script)
        self.assertIn("state.json",script)
        self.assertNotIn("collectstatic",script)
        self.assertNotIn("objects.create(",script)
        self.assertNotIn("shutil.rmtree",script)

if __name__=="__main__":unittest.main()
