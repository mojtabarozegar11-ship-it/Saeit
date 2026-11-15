"""Public Moj Prop customer record integrity: reject loss and type confusion."""
import json
from django.test import TestCase, override_settings
from core.models import MojPropRequest, MojPropRateBucket

URL="/moj-prop-intake/"
BASE={"name":"Customer Lead", "email":"contact@example.org",
      "service":"audit", "horizon":"month",
      "notes":"Please explain the fee, research deliverable and timing.",
      "consent":True}


@override_settings(ALLOWED_HOSTS=["testserver","mojplaywin.com"])
class MojPropC67PayloadIntegrityTests(TestCase):
    def post(self, **fields):
        data=dict(BASE)
        data.update(fields)
        return self.client.post(URL,data=json.dumps(data),
                                content_type="application/json",
                                REMOTE_ADDR="127.0.0.42")

    def denied(self,field,value):
        result=self.post(**{field:value})
        self.assertEqual(result.status_code,400)
        self.assertIn(field,result.json()["fields"])
        self.assertFalse(MojPropRequest.objects.exists())
        self.assertFalse(MojPropRateBucket.objects.exists())

    def test_dict_name_cannot_be_coerced_to_str(self):
        self.denied("name",{"user":"bob"})

    def test_list_notes_cannot_be_coerced_to_str(self):
        self.denied("notes",["could","look","valid","but","not","text"])

    def test_numeric_name_cannot_be_passed_as_legal_identity(self):
        self.denied("name",1234)

    def test_null_email_cannot_be_passed_as_missing_valid_string(self):
        self.denied("email",None)

    def test_list_horizon_cannot_be_interpreted_as_label(self):
        self.denied("horizon",["week"])

    def test_overlong_notes_not_truncated_after_consent(self):
        self.denied("notes","x"*5001)

    def test_overlong_name_not_silently_truncated(self):
        self.denied("name","a"*201)

    def test_overlong_email_not_silently_truncated(self):
        self.denied("email","a"*255)

    def test_overlong_service_not_truncated(self):
        self.denied("service","b"*31)

    def test_overlong_horizon_not_truncated(self):
        self.denied("horizon","w"*21)

    def test_valid_boundary_size_notes_still_admitted(self):
        r=self.post(notes="g"*5000)
        self.assertEqual(r.status_code,201)
        self.assertEqual(len(MojPropRequest.objects.get().notes),5000)

    def test_honeypot_denied_without_lead(self):
        r=self.post(website="bot.example")
        self.assertEqual(r.status_code,400)
        self.assertFalse(MojPropRequest.objects.exists())

    def test_json_array_root_denied_without_database_write(self):
        r=self.client.post(URL,data=json.dumps([BASE]),
                           content_type="application/json")
        self.assertEqual(r.status_code,400)
        self.assertFalse(MojPropRateBucket.objects.exists())
