"""Live tests against the real ISMS Plus API.

Deselected by default; run with ``pytest -m integration``. Tests that deliver
messages send real SMS (using credit) to SSLWIRELESS_SMS_TEST_MSISDN, and the machine's
IP must be whitelisted in the ISMS Plus portal:

    export SSLWIRELESS_SMS_API_TOKEN=... SSLWIRELESS_SMS_SID=... SSLWIRELESS_SMS_TEST_MSISDN=8801XXXXXXXXX
    export SSLWIRELESS_SMS_SECRET_KEY=...   # optional, enables the OTP test
    export SSLWIRELESS_SMS_BASE_URL=...     # optional, overrides the default API host
    uv run pytest -m integration
"""

import os

import pytest
from django.test import override_settings

import django_sslwireless_sms
from django_sslwireless_sms import AuthenticationError, SSLWirelessClient, StatusCode
from django_sslwireless_sms.client import DEFAULT_BASE_URL

pytestmark = pytest.mark.integration

API_TOKEN = os.environ.get("SSLWIRELESS_SMS_API_TOKEN", "")
SID = os.environ.get("SSLWIRELESS_SMS_SID", "")
MSISDN = os.environ.get("SSLWIRELESS_SMS_TEST_MSISDN", "")
SECRET_KEY = os.environ.get("SSLWIRELESS_SMS_SECRET_KEY", "")
BASE_URL = os.environ.get("SSLWIRELESS_SMS_BASE_URL") or DEFAULT_BASE_URL

needs_credentials = pytest.mark.skipif(
    not (API_TOKEN and SID and MSISDN),
    reason="set SSLWIRELESS_SMS_API_TOKEN, SSLWIRELESS_SMS_SID and SSLWIRELESS_SMS_TEST_MSISDN",
)
needs_secret_key = pytest.mark.skipif(
    not (API_TOKEN and SID and MSISDN and SECRET_KEY),
    reason="set SSLWIRELESS_SMS_SECRET_KEY and the other SSLWIRELESS_SMS_* variables",
)


@pytest.fixture
def client():
    return SSLWirelessClient(API_TOKEN, SID, secret_key=SECRET_KEY or None, base_url=BASE_URL)


def assert_delivered(result, count=1):
    assert result.ok, result
    assert len(result.succeeded) == count, result
    assert all(info.reference_id for info in result.succeeded)


def test_invalid_token_is_rejected():
    """Needs no credentials and cannot send anything."""
    client = SSLWirelessClient("invalid-token", "INVALIDSID", base_url=BASE_URL)

    with pytest.raises(AuthenticationError) as excinfo:
        client.send_sms("8801700000000", "django-sslwireless-sms integration probe")

    assert excinfo.value.status_code == StatusCode.UNAUTHORIZED


@needs_credentials
def test_send_sms_through_django_settings():
    settings = {"API_TOKEN": API_TOKEN, "SID": SID, "BASE_URL": BASE_URL}
    with override_settings(SSLWIRELESS_SMS=settings):
        result = django_sslwireless_sms.send_sms(
            MSISDN, "django-sslwireless-sms integration test: single"
        )

    assert_delivered(result)


@needs_credentials
def test_send_bulk_sms(client):
    assert_delivered(client.send_bulk_sms([MSISDN], "django-sslwireless-sms integration test: bulk"))


@needs_credentials
def test_send_dynamic_sms(client):
    result = client.send_dynamic_sms(
        [{"msisdn": MSISDN, "text": "django-sslwireless-sms integration test: dynamic"}]
    )
    assert_delivered(result)


@needs_secret_key
def test_send_otp(client):
    assert_delivered(client.send_otp(MSISDN, "django-sslwireless-sms integration test: OTP 123456"))
