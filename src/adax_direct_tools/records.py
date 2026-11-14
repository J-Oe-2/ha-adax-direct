"""The record file: what `adax-direct pair` learns about each heater, kept append-only.

Default `$XDG_CONFIG_HOME/adax-direct/heaters.json`, else `~/.config/adax-direct/heaters.json`.
Shape `{"heaters": [{name, unique_id, mac_id_hex, ble_address, ip_address, token, timestamp}]}`.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def default_records_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")   # XDG_CONFIG_HOME is the only environment variable the tool reads
    root = Path(base) if base else Path.home() / ".config"
    return root / "adax-direct" / "heaters.json"


def load_records(path: Path) -> list[dict]:
    try:
        records = json.loads(path.read_text())["heaters"]
        assert isinstance(records, list)
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        die(f"cannot read heater records from {path}")
    return records


def append_record(path: Path, rec: dict) -> None:
    """Append rec to {"heaters": [...]} atomically, mode 600. Never drops an old record."""
    data: dict = {"heaters": []}
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            assert isinstance(data["heaters"], list)
        except (ValueError, KeyError, TypeError, AssertionError):
            die(f"{path} exists but is not {{\"heaters\": [...]}} - refusing to overwrite it")
    data["heaters"].append(rec)
    os.makedirs(path.parent, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".heaters.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            try:
                os.fchmod(f.fileno(), 0o600)       # best effort: Windows has no fchmod
            except (AttributeError, OSError):
                pass
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def select_record(records: list[dict], name: str | None, device_id: str | None) -> dict:
    """The newest record with this unique_id (`device_id`), else the newest with this name."""
    if device_id is not None:
        hits = [r for r in records if str(r.get("unique_id")) == device_id]
        if not hits:
            die(f"no record with unique_id {device_id}")
    else:
        hits = [r for r in records if r.get("name") == name]
        if not hits:
            die(f"no record named {name!r}")
    return max(hits, key=lambda r: r["timestamp"])
