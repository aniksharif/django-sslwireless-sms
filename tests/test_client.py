"""Unit tests for SSLWirelessClient against a mocked HTTP layer.

Response bodies follow the samples in the ISMS Plus API documentation.
"""

import json

import pytest
import requests
from responses import matchers

from django_sslwireless_sms import (
    AuthenticationError,
    InvalidRequestError,
    RateLimitError,
    ServerError,
    SignatureError,
    SSLWirelessAPIError,
    SSLWirelessClient,
    SSLWirelessConnectionError,
    SSLWirelessResponseError,
    StatusCode,
    crypto,
)
from django_sslwireless_sms.client import DEFAULT_BASE_URL

API_TOKEN = "test-api-token"
SID = "TESTSID"
SECRET_KEY = "test-secret"


def sms_info(msisdn, csms_id, status="SUCCESS", message="Success"):
    return {
        "sms_status": status,
        "status_message": message,
        "msisdn": msisdn,
        "sms_type": "EN",
        "csms_id": csms_id,
        "reference_id": "5da2f0b5ba3a2248110",
    }


def success_body(*infos):
    return {"status": "SUCCESS", "status_code": 200, "error_message": "", "smsinfo": list(infos)}


def failure_body(code, message, *infos):
    return {"status": "FAILED", "status_code": code, "error_message": message, "smsinfo": list(infos)}


def sent_json(mocked_api, index=0):
    return json.loads(mocked_api.calls[index].request.body)


@pytest.fixture
def client():
    return SSLWirelessClient(API_TOKEN, SID, secret_key=SECRET_KEY)


# --- single SMS -----------------------------------------------------------------------


def test_send_sms_posts_documented_payload(client, mocked_api):
    mocked_api.post(
        f"{DEFAULT_BASE_URL}/send-sms",
        match=[
            matchers.json_params_matcher(
                {
                    "api_token": API_TOKEN,
                    "sid": SID,
                    "msisdn": "8801712345678",
                    "sms": "Hello",
                    "csms_id": "order-42",
                }
            )
        ],
        json=success_body(sms_info("8801712345678", "order-42")),
    )

    result = client.send_sms("8801712345678", "Hello", csms_id="order-42")

    assert result.ok
    assert result.status_code == StatusCode.SUCCESS
    assert result.smsinfo[0].ok
    assert result.smsinfo[0].csms_id == "order-42"
    assert result.smsinfo[0].reference_id == "5da2f0b5ba3a2248110"
    assert result.raw["status"] == "SUCCESS"
    headers = mocked_api.calls[0].request.headers
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


def test_send_sms_generates_unique_csms_ids_and_stringifies_msisdn(client, mocked_api):
    mocked_api.post(f"{DEFAULT_BASE_URL}/send-sms", json=success_body())

    client.send_sms(8801712345678, "Hello")
    client.send_sms(8801712345678, "Hello")

    first, second = sent_json(mocked_api, 0), sent_json(mocked_api, 1)
    assert first["msisdn"] == "8801712345678"
    assert len(first["csms_id"]) == 20 and first["csms_id"].isalnum()
    assert first["csms_id"] != second["csms_id"]


@pytest.mark.parametrize("csms_id", ["", "x" * 21])
def test_invalid_csms_id_is_rejected_before_sending(client, mocked_api, csms_id):
    with pytest.raises(ValueError, match="csms_id"):
        client.send_sms("8801712345678", "Hello", csms_id=csms_id)
    assert not mocked_api.calls


def test_custom_base_url_and_timeout(mocked_api):
    client = SSLWirelessClient(API_TOKEN, SID, base_url="https://sms.example.test/api/v3/", timeout=3)
    mocked_api.post("https://sms.example.test/api/v3/send-sms", json=success_body())

    client.send_sms("8801712345678", "Hello")

    assert mocked_api.calls[0].request.req_kwargs["timeout"] == 3


# --- bulk SMS -------------------------------------------------------------------------


