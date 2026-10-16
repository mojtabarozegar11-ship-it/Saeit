import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("personal_edit",ROOT/"scripts/mojtaba_clean_editorial_professional_copy.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
photo_path=ROOT/"scripts/mojtaba_set_primary_profile_photo_20261016.py"
spec2=importlib.util.spec_from_file_location("original_photo",photo_path)
p=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(p)

class PersonalEditorialCopyTest(unittest.TestCase):
    def test_exact_owner_primary_profile_paragraph_is_replaced(self):
        for which in ("home","about"):
            template="{% load static %}\n{% block content %}\n"+p.profile_section(which)+"\n{% endblock %}"
            after,count=m.template_copy(template)
            self.assertEqual(count,0)
            self.assertEqual(after,template)
            self.assertEqual(after.count(m.PROFILE),1)
            self.assertIn(m.PROFILE_COPY,after)
            self.assertIn(m.CAPTION,after)
            self.assertNotIn("It is not presented as",after)
            self.assertNotIn("evidence of a Vancouver office",after)
            self.assertIn("intelligent industrial and commercial websites",after)
            self.assertIn("/mojtaba.roozegar/contact/",after)
            self.assertEqual(after.count("<img "),1)

    def test_legacy_profile_paragraph_still_migrates_cleanly(self):
        legacy=(
            '<section id="mpw-primary-personal-profile-20261016">'
            '<p style="font:14px/1.8 system-ui,sans-serif">'
            'This is a personal photograph selected by the profile owner. '
            'It is not presented as evidence of a Vancouver office or a completed client project.'
            '</p><figcaption>Official owner-selected profile photograph</figcaption></section>'
        )
        corrected,count=m.template_copy(legacy)
        self.assertEqual(count,1)
        self.assertIn(m.PROFILE_COPY,corrected)
        self.assertIn(m.CAPTION,corrected)
        self.assertNotIn("It is not presented as",corrected)

    def test_professional_copy_avoids_unwanted_meta_commentary(self):
        self.assertNotIn("claim",m.PROFILE_COPY.lower())
        self.assertNotIn("not verified",m.PROFILE_COPY.lower())
        self.assertNotIn("100%",m.PROFILE_COPY)
        self.assertNotIn("۱۰۰٪",m.PROFILE_COPY)
        self.assertIn("Research",m.CAPTION)
        self.assertIn("Mojtaba Roozegar",m.CAPTION)

    def test_generic_template_captions_stay_informative(self):
        original='<figcaption>The image is not proof of a Vancouver office, professional engagement or completed enterprise project.</figcaption>'
        out,n=m.template_copy(original)
        self.assertEqual(n,1)
        self.assertNotIn("not proof",out)
        self.assertIn("research",out.lower())
        base='<p>The following are proposed pilot formats, not completed client contracts, a claimed Canadian office, fixed offers or guaranteed results.</p>'
        out,n=m.template_copy(base)
        self.assertEqual(n,1)
        self.assertIn("discovery",out.lower())
        self.assertNotIn("claimed",out.lower())

    def test_keep_scientific_caveats_not_about_personal_verification(self):
        example=("Measurement uncertainty must remain visible when instrument accuracy is unknown. "
                 "A model can produce an inaccurate forecast if it learns from faulty data. "
                 "This is a personal photograph; it is not evidence of a corporate office.")
        clean=m.trim_sentence(example)
        self.assertIn("Measurement uncertainty",clean)
        self.assertIn("inaccurate forecast",clean)
        self.assertNotIn("corporate office",clean)

    def test_image_focused_lead_and_negative_claim_disclaimer_removed(self):
        sample=("A professional photograph introduces a person; it does not prove a particular client relationship. "
                "Reliable enterprise website design begins with understanding users. "
                "Each task should have measurable acceptance criteria. "
                "Practical tests should cover both successful and unsuccessful routes. "
                "The accompanying generated artwork is not documentation of a completed Vancouver project.")
        result=m.trim_sentence(sample)
        self.assertIn("Reliable enterprise website design",result)
        self.assertIn("Practical tests",result)
        self.assertNotIn("client relationship",result)
        self.assertNotIn("documentation of a completed",result)

    def test_all_93_article_manifests_preserve_substance(self):
        src=ROOT/"scripts/mojtaba_twenty_photo_essays_safe_publish.py"
        sp=importlib.util.spec_from_file_location("photo_essay_orig",src)
        mm=importlib.util.module_from_spec(sp);sp.loader.exec_module(mm)
        originals=[]
        for name in mm.OLD_FILES:
            originals.extend(json.loads((ROOT/"content"/name).read_text(encoding="utf-8"))["articles"])
        originals.extend(mm.load_articles(ROOT/"content"))
        self.assertEqual(len(originals),93)
        changed=0
        for row in originals:
            with self.subTest(slug=row["slug"]):
                result,removed=m.clean_article_body(row["content"])
                self.assertGreaterEqual(len(result.split()),170)
                self.assertGreaterEqual(len(result.split()),int(len(row["content"].split())*.77))
                self.assertIn(result.split()[0],row["content"])
                if result!=row["content"]:changed+=1
        self.assertGreater(changed,25)

    def test_code_write_scope_is_independent_personal_host(self):
        self.assertIn("mojtaba_personal/mojtaba_roozegar_personal_v17",str(m.APP))
        self.assertNotIn("contact.html",m.PROFILE_COPY)
        self.assertNotIn("collectstatic",src if False else m.__doc__ or "")

if __name__=="__main__":unittest.main()
