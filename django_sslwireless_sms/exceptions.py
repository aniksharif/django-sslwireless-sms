from __future__ import annotations

from .results import SendResult, StatusCode


class SSLWirelessError(Exception):
    """Base class for every error raised by django-sslwireless-sms."""


class SSLWirelessConnectionError(SSLWirelessError):
    """The API could not be reached (DNS, TLS, timeout, connection reset...)."""


class SSLWirelessResponseError(SSLWirelessError):
    """The API answered with something that is not a recognisable JSON result."""

    def __init__(self, message: str, *, http_status: int, body: str) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.body = body


class SSLWirelessAPIError(SSLWirelessError):
    """The API returned ``"status": "FAILED"``. The parsed response is on ``.result``."""

    def __init__(self, result: SendResult) -> None:
        super().__init__(f"[{result.status_code}] {result.error_message or 'Request failed'}")
        self.result = result

    @property
    def status_code(self) -> int:
        return self.result.status_code

    @property
    def error_message(self) -> str:
        return self.result.error_message


class AuthenticationError(SSLWirelessAPIError):
    """Bad API token, SID not permitted, or request IP not whitelisted."""


class InvalidRequestError(SSLWirelessAPIError):
    """The request was malformed or contained invalid data (bad MSISDN, duplicate ID...)."""


class RateLimitError(SSLWirelessAPIError):
    """Request rate, TPS, or per-recipient OTP limit exceeded. Retry later."""


class SignatureError(SSLWirelessAPIError):
    """Secure OTP decryption or signature verification failed. Check SECRET_KEY."""


class ServerError(SSLWirelessAPIError):
    """Internal error on the ISMS Plus side."""


_ERRORS_BY_CODE: dict[int, type[SSLWirelessAPIError]] = {
    StatusCode.UNAUTHORIZED: AuthenticationError,
    StatusCode.SID_NOT_PERMITTED: AuthenticationError,
    StatusCode.IP_BLACKLISTED: AuthenticationError,
    StatusCode.TOO_MANY_REQUESTS: RateLimitError,
    StatusCode.TPS_EXCEEDED: RateLimitError,
    StatusCode.TOO_MANY_OTP_REQUESTS: RateLimitError,
    StatusCode.UNABLE_TO_DECRYPT_SMS: SignatureError,
    StatusCode.SIGNATURE_MISMATCH: SignatureError,
    StatusCode.INTERNAL_ERROR: ServerError,
}


def error_for_result(result: SendResult) -> SSLWirelessAPIError:
    """Build the most specific exception for a failed result."""
    if result.status_code in _ERRORS_BY_CODE:
        cls = _ERRORS_BY_CODE[result.status_code]
    elif 4000 <= result.status_code < 5000:
        cls = InvalidRequestError
    else:
        cls = SSLWirelessAPIError
    return cls(result)
