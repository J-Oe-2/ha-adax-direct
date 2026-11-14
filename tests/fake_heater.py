"""Test double of an Adax heater's local HTTPS API, as a pure class (no server, no sockets).

Behaviour is what was observed on real Gen2 and Gen3 heaters:
  command=stat                  -> 200 application/json, EXACTLY {"currTemp":..,"targTemp":..,"energ":0,"pow":0}
  command=set_target&value=<x100> -> 200, EMPTY body; stored: 0 -> 0 (off), 0 < v < 500 and negatives -> 500,
                                     v > 3500 -> 3500, else v
Modes (apply to every command): ok, timeout (raises TimeoutError), http500, garbage (200 with a non-JSON body).
Every set_target value received is appended to `log`, before the mode is looked at.
"""
from __future__ import annotations

import json

TOKEN = "test-token-0123456789"


class FakeHeater:
    def __init__(self) -> None:
        self.mode = "ok"
        self.currTemp = 1632
        self.targTemp = 900
        self.log: list[int] = []

    def clamp(self, value: int) -> int:
        if value == 0:
            return 0
        if value < 500:
            return 500
        return min(value, 3500)

    def handle(self, command: str, value: int | str | None = None) -> tuple[int, str | None, bytes]:
        """Answer one request as (status, content_type, body)."""
        if command == "set_target":
            try:
                self.log.append(int(value))
            except (TypeError, ValueError):
                return 400, None, b""
        if self.mode == "timeout":
            raise TimeoutError("the heater did not answer")
        if self.mode == "http500":
            return 500, None, b""
        if self.mode == "garbage":
            return 200, "text/html", b"<html>not json</html>"
        if command == "stat":
            body = {"currTemp": self.currTemp, "targTemp": self.targTemp, "energ": 0, "pow": 0}
            return 200, "application/json", json.dumps(body, separators=(",", ":")).encode()
        if command == "set_target":
            self.targTemp = self.clamp(self.log[-1])
            return 200, None, b""
        return 400, None, b""
