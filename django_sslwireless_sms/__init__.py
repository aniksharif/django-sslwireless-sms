"""Django integration for the SSL Wireless ISMS Plus SMS API (v3)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .backends import get_backend
from .backends.base import SentSMS
from .backends.locmem import outbox
from .client import SSLWirelessClient
from .exceptions import (
    AuthenticationError,
    InvalidRequestError,
    RateLimitError,
    ServerError,
    SignatureError,
    SSLWirelessAPIError,
    SSLWirelessConnectionError,
    SSLWirelessError,
    SSLWirelessResponseError,
)
from .results import SendResult, SMSInfo, SMSStatus, StatusCode

__version__ = "1.0.2"

__all__ = [
    "AuthenticationError",
    "InvalidRequestError",
    "RateLimitError",
    "SMSInfo",
    "SMSStatus",
    "SSLWirelessAPIError",
    "SSLWirelessClient",
    "SSLWirelessConnectionError",
    "SSLWirelessError",
    "SSLWirelessResponseError",
    "SendResult",
    "SentSMS",
    "ServerError",
    "SignatureError",
    "StatusCode",
    "get_backend",
    "outbox",
    "send_bulk_sms",
    "send_dynamic_sms",
    "send_otp",
    "send_sms",
]


def send_sms(
    msisdn: str | int, text: str, *, csms_id: str | None = None, backend: str | None = None
) -> SendResult:
    """Send one SMS to one recipient."""
    return get_backend(backend).send_sms(msisdn, text, csms_id=csms_id)


def send_bulk_sms(
    msisdns: Iterable[str | int],
    text: str,
    *,
    batch_csms_id: str | None = None,
    backend: str | None = None,
) -> SendResult:
    """Send the same SMS to up to 100 recipients."""
    return get_backend(backend).send_bulk_sms(msisdns, text, batch_csms_id=batch_csms_id)


def send_dynamic_sms(
    messages: Iterable[Mapping[str, str]], *, backend: str | None = None
) -> SendResult:
    """Send up to 100 personalised messages (``{"msisdn", "text", "csms_id"?}`` mappings)."""
    return get_backend(backend).send_dynamic_sms(messages)


def send_otp(
    msisdn: str | int, text: str, *, csms_id: str | None = None, backend: str | None = None
) -> SendResult:
    """Send an OTP through the encrypted, signed ``secure/otp-sms`` endpoint."""
    return get_backend(backend).send_otp(msisdn, text, csms_id=csms_id)
