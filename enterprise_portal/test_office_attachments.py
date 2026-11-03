"""Security and integrity regression for private correspondence attachments."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import AuditEvent, OfficeAttachment, OfficeLetter

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"


@override_settings(DEBUG=True, COMPANY_OFFICE_REQUIRE_MFA=False)
class PrivateOfficeAttachmentTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zm-office-private-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "secure" / "files"
        setting = override_settings(COMPANY_OFFICE_ATTACHMENT_ROOT=self.root)
        setting.enable()
        self.addCleanup(setting.disable)
        users = get_user_model()
        self.owner = users.objects.create_user(
            username="letter_owner", password="OnlyForTest!123", is_staff=True,
        )
        self.other = users.objects.create_user(
            username="letter_other", password="OnlyForTest!123", is_staff=True,
        )
        permissions = Permission.objects.filter(
            content_type__app_label="enterprise_portal",
            codename__in=(
                "view_businessunit", "add_officeletter", "view_officeletter",
                "add_officeattachment", "download_officeattachment",
            ),
        )
        for user in (self.owner, self.other):
            user.user_permissions.add(*permissions)
        self.client.force_login(self.owner)

    def letter_data(self, name="LT-2026-001", filedata=PDF):
        return {
            "number": name,
            "subject": "نامه محرمانه داخلی",
            "direction": "incoming",
            "body": "محتوای نامه برای مسئول مربوط",
            "classification": "confidential",
            "sent_on": "2026-11-01",
            "recipient": "دبیرخانه",
            "attachment": SimpleUploadedFile(
                "evidence.pdf", filedata, content_type="application/pdf",
            ),
        }

    def _create(self):
        response = self.client.post(
            reverse("enterprise_portal:new_letter"), self.letter_data(), secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(OfficeAttachment.objects.count(), 1)
        return OfficeAttachment.objects.get()

    def test_authorized_upload_download_hash_and_private_cache_controls(self):
        attachment = self._create()
        self.assertTrue(self.root.is_dir())
        self.assertFalse(self.root.stat().st_mode & 0o077)
        self.assertEqual((self.root / attachment.storage_key).read_bytes(), PDF)
        self.assertNotIn("public_html", str(self.root))
        self.assertEqual(attachment.letter.created_by, self.owner)
        self.assertEqual(
            AuditEvent.objects.filter(
                target=f"OfficeLetter:{attachment.letter_id}",
                action="office_attachment_uploaded",
            ).count(), 1,
        )
        response = self.client.get(
            reverse("enterprise_portal:download_office_attachment",
                    args=[attachment.pk]), secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("nosniff", response["X-Content-Type-Options"])
        listing = self.client.get(reverse("enterprise_portal:letters"), secure=True)
        self.assertContains(listing, "evidence.pdf")
        self.assertNotContains(listing, attachment.storage_key)

    def test_unrelated_staff_cannot_list_or_download_private_letter_file(self):
        attachment = self._create()
        self.client.force_login(self.other)
        listing = self.client.get(reverse("enterprise_portal:letters"), secure=True)
        self.assertNotContains(listing, "نامه محرمانه داخلی")
        download = self.client.get(
            reverse("enterprise_portal:download_office_attachment",
                    args=[attachment.pk]), secure=True,
        )
        self.assertEqual(download.status_code, 404)

    def test_download_needs_separate_permission(self):
        attachment = self._create()
        perm = Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="download_officeattachment",
        )
        self.owner.user_permissions.remove(perm)
        fresh_client = Client()
        fresh_client.force_login(self.owner)
        self.assertEqual(fresh_client.get(
            reverse("enterprise_portal:download_office_attachment",
                    args=[attachment.pk]), secure=True,
        ).status_code, 403)

    def test_invalid_file_type_and_forged_signature_are_refused(self):
        invalid = self.letter_data("LT-SVG")
        invalid["attachment"] = SimpleUploadedFile(
            "evil.svg", b"<svg><script>alert(1)</script></svg>",
            content_type="image/svg+xml",
        )
        response = self.client.post(
            reverse("enterprise_portal:new_letter"), invalid, secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF")
        forged = self.letter_data("LT-FAKE", b"<script>not PDF</script>")
        response = self.client.post(
            reverse("enterprise_portal:new_letter"), forged, secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نوع واقعی فایل")
        self.assertFalse(OfficeLetter.objects.exists())
        self.assertFalse(OfficeAttachment.objects.exists())

    def test_modified_file_cannot_be_downloaded(self):
        attachment = self._create()
        (self.root / attachment.storage_key).write_bytes(b"%PDF-1.4\nTAMPER\n")
        response = self.client.get(
            reverse("enterprise_portal:download_office_attachment",
                    args=[attachment.pk]), secure=True,
        )
        self.assertEqual(response.status_code, 404)

    def test_csrf_protection_applies_to_multipart_post(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.owner)
        response = protected.post(
            reverse("enterprise_portal:new_letter"), self.letter_data("LT-CSRF"),
            secure=True,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(OfficeAttachment.objects.exists())

    def test_no_stray_blob_when_metadata_audit_fails(self):
        original = AuditEvent.objects.create
        call_count = 0

        def fail_second(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("synthetic DB audit failure")
            return original(*args, **kwargs)

        with patch.object(AuditEvent.objects, "create", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("enterprise_portal:new_letter"),
                    self.letter_data("LT-ROLLBACK"), secure=True,
                )
        self.assertFalse(OfficeLetter.objects.exists())
        self.assertFalse(OfficeAttachment.objects.exists())
        self.assertEqual(list(self.root.iterdir()), [])
