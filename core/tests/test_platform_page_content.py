from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import PlatformPageContent


def make_page(**overrides):
    values = {
        "page_key": "agriculture",
        "kicker": "AGRICULTURE / MANAGED",
        "title": "Managed agriculture title",
        "lead": "Managed lead text",
        "badge": "MANAGED",
        "heading": "Managed heading",
        "body": "Managed body text",
        "items": [{"title": "Managed card", "text": "Managed card text"}],
        "links": [{"title": "Research", "text": "Open research", "url": "/research/"}],
        "cta_title": "Managed action",
        "cta_text": "Managed action text",
        "cta_label": "Continue",
        "cta_url": "/contact/",
        "seo_title": "Managed SEO title",
        "meta_description": "Managed SEO description",
        "published": True,
    }
    values.update(overrides)
    return PlatformPageContent.objects.create(**values)


class PlatformPageContentPublicTests(TestCase):
    def test_published_content_replaces_static_copy_and_seo(self):
        make_page()
        response = self.client.get("/agriculture/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Managed agriculture title")
        self.assertContains(response, "Managed card text")
        self.assertContains(response, "Managed SEO title")
        self.assertContains(response, "Managed SEO description")

    def test_draft_content_does_not_change_public_page(self):
        make_page(published=False, title="Draft title must stay private")
        response = self.client.get("/agriculture/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "کشاورزی و زنجیره ارزش")
        self.assertNotContains(response, "Draft title must stay private")

    def test_published_links_must_be_internal_paths(self):
        page = PlatformPageContent(
            **{
                "page_key": "agriculture",
                "kicker": "Kicker",
                "title": "Title",
                "lead": "Lead",
                "badge": "Badge",
                "heading": "Heading",
                "body": "Body",
                "items": [],
                "links": [{"title": "External", "text": "Link", "url": "https://example.com"}],
                "cta_title": "CTA",
                "cta_text": "Text",
                "cta_label": "Go",
                "cta_url": "/contact/",
                "published": True,
            }
        )
        with self.assertRaises(ValidationError):
            page.full_clean()


class PlatformPageContentAdminTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="content_editor",
            password="test-pass",
            is_staff=True,
        )
        self.staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="core",
                codename="change_platformpagecontent",
            ),
            Permission.objects.get(
                content_type__app_label="core",
                codename="delete_platformpagecontent",
            ),
        )
        self.client.force_login(self.staff)

    def test_staff_cannot_publish_draft_directly(self):
        page = make_page(published=False)
        response = self.client.post(
            reverse("admin:core_platformpagecontent_change", args=(page.pk,)),
            {
                "page_key": page.page_key,
                "kicker": page.kicker,
                "title": page.title,
                "lead": page.lead,
                "badge": page.badge,
                "heading": page.heading,
                "body": page.body,
                "items": '[{"title": "Managed card", "text": "Managed card text"}]',
                "links": '[{"title": "Research", "text": "Open research", "url": "/research/"}]',
                "cta_title": page.cta_title,
                "cta_text": page.cta_text,
                "cta_label": page.cta_label,
                "cta_url": page.cta_url,
                "seo_title": page.seo_title,
                "meta_description": page.meta_description,
                "published": "on",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        page.refresh_from_db()
        self.assertFalse(page.published)

    def test_staff_cannot_edit_or_delete_published_page(self):
        page = make_page()
        change_url = reverse("admin:core_platformpagecontent_change", args=(page.pk,))
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="title"')
        self.assertEqual(
            self.client.get(
                reverse("admin:core_platformpagecontent_delete", args=(page.pk,))
            ).status_code,
            403,
        )



class PlatformPageBlockTests(TestCase):
    def test_published_page_renders_active_blocks_in_order(self):
        page = make_page()
        from core.models import PlatformPageBlock

        PlatformPageBlock.objects.create(
            page=page, kind="text", title="Second block", body="Ordered content second",
            sort_order=20,
        )
        PlatformPageBlock.objects.create(
            page=page, kind="text", title="First block", body="Ordered content first",
            sort_order=10,
        )
        PlatformPageBlock.objects.create(
            page=page, kind="text", title="Hidden block", body="Inactive content",
            sort_order=5, active=False,
        )

        response = self.client.get("/agriculture/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "First block")
        self.assertContains(response, "Second block")
        self.assertNotContains(response, "Inactive content")
        self.assertLess(
            response.content.index(b"First block"),
            response.content.index(b"Second block"),
        )

    def test_draft_page_blocks_are_not_public(self):
        page = make_page(published=False)
        from core.models import PlatformPageBlock

        PlatformPageBlock.objects.create(
            page=page, kind="text", title="Draft-only block", body="Not public",
        )
        response = self.client.get("/agriculture/")
        self.assertNotContains(response, "Draft-only block")
        self.assertNotContains(response, "Not public")

    def test_block_rejects_external_links(self):
        from core.models import PlatformPageBlock

        page = make_page(published=False)
        block = PlatformPageBlock(
            page=page,
            kind="links",
            items=[{"title": "External", "text": "Unsafe", "url": "https://example.com"}],
        )
        with self.assertRaises(ValidationError):
            block.full_clean()

    def test_staff_cannot_edit_blocks_on_published_page(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from core.admin import PlatformPageBlockInline
        from core.models import PlatformPageBlock

        page = make_page()
        request = RequestFactory().get("/admin/")
        request.user = self.staff
        inline = PlatformPageBlockInline(PlatformPageContent, admin.site)
        self.assertFalse(inline.has_add_permission(request, page))
        self.assertFalse(inline.has_change_permission(request, page))
        self.assertFalse(inline.has_delete_permission(request, page))

        owner = get_user_model().objects.create_superuser(
            username="site_owner", email="owner@example.com", password="test-pass"
        )
        request.user = owner
        self.assertTrue(inline.has_add_permission(request, page))
