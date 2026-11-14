# Modelled power and energy for local Adax entries

## The gap today

In Home Assistant core, the `adax` integration creates energy sensors only for cloud entries: `homeassistant/components/adax/sensor.py` (line 56 at commit `f5a4ea0d`) returns without sensors when the connection type is local, and the integration's documentation says energy sensors "are only available when using the cloud connection, as the local integration does not support energy data". The reason is that the heaters report nothing useful locally: the local `stat` answer carries `pow` and `energ` fields, but they are 0 on every heater we tested (Gen2 and Gen3 controllers). Users who switch to local control lose their energy history source, and the Energy dashboard has nothing to show for those heaters.

## What ha-adax-direct does

It models power instead of reading it. The element is switched time-proportionally, so power is rated power multiplied by a duty between 0 and 1, and duty = clamp(`duty_base` + `duty_slope` × (target − room in K), 0, 1), with 0 when the heater is off. The defaults are 0.23 and 0.30, fitted on a plug-measured heater; rated power is a user option (100–3000 W, default 1000), and all three can be set per heater. Energy is the running sum of the previous poll's power times the time since that poll, where a poll interval never counts for more than 180 s and failed polls book nothing. The total is a `total_increasing` kWh sensor restored across restarts, and the power sensor carries the duty as an attribute. Code: [coordinator.py lines 75-107](https://github.com/J-Oe-2/ha-adax-direct/blob/v0.1.0/custom_components/adax_direct/coordinator.py#L75-L107) and [sensor.py lines 52-100](https://github.com/J-Oe-2/ha-adax-direct/blob/v0.1.0/custom_components/adax_direct/sensor.py#L52-L100).

Evidence: with the default curve and a measured wattage, the energy was within ±10 % per hour-long run on four plug-measured Gen2 heaters (−10.1 %, −3.5 %, −1.4 %, +1.4 %). Shorter windows deviate more (up to +14 % over 30 minutes), and near the setpoint, where little energy flows, the relative error is larger still. Resistive elements draw power proportional to V², so the label wattage applies at the label voltage only.

## Suggested change for core

Create optional power and energy sensors for local entries, clearly marked as estimated, with three options per entry (rated power, duty at target, duty per kelvin below target). In pseudo-code, per successful local poll:

```
duty  = 0 if target == 0 else clamp(base + slope * (target - room), 0, 1)
power = rated_power * duty
energy_total += previous_power * min(seconds_since_previous_successful_poll, 180) / 3600 / 1000
```

The energy total must survive restarts (restore the last state), and a failed poll must neither add nor reset anything.

## How to test it

With a fake local heater answering room 16.32 °C and target 20.00 °C and the default options with rated power 1000 W: the power sensor reads 1000 W (duty clamped to 1); after four polls 60 s apart the energy sensor reads 0.066667 kWh; after one further poll 600 s later it reads 0.116667 kWh (the interval is capped at 180 s); a failed poll leaves it at 0.116667; the next successful poll 60 s after the failure (120 s after the last good poll) brings it to 0.15 kWh. With options base 0.26, slope 0.34: room 20.00 and target 20.00 gives 260 W; a gap of 1 K gives 600 W; a gap of 3 K gives 1000 W; room above target gives 0 W; target 0 gives 0 W. A restored total of 1.5 kWh plus one 60 s poll at 1000 W reads 1.516667 kWh.

## Effort and risk

Small: one pure function, one accumulator, three options, two sensors. The risk is policy, not code: an estimated value in a place where users expect a measurement may not fit core's rules, and the accuracy statement above is from one household with four plug-measured heaters. The maintainers decide whether estimated sensors belong in core at all.
