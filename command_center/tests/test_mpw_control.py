"""Database and HTTP regression checks: main tenant only, no payment without proof."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from command_center.models import MpwRecord, TENANT
from command_center.mpw_public import public_context
from command_center.mpw_workflow import create_record, change_record


@override_settings(ALLOWED_HOSTS=["mojplaywin.com","www.mojplaywin.com","outside.example"],
                   MPW_CONTROL_ENABLED=True, MPW_ENABLE_CHECKOUT=False)
class MainControlTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(username="mpw_owner_test",
                    email="owner@test.example",password="irrelevant-test-pass")
        self.staff = User.objects.create_user(username="mpw_staff_test",
                    password="irrelevant-test-pass",is_staff=True)
        self.client.force_login(self.owner)

    def content_source(self, title="Original"):
        return {"title":title,"body":"Verified guide","slot":"row",
                "group":"editorial","url":"/knowledge/","image":"site/heroes/research.webp"}

    def test_host_isolation_and_access_control(self):
        response=self.client.get("/staff/command-center/mpw-operations/",
                                 HTTP_HOST="outside.example")
        self.assertEqual(response.status_code,404)
        self.client.logout()
        response=self.client.get("/staff/command-center/mpw-operations/",
                                 HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,302)
        self.assertEqual(public_context(type("Request",(),{"get_host":lambda s:"outside.example","path":"/"})())["mpw_managed_blocks"],[])

    def test_quality_failure_returns_to_rework_without_destroying_previous_publication(self):
        row=create_record(self.owner,"content","approved-guide","/",self.content_source())
        row=change_record(self.owner,row.pk,"submit",revision=row.revision)
        row=change_record(self.owner,row.pk,"qa_pass",revision=row.revision,evidence="qa/report-01")
        row=change_record(self.owner,row.pk,"approve",revision=row.revision,evidence="owner/review-01")
        row=change_record(self.owner,row.pk,"publish",revision=row.revision)
        self.assertEqual(row.published_snapshot["title"],"Original")
        row=change_record(self.owner,row.pk,"edit",revision=row.revision,
                          payload=self.content_source("Updated"))
        row=change_record(self.owner,row.pk,"submit",revision=row.revision)
        row=change_record(self.owner,row.pk,"reject",revision=row.revision,
                          note="Broken contrast; revise before QA.")
        self.assertEqual(row.state,"needs_revision")
        self.assertEqual(row.published_snapshot["title"],"Original")
        self.assertTrue(row.quality_note)
        self.assertEqual(MpwRecord.objects.filter(tenant=TENANT,kind="content").count(),1)

    def test_unreviewed_offer_is_not_public_and_payments_fail_closed(self):
        offer={"title":"Test handbook","body":"Preview","price":"5.00","currency":"USD",
               "checkout_path":"/store/product/5/checkout/",
               "rights_verified":True,"payment_verified":True,"delivery_verified":True,
               "payment_evidence":"run-1","delivery_evidence":"run-2"}
        row=create_record(self.owner,"offer","test-handbook","/store/",offer)
        self.assertEqual(row.published_snapshot,{})
        row=change_record(self.owner,row.pk,"submit",revision=row.revision)
        row=change_record(self.owner,row.pk,"qa_pass",revision=row.revision,evidence="qa-proof")
        with self.assertRaises(ValidationError):
            change_record(self.staff,row.pk,"approve",revision=row.revision,evidence="not-owner")
        row=change_record(self.owner,row.pk,"approve",revision=row.revision,evidence="owner-proof")
        row=change_record(self.owner,row.pk,"publish",revision=row.revision)
        from django.test import RequestFactory
        context=public_context(RequestFactory().get("/store/",HTTP_HOST="mojplaywin.com"))
        self.assertEqual(context["mpw_managed_offers"][0]["title"],"Test handbook")
        self.assertFalse(context["mpw_managed_offers"][0]["payable"])
        self.assertFalse(context["mpw_managed_offers"][0]["checkout_path"])

    def test_source_validation_and_job_provenance(self):
        with self.assertRaises(ValidationError):
            create_record(self.owner,"content","cross","//external.example",self.content_source())
        with self.assertRaises(ValidationError):
            create_record(self.owner,"content","bad-img","/",
                          {**self.content_source(),"image":"../admin/private.png"})
        job=create_record(self.owner,"job","factory-work","/",
                          {"title":"Customer request","origin":"customer",
                           "source_ref":"order-evidence-01","target_key":"not-published"})
        job=change_record(self.owner,job.pk,"submit",revision=job.revision)
        job=change_record(self.owner,job.pk,"qa_pass",revision=job.revision,evidence="qa-proof")
        job=change_record(self.owner,job.pk,"approve",revision=job.revision,evidence="owner-proof")
        with self.assertRaises(ValidationError):
            change_record(self.owner,job.pk,"publish",revision=job.revision)
        self.assertEqual(MpwRecord.objects.get(pk=job.pk).state,"approved")

    def test_post_requires_csrf_in_real_browser_and_staff(self):
        response=self.client.get("/staff/command-center/mpw-operations/",HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        self.client.force_login(self.staff)
        response=self.client.post("/staff/command-center/mpw-operations/",
                   {"action":"create","kind":"content","key":"staff-card","page_path":"/",
                    **self.content_source()},HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,302)
        self.assertTrue(MpwRecord.objects.filter(key="staff-card").exists())
