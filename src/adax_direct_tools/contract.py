"""Contract check of an Adax heater's local API: a real heater and the test double must agree.

Asserts, for `stat`: HTTP 200, Content-Type application/json, a JSON object with EXACTLY the keys
currTemp, targTemp, energ, pow, every value an int. With writes allowed it also checks the
`set_target` rules observed on real heaters: always HTTP 200 with an empty body; 0 -> 0 (off);
0 < v < 500 and negatives -> 500; 550 -> 550; v > 3500 -> 3500; the original target is restored.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable

KEYS = {"currTemp", "targTemp", "energ", "pow"}
WRITES = ((0, 0), (400, 500), (100, 500), (-100, 500), (450, 500), (550, 550), (3600, 3500), (900, 900))

Get = Callable[..., tuple[int, str, bytes]]


class ContractError(Exception):
    """The heater broke a rule of the contract."""


def _check(ok: bool, message: str) -> None:
    if not ok:                      # not `assert`: `python -O` must not strip a check
        raise ContractError(message)


def _stat(get: Get) -> dict:
    code, ctype, body = get("stat")
    _check(code == 200, f"stat: HTTP {code}")
    _check((ctype or "").split(";")[0].strip() == "application/json", f"stat: content type {ctype!r}")
    try:
        d = json.loads(body)
    except ValueError:
        raise ContractError("stat: body is not JSON") from None
    _check(isinstance(d, dict) and set(d) == KEYS,
           f"stat: keys {sorted(d) if isinstance(d, dict) else d!r}, expected {sorted(KEYS)}")
    _check(all(type(v) is int for v in d.values()), f"stat: non-int value in {d}")
    return d


def _set_target(get: Get, value: int) -> None:
    code, _, body = get("set_target", value=value)
    _check(code == 200, f"set_target {value}: HTTP {code}")
    _check(body == b"", f"set_target {value}: body {body!r}, expected empty")


def run_contract(get: Get, allow_writes: bool, log: Callable[[str], None] = print, settle_s: float = 0.3) -> None:
    first = _stat(get)
    log(f"ok  stat: 200, application/json, keys {sorted(first)}, all int")
    if not allow_writes:
        return
    original = first["targTemp"]
    try:
        for sent, stored in WRITES:
            _set_target(get, sent)
            time.sleep(settle_s)
            got = _stat(get)["targTemp"]
            _check(got == stored, f"set_target {sent}: heater stores {got}, expected {stored}")
            log(f"ok  set_target {sent} -> stored {got}")
    finally:
        _set_target(get, original if original else 0)
        log(f"restored target {original}")
