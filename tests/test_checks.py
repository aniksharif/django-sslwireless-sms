from django.core import checks
from django.test import override_settings

from django_sslwireless_sms.checks import check_sslwireless_sms_settings


def test_valid_settings_pass():
    assert check_sslwireless_sms_settings() == []


@override_settings(SSLWIRELESS_SMS={})
def test_missing_credentials_are_reported():
    errors = check_sslwireless_sms_settings()

    assert [error.id for error in errors] == ["django_sslwireless_sms.E002", "django_sslwireless_sms.E002"]
    assert "API_TOKEN" in errors[0].msg
    assert "SID" in errors[1].msg


@override_settings(SSLWIRELESS_SMS={"BACKEND": "myproject.sms.MissingBackend"})
def test_unimportable_backend_is_reported():
    assert [error.id for error in check_sslwireless_sms_settings()] == ["django_sslwireless_sms.E001"]


@override_settings(SSLWIRELESS_SMS={"BACKEND": "django_sslwireless_sms.backends.locmem.LocmemBackend"})
def test_simulated_backends_need_no_credentials():
    assert check_sslwireless_sms_settings() == []


@override_settings(SSLWIRELESS_SMS={})
def test_check_is_registered_with_django():
    assert "django_sslwireless_sms.E002" in {message.id for message in checks.run_checks()}
