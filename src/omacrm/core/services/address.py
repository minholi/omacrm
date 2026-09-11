"""Address formatting helpers.

Addresses are stored as separate fields (``address_street``,
``billing_address_street``, ...). These helpers build display strings for
templates, the portal and notifications.
"""

ADDRESS_PARTS = ("street", "city", "state", "postal_code", "country")

DEFAULT_ORDER = ("street", "city", "state", "postal_code", "country")


def get_address_values(record, prefix: str = "") -> dict:
    """Return the address parts of a record.

    ``prefix`` selects the address block, e.g. ``"billing_"`` or
    ``"shipping_"`` (empty string for a single ``address_*`` block).
    """

    values = {}
    for part in ADDRESS_PARTS:
        attr = f"{prefix}address_{part}"
        values[part] = getattr(record, attr, "") or ""
    return values


def format_address(
    record,
    prefix: str = "",
    separator: str = ", ",
    order=DEFAULT_ORDER,
) -> str:
    """Format a record address, skipping empty parts."""

    values = get_address_values(record, prefix)
    return format_address_values(
        separator=separator,
        order=order,
        **values,
    )


def format_address_values(
    street: str = "",
    city: str = "",
    state: str = "",
    postal_code: str = "",
    country: str = "",
    separator: str = ", ",
    order=DEFAULT_ORDER,
) -> str:
    """Format raw address values, skipping empty parts."""

    values = {
        "street": street,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "country": country,
    }
    parts = [str(values[part]) for part in order if values.get(part)]
    return separator.join(parts)
