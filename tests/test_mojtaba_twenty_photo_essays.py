import base64
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("essay20",ROOT/"scripts/mojtaba_twenty_photo_essays_safe_publish.py")
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

def original_template():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Owner photo archive</div>
<div id="mpw-fifty-editorials-20261015">Fifty original editorials</div>
<div id="mpw-academic-profile-20261016">Academic sections</div>
<div id="mpw-personal-expanded-20261016">Thirty-two extended sections</div>
<div id="mpw-journal-longform-index-20261016">Seven</div>
<div id="mpw-journal-advanced-index-20261016">Six</div>
<div id="mpw-website-ten-index-20261016">Ten specialist web articles</div>
<div id="mpw-vancouver-collab-photo-ten-20261016">Ten original Vancouver articles</div>
<div id="mpw-vancouver-enterprise-20-index-20261016">First twenty enterprise articles</div>
<div id="mpw-vancouver-enterprise-20-series2-index-20261016">Second twenty enterprise articles</div>
<p>Unrelated prior biography, posts, photos and templates remain in place.</p>
{% endblock %}"""

class TestPhotoLedPersonalJournal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=m.load_articles(ROOT/"content")

    def test_all_20_distinct_and_substantive(self):
        self.assertEqual(len(self.rows),20)
        self.assertEqual({r["photo_index"] for r in self.rows},set(range(1,21)))
        self.assertEqual(len({r["slug"] for r in self.rows}),20)
        self.assertTrue(all(len(r["content"].split())>=265 for r in self.rows))
        self.assertGreater(sum(len(r["content"].split()) for r in self.rows),5900)
        self.assertTrue(all(r["source_kind"]=="owner_supplied" for r in self.rows[:10]))
        self.assertTrue(all(r["source_kind"]=="generated_illustration" for r in self.rows[10:]))

    def test_asset_archive_is_exact_original_twenty_web_images(self):
        parts=sorted((ROOT/"content").glob("mojtaba_20_photo_hq_asset_part_*.b64"))
        self.assertEqual(len(parts),32)
        s="".join(p.read_text(encoding="ascii") for p in parts)
        archive=base64.b64decode(s,validate=False)
        self.assertEqual(hashlib.sha256(archive).hexdigest(),"ed62ebc89eee676d9a12627f4fe0be45655168c22facbad89360b4c4e505586c")
        with zipfile.ZipFile(io.BytesIO(archive)) as f:
            names=set(f.namelist())
            self.assertEqual(names,{f"photo_{n:02d}.webp" for n in range(1,21)}|{"manifest.json"})
            manifest=json.loads(f.read("manifest.json"))
            self.assertEqual(len(manifest),20)
            for record in manifest:
                name=record["name"]
                data=f.read(name)
                self.assertGreater(len(data),4000)
                self.assertEqual(data[:4],b"RIFF")
                self.assertEqual(data[8:12],b"WEBP")
                self.assertEqual(hashlib.sha256(data).hexdigest(),record["sha256"])

    def test_old_73_articles_manifest_preserved(self):
        self.assertEqual(len(m.OLD_FILES),13)
        slugs=m.load_older(ROOT/"content")
        self.assertEqual(len(slugs),73)

    def test_exclusive_home_and_journal_additive_cards(self):
        for page in ("home","posts"):
            body=m.patch(page,original_template(),self.rows)
            self.assertEqual(body.count(m.INDEX_MARK),1)
            self.assertEqual(body.count("<article"),20)
            self.assertEqual(body.count("mojtaba_personal_image_essays_20261016/"),20)
            self.assertIn("Unrelated prior biography",body)
            for marker in m.PROTECTED:
                self.assertEqual(body.count(marker),1)
            with self.assertRaises(ValueError):m.patch(page,body,self.rows)

    def test_detail_20_matching_photos_only(self):
        original="{% extends 'personal_site/base.html' %}{% block content %}<h1>{{ item.title }}</h1>{{ item.content|linebreaks }}{% endblock %}"
        body=m.patch("detail",original,self.rows)
        self.assertEqual(body.count(m.DETAIL_MARK),20)
        self.assertEqual(body.count("item.slug =="),20)
        self.assertEqual(body.count("mojtaba_personal_image_essays_20261016/"),20)
        self.assertIn("{{ item.content|linebreaks }}",body)
        with self.assertRaises(ValueError):m.patch("detail",body,self.rows)

    def test_reject_missing_prior_sections(self):
        for marker in m.PROTECTED:
            with self.assertRaises(ValueError):
                m.patch("home",original_template().replace(marker,"missing"),self.rows)

    def test_upload_manifest_archive_listing_does_not_break_pipefail(self):
        workflow=(ROOT/".github/workflows/mojtaba-twenty-photo-essays-publish.yml").read_text()
        self.assertIn('tar -tzf "$stage/photos.tgz" > "$stage/photo-archive-list.txt"',workflow)
        self.assertIn('grep -Fxq "mojtaba20pics/manifest.json" "$stage/photo-archive-list.txt"',workflow)
        self.assertNotIn('tar -tzf "$stage/photos.tgz" | grep -q',workflow)

    def test_scope_limited_to_three_personal_templates(self):
        self.assertEqual(set(m.TEMPLATES),{"home","posts","detail"})
        self.assertEqual(m.STATIC_FOLDER,"personal_site/mojtaba_personal_image_essays_20261016")

if __name__=="__main__":unittest.main()
