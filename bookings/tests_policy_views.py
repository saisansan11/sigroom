"""Contract regression: public policy routes and CSRF cookie disclosure."""
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

ROUTES = ("privacy", "cookies", "terms", "disclaimer")

class PublicPolicyRoutesTests(SimpleTestCase):
    def test_anonymous_routes_and_crosslinks(self):
        for route in ROUTES:
            with self.subTest(route=route):
                response = self.client.get(reverse(route), secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["current_policy"], route)
                tabs = response.content.decode("utf-8").split('<nav class="policy-tabs-nav"', 1)[1].split("</nav>", 1)[0]
                self.assertEqual(tabs.count('aria-current="page"'), 1)
                self.assertIn(f'href="{reverse(route)}" aria-current="page"', tabs)
                for linked in ROUTES:
                    self.assertContains(response, f"/{linked}/")

    @override_settings(CSRF_USE_SESSIONS=True, DJANGO_SECURE=True, SESSION_COOKIE_NAME="__session")
    def test_secure_session_mode_does_not_claim_csrf_cookie(self):
        response = self.client.get(reverse("cookies"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["csrf_use_sessions"])
        self.assertContains(response, "__session")
        self.assertNotContains(response, "<code>csrftoken</code>", html=False)

    @override_settings(CSRF_USE_SESSIONS=False, DJANGO_SECURE=False, SESSION_COOKIE_NAME="sessionid")
    def test_cookie_csrf_mode_shows_cookie(self):
        response = self.client.get(reverse("cookies"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["csrf_use_sessions"])
        self.assertContains(response, "<code>csrftoken</code>", html=False)

    def test_browser_storage_disclosure_matches_push_only_worker(self):
        response = self.client.get(reverse("cookies"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ไม่ได้ประกาศใช้ Offline Cache")
        self.assertNotContains(response, "<strong>SessionStorage:</strong>", html=False)
        self.assertNotContains(response, "<strong>LocalStorage:</strong>", html=False)

    def test_lodging_and_audit_disclosure_match_current_schema(self):
        from audit.models import AuditLog
        fields = {field.name for field in AuditLog._meta.get_fields()}
        self.assertIn("ip", fields)
        self.assertNotIn("user_agent", fields)
        self.assertNotIn("session", fields)
        response = self.client.get(reverse("privacy"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "บันทึกการรับกุญแจ")
        self.assertNotContains(response, "ชื่อ-สกุล, เพศ")
        self.assertContains(response, "ไม่ได้บันทึก User-Agent หรือ Session Data")
