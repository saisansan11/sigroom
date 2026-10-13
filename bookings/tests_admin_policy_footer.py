"""Django Admin uses its own template, independent from the SIGROOM login."""
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .tests_policy_views import ROUTES

CREDITS = (
    "© 2569 แผนกวิชาการสื่อสารประเภทวิทยุและการสงครามอิเล็กทรอนิกส์",
    "© 2026 Radio Communications and Electronic Warfare Department",
    "สร้างสรรค์และดูแลระบบโดย ร.ต. วสันต์ ทัศนามล",
    "Created &amp; Maintained by 2nd Lt. Wasan Thatsanamol",
)

@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
class AdminPolicyFooterTests(SimpleTestCase):
    def test_anonymous_admin_login_discloses_policy_links_and_attribution(self):
        response = self.client.get(reverse("admin:login"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="login-form"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertContains(response, f'href="{reverse(route)}"')
        for credit in CREDITS:
            self.assertContains(response, credit, html=False)
        self.assertContains(response, "css/admin_policy_footer.css")

    def test_public_login_unchanged(self):
        response = self.client.get(reverse("login"), secure=True)
        self.assertEqual(response.status_code, 200)
        for route in ROUTES:
            self.assertContains(response, reverse(route))
