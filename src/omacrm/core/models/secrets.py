"""Named credentials (API keys, passwords) stored encrypted at rest."""

from django.db import models


class AppSecret(models.Model):
    """An application secret referenced by name, never by value.

    The value is Fernet-encrypted with a key derived from ``SECRET_KEY``
    (``core/services/crypto.py``), mirroring the IMAP account passwords, so a
    database dump does not expose the credentials.
    """

    name = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def set_value(self, raw: str) -> None:
        from omacrm.core.services.crypto import encrypt

        self.value = encrypt(raw)

    def get_value(self) -> str:
        from omacrm.core.services.crypto import decrypt

        return decrypt(self.value)