def test_send_bulk_sms_posts_documented_payload(client, mocked_api):
    msisdns = ["8801712345678", "8801812345678"]
    mocked_api.post(
        f"{DEFAULT_BASE_URL}/send-sms/bulk",
        match=[
            matchers.json_params_matcher(
                {
                    "api_token": API_TOKEN,
                    "sid": SID,
                    "msisdn": msisdns,
                    "sms": "Sale starts today",
                    "batch_csms_id": "batch-1",
                }
            )
        ],
        json=success_body(*(sms_info(m, f"batch-1-{i}") for i, m in enumerate(msisdns))),
    )

    result = client.send_bulk_sms(msisdns, "Sale starts today", batch_csms_id="batch-1")

    assert [info.msisdn for info in result.succeeded] == msisdns
    assert result.failed == ()


def test_bulk_result_exposes_rejected_recipients(client, mocked_api):
    mocked_api.post(
        f"{DEFAULT_BASE_URL}/send-sms/bulk",
        json=success_body(
            sms_info("8801712345678", "a"),
            sms_info("880123", "b", status="INVALID", message="Invalid MSISDN"),
        ),
    )

    result = client.send_bulk_sms(["8801712345678", "880123"], "Hi")

    assert result.ok
    assert [info.msisdn for info in result.succeeded] == ["8801712345678"]
    assert [(info.msisdn, info.status_message) for info in result.failed] == [("880123", "Invalid MSISDN")]


@pytest.mark.parametrize(
    ("msisdns", "message"),
    [([], "must not be empty"), ([f"88017{i:08d}" for i in range(101)], "at most 100")],
)
def test_bulk_batch_size_is_validated_before_sending(client, mocked_api, msisdns, message):
    with pytest.raises(ValueError, match=message):
        client.send_bulk_sms(msisdns, "Hi")
    assert not mocked_api.calls


# --- dynamic SMS ----------------------------------------------------------------------


def test_send_dynamic_sms_posts_documented_payload(client, mocked_api):
    mocked_api.post(f"{DEFAULT_BASE_URL}/send-sms/dynamic", json=success_body())

    client.send_dynamic_sms(
        [
            {"msisdn": "8801712345678", "text": "Hello John!", "csms_id": "DYN-001"},
            {"msisdn": 8801812345678, "text": "Hello Jane!"},
        ]
    )

    body = sent_json(mocked_api)
    assert body["api_token"] == API_TOKEN
    assert body["sid"] == SID
    assert body["sms"][0] == {"msisdn": "8801712345678", "text": "Hello John!", "csms_id": "DYN-001"}
    assert body["sms"][1]["msisdn"] == "8801812345678"
    assert body["sms"][1]["text"] == "Hello Jane!"
    assert len(body["sms"][1]["csms_id"]) == 20


@pytest.mark.parametrize(
    ("messages", "error"),
    [
        ([{"msisdn": "8801712345678"}], "missing \\['text'\\]"),
        ([], "must not be empty"),
        ([{"msisdn": "8801712345678", "text": "x"}] * 101, "at most 100"),
    ],
)
def test_dynamic_messages_are_validated_before_sending(client, mocked_api, messages, error):
    with pytest.raises(ValueError, match=error):
        client.send_dynamic_sms(messages)
    assert not mocked_api.calls


# --- secure OTP -----------------------------------------------------------------------


def test_send_otp_encrypts_body_and_signs_request(client, mocked_api):
    mocked_api.post(
        f"{DEFAULT_BASE_URL}/secure/otp-sms",
        json=success_body(sms_info("8801712345678", "otp-1")),
    )

    result = client.send_otp("8801712345678", "Your OTP is 123456", csms_id="otp-1")

    assert result.ok
    request = mocked_api.calls[0].request
    body = json.loads(request.body)
    assert "Your OTP is" not in request.body.decode()
    assert crypto.decrypt_sms(body["sms"], SECRET_KEY) == "Your OTP is 123456"
    assert body["api_token"] == API_TOKEN
    expected_signature = crypto.sign(
        {"csms_id": "otp-1", "msisdn": "8801712345678", "sid": SID, "sms": body["sms"]},
        SECRET_KEY,
    )
    assert request.headers["X-Signature"] == expected_signature


