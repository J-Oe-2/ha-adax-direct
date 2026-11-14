# Adax Direct (unofficial) — set up Adax heaters from your laptop

Set up Adax heaters from your laptop — no need to carry Home Assistant to each heater. Local control, no cloud.

**Not actively maintained.** This is published as is, from one household's private use. Issues and pull requests may go unanswered. Fork freely (Apache-2.0).

Not affiliated with, endorsed by or supported by Adax AS.

- Heaters are paired from a laptop's Bluetooth with the `adax-direct` tool: nobody carries the Home Assistant box to each heater.
- The Home Assistant integration `adax_direct` is set up from the heater's IP address and access token, one config entry per heater.
- Power and energy are modelled (the heaters report 0 W locally), with a calibration tool to fit the model to your heater.

Install line for the tool: `pipx install "git+https://github.com/J-Oe-2/ha-adax-direct@v0.1.0"`.

## What you get

Per heater, one device with:

- `climate.<name>` — on/off and target temperature (off is target 0; only 0 or 5–35 °C is ever written).
- `sensor.<name>_temperature` — the room temperature the heater reports.
- `sensor.<name>_power` — modelled power in W, with the attribute `duty`.
- `sensor.<name>_energy` — modelled energy in kWh, total increasing, restored across restarts.
- `sensor.<name>_reported_pow` and `sensor.<name>_reported_energ` — what the heater itself reports (diagnostic, disabled by default, always 0 on the heaters tested).

One config entry per heater. No cloud.

## Consequences of local control — read first

- The heater leaves the Adax cloud: the Adax app stops working for it.
- "Off" is target temperature 0.
- A target between 0 and 5 °C is not "almost off": the heater stores it as 5 °C and heats. This is why the integration only ever sends 0 or 5–35 °C.
- Going back is only possible by resetting the heater and pairing it again in the Adax app.

## Install the integration

1. In HACS, add the custom repository `https://github.com/J-Oe-2/ha-adax-direct` with category Integration, then install "Adax Direct (unofficial)". Alternatively copy the folder `custom_components/adax_direct` into your Home Assistant configuration by hand.
2. Restart Home Assistant.

Requires Home Assistant 2026.9 or newer (tested on 2026.9.x).

## Pair a heater from your laptop

Install the tool (Python 3.10 or newer):

```
pipx install "git+https://github.com/J-Oe-2/ha-adax-direct@v0.1.0"
```

On macOS the terminal app needs Bluetooth permission (System Settings › Privacy & Security › Bluetooth); it is asked for at the first scan.

1. Check what the laptop can see: `adax-direct scan`. It lists every device advertising the Adax Bluetooth service and says which can be set up. Nothing is configured, nothing is connected.
2. Stand next to only the heater you are pairing. The library takes the first Adax device it sees; if that one is already registered it stops with "heater not available". A heater that is still on the Adax cloud does not advertise over Bluetooth at all until it is reset.
3. Reset that heater as Home Assistant's own Adax documentation words it: press + and OK until the display shows Reset, then press and hold the OK button until the blue LED starts blinking.
4. Pair it:

   ```
   adax-direct pair --name "Living room" --ssid TestNet
   ```

   The Wi-Fi password is asked for without echo and never printed. There is deliberately no `--password` option; `--wifi-file PATH` takes a JSON file `{"ssid": "...", "password": "..."}` instead (a warning is printed if the file is readable by others). Assume a 2.4 GHz network; this is not verified. Unlike Home Assistant's own flow, the password is not stripped of spaces.

Pairing can take several minutes (up to two Bluetooth scans of 60 s, then up to 20 s for the heater to join your Wi-Fi and report its IP address). Success prints the name, IP address, `unique_id` and only the token's length, then appends the record to the record file.

The record file is `$XDG_CONFIG_HOME/adax-direct/heaters.json`, else `~/.config/adax-direct/heaters.json` (all operating systems), or the path given with `--records`. It holds the token, so it is created with mode 0600 in a directory with mode 0700. On Windows these modes are best-effort. Records are only ever appended; pairing the same name again adds a record and the newest one is the valid one. `adax-direct list` shows name, `unique_id`, IP address and time, never the token.

