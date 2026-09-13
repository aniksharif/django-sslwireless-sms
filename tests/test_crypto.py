"""Compatibility tests for the secure OTP encryption and signature.

The expected values were produced by running the official Python (pycryptodome)
and Node.js samples from the ISMS Plus documentation with the IV pinned to
``bytes(range(16))``. Both samples produced identical output.
"""

import pytest

from django_sslwireless_sms import crypto

SECRET_KEY = "test-secret"
FIXED_IV = bytes(range(16))
FIELDS = {"sid": "TESTSID", "msisdn": "8801712345678", "csms_id": "SSIG-ID-001"}

OFFICIAL_VECTORS = [
    pytest.param(
        "Your OTP is 123456",
        "AAECAwQFBgcICQoLDA0OD1o0Q0dIOVhQbE1ERTlaclNjNGpCVE54eUQ3SEZLdkhGYm5hZ3QxaThVeFk9",
        "4454fd0a393518b8c36a2b638be9b853559a7fa3a93e3686f78f8b1c328b2275",
        id="english",
    ),
    pytest.param(
        "আপনার ওটিপি কোড 123456",
        "AAECAwQFBgcICQoLDA0OD1lvckszVHdaVENOODdpamNuRkhHRWJOSnQ3bUN0MG5mZ1RJeU9qV3pienMzdjRu"
        "OEFaRmVsZi9uSzh2ZG8wVjZuazdGVzRnNzlCRFJ6em05R1ZNV3J3PT0=",
        "976bd2e2800c0fecb670ff8c3288622d3c8215eca8cbdfbe2ac48c64ae8a384c",
        id="bangla",
    ),
]


@pytest.mark.parametrize(("text", "encrypted", "signature"), OFFICIAL_VECTORS)
def test_encrypt_sms_matches_official_samples(text, encrypted, signature):
    assert crypto.encrypt_sms(text, SECRET_KEY, iv=FIXED_IV) == encrypted


@pytest.mark.parametrize(("text", "encrypted", "signature"), OFFICIAL_VECTORS)
def test_sign_matches_official_samples(text, encrypted, signature):
    assert crypto.sign({**FIELDS, "sms": encrypted}, SECRET_KEY) == signature


@pytest.mark.parametrize(("text", "encrypted", "signature"), OFFICIAL_VECTORS)
def test_decrypt_sms_recovers_plaintext(text, encrypted, signature):
    assert crypto.decrypt_sms(encrypted, SECRET_KEY) == text


def test_sign_is_independent_of_field_order():
    fields = {**FIELDS, "sms": "abc+/="}
    assert crypto.sign(fields, SECRET_KEY) == crypto.sign(dict(reversed(fields.items())), SECRET_KEY)


def test_encrypt_sms_uses_a_fresh_iv_each_time():
    first = crypto.encrypt_sms("123456", SECRET_KEY)
    second = crypto.encrypt_sms("123456", SECRET_KEY)
    assert first != second
    assert crypto.decrypt_sms(first, SECRET_KEY) == crypto.decrypt_sms(second, SECRET_KEY) == "123456"


def test_decrypt_with_wrong_secret_key_fails():
    encrypted = crypto.encrypt_sms("Your OTP is 123456", SECRET_KEY, iv=FIXED_IV)
    with pytest.raises(ValueError):
        crypto.decrypt_sms(encrypted, "another-secret")


def test_encrypt_sms_rejects_bad_iv_length():
    with pytest.raises(ValueError, match="16 bytes"):
        crypto.encrypt_sms("x", SECRET_KEY, iv=b"short")
