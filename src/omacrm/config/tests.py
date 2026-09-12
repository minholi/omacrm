import importlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, clear_url_caches, resolve

from omacrm.config import settings as project_settings
from omacrm.config import urls as project_urls


class EnvParsingTests(SimpleTestCase):
    def test_env_bool_uses_default_when_unset(self):
        with patch.dict(os.environ):
            os.environ.pop("DJANGO_DEBUG", None)
            self.assertIs(project_settings._env_bool("DJANGO_DEBUG", True), True)
            self.assertIs(project_settings._env_bool("DJANGO_DEBUG", False), False)

    def test_env_bool_falsy_values(self):
        for value in ("0", "false", "no", "off", ""):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"DJANGO_DEBUG": value}):
                    self.assertFalse(
                        project_settings._env_bool("DJANGO_DEBUG", True)
                    )

    def test_env_bool_truthy_values(self):
        for value in ("1", "true", "yes", "on", " 1 "):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"DJANGO_DEBUG": value}):
                    self.assertTrue(
                        project_settings._env_bool("DJANGO_DEBUG", False)
                    )

    def test_env_list_uses_default_when_unset(self):
        with patch.dict(os.environ):
            os.environ.pop("DJANGO_ALLOWED_HOSTS", None)
            self.assertEqual(
                project_settings._env_list("DJANGO_ALLOWED_HOSTS", ["*"]), ["*"]
            )

    def test_env_list_parses_and_strips_values(self):
        with patch.dict(
            os.environ, {"DJANGO_ALLOWED_HOSTS": "example.com, crm.example.com,"}
        ):
            self.assertEqual(
                project_settings._env_list("DJANGO_ALLOWED_HOSTS", ["*"]),
                ["example.com", "crm.example.com"],
            )

    def test_env_list_blank_value_falls_back_to_default(self):
        with patch.dict(os.environ, {"DJANGO_CSRF_TRUSTED_ORIGINS": "   "}):
            self.assertEqual(
                project_settings._env_list("DJANGO_CSRF_TRUSTED_ORIGINS", []), []
            )


class DeploymentSettingsTests(SimpleTestCase):
    def test_debug_defaults_to_true(self):
        with patch.dict(os.environ):
            os.environ.pop("DJANGO_DEBUG", None)
            self.assertTrue(project_settings._env_bool("DJANGO_DEBUG", True))

    def test_settings_are_env_driven(self):
        self.assertEqual(
            project_settings.DEBUG,
            project_settings._env_bool("DJANGO_DEBUG", True),
        )
        self.assertEqual(
            project_settings.ALLOWED_HOSTS,
            project_settings._env_list("DJANGO_ALLOWED_HOSTS", ["*"]),
        )
        self.assertEqual(
            project_settings.CSRF_TRUSTED_ORIGINS,
            project_settings._env_list("DJANGO_CSRF_TRUSTED_ORIGINS", []),
        )
        self.assertEqual(
            project_settings.SERVE_MEDIA,
            project_settings._env_bool("DJANGO_SERVE_MEDIA", False),
        )

    def test_proxy_ssl_header(self):
        self.assertEqual(
            project_settings.SECURE_PROXY_SSL_HEADER,
            ("HTTP_X_FORWARDED_PROTO", "https"),
        )


class MediaRouteTests(SimpleTestCase):
    def setUp(self):
        self.addCleanup(self._reload_urls)

    @staticmethod
    def _reload_urls():
        importlib.reload(project_urls)
        clear_url_caches()

    def test_media_route_absent_by_default(self):
        self.assertFalse(project_settings.SERVE_MEDIA)
        with self.assertRaises(Resolver404):
            resolve("/media/example.txt")

    def test_media_route_serves_files_when_enabled(self):
        with tempfile.TemporaryDirectory() as media_root:
            Path(media_root, "example.txt").write_text("hello media")
            with override_settings(SERVE_MEDIA=True, MEDIA_ROOT=media_root):
                self._reload_urls()
                response = self.client.get("/media/example.txt")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    b"".join(response.streaming_content), b"hello media"
                )
