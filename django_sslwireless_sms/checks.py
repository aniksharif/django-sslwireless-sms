from __future__ import annotations

from django.core.checks import CheckMessage, Error, register
from django.utils.module_loading import import_string

from .backends.api import SSLWirelessBackend
from .conf import get_settings


@register()
def check_sslwireless_sms_settings(app_configs=None, **kwargs) -> list[CheckMessage]:
    conf = get_settings()
    try:
        backend = import_string(conf["BACKEND"])
    except ImportError as exc:
        return [
            Error(
                f"SSLWIRELESS_SMS['BACKEND'] could not be imported: {exc}",
                id="django_sslwireless_sms.E001",
            )
        ]

    if not (isinstance(backend, type) and issubclass(backend, SSLWirelessBackend)):
        return []

    return [
        Error(
            f"SSLWIRELESS_SMS['{key}'] is not set.",
            hint="Copy it from the ISMS Plus portal, or use a locmem/console backend.",
            id="django_sslwireless_sms.E002",
        )
        for key in ("API_TOKEN", "SID")
        if not conf[key]
    ]
