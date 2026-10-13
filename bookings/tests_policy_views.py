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
