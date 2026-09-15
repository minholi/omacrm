from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from omacrm.core.models import User


class SwaggerPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "swagger-admin", "swagger@example.com", "pw"
        )

    def test_anonymous_is_redirected_to_the_admin_login(self):
        response = self.client.get(reverse("swagger"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_non_staff_user_is_redirected(self):
        user = User.objects.create_user("swagger-user", "swagger@example.com", "pw")
        self.client.force_login(user)
        response = self.client.get(reverse("swagger"))
        self.assertEqual(response.status_code, 302)

    def test_staff_user_sees_the_swagger_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("swagger"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vendor/swagger-ui/swagger-ui-bundle.js")
        self.assertContains(response, "vendor/swagger-ui/swagger-ui.css")
        self.assertContains(response, reverse("openapi_spec"))
        self.assertContains(response, "SwaggerUIBundle")

    def test_page_is_standalone_with_the_copy_icon_fix(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("swagger"))
        self.assertContains(response, "api-docs-bar")
        self.assertContains(response, "Back to admin")
        self.assertContains(
            response, ".view-line-link.copy-to-clipboard button svg"
        )
        self.assertNotContains(response, "unfold/")

    def test_vendored_assets_are_available(self):
        for name in (
            "vendor/swagger-ui/swagger-ui-bundle.js",
            "vendor/swagger-ui/swagger-ui.css",
        ):
            self.assertIsNotNone(finders.find(name), name)
