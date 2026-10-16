import base64,hashlib,importlib.util,io,json,zipfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("profile",ROOT/"scripts/mojtaba_set_primary_profile_photo_20261016.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def home():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Original owner photos</div>
<div id="mpw-mojtaba-twenty-image-essays-20261016">Preserved twenty portrait essays</div>
<div id="mpw-enterprise-collaboration-brief-20261016">Collaboration contact information</div>
{% endblock %}"""
def about():
    return """{% extends 'personal_site/base.html' %}
{% load static %}
{% block content %}
<section id="mpw-academic-profile-20261016">Preserved biography and education</section>
<p>Original about content remains unchanged</p>
{% endblock %}"""
class PrimaryProfilePhotoSafety(unittest.TestCase):
    def test_exact_uploaded_photo_and_distinct_webp_versions(self):
        text=(ROOT/"content/mojtaba_primary_profile_source_20261016.b64").read_text()
        data=base64.b64decode(text)
        self.assertEqual(hashlib.sha256(data).hexdigest(),m.ORIGINAL_SHA)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(set(z.namelist()),{"avatar.webp","portrait.webp","manifest.json"})
            source=json.loads(z.read("manifest.json"))
            self.assertEqual(source["source_uploaded_photo_sha256"],"50493b0e83f475b7f54405570e0cbce210bf6eb9e2520f024e316e999779e04a")
            for name,digest in m.IMAGES.items():
                b=z.read(name)
                self.assertEqual(hashlib.sha256(b).hexdigest(),digest)
                self.assertEqual(b[0:4],b"RIFF")
                self.assertEqual(b[8:12],b"WEBP")
            self.assertNotEqual(z.read("avatar.webp"),z.read("portrait.webp"))
    def test_additive_primary_home_image_preserves_original(self):
        s=m.patch("home",home())
        self.assertEqual(s.count(m.MARK),1)
        self.assertIn("portrait.webp",s)
        self.assertNotIn("avatar.webp",s)
        self.assertIn("Preserved twenty portrait essays",s)
        self.assertIn("Original owner photos",s)
        self.assertIn("Mojtaba Roozegar",s)
        self.assertIn("/mojtaba.roozegar/contact/",s)
        self.assertEqual(s.count("{% load static %}"),1)
        with self.assertRaises(ValueError):m.patch("home",s)
    def test_about_primary_circle_and_biography_unaltered(self):
        s=m.patch("about",about())
        self.assertEqual(s.count(m.MARK),1)
        self.assertIn("avatar.webp",s)
        self.assertIn("border-radius:50%",s)
        self.assertNotIn("portrait.webp",s)
        self.assertIn("Original about content remains unchanged",s)
        self.assertIn("mpw-academic-profile-20261016",s)
        self.assertEqual(s.count("{% load static %}"),1)
    def test_never_overwrite_other_profiles_galleries_or_payments(self):
        path=ROOT/"scripts/mojtaba_set_primary_profile_photo_20261016.py"
        script=path.read_text()
        self.assertEqual(set(m.TEMPLATES),{"home","about"})
        self.assertEqual(len(m.IMAGES),2)
        self.assertNotIn("Post.objects.create(",script)
        self.assertNotIn("Post.objects.update(",script)
        self.assertNotIn("gallery.html",script)
        self.assertNotIn("contact.html",script)
        self.assertNotIn("payment",script)
    def test_missing_original_context_fails_closed(self):
        with self.assertRaises(ValueError):m.patch("home",home().replace("mpw-new-originals-20261015-b","removed"))
        with self.assertRaises(ValueError):m.patch("about",about().replace("mpw-academic-profile-20261016","removed"))
if __name__=="__main__":unittest.main()
