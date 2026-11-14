"""Client for the local HTTPS API of an Adax heater.

GET https://<host>/api?command=stat&time=<unix>            -> JSON {currTemp, targTemp, energ, pow}
GET https://<host>/api?command=set_target&time=<unix>&value=<degC x 100>  -> 200, empty body
Header `Authorization: Basic <token>` (the token is sent verbatim, it is not base64 credentials).
Temperatures are degC x 100. The token never appears in a log line or an exception text.
"""

from __future__ import annotations

import json
import time
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT_S, TARGET_MAX, TARGET_MIN, TARGET_OFF


class AdaxDirectError(Exception):
    """The heater did not give a usable answer (timeout, connection, HTTP, body)."""


class AdaxDirectApi:
    """One heater."""

    def __init__(self, session: aiohttp.ClientSession | None, host: str, token: str) -> None:
        self._session = session
        self._url = f"https://{host}/api"          # port 443 unless `host` contains `:port`
        self._headers = {"Authorization": f"Basic {token}"}

    async def _get(self, params: dict[str, Any]) -> tuple[int, bytes]:
        assert self._session is not None
        try:
            async with self._session.get(
                self._url,
                params={**params, "time": int(time.time())},
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_S),
            ) as resp:
                return resp.status, await resp.read()
        except TimeoutError as err:
            raise AdaxDirectError("timeout") from err
        except (aiohttp.ClientError, OSError) as err:
            raise AdaxDirectError(f"connection error ({type(err).__name__})") from err

    async def async_stat(self) -> dict[str, int]:
        """Read the heater; raises AdaxDirectError on anything that is not a clean answer."""
        status, body = await self._get({"command": "stat"})
        if status != 200:
            raise AdaxDirectError(f"HTTP {status}")
        try:
            data = json.loads(body)
        except ValueError as err:
            raise AdaxDirectError("body is not JSON") from err
        if not isinstance(data, dict):
            raise AdaxDirectError("body is not a JSON object")
        for key in ("currTemp", "targTemp"):
            if type(data.get(key)) is not int:
                raise AdaxDirectError(f"{key} missing or not an int")
        return data

    async def async_set_target(self, value: int) -> None:
        """Write the target (degC x 100). Only 0 (off) or 500..3500 are ever sent (write guard)."""
        if value != TARGET_OFF and not TARGET_MIN <= value <= TARGET_MAX:
            raise ValueError(f"refusing to send target {value}: only 0 or {TARGET_MIN}..{TARGET_MAX}")
        status, _ = await self._get({"command": "set_target", "value": value})
        if status != 200:
            raise AdaxDirectError(f"HTTP {status}")

