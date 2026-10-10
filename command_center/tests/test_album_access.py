from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from core.models import CompanyGalleryMedia

class AlbumAccessTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(username="media_staff", password="test-only", is_staff=True)
        self.url = reverse("command_center_media_album_api")

    def test_unpublished_item_has_no_public_url_in_response(self):
        CompanyGalleryMedia.objects.create(
            media_type="image", title="Orchard", project_label="pistachio",
            image="company/gallery/images/orchard.jpg", published=False
        )
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["items"][0]["image_url"])

    def test_non_staff_cannot_list(self):
        user = get_user_model().objects.create_user(username="media_reader", password="test-only")
        self.client.force_login(user)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
