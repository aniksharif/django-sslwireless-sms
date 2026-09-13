from __future__ import annotations

import requests
from django.core.exceptions import ImproperlyConfigured

from ..client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, SSLWirelessClient
from ..conf import get_settings
from .base import BaseSMSBackend


def _parse_timeout(value) -> float:
    # Accepts strings so the setting can come straight from an environment variable.
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ImproperlyConfigured(
            f"SSLWIRELESS_SMS['TIMEOUT'] must be a number of seconds, got {value!r}."
        ) from None


class SSLWirelessBackend(BaseSMSBackend):
    """Sends messages through the ISMS Plus API.

    Configuration comes from ``settings.SSLWIRELESS_SMS``; keyword arguments override it.
    """

    def __init__(
        self,
        *,
        api_token: str | None = None,
        sid: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        conf = get_settings()
        api_token = api_token or conf["API_TOKEN"]
        sid = sid or conf["SID"]
        if not api_token or not sid:
            raise ImproperlyConfigured(
                "SSLWIRELESS_SMS['API_TOKEN'] and SSLWIRELESS_SMS['SID'] must be set to use SSLWirelessBackend."
            )
        self.client = SSLWirelessClient(
            api_token,
            sid,
            secret_key=secret_key or conf["SECRET_KEY"] or None,
            # An empty value (e.g. an unset environment variable) means "use the default".
            base_url=base_url or conf["BASE_URL"] or DEFAULT_BASE_URL,
            timeout=_parse_timeout(timeout if timeout is not None else conf["TIMEOUT"] or DEFAULT_TIMEOUT),
            session=session,
        )

    def send_sms(self, msisdn, text, *, csms_id=None):
        return self.client.send_sms(msisdn, text, csms_id=csms_id)

    def send_bulk_sms(self, msisdns, text, *, batch_csms_id=None):
        return self.client.send_bulk_sms(msisdns, text, batch_csms_id=batch_csms_id)

    def send_dynamic_sms(self, messages):
        return self.client.send_dynamic_sms(messages)

    def send_otp(self, msisdn, text, *, csms_id=None):
        if not self.client.secret_key:
            raise ImproperlyConfigured("SSLWIRELESS_SMS['SECRET_KEY'] must be set to use send_otp().")
        return self.client.send_otp(msisdn, text, csms_id=csms_id)
