"""Create the `adax_direct` config entry of ONE heater in Home Assistant, from its setup record.

Runs the REST config flow of the integration: host = the record's IP (or --host-override), token,
device_id = the record's unique_id, name, rated power. Prints the entry id and title - never a token.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .ha import Ha
from .records import die, load_records, select_record

HANDLER = "adax_direct"
MIN_RATED_POWER_W, MAX_RATED_POWER_W = 100, 3000


def run(*, name: str | None, device_id: str | None, rated_power: int, ha_url: str, ha_token_file: str,
        host_override: str | None, records_path: Path) -> int:
    if not MIN_RATED_POWER_W <= rated_power <= MAX_RATED_POWER_W:
        die(f"--rated-power must be {MIN_RATED_POWER_W}..{MAX_RATED_POWER_W} W, got {rated_power}")
    if (name is None) == (device_id is None):
        die("give exactly one of --name and --device-id")
    rec = select_record(load_records(records_path), name, device_id)
    try:
        ha_token = Path(ha_token_file).read_text().strip()
    except OSError as err:
        die(f"cannot read the Home Assistant token file ({type(err).__name__})")
    if not ha_token:
        die("the Home Assistant token file is empty")

    ha = Ha(ha_url, ha_token)
    try:
        code, flow = ha.req("POST", "/api/config/config_entries/flow", {"handler": HANDLER})
        if code != 200 or not isinstance(flow, dict) or flow.get("type") != "form":
            print(f"flow did not start: HTTP {code}")
            return 1
        user_input = {
            "host": host_override or rec["ip_address"],
            "token": rec["token"],
            "device_id": str(rec["unique_id"]),
            "name": rec.get("name") if name is None else name,
            "rated_power_w": rated_power,
        }
        code, res = ha.req("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", user_input)
        if code == 200 and isinstance(res, dict) and res.get("type") == "create_entry":
            result = res.get("result")
            entry_id = result.get("entry_id") if isinstance(result, dict) else result
            print(f"entry_id: {entry_id}")
            print(f"title: {res.get('title')}")
            return 0
        if code == 200 and isinstance(res, dict) and res.get("type") == "abort":
            print(f"abort: {res.get('reason')}")
        elif code == 200 and isinstance(res, dict) and res.get("type") == "form":
            print(f"error: {', '.join(res.get('errors', {}).values()) or 'form re-shown'}")
            ha.req("DELETE", f"/api/config/config_entries/flow/{res['flow_id']}")
        else:
            print(f"error: HTTP {code}")
    except OSError as err:
        print(f"error: cannot reach Home Assistant ({type(err).__name__})", file=sys.stderr)
    return 1