If something goes wrong the tool exits with code 3 and says why: no heater found, heater not available (already registered, reset it again), Wi-Fi credentials rejected, or "no IP within 20 s", which is what a wrong Wi-Fi password looks like in practice (the library raises its credential error inside a Bluetooth callback, where it cannot reach the caller). Nothing is written in that case. Other exit codes: 1 operation failed, 2 usage or input error.

Finally, give the heater a fixed IP address (a DHCP reservation) on your router: Home Assistant stores the IP address, not a hostname.

## Add the heater to Home Assistant

Either in the user interface: Settings › Devices & services › Add integration › "Adax Direct (unofficial)". Fill in the fields as described under Options below. `adax-direct list` shows the name, `unique_id` and IP address to use; the token is copied by you from the record file, the tool never prints it.

Or from the laptop, with a long-lived access token of your Home Assistant saved in a file:

```
adax-direct add-entry --name "Living room" --rated-power 1000 \
    --ha-url http://homeassistant.example:8123 --ha-token-file ./ha-token-file
```

It runs the integration's config flow over the REST API and prints the entry id and title. `--device-id ID` selects a record by `unique_id` instead of by name, and `--host-override HOST[:PORT]` replaces the recorded IP address.

## Options

| Option | Where | Range | Default | Meaning |
|---|---|---|---|---|
| Host | setup + options | IP or host, `host:port` for a non-standard port | — | heater address (give it a DHCP reservation) |
| Access token | setup + options | text | — | as stored by `adax-direct pair` |
| Adax device id | setup | text | — | `unique_id` from the record; the entry's unique id |
| Name | setup | text | — | device name; entity ids derive from it |
| Rated power (W) | setup + options | 100–3000 | 1000 | measured wattage at your mains (a Clea H 10 KWT measured 965–998 W at 230 V, see Measured behaviour) |
| Duty at target (`duty_base`) | options | 0–1 | 0.23 | share of time on when room = target |
| Duty per K below target (`duty_slope`) | options | 0–5 | 0.30 | added on-share per K the room is below target |
| Idle offset (K) (`idle_offset_k`) | options | −5 to 5 | 1.5 (0 = off) | added to the reading once the heater has not heated for the settle time; measure it idle against a reference thermometer |
| Settle time (min) (`settle_min`) | options | 0–180 | 45 | wait after the heater last heated before the offset applies; after a restart or a reload the wait starts again |

Fixed behaviours: poll every 60 s; entities become unavailable only after 5 failed polls in a row; only 0 (off) or 5–35 °C is ever written; energy is booked from successful polls only, at most 180 s per interval.

## Energy model and accuracy

The heaters report 0 W locally. Power is modelled: rated power × duty, duty = clamp(duty_base + duty_slope × (target − room) [K], 0, 1). With the default curve (0.23 / 0.30) and a measured wattage, the energy was within ±10 % per hour-long run on four plug-measured Gen2 heaters (−10.1 %, −3.5 %, −1.4 %, +1.4 %); shorter windows deviate more (up to +14 % over 30 min; near the setpoint, where little energy flows, much more in relative terms). Resistive elements draw power ∝ V²: the label wattage applies at the label voltage, so measure at your mains voltage or correct by (V / V_label)².

## Measured behaviour

Measurements on one installation (8 heaters: Clea H 10 KWT ×6, Clea H 12 KWT ×1, Neo L 14 WT ×1). Use them as typical values, not as specifications.

**Wattage.** Measured with a plug power meter while the element was warm, and normalised to 230 V from the measured resistance (P = V² / R): five Clea H 10 KWT (label 1000 W) delivered 965–998 W at 230 V (53.0–54.8 Ω, mean ≈ 982 W); at the actual supply of 223–230 V that was 926–988 W. One Clea H 12 KWT (label 1200 W) delivered ≈ 1133 W at 230 V. The rated-power default stays the label value; enter your measured value for better energy figures. A whole-house meter reproduced a plug-measured step within ≈ 1 %, at night with little other load.

