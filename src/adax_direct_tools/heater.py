"""One Adax heater's local HTTPS API, over urllib (the heater's certificate is self-signed)."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request


class Heater:
    def __init__(self, host: str, token: str) -> None:
        self.host, self._token = host, token
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def get(self, command: str, **params) -> tuple[int, str, bytes]:
        """(status, content type, body); an HTTP error status is returned, not raised."""
        query = "&".join([f"command={command}", f"time={int(time.time())}"] + [f"{k}={v}" for k, v in params.items()])
        req = urllib.request.Request(f"https://{self.host}/api?{query}", headers={"Authorization": f"Basic {self._token}"})
        try:
            with urllib.request.urlopen(req, timeout=10, context=self._ctx) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type", ""), e.read()

    def stat(self) -> dict:
        return json.loads(self.get("stat")[2])

    def set_target(self, value: int) -> None:
        if value != 0 and not 500 <= value <= 3500:      # the heater stores 0 < v < 500 as 5 C and heats
            raise ValueError(f"refusing target {value}")
        self.get("set_target", value=value)
