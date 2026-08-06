from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operator", password="strong-test-password")
        self.admin = get_user_model().objects.create_superuser(username="admin", password="strong-test-password", email="admin@example.com")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertRedirects(response, "/login/?next=/")

    def test_authenticated_user_can_view_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_view_admin_portal(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:admin_portal"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_view_admin_portal(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_portal"))
        self.assertEqual(response.status_code, 200)

    def test_login_form_is_csrf_protected(self):
        response = self.client.get(reverse("dashboard:login"))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
