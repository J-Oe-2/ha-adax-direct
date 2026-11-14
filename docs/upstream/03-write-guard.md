# Never send a target between 0 and 5 °C

## The gap today

In the Adax-local library (0.3.0), `Adax.set_target_temperature(t)` sends `int(t * 100)` without any check. Home Assistant core's climate entity relies on its `min_temp` of 5 and `max_temp` of 35 to keep values in range (`homeassistant/components/adax/climate.py` at commit `f5a4ea0d`). Any path that bypasses the entity's range check, for example a future code path or another caller of the library, can send a small positive value. The heater does not treat that as "almost off": it stores any value between 1 and 499 (hundredths of a degree) as 500, i.e. 5 °C, and heats.

Observed on real Gen2 and Gen3 heaters (value sent, in hundredths of °C, and the value the heater stores):

| Sent | Stored |
|---|---|
| 0 | 0 (off) |
| 400, 100, 450 | 500 |
| −100 | 500 |
| 550 | 550 |
| 3600 | 3500 |

## What ha-adax-direct does

The API client refuses to send anything except 0 (off) or 500 to 3500, raising before any request is made, so a mistaken caller cannot make a heater heat when it meant to switch it off. Code: [api.py lines 63-70](https://github.com/J-Oe-2/ha-adax-direct/blob/v0.1.0/custom_components/adax_direct/api.py#L63-L70). The repository also contains a contract check, `adax-direct contract`, that verifies the table above against a real heater and against the test double used in the tests.

## Suggested change for core

Add the same check where the library sends the value, or in the climate entity as defence in depth: a value that is not 0 and not between 500 and 3500 (in hundredths of a degree) is rejected with an error instead of being sent.

```
def set_target(value_c100):
    if value_c100 != 0 and not 500 <= value_c100 <= 3500:
        raise ValueError("only 0 or 500..3500 may be sent")
    send(value_c100)
```

## How to test it

With a fake heater that records every set-target value: sending 450, 499, 3501, −100 and 1 raises an error and records nothing; sending 0, 500 and 3500 succeeds and records exactly [0, 500, 3500]. In the climate entity, a temperature of 4 °C is rejected and nothing is recorded.

## Effort and risk

A few lines and one test. The risk is that someone relies on a value above 3500 being clamped by the heater; the check turns that into an error, which is the point.
