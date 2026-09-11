from decimal import Decimal

from django.db import models


class Currency(models.Model):
    """Currency and its rate relative to the base currency.

    ``rate`` is the value of one unit of this currency expressed in the base
    currency (the base currency itself has rate 1). It is the fallback /
    current rate; dated values live in :class:`CurrencyRate`.
    """

    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=64, blank=True, default="")
    symbol = models.CharField(max_length=8, blank=True, default="")
    rate = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("1")
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "currencies"

    def __str__(self):
        return self.code


class CurrencyRate(models.Model):
    """Value of one unit of ``currency`` in the base currency on ``date``."""

    currency = models.ForeignKey(
        Currency, on_delete=models.CASCADE, related_name="rates"
    )
    date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "currency__code"]
        unique_together = [("currency", "date")]
        indexes = [models.Index(fields=["currency", "-date"])]

    def __str__(self):
        return f"{self.currency.code} @ {self.date}: {self.rate}"
