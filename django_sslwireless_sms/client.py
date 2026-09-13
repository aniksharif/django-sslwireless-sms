"""HTTP client for the SSL Wireless ISMS Plus SMS API v3.

This module does not depend on Django and can be used on its own.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from typing import Any

import requests

from . import crypto
from .exceptions import SSLWirelessConnectionError, SSLWirelessResponseError, error_for_result
from .results import SendResult

DEFAULT_BASE_URL = "https://smsplus.sslwireless.com/api/v3"
DEFAULT_TIMEOUT = 10.0
MAX_BATCH_SIZE = 100
MAX_CSMS_ID_LENGTH = 20


def generate_csms_id() -> str:
    """Return a random client reference ID within the API's 20-character limit."""
    return uuid.uuid4().hex[:MAX_CSMS_ID_LENGTH]


def resolve_csms_id(csms_id: str | None) -> str:
    if csms_id is None:
        return generate_csms_id()
    csms_id = str(csms_id)
    if not 0 < len(csms_id) <= MAX_CSMS_ID_LENGTH:
        raise ValueError(f"csms_id must be 1-{MAX_CSMS_ID_LENGTH} characters, got {csms_id!r}")
    return csms_id


def check_batch_size(items: list[Any], name: str) -> None:
    if not items:
        raise ValueError(f"{name} must not be empty")
    if len(items) > MAX_BATCH_SIZE:
        raise ValueError(
            f"{name} accepts at most {MAX_BATCH_SIZE} entries per request, got {len(items)}"
        )


def normalize_dynamic_messages(messages: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Validate dynamic messages and fill in missing ``csms_id`` values."""
    normalized = []
    for message in messages:
        missing = {"msisdn", "text"} - message.keys()
        if missing:
            raise ValueError(f"dynamic message is missing {sorted(missing)}: {message!r}")
        normalized.append(
            {
                "msisdn": str(message["msisdn"]),
                "text": message["text"],
                "csms_id": resolve_csms_id(message.get("csms_id")),
            }
        )
    check_batch_size(normalized, "messages")
    return normalized


class SSLWirelessClient:
    """Wrapper around the four ISMS Plus v3 endpoints.

    Every ``send_*`` method returns a :class:`SendResult` when the API reports
    ``SUCCESS`` and raises an :class:`~django_sslwireless_sms.exceptions.SSLWirelessAPIError`
    subclass when it reports ``FAILED``. A missing ``csms_id`` is generated.
    """

    def __init__(
        self,
        api_token: str,
        sid: str,
        *,
        secret_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.api_token = api_token
        self.sid = sid
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def send_sms(self, msisdn: str | int, text: str, *, csms_id: str | None = None) -> SendResult:
        """Send one SMS to one recipient (``POST /send-sms``)."""
        return self._post(
            "send-sms",
            {
                **self._credentials(),
                "msisdn": str(msisdn),
                "sms": text,
                "csms_id": resolve_csms_id(csms_id),
            },
        )

    def send_bulk_sms(
        self, msisdns: Iterable[str | int], text: str, *, batch_csms_id: str | None = None
    ) -> SendResult:
        """Send the same SMS to up to 100 recipients (``POST /send-sms/bulk``)."""
        msisdns = [str(msisdn) for msisdn in msisdns]
        check_batch_size(msisdns, "msisdns")
        return self._post(
            "send-sms/bulk",
            {
                **self._credentials(),
                "msisdn": msisdns,
                "sms": text,
                "batch_csms_id": resolve_csms_id(batch_csms_id),
            },
        )

    def send_dynamic_sms(self, messages: Iterable[Mapping[str, Any]]) -> SendResult:
        """Send up to 100 different messages (``POST /send-sms/dynamic``).

        Each message is a mapping with ``msisdn``, ``text`` and optionally ``csms_id``.
        """
        return self._post(
            "send-sms/dynamic",
            {**self._credentials(), "sms": normalize_dynamic_messages(messages)},
        )

    def send_otp(self, msisdn: str | int, text: str, *, csms_id: str | None = None) -> SendResult:
        """Send an OTP with an encrypted body and ``X-Signature`` (``POST /secure/otp-sms``).

        Requires the client's ``secret_key`` from the ISMS Plus portal.
        """
        if not self.secret_key:
            raise ValueError("send_otp requires a secret_key")
        fields = {
            "sid": str(self.sid),
            "msisdn": str(msisdn),
            "sms": crypto.encrypt_sms(text, self.secret_key),
            "csms_id": resolve_csms_id(csms_id),
        }
        return self._post(
            "secure/otp-sms",
            {"api_token": self.api_token, **fields},
            headers={"X-Signature": crypto.sign(fields, self.secret_key)},
        )

    def _credentials(self) -> dict[str, str]:
        return {"api_token": self.api_token, "sid": self.sid}

    def _post(
        self, path: str, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> SendResult:
        url = f"{self.base_url}/{path}"
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Accept": "application/json", **(headers or {})},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise SSLWirelessConnectionError(f"POST {url} failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, dict) or "status" not in data:
            raise SSLWirelessResponseError(
                f"Unexpected response from {url} (HTTP {response.status_code})",
                http_status=response.status_code,
                body=response.text,
            )

        result = SendResult.from_dict(data)
        if not result.ok:
            raise error_for_result(result)
        return result
