"""The `adax-direct` command: pair Adax heaters from this computer's Bluetooth, add them to Home Assistant,
check them, and calibrate the energy model.

Exit codes: 0 success, 1 operation failed, 2 usage or input error, 3 heater or Bluetooth failure.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import __version__
from .records import default_records_path, die, load_records, select_record

RECORDS_HELP = "record file (default $XDG_CONFIG_HOME/adax-direct/heaters.json, else ~/.config/adax-direct/heaters.json)"


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="adax-direct", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"adax-direct {__version__}")
    sub = ap.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def command(name: str, help_: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_, description=help_)

    p = command("scan", "scan for Adax heaters over Bluetooth and say which can be set up (changes nothing)")
    p.add_argument("--seconds", type=float, default=15.0, help="scan duration (default 15)")

    p = command("pair", "put ONE heater on your Wi-Fi over Bluetooth and store its address and token")
    p.add_argument("--name", required=True, help='your name for the heater, e.g. "Living room"')
    p.add_argument("--ssid", help="Wi-Fi network name (2.4 GHz)")
    p.add_argument("--wifi-file", help='JSON file {"ssid": ..., "password": ...}; without it the password is asked')
    p.add_argument("--records", help=RECORDS_HELP)

    p = command("list", "list the stored heaters (never prints a token)")
    p.add_argument("--records", help=RECORDS_HELP)

    p = command("add-entry", "create the Home Assistant config entry of a stored heater")
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--name", help="the heater's name in the record file (newest record wins)")
    who.add_argument("--device-id", help="the record with this unique_id")
    p.add_argument("--rated-power", type=int, required=True, help="rated power in W (100..3000)")
    p.add_argument("--ha-url", required=True, help="Home Assistant address, e.g. http://homeassistant.example:8123")
    p.add_argument("--ha-token-file", required=True, help="file holding a long-lived access token")
    p.add_argument("--host-override", help="host[:port] instead of the record's ip_address")
    p.add_argument("--records", help=RECORDS_HELP)

    p = command("contract", "check a real heater against the rules the test double implements")
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--name", help="the heater's name in the record file")
    who.add_argument("--device-id", help="the record with this unique_id")
    p.add_argument("--allow-writes", action="store_true", help="also test set_target (restores the old target)")
    p.add_argument("--records", help=RECORDS_HELP)

    p = command("calibrate", "log a heater and a smart plug's power through target phases (up to 3 h)")
    p.add_argument("--name", required=True, help="the heater's name in the record file")
    p.add_argument("--ha-url", required=True, help="Home Assistant address")
    p.add_argument("--ha-token-file", required=True, help="file holding a long-lived access token")
    p.add_argument("--plug", required=True, help="entity id of the plug's power sensor (W)")
    p.add_argument("--phases", default="+100:30,+200:30", help="<target>:<minutes>,... (default +100:30,+200:30)")
    p.add_argument("--interval", type=float, default=10.0, help="seconds between samples (default 10)")
    p.add_argument("--out-dir", default=".", help="where the CSV goes (default: current directory)")
    p.add_argument("--records", help=RECORDS_HELP)

    p = command("fit", "fit the duty model from calibration CSVs")
    p.add_argument("csv", nargs="+")
    p.add_argument("--on-threshold", type=float, default=100.0, help="plug W above which the element is on")
    return ap


def _records(args: argparse.Namespace) -> Path:
    return Path(args.records) if args.records else default_records_path()


def _need_adax_local() -> None:
    try:
        import adax_local  # noqa: F401
    except ImportError:
        die("Adax-local is not importable - install this tool with pipx (see README)")


def _list(path: Path) -> int:
    if not path.is_file():
        print(f"no record file at {path}")
        return 0
    for r in load_records(path):
        print(f"{r.get('name')}  unique_id={r.get('unique_id')}  ip_address={r.get('ip_address')}  "
              f"timestamp={r.get('timestamp')}")
    return 0


def _contract(args: argparse.Namespace) -> int:
    from .contract import ContractError, run_contract
    from .heater import Heater

    rec = select_record(load_records(_records(args)), args.name, args.device_id)
    print(f"heater {rec.get('name')}: record {rec.get('timestamp')} (stat only unless --allow-writes)")
    try:
        run_contract(Heater(rec["ip_address"], rec["token"]).get, args.allow_writes)
    except ContractError as err:
        print(f"contract test: FAIL - {err}")
        return 1
    except OSError as err:
        print(f"contract test: FAIL - cannot reach the heater ({type(err).__name__})")
        return 3
    print("contract test: PASS (with writes)" if args.allow_writes else "contract test: PASS (read-only)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cmd = args.command
    if cmd == "scan":
        _need_adax_local()
        from .ble import scan
        return asyncio.run(scan(args.seconds))
    if cmd == "pair":
        _need_adax_local()
        from .ble import configure, wifi_credentials
        ssid, password = wifi_credentials(args.ssid, args.wifi_file)
        return asyncio.run(configure(args.name, ssid, password, _records(args)))
    if cmd == "list":
        return _list(_records(args))
    if cmd == "add-entry":
        from .add_entry import run
        return run(name=args.name, device_id=args.device_id, rated_power=args.rated_power, ha_url=args.ha_url,
                   ha_token_file=args.ha_token_file, host_override=args.host_override, records_path=_records(args))
    if cmd == "contract":
        return _contract(args)
    if cmd == "calibrate":
        from .calibrate import run
        return run(name=args.name, ha_url=args.ha_url, ha_token_file=args.ha_token_file, plug=args.plug,
                   phases_text=args.phases, interval=args.interval, out_dir=args.out_dir, records_path=_records(args))
    from .fit_duty import run
    return run(args.csv, args.on_threshold)


if __name__ == "__main__":
    sys.exit(main())
