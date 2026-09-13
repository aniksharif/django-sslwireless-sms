from django.apps import AppConfig


class SSLWirelessConfig(AppConfig):
    name = "django_sslwireless_sms"
    verbose_name = "SSL Wireless SMS"

    def ready(self) -> None:
        from . import checks  # noqa: F401  (registers system checks)
