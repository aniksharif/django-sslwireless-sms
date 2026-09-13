import pytest
import responses

from django_sslwireless_sms import outbox


@pytest.fixture(autouse=True)
def empty_outbox():
    outbox.clear()
    yield outbox
    outbox.clear()


@pytest.fixture
def mocked_api():
    """Intercept all HTTP traffic; unregistered requests raise ConnectionError."""
    with responses.RequestsMock() as rsps:
        yield rsps