**The heater's own temperature sensor reads low while the heater is idle.** This is the sensor's idle reading bias, measured at the sensor's own location: a reference probe (three probes agreeing within ±0.03 K) sat right next to the heater's sensor on the control unit. While idle the heaters read 1.0 to 1.9 K too low (mean 1.5 K); while heating there is no bias. The spread between heaters is up to 0.9 K, so an exact correction is per heater; one value of 1.5 K puts every measured heater within ±0.5 K. While heating, the reading converges on the reference within about 15 minutes of continuous heating (for example −1.9 K → ±0.15 K): heating ventilates the sensor with room air, and it does not read high. After switch-off the reading stays right for about 10 minutes, then drifts low with a time constant of about 30 minutes (fit on one heater: Δ ≈ −1.6 · (1 − e^(−(t − 10) / 30)) K, t in minutes). A rule of "no correction while heating and for 45 minutes afterwards, then the idle offset" stays within ±1 K of the reference (at worst 0.5 K too warm just after the 45 minutes).

**How to measure the bias yourself.** Compare only after at least 20 minutes of settling. Settled means the difference (heater − reference) stops changing, i.e. less than 0.2 K between consecutive 10-minute means, not that the reference stops changing.

## Calibrate with a smart plug

If you have a smart plug with power measurement for the heater, fit the model to it:

```
adax-direct calibrate --name "Living room" --plug sensor.<plug>_power \
    --ha-url http://homeassistant.example:8123 --ha-token-file ./ha-token-file
adax-direct fit *.csv
```

`calibrate` drives the heater through target phases (by default +1 K for 30 min, then +2 K for 30 min, relative to the room temperature at the start of each phase) and logs the heater and the plug every 10 s into a CSV in `--out-dir`. It never runs longer than 3 h, and the heater's original target is restored when the run ends, fails, or receives an interrupt or termination signal. `fit` prints three values; enter them in the heater's options as rated power, `duty_base` and `duty_slope`.

Two things worth knowing: the heater switches its element on within about 3 s of a target change, and the model is time-proportional with a cycle of about 110 s.

## Tested on

| Heater | Controller | Verified | Energy model |
|---|---|---|---|
| Adax Clea H 10 KWT, Clea H 12 KWT | Gen2 | setup, control | plug-validated |
| Adax Clea H 10 KWT | Gen3 | setup, contract, control, 2-h heater-on test | assumed (wall-mounted, no plug) |
| Adax Neo L 14 WT, 400 V | Gen2 | setup, control | assumed |

One house. Home Assistant 2026.9.x. Setup tool run on macOS only; Linux and Windows untested.

## Local API (for developers)

The heater serves HTTPS with a self-signed certificate:

- `GET https://<ip>/api?command=stat&time=<unix>` returns JSON with four integer fields: `currTemp`, `targTemp` (both °C × 100), `energ` and `pow` (both always 0 locally).
- `GET https://<ip>/api?command=set_target&time=<unix>&value=<°C × 100>` returns 200 with an empty body.
- Header `Authorization: Basic <token>`, the token verbatim (it is not base64 credentials).

The heater stores the target as follows, which is why the integration refuses to send anything but 0 or 500–3500:

| Sent | Stored |
|---|---|
| 0 | 0 (off) |
| 1 to 499, and negative values | 500 (5 °C, and it heats) |
| 500 to 3500 | as sent |
| above 3500 | 3500 |

No other command is documented anywhere we found. `adax-direct contract --name "Living room"` checks a real heater against these rules (read-only; add `--allow-writes` to test `set_target`, the original target is restored). The same rules are implemented by the test double in `tests/fake_heater.py`.

## Suggestions for the official integration

Four small, self-contained suggestions for the maintainers of Home Assistant's official Adax integration are in [docs/upstream](docs/upstream/README.md), which also says where each was filed.

## Licence and attribution

Apache License 2.0, see `LICENSE`; attribution in `NOTICE`. The setup tool depends on [Adax-local](https://github.com/Danielhiversen/pyAdaxLocal) (MIT License) and its Bluetooth advertisement decoding follows that library; its licence text is in `NOTICE`. Not affiliated with, endorsed by or supported by Adax AS; "Adax" only names the heaters this software works with. Not actively maintained.
