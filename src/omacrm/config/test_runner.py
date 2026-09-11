import os
from pathlib import Path

from django.test.runner import DiscoverRunner

SRC_DIR = Path(__file__).resolve().parents[2]


class OmacrmDiscoverRunner(DiscoverRunner):
    """Test runner aware of the src/ layout.

    Plain ``manage.py test`` discovers tests from the repository root, which
    does not contain a package; default instead to ``src/``.
    """

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        if not test_labels:
            test_labels = [os.fspath(SRC_DIR)]
        return super().build_suite(test_labels, extra_tests=extra_tests, **kwargs)
