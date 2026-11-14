"""Bluetooth side of the setup tool: scan for heaters, and put ONE heater on your Wi-Fi.

Speaks the same BLE protocol as Home Assistant's own Adax local config flow, by calling the same
library call (adax_local.AdaxConfig(ssid, pswd).configure_device(), Adax-local==0.3.0), but from
this computer instead of the Home Assistant host.
"""
from __future__ import annotations

import getpass
import json
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

# Adax-local 0.3.0 calls urllib.parse.quote() after only `import urllib`; inside Home Assistant some
# other module has imported urllib.parse already, standalone it raises AttributeError
# (hit on the first real heater). Importing it here makes the submodule present.
import urllib.parse  # noqa: F401

from .records import append_record, die, load_records


def decode_adv(adv) -> dict:
    """Decode the manufacturer data as adax_local.scan_for_available_ble_device does."""
    import adax_local

    md = adv.manufacturer_data
    if not md:
        return {"decoded": False}
    first = next(iter(md))
    lst = [first % 256, first // 256] + list(md[first])
    status = lst[1]
    return {
        "decoded": True,
        "type_id": lst[0],
        "is_heater": lst[0] in adax_local.ADAX_DEVICE_TYPE_HEATER_BLE,
        "registered": bool(status & 1),
        "managed": bool(status & 2),
        "mac_id": adax_local.find_mac_id(lst) if len(lst) >= 10 else 0,
        "len": len(lst),
    }


async def scan(seconds: float) -> int:
    import adax_local
    import bleak

    print(f"scanning {seconds:.0f} s for BLE devices advertising the Adax service "
          f"{adax_local.UUID_ADAX_BLE_SERVICE} ... (nothing is configured, nothing is connected)")
    found = await bleak.BleakScanner.discover(timeout=seconds, return_adv=True)
    rows = []
    for dev, adv in found.values():
        if adax_local.UUID_ADAX_BLE_SERVICE in (adv.service_uuids or []):
            rows.append((dev, adv, decode_adv(adv)))
    print(f"{len(found)} BLE devices seen, {len(rows)} Adax.")
    if not rows:
        print("No Adax heater advertising. A heater only advertises after the reset steps in the "
              "README (press + and OK until 'Reset', then hold OK until the blue LED blinks).")
        return 1
    rows.sort(key=lambda r: -(r[1].rssi if r[1].rssi is not None else -999))
    print(f"{'name':<22} {'address (UUID on macOS)':<38} {'RSSI':>5}  type  reg  mgd  mac_id(adax)   verdict")
    for dev, adv, d in rows:
        if not d["decoded"]:
            verdict = "no manufacturer data"
            tail = "-    -    -    -"
        else:
            avail = d["is_heater"] and not d["registered"] and not d["managed"] and bool(d["mac_id"])
            verdict = "AVAILABLE for setup" if avail else "NOT available (already registered/managed - reset it)"
            tail = f"{d['type_id']:<5} {int(d['registered']):<4} {int(d['managed']):<4} {d['mac_id']}"
        print(f"{(dev.name or '?'):<22} {dev.address:<38} {adv.rssi!s:>5}  {tail}  {verdict}")
    print("\nNote: configure_device() takes the FIRST Adax device it sees; if that one is not "
          "available it aborts with 'heater not available'. Keep only the target close.")
    return 0


def read_wifi(path: Path) -> tuple[str, str]:
    if not path.is_file():
        die(f"{path} missing. Create it (chmod 600) as JSON: "
            '{"ssid": "<2.4 GHz network name>", "password": "<wifi password>"}')
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        print(f"WARNING: {path.name} is readable by group/others (mode {oct(mode)}); run chmod 600.",
              file=sys.stderr)
    try:
        d = json.loads(path.read_text())
        ssid, pw = d["ssid"], d["password"]
    except (ValueError, KeyError, TypeError):
        die(f'{path.name} must be a JSON object with keys "ssid" and "password"')
    if not isinstance(ssid, str) or not isinstance(pw, str) or not ssid or not pw:
        die(f"{path.name}: ssid and password must be non-empty strings")
    return ssid, pw


def wifi_credentials(ssid: str | None, wifi_file: str | None) -> tuple[str, str]:
    """(ssid, password): from --wifi-file, else --ssid plus a hidden prompt. A given --ssid wins."""
    if wifi_file:
        file_ssid, pw = read_wifi(Path(wifi_file))
        return ssid or file_ssid, pw
    if not ssid:
        die("give --ssid, or --wifi-file with the network name and password")
    pw = getpass.getpass(f"Wi-Fi password for {ssid}: ")
    if not pw:
        die("no Wi-Fi password given")
    return ssid, pw


async def configure(name: str, ssid: str, password: str, records_path: Path) -> int:
    import adax_local

    if records_path.is_file() and any(h.get("name") == name for h in load_records(records_path)):
        print(f"NOTE: {name!r} already has a record in {records_path.name}; the new one is appended "
              "(the older record is kept; the NEWEST is the valid one).")

    print("\nBefore continuing, on the heater: press + and OK together until the display shows "
          "'Reset', then press and hold OK until the blue LED blinks.")
    print("Keep this computer within about 1-2 m of ONLY this heater. This can take several minutes.")
    input("Press Enter when the blue LED is blinking ... ")

    # configure_device() discards the BLE address; wrap the module-level scan to keep it.
    seen: dict = {}
    orig_scan = adax_local.scan_for_available_ble_device

    async def recording_scan(*a, **kw):
        dev, mac_id = await orig_scan(*a, **kw)
        seen["address"], seen["name"] = dev.address, dev.name
        return dev, mac_id

    adax_local.scan_for_available_ble_device = recording_scan
    try:
        cfg = adax_local.AdaxConfig(ssid, password)
        try:
            ok = await cfg.configure_device()
        except adax_local.HeaterNotAvailable:
            die("heater not available: the nearest Adax device is already registered/managed. "
                "Repeat the reset steps (and run `adax-direct scan` to see the flags).", 3)
        except adax_local.HeaterNotFound:
            die("no Adax heater found (2 scans of 60 s). Redo the reset steps; on macOS check the Bluetooth "
                "permission for this terminal app (System Settings > Privacy & Security > Bluetooth).", 3)
        except adax_local.InvalidWifiCred:
            die("the heater rejected the Wi-Fi credentials", 3)
    finally:
        adax_local.scan_for_available_ble_device = orig_scan
    if not ok:
        die("no IP reported by the heater within 20 s (wrong Wi-Fi password, 5 GHz-only network, "
            "or out of Wi-Fi range?). The heater is NOT configured; no record written.", 3)

    rec = {
        "name": name,
        "unique_id": str(cfg.mac_id),        # = what Home Assistant's own config flow stores as unique_id
        "mac_id_hex": f"{cfg.mac_id:016x}",
        "ble_address": seen.get("address"),   # UUID on macOS, MAC on Linux - NOT the adax mac_id
        "ip_address": cfg.device_ip,
        "token": cfg.access_token,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    append_record(records_path, rec)
    print(f"\nconfigured {name}: ip={rec['ip_address']} unique_id={rec['unique_id']} "
          f"token=<{len(rec['token'])} chars, stored, not shown>")
    print(f"record appended to {records_path} (mode 600)")
    return 0
