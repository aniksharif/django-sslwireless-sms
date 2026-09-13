from __future__ import annotations

from typing import Any

from django.utils.module_loading import import_string

from ..conf import get_settings
from .base import BaseSMSBackend


def get_backend(backend: str | None = None, **options: Any) -> BaseSMSBackend:
    """Instantiate ``backend`` (a dotted path), defaulting to ``SSLWIRELESS_SMS['BACKEND']``."""
    return import_string(backend or get_settings()["BACKEND"])(**options)
