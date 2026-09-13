from __future__ import annotations

from .base import SentSMS, SimulatedBackend

#: Messages captured by :class:`LocmemBackend`. Clear it between tests.
outbox: list[SentSMS] = []


class LocmemBackend(SimulatedBackend):
    """Stores messages in ``django_sslwireless_sms.outbox`` instead of sending them. For tests."""

    def deliver(self, messages: list[SentSMS]) -> None:
        outbox.extend(messages)
