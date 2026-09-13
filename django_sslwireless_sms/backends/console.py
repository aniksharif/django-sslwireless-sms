from __future__ import annotations

import sys
from typing import Any, TextIO

from .base import SentSMS, SimulatedBackend


class ConsoleBackend(SimulatedBackend):
    """Writes messages to a stream (stdout by default) instead of sending them. For development."""

    def __init__(self, *, stream: TextIO | None = None, **options: Any) -> None:
        super().__init__(**options)
        self.stream = stream or sys.stdout

    def deliver(self, messages: list[SentSMS]) -> None:
        for message in messages:
            self.stream.write(
                f"SMS ({message.kind}) to {message.msisdn} [csms_id={message.csms_id}]\n"
                f"{message.text}\n{'-' * 60}\n"
            )
        self.stream.flush()
