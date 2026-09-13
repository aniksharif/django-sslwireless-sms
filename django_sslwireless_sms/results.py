"""Typed views of API responses."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum, IntEnum
from typing import Any


class StatusCode(IntEnum):
    """Top-level ``status_code`` values from the API documentation."""

    SUCCESS = 200
    UNAUTHORIZED = 4001
    SID_NOT_PERMITTED = 4002
    IP_BLACKLISTED = 4003
    INVALID_REQUEST_FORMAT = 4004
    ENDPOINT_NOT_FOUND = 4005
    INVALID_CSMS_ID = 4020
    REQUIRED_PARAMETER_MISSING = 4022
    DUPLICATE_CSMS_ID = 4023
    DUPLICATE_MSISDN = 4024
    INVALID_MSISDN = 4025
    BLOCKED_MSISDN = 4026
    MESSAGE_LENGTH_EXCEEDED = 4027
    INVALID_MESSAGE_DATA = 4028
    TOO_MANY_REQUESTS = 4029
    LIMIT_EXCEEDED = 4030
    TPS_EXCEEDED = 4031
    INVALID_SMS = 4032
    TOO_MANY_OTP_REQUESTS = 4033
    UNABLE_TO_DECRYPT_SMS = 4034
    SIGNATURE_MISMATCH = 4035
    INTERNAL_ERROR = 5000


class SMSStatus(str, Enum):
    """Per-recipient ``smsinfo[].sms_status`` values."""

    SUCCESS = "SUCCESS"
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class SMSInfo:
    """One entry of the response's ``smsinfo`` array."""

    sms_status: str
    status_message: str = ""
    msisdn: str = ""
    sms_type: str = ""  # "EN" or "BN" (Unicode)
    csms_id: str = ""
    reference_id: str = ""
    sms_body: str = ""  # only echoed by some endpoints

    @property
    def ok(self) -> bool:
        return self.sms_status == SMSStatus.SUCCESS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SMSInfo:
        return cls(**{f.name: str(data.get(f.name) or "") for f in fields(cls)})


@dataclass(frozen=True)
class SendResult:
    """A parsed API response."""

    status: str
    status_code: int
    error_message: str
    smsinfo: tuple[SMSInfo, ...]
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"

    @property
    def succeeded(self) -> tuple[SMSInfo, ...]:
        return tuple(info for info in self.smsinfo if info.ok)

    @property
    def failed(self) -> tuple[SMSInfo, ...]:
        """Recipients the API did not accept, even when the request as a whole succeeded."""
        return tuple(info for info in self.smsinfo if not info.ok)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SendResult:
        try:
            status_code = int(data.get("status_code"))
        except (TypeError, ValueError):
            status_code = 0
        return cls(
            status=str(data.get("status") or "").upper(),
            status_code=status_code,
            error_message=str(data.get("error_message") or ""),
            smsinfo=tuple(
                SMSInfo.from_dict(item)
                for item in data.get("smsinfo") or ()
                if isinstance(item, dict)
            ),
            raw=data,
        )