def test_send_otp_requires_secret_key(mocked_api):
    client = SSLWirelessClient(API_TOKEN, SID)
    with pytest.raises(ValueError, match="secret_key"):
        client.send_otp("8801712345678", "Your OTP is 123456")
    assert not mocked_api.calls


# --- failures -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "error_class"),
    [
        (4001, AuthenticationError),
        (4002, AuthenticationError),
        (4003, AuthenticationError),
        (4022, InvalidRequestError),
        (4023, InvalidRequestError),
        (4025, InvalidRequestError),
        (4028, InvalidRequestError),
        (4030, InvalidRequestError),
        (4029, RateLimitError),
        (4031, RateLimitError),
        (4033, RateLimitError),
        (4034, SignatureError),
        (4035, SignatureError),
        (5000, ServerError),
        (6001, SSLWirelessAPIError),
    ],
)
def test_failed_status_raises_specific_error(client, mocked_api, code, error_class):
    mocked_api.post(
        f"{DEFAULT_BASE_URL}/send-sms",
        json=failure_body(
            code, "Invalid MSISDN", sms_info("880123", "x", status="INVALID", message="Invalid MSISDN")
        ),
    )

    with pytest.raises(SSLWirelessAPIError) as excinfo:
        client.send_sms("880123", "Hello", csms_id="x")

    assert type(excinfo.value) is error_class
    assert excinfo.value.status_code == code
    assert excinfo.value.error_message == "Invalid MSISDN"
    assert excinfo.value.result.smsinfo[0].sms_status == "INVALID"
    assert str(excinfo.value) == f"[{code}] Invalid MSISDN"


def test_failed_response_without_smsinfo(client, mocked_api):
    # Shape returned by the live API for an invalid token.
    mocked_api.post(
        f"{DEFAULT_BASE_URL}/send-sms",
        json={"status": "FAILED", "status_code": 4001, "error_message": "Unauthorized"},
    )

    with pytest.raises(AuthenticationError, match=r"^\[4001\] Unauthorized$") as excinfo:
        client.send_sms("8801712345678", "Hello")

    assert excinfo.value.result.smsinfo == ()


def test_failed_status_with_http_error_code_is_still_parsed(client, mocked_api):
    mocked_api.post(
        f"{DEFAULT_BASE_URL}/secure/otp-sms",
        status=401,
        json={"status": "FAILED", "error_message": "Client signature mismatch", "status_code": 4035, "smsinfo": []},
    )

    with pytest.raises(SignatureError) as excinfo:
        client.send_otp("8801712345678", "Your OTP is 123456")

    assert excinfo.value.result.smsinfo == ()


def test_network_failure_raises_connection_error_without_leaking_token(client, mocked_api):
    mocked_api.post(f"{DEFAULT_BASE_URL}/send-sms", body=requests.ConnectTimeout("timed out"))

    with pytest.raises(SSLWirelessConnectionError) as excinfo:
        client.send_sms("8801712345678", "Hello")

    assert API_TOKEN not in str(excinfo.value)


@pytest.mark.parametrize(
    ("status", "body"),
    [(502, "<html>Bad Gateway</html>"), (200, json.dumps({"message": "Server Error"})), (200, "[]")],
)
def test_unrecognised_response_raises_response_error(client, mocked_api, status, body):
    mocked_api.post(f"{DEFAULT_BASE_URL}/send-sms", status=status, body=body)

    with pytest.raises(SSLWirelessResponseError) as excinfo:
        client.send_sms("8801712345678", "Hello")

    assert excinfo.value.http_status == status
    assert excinfo.value.body == body
