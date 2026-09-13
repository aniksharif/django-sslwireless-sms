"""Encryption and request signing for the ``secure/otp-sms`` endpoint.

The server expects exactly what PHP's ``openssl_encrypt`` produces, which has
two quirks this module reproduces (see the official samples):

* The AES-256 key is the first 32 *characters* of the hex SHA-256 digest of
  the secret key, used as ASCII bytes.
* ``openssl_encrypt`` returns base64 ciphertext, so the final value is
  ``base64(raw_iv + base64(ciphertext))``.

The ``X-Signature`` header is the lowercase hex HMAC-SHA256 (keyed with the raw
secret key) of the alphabetically sorted, URL-encoded fields.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from collections.abc import Mapping
from urllib.parse import urlencode

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

IV_SIZE = 16


def _derive_key(secret_key: str) -> bytes:
    return hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:32].encode("ascii")


def encrypt_sms(text: str, secret_key: str, *, iv: bytes | None = None) -> str:
    """Encrypt an SMS body for the secure OTP endpoint.

    ``iv`` defaults to 16 random bytes; pass one only for deterministic tests.
    """
    if iv is None:
        iv = os.urandom(IV_SIZE)
    elif len(iv) != IV_SIZE:
        raise ValueError(f"iv must be {IV_SIZE} bytes, got {len(iv)}")

    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(text.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(_derive_key(secret_key)), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + base64.b64encode(ciphertext)).decode("ascii")


def decrypt_sms(payload: str, secret_key: str) -> str:
    """Reverse :func:`encrypt_sms` (what the server does on receipt)."""
    raw = base64.b64decode(payload)
    iv, ciphertext = raw[:IV_SIZE], base64.b64decode(raw[IV_SIZE:])
    decryptor = Cipher(algorithms.AES(_derive_key(secret_key)), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


def sign(fields: Mapping[str, str], secret_key: str) -> str:
    """Return the ``X-Signature`` value for ``fields`` (csms_id, msisdn, sid, sms)."""
    canonical = urlencode(sorted(fields.items()))
    return hmac.new(secret_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
