from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ..client import check_batch_size, normalize_dynamic_messages, resolve_csms_id
from ..results import SendResult, SMSInfo, SMSStatus


class BaseSMSBackend:
    """Interface shared by all backends. Signatures match :class:`SSLWirelessClient`."""

    def __init__(self, **options: Any) -> None:
        pass

    def send_sms(self, msisdn: str | int, text: str, *, csms_id: str | None = None) -> SendResult:
        raise NotImplementedError

    def send_bulk_sms(
        self, msisdns: Iterable[str | int], text: str, *, batch_csms_id: str | None = None
    ) -> SendResult:
        raise NotImplementedError

    def send_dynamic_sms(self, messages: Iterable[Mapping[str, Any]]) -> SendResult:
        raise NotImplementedError

    def send_otp(self, msisdn: str | int, text: str, *, csms_id: str | None = None) -> SendResult:
        raise NotImplementedError


@dataclass(frozen=True)
class SentSMS:
    """A message captured by a simulated backend."""

    kind: str  # "single", "bulk", "dynamic" or "otp"
    msisdn: str
    text: str
    csms_id: str


class SimulatedBackend(BaseSMSBackend):
    """Validates input like the real client, then hands messages to :meth:`deliver`
    instead of calling the API, and returns a successful result."""

    def deliver(self, messages: list[SentSMS]) -> None:
        raise NotImplementedError

    def send_sms(self, msisdn, text, *, csms_id=None):
        return self._send([SentSMS("single", str(msisdn), text, resolve_csms_id(csms_id))])

    def send_bulk_sms(self, msisdns, text, *, batch_csms_id=None):
        msisdns = [str(msisdn) for msisdn in msisdns]
        check_batch_size(msisdns, "msisdns")
        batch_csms_id = resolve_csms_id(batch_csms_id)
        return self._send([SentSMS("bulk", msisdn, text, batch_csms_id) for msisdn in msisdns])

    def send_dynamic_sms(self, messages):
        return self._send(
            [
                SentSMS("dynamic", message["msisdn"], message["text"], message["csms_id"])
                for message in normalize_dynamic_messages(messages)
            ]
        )

    def send_otp(self, msisdn, text, *, csms_id=None):
        return self._send([SentSMS("otp", str(msisdn), text, resolve_csms_id(csms_id))])

    def _send(self, messages: list[SentSMS]) -> SendResult:
        self.deliver(messages)
        return SendResult(
            status="SUCCESS",
            status_code=200,
            error_message="",
            smsinfo=tuple(
                SMSInfo(
                    sms_status=SMSStatus.SUCCESS.value,
                    status_message="Success",
                    msisdn=message.msisdn,
                    csms_id=message.csms_id,
                    reference_id=uuid.uuid4().hex[:19],
                )
                for message in messages
            ),
        )
