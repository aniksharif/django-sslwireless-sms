import io
import json

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_sslwireless_sms import (
    SentSMS,
    crypto,
    get_backend,
    outbox,
    send_bulk_sms,
    send_dynamic_sms,
    send_otp,
    send_sms,
)
from django_sslwireless_sms.backends.api import SSLWirelessBackend
from django_sslwireless_sms.backends.console import ConsoleBackend
from django_sslwireless_sms.backends.locmem import LocmemBackend
from django_sslwireless_sms.client import DEFAULT_BASE_URL

LOCMEM = "django_sslwireless_sms.backends.locmem.LocmemBackend"
SUCCESS = {"status": "SUCCESS", "status_code": 200, "error_message": "", "smsinfo": []}


# --- API backend ----------------------------------------------------------------------


def test_default_backend_is_configured_from_settings():
    backend = get_backend()

    assert isinstance(backend, SSLWirelessBackend)
    assert backend.client.api_token == "test-api-token"
    assert backend.client.sid == "TESTSID"
    assert backend.client.secret_key == "test-secret"
    assert backend.client.base_url == DEFAULT_BASE_URL
    assert backend.client.timeout == 10


def test_backend_options_override_settings():
    backend = get_backend(api_token="other-token", sid="OTHERSID", timeout=2)

    assert backend.client.api_token == "other-token"
    assert backend.client.sid == "OTHERSID"
    assert backend.client.timeout == 2


@override_settings(SSLWIRELESS_SMS={})
def test_api_backend_requires_credentials():
    with pytest.raises(ImproperlyConfigured, match="API_TOKEN"):
        get_backend()


@override_settings(SSLWIRELESS_SMS={"API_TOKEN": "t", "SID": "S"})
def test_api_backend_otp_requires_secret_key(mocked_api):
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        send_otp("8801712345678", "Your OTP is 123456")
    assert not mocked_api.calls


def test_shortcuts_use_settings_credentials(mocked_api):
    mocked_api.post(f"{DEFAULT_BASE_URL}/send-sms", json=SUCCESS)
    mocked_api.post(f"{DEFAULT_BASE_URL}/send-sms/bulk", json=SUCCESS)
    mocked_api.post(f"{DEFAULT_BASE_URL}/send-sms/dynamic", json=SUCCESS)
    mocked_api.post(f"{DEFAULT_BASE_URL}/secure/otp-sms", json=SUCCESS)

    send_sms("8801712345678", "one")
    send_bulk_sms(["8801712345678"], "bulk")
    send_dynamic_sms([{"msisdn": "8801712345678", "text": "dynamic"}])
    send_otp("8801712345678", "Your OTP is 123456")

    bodies = [json.loads(call.request.body) for call in mocked_api.calls]
    assert all(body["api_token"] == "test-api-token" and body["sid"] == "TESTSID" for body in bodies)
    assert crypto.decrypt_sms(bodies[3]["sms"], "test-secret") == "Your OTP is 123456"


@override_settings(
    SSLWIRELESS_SMS={"API_TOKEN": "t", "SID": "S", "BASE_URL": "https://sms.example.test/api/v3", "TIMEOUT": 4}
)
def test_base_url_and_timeout_settings(mocked_api):
    mocked_api.post("https://sms.example.test/api/v3/send-sms", json=SUCCESS)

    send_sms("8801712345678", "Hello")

    assert mocked_api.calls[0].request.req_kwargs["timeout"] == 4


@override_settings(SSLWIRELESS_SMS={"API_TOKEN": "t", "SID": "S", "BASE_URL": "", "TIMEOUT": "7.5"})
def test_values_read_from_environment_variables_are_accepted():
    # e.g. os.environ.get("SSLWIRELESS_SMS_BASE_URL", "") left unset, TIMEOUT given as a string
    backend = get_backend()

    assert backend.client.base_url == DEFAULT_BASE_URL
    assert backend.client.timeout == 7.5


@override_settings(SSLWIRELESS_SMS={"API_TOKEN": "t", "SID": "S", "TIMEOUT": "soon"})
def test_invalid_timeout_is_reported():
    with pytest.raises(ImproperlyConfigured, match="TIMEOUT"):
        get_backend()


# --- locmem backend -------------------------------------------------------------------


@override_settings(SSLWIRELESS_SMS={"BACKEND": LOCMEM})
def test_locmem_backend_records_every_message_type():
    single = send_sms("8801712345678", "Hello", csms_id="s-1")
    bulk = send_bulk_sms(["8801712345678", 8801812345678], "Sale", batch_csms_id="b-1")
    send_dynamic_sms([{"msisdn": "8801912345678", "text": "Hi Jane", "csms_id": "d-1"}])
    send_otp("8801712345678", "Your OTP is 123456", csms_id="o-1")

    assert outbox == [
        SentSMS("single", "8801712345678", "Hello", "s-1"),
        SentSMS("bulk", "8801712345678", "Sale", "b-1"),
        SentSMS("bulk", "8801812345678", "Sale", "b-1"),
        SentSMS("dynamic", "8801912345678", "Hi Jane", "d-1"),
        SentSMS("otp", "8801712345678", "Your OTP is 123456", "o-1"),
    ]
    assert single.ok and single.smsinfo[0].csms_id == "s-1" and single.smsinfo[0].reference_id
    assert [info.msisdn for info in bulk.succeeded] == ["8801712345678", "8801812345678"]


@override_settings(SSLWIRELESS_SMS={"BACKEND": LOCMEM})
def test_locmem_backend_validates_like_the_real_client():
    with pytest.raises(ValueError, match="at most 100"):
        send_bulk_sms([f"88017{i:08d}" for i in range(101)], "Hi")
    with pytest.raises(ValueError, match="csms_id"):
        send_sms("8801712345678", "Hi", csms_id="x" * 21)
    assert outbox == []


def test_backend_argument_overrides_settings(mocked_api):
    send_sms("8801712345678", "Hello", backend=LOCMEM)

    assert len(outbox) == 1
    assert not mocked_api.calls


def test_locmem_backend_needs_no_credentials():
    with override_settings(SSLWIRELESS_SMS={}):
        assert isinstance(get_backend(LOCMEM), LocmemBackend)


# --- console backend ------------------------------------------------------------------


def test_console_backend_writes_messages_to_stream():
    stream = io.StringIO()
    backend = ConsoleBackend(stream=stream)

    result = backend.send_dynamic_sms(
        [
            {"msisdn": "8801712345678", "text": "Hello John!", "csms_id": "DYN-001"},
            {"msisdn": "8801812345678", "text": "Hello Jane!", "csms_id": "DYN-002"},
        ]
    )

    output = stream.getvalue()
    assert "SMS (dynamic) to 8801712345678 [csms_id=DYN-001]\nHello John!" in output
    assert "SMS (dynamic) to 8801812345678 [csms_id=DYN-002]\nHello Jane!" in output
    assert len(result.smsinfo) == 2
    assert outbox == []
