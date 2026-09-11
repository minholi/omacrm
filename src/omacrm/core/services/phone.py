"""Phone number parsing, validation and formatting (libphonenumber)."""

import phonenumbers

_FORMATS = {
    "international": phonenumbers.PhoneNumberFormat.INTERNATIONAL,
    "national": phonenumbers.PhoneNumberFormat.NATIONAL,
    "e164": phonenumbers.PhoneNumberFormat.E164,
}


def default_region() -> str:
    try:
        from constance import config

        region = getattr(config, "phone_default_region", None)
    except Exception:  # noqa: BLE001 - constance may be unavailable
        region = None
    return (region or "US").upper()


def parse(value, region: str | None = None):
    """Return a phonenumbers PhoneNumber or ``None`` when unparseable."""

    if value in (None, ""):
        return None
    try:
        return phonenumbers.parse(str(value), region or default_region())
    except phonenumbers.NumberParseException:
        return None


def is_valid_phone(value, region: str | None = None) -> bool:
    number = parse(value, region)
    return bool(number and phonenumbers.is_valid_number(number))


def normalize_phone(value, region: str | None = None) -> str:
    """Return the E.164 form when valid, otherwise the original value."""

    number = parse(value, region)
    if number is None or not phonenumbers.is_valid_number(number):
        return str(value).strip() if value is not None else value
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def format_phone(value, region: str | None = None, style: str = "international"):
    """Format a phone number; invalid values are returned unchanged."""

    number = parse(value, region)
    if number is None or not phonenumbers.is_valid_number(number):
        return value
    return phonenumbers.format_number(
        number, _FORMATS.get(style, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    )
