# django-sslwireless-sms

Django integration for the [SSL Wireless ISMS Plus SMS API v3](https://ismsplus.sslwireless.com/api-documentation).

| Function           | Endpoint                 | Use for                                           |
| ------------------ | ------------------------ | ------------------------------------------------- |
| `send_sms`         | `POST /send-sms`         | One message to one recipient                      |
| `send_bulk_sms`    | `POST /send-sms/bulk`    | The same message to up to 100 recipients          |
| `send_dynamic_sms` | `POST /send-sms/dynamic` | Up to 100 different messages in one request       |
| `send_otp`         | `POST /secure/otp-sms`   | OTPs: AES-256-CBC encrypted body + `X-Signature`  |

Requires Python 3.10+ and Django 4.2+.

## Installation

```bash
pip install django-sslwireless-sms
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "django_sslwireless_sms",  # optional; enables system checks for the settings below
]

SSLWIRELESS_SMS = {
    "API_TOKEN": os.environ["SSLWIRELESS_SMS_API_TOKEN"],
    "SID": os.environ["SSLWIRELESS_SMS_SID"],
    "SECRET_KEY": os.environ.get("SSLWIRELESS_SMS_SECRET_KEY", ""),  # only needed for send_otp
    # Optional. Empty or unset uses https://smsplus.sslwireless.com/api/v3
    "BASE_URL": os.environ.get("SSLWIRELESS_SMS_BASE_URL", ""),
    "TIMEOUT": os.environ.get("SSLWIRELESS_SMS_TIMEOUT", 10),  # seconds
    # "BACKEND": "django_sslwireless_sms.backends.api.SSLWirelessBackend",  # default
}
```

The API only accepts requests from IPs whitelisted in the ISMS Plus portal.

## Usage

```python
from django_sslwireless_sms import send_sms, send_bulk_sms, send_dynamic_sms, send_otp

send_sms("8801712345678", "Your order has shipped", csms_id="order-1042")

send_bulk_sms(["8801712345678", "8801812345678"], "We are closed on Friday")

send_dynamic_sms([
    {"msisdn": "8801712345678", "text": "Hi John, your balance is 120 BDT"},
    {"msisdn": "8801812345678", "text": "Hi Jane, your balance is 80 BDT", "csms_id": "bal-2"},
])

send_otp("8801712345678", "Your login code is 482913")
```

`csms_id` is your unique reference for a message (at most 20 characters). If you leave it
out, a random one is generated. Batch size (100) and `csms_id` length are checked before
anything is sent, and violations raise `ValueError`.

### Results

Every call returns a `SendResult`:

```python
result = send_bulk_sms(numbers, "Hello")
result.status_code          # 200
for info in result.smsinfo:  # one SMSInfo per recipient
    info.msisdn, info.sms_status, info.csms_id, info.reference_id
result.failed               # recipients the API did not accept
result.raw                  # the decoded JSON
```

### Errors

When the API answers `"status": "FAILED"`, the call raises a subclass of `SSLWirelessAPIError`.
The error carries `.status_code`, `.error_message`, and the parsed `.result`.

| Exception               | Status codes                                             |
| ----------------------- | -------------------------------------------------------- |
| `AuthenticationError`   | 4001 unauthorized, 4002 SID not permitted, 4003 IP not whitelisted |
| `RateLimitError`        | 4029, 4031 TPS, 4033 too many OTPs to one recipient      |
| `SignatureError`        | 4034 can't decrypt SMS, 4035 signature mismatch          |
| `ServerError`           | 5000                                                     |
| `InvalidRequestError`   | Any other 4xxx (invalid MSISDN, duplicate `csms_id`, ...) |

The other errors are:
- `SSLWirelessConnectionError`: the API could not be reached.
- `SSLWirelessResponseError`: the API returned something other than a JSON result.

All of these errors inherit from `SSLWirelessError`. `StatusCode` lists every documented code.

```python
from django_sslwireless_sms import RateLimitError, SSLWirelessError, StatusCode, send_otp

try:
    send_otp(phone, f"Your code is {code}")
except RateLimitError:
    ...  # ask the user to wait
except SSLWirelessError:
    logger.exception("OTP delivery failed")
```

### Without Django settings

`SSLWirelessClient` has no Django dependency:

```python
from django_sslwireless_sms import SSLWirelessClient

client = SSLWirelessClient(api_token, sid, secret_key=secret_key, timeout=5)
client.send_sms("8801712345678", "Hello")
```

## Backends

Backends work like Django's email backends. Choose one with `SSLWIRELESS_SMS["BACKEND"]`, or pass
`backend="dotted.path"` to any `send_*` function.

| Backend                                                  | Behaviour                                                  |
| -------------------------------------------------------- | ---------------------------------------------------------- |
| `django_sslwireless_sms.backends.api.SSLWirelessBackend` | Sends through the API (default)                            |
| `django_sslwireless_sms.backends.locmem.LocmemBackend`   | Stores messages in `django_sslwireless_sms.outbox` instead |
| `django_sslwireless_sms.backends.console.ConsoleBackend` | Prints messages to stdout instead                          |

The simulated backends validate input the same way the API client does. They return a
successful `SendResult` and need no credentials.

### Testing your project

```python
import django_sslwireless_sms
from django.test import TestCase, override_settings


@override_settings(SSLWIRELESS_SMS={"BACKEND": "django_sslwireless_sms.backends.locmem.LocmemBackend"})
class SignupTests(TestCase):
    def setUp(self):
        django_sslwireless_sms.outbox.clear()

    def test_sends_otp(self):
        self.client.post("/signup/", {"phone": "8801712345678"})
        [sms] = django_sslwireless_sms.outbox
        assert sms.kind == "otp" and sms.msisdn == "8801712345678"
```

For local development, set `"BACKEND": "django_sslwireless_sms.backends.console.ConsoleBackend"`.

## Development

```bash
uv sync
uv run pytest                  # unit tests; HTTP is mocked, nothing leaves the machine
```

The unit tests mock HTTP with [`responses`](https://github.com/getsentry/responses) and check
request payloads against the API documentation. The OTP encryption and signature are compared
with known-answer vectors from the official Python and Node.js samples.

Integration tests call the real API and are deselected by default:

```bash
uv run pytest -m integration   # without credentials: only checks that a bad token is rejected

export SSLWIRELESS_SMS_API_TOKEN=... SSLWIRELESS_SMS_SID=... SSLWIRELESS_SMS_TEST_MSISDN=8801XXXXXXXXX
export SSLWIRELESS_SMS_SECRET_KEY=...  # optional, enables the OTP test
export SSLWIRELESS_SMS_BASE_URL=...    # optional, overrides the default API host
uv run pytest -m integration   # sends real SMS to SSLWIRELESS_SMS_TEST_MSISDN (uses credit)
```

Run the tests from a whitelisted IP.

## License

MIT. See [LICENSE](LICENSE).
