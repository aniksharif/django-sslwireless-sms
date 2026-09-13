"""Access to the ``SSLWIRELESS_SMS`` Django setting, merged with defaults."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from .client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT

DEFAULTS: dict[str, Any] = {
    "BACKEND": "django_sslwireless_sms.backends.api.SSLWirelessBackend",
    "API_TOKEN": "",
    "SID": "",
    # Only needed for send_otp(); copy it from the ISMS Plus portal.
    "SECRET_KEY": "",
    "BASE_URL": DEFAULT_BASE_URL,
    "TIMEOUT": DEFAULT_TIMEOUT,
}


def get_settings() -> dict[str, Any]:
    """Return ``settings.SSLWIRELESS_SMS`` layered over :data:`DEFAULTS`.

    Read on every call so ``override_settings`` works in tests.
    """
    return {**DEFAULTS, **getattr(settings, "SSLWIRELESS_SMS", {})}
