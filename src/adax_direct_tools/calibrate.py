"""Calibration logger: drive ONE locally-controlled Adax heater through target phases while logging its
local `stat` and a plug power meter from Home Assistant every 10 s. The CSV feeds `adax-direct fit`.

Phase syntax: <target>:<minutes>, comma-separated. Target "+100" = room temperature at phase start + 1 K, rounded to
a whole degree (the heater display shows whole degrees); "1600" = absolute degC x 100. Allowed range 500..3500.

Safety: the heater's ORIGINAL target is restored when the run ends, fails, or receives SIGINT/SIGTERM/SIGHUP. One
process runs all phases, so no second logger can outlive a phase. Reads only: the heater (stat + set_target) and ONE
Home Assistant state (GET /api/states/<plug>). Never prints the heater token or the Home Assistant token.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import signal
import sys
import time
import urllib.request
from pathlib import Path

from .heater import Heater
from .records import die, load_records, select_record

MAX_TOTAL_MINUTES = 180


def parse_phases(text: str) -> list[tuple[str, float]]:
    phases = []
    for part in text.split(","):
        try:
            tgt, mins = part.split(":")
            phases.append((tgt.strip(), float(mins)))
        except ValueError:
            die(f"bad phase {part!r}; expected <target>:<minutes>")
    if sum(m for _, m in phases) > MAX_TOTAL_MINUTES:
        die("more than 3 h of phases - split the run (safety limit)")
    return phases


def csv_name(name: str, now: dt.datetime) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "heater"
    return f"{slug}-{now.strftime('%Y%m%dT%H%MZ')}.csv"


def run(*, name: str, ha_url: str, ha_token_file: str, plug: str, phases_text: str, interval: float,
        out_dir: str, records_path: Path) -> int:
    phases = parse_phases(phases_text)
    try:
        ha_token = Path(ha_token_file).read_text().strip()
    except OSError as err:
        die(f"cannot read the Home Assistant token file ({type(err).__name__})")
    rec = select_record(load_records(records_path), name, None)
    heater = Heater(rec["ip_address"], rec["token"])
    base = ha_url.rstrip("/")
    original = heater.stat()["targTemp"]

    def restore(*_sig) -> None:
        try:
            heater.set_target(original)
            print(f"restored target {original}: {heater.stat()}", flush=True)
        except Exception as err:                           # noqa: BLE001 - report, never mask
            print(f"RESTORE FAILED ({type(err).__name__}): set target {original} by hand!", flush=True)
        if _sig:
            sys.exit(130)

    for s in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGHUP", None)):
        if s is not None:
            signal.signal(s, restore)

    def read_plug() -> tuple[str, str]:
        req = urllib.request.Request(f"{base}/api/states/{plug}", headers={"Authorization": "Bearer " + ha_token})
        st = json.load(urllib.request.urlopen(req, timeout=10))
        return st["state"], st.get("last_reported") or st["last_updated"]

    out = Path(out_dir)
    os.makedirs(out, exist_ok=True)
    path = out / csv_name(name, dt.datetime.now(dt.timezone.utc))
    print(f"log {path}; {name} original target {original}", flush=True)
    try:
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["utc", "phase", "currTemp", "targTemp", "pow", "energ", "plug_W", "plug_reported"])
            for i, (tgt, mins) in enumerate(phases, 1):
                room = heater.stat()["currTemp"]
                target = round((room + int(tgt[1:])) / 100) * 100 if tgt.startswith("+") else int(tgt)
                target = max(500, min(3500, target))
                heater.set_target(target)
                print(f"phase {i}: room {room} -> target {target} for {mins:g} min", flush=True)
                end = time.time() + mins * 60
                while time.time() < end:
                    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                    try:
                        s = heater.stat()
                    except Exception as err:               # noqa: BLE001 - log the gap, keep going
                        s = {}
                        print(f"{now} heater error {type(err).__name__}", flush=True)
                    try:
                        pw, rep = read_plug()
                    except Exception as err:               # noqa: BLE001
                        pw, rep = "", ""
                        print(f"{now} plug error {type(err).__name__}", flush=True)
                    w.writerow([now, i, s.get("currTemp"), s.get("targTemp"), s.get("pow"), s.get("energ"), pw, rep])
                    fh.flush()
                    time.sleep(interval)
    finally:
        restore()
    print(f"next: adax-direct fit {path}", flush=True)
    return 0
