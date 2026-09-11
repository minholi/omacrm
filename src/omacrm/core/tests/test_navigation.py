from django.test import RequestFactory, TestCase

from omacrm.core.models import User
from omacrm.core.services.navigation import sidebar_navigation


class SidebarNavigationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = User.objects.create_superuser("nav", "nav@example.com", "pw")

    def _request(self, user):
        request = self.factory.get("/admin/")
        request.user = user
        return request

    def _group(self, navigation, title):
        return next(group for group in navigation if group["title"] == title)

    def test_email_templates_are_listed_under_marketing(self):
        navigation = sidebar_navigation(self._request(self.admin))
        titles = [item["title"] for item in self._group(navigation, "Marketing")["items"]]
        self.assertIn("Email Templates", titles)

    def test_email_templates_are_not_duplicated_in_system(self):
        navigation = sidebar_navigation(self._request(self.admin))
        titles = [item["title"] for item in self._group(navigation, "System")["items"]]
        self.assertNotIn("Email Templates", titles)
