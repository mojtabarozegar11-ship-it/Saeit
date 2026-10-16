import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("diverse",ROOT/"scripts/mojtaba_six_diverse_collab_photos_publish.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sp=importlib.util.spec_from_file_location("original_collab",ROOT/"scripts/mojtaba_enterprise_collaboration_inquiry.py")
c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)

def template():
    return """{% extends 'personal_site/base.html' %}\n{% load static %}\n{% block content %}\n"""+ "\n".join("<div "+mark+">Prior content</div>" for mark in m.PROTECTED) +"\n"+c.card_section()+"\n{% endblock %}"

class UniqueCollaborationPhotoTest(unittest.TestCase):
    def test_six_distinct_non_repeated_topic_images(self):
        self.assertEqual(len(m.FILES),6)
        self.assertEqual(len(set(m.FILES)),6)
        self.assertEqual(len(set(m.ALT)),6)
        self.assertEqual(len(c.OFFERS),6)
        content=template()
        changed=m.patch(content)
        self.assertEqual(changed.count(m.NEW_MARK),6)
        self.assertEqual(changed.count(m.CARD_MARK),1)
        self.assertEqual(changed.count('<img '),6)
        self.assertIn("AI",changed)
        for filename in m.FILES:self.assertEqual(changed.count(filename),1)
        for marker in m.PROTECTED:self.assertEqual(changed.count(marker),1)
        self.assertIn(c.CONTACT,changed)
        self.assertEqual(changed.count("Read the relevant technical article"),6)
        self.assertIn("Technology and engineering illustration",changed)
        self.assertNotIn("not an actual client installation",changed)
        with self.assertRaises(ValueError):m.patch(changed)

    def test_fail_closed_on_earlier_page_changes(self):
        for marker in m.PROTECTED:
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):m.patch(template().replace(marker,"MISSING"),)
        with self.assertRaises(ValueError):m.patch(template().replace("PROPOSAL 04","INVALID OFFER 04"))

    def test_all_generated_files_checksum_and_webp(self):
        files=sorted((ROOT/"content").glob("mojtaba_diverse_collab_photo_chunk_*.b64"))
        self.assertEqual(len(files),20)
        data=base64.b64decode("".join(x.read_text(encoding="ascii") for x in files))
        self.assertEqual(hashlib.sha256(data).hexdigest(),"a750fb7a8a11525d6cebc9b84fbd213aa0d00698596890f2d12df26941980525")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=set(z.namelist())
            self.assertEqual(len(names),7)
            self.assertEqual(names,set(m.FILES)|{"manifest.json"})
            entries=json.loads(z.read("manifest.json"))
            self.assertEqual(len(entries),6)
            observed=set()
            for i,entry in enumerate(entries):
                self.assertEqual(entry["filename"],m.FILES[i])
                binary=z.read(entry["filename"])
                self.assertEqual(binary[:4],b"RIFF")
                self.assertEqual(binary[8:12],b"WEBP")
                sha=hashlib.sha256(binary).hexdigest()
                self.assertEqual(entry["sha256"],sha)
                self.assertNotIn(sha,observed)
                observed.add(sha)
                self.assertIn("conceptual",entry["origin"])

    def test_six_cards_only_not_any_existing_article_or_gallery(self):
        script=(ROOT/"scripts/mojtaba_six_diverse_collab_photos_publish.py").read_text()
        self.assertEqual(set(m.STATIC_FOLDER.split("/")) , {"personal_site","mojtaba_six_diverse_collaboration_photos_20261016"})
        self.assertNotIn("Post.objects.create(",script)
        self.assertNotIn("Post.objects.filter(",script.replace("Post.objects.filter(slug__in=old,published=True)","").replace('Post.objects.filter(slug__in=[x["slug"] for x in new],published=True)',""))
        self.assertNotIn("contact.html",script)
        self.assertEqual(set(("home","posts")),set(("home","posts")))
        self.assertNotIn("detail.html",script)

if __name__=="__main__":unittest.main()
