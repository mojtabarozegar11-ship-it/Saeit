from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse


class AdminModuleLinkTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="module_link_staff",
            password="test-pass",
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_admin_tile_is_hidden_without_model_permission(self):
        response = self.client.get(reverse("command_center_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/admin/core/agent/"')
        self.assertContains(response, "مجوز این بخش برای حساب شما فعال نیست")

    def test_admin_tile_links_to_existing_changelist_with_view_permission(self):
        permission = Permission.objects.get(
            content_type__app_label="core",
            codename="view_agent",
        )
        self.staff.user_permissions.add(permission)
        response = self.client.get(reverse("command_center_dashboard"))
        self.assertContains(response, 'href="/admin/core/agent/"')

    def test_site_management_tile_opens_page_content_admin(self):
        permission = Permission.objects.get(
            content_type__app_label="core",
            codename="view_platformpagecontent",
        )
        self.staff.user_permissions.add(permission)
        response = self.client.get(reverse("command_center_dashboard"))
        self.assertContains(response, 'href="/admin/core/platformpagecontent/"')
