from django.test import TestCase, override_settings


@override_settings(ALLOWED_HOSTS=['mojplaywin.com', 'zomorodmelal.ir', 'testserver'])
class MojPlayWinAboutTests(TestCase):
    def test_mojplaywin_about_is_editorial_draft(self):
        response = self.client.get('/about/', HTTP_HOST='mojplaywin.com')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mojtaba Roozegar')
        self.assertContains(response, 'Vancouver')
        self.assertContains(response, 'Researcher')
        self.assertContains(response, 'Editor-in-Chief')
        self.assertIn('noindex', response['X-Robots-Tag'])
        self.assertNotIn('23 May 1984', response.content.decode())

    def test_other_host_preserves_company_redirect(self):
        response = self.client.get('/about/', HTTP_HOST='zomorodmelal.ir')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/company/')
