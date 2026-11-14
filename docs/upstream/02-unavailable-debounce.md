# A debounce before local Adax entities become unavailable

## The gap today

In Home Assistant core, `homeassistant/components/adax/coordinator.py` (commit `f5a4ea0d`), `AdaxLocalCoordinator._async_update_data` returns the library's answer if it is truthy and raises `UpdateFailed` otherwise. The library's `Adax.get_status()` (Adax-local 0.3.0) returns a truthy dictionary `{"target_temperature": None, "current_temperature": None}` on a non-200 answer or a timeout, so such a failure never reaches `UpdateFailed`: the entity stays available but shows no temperature. Other exceptions (connection refused, a body that is not JSON) are not caught there and reach `DataUpdateCoordinator`, which marks the update failed at the first occurrence. The poll interval is 60 s. The result is two behaviours for one kind of problem: a silent "available but empty" for some failures, and an immediate flip to unavailable for others, with no tolerance for a single dropped poll on a Wi-Fi heater.

## What ha-adax-direct does

It treats every failure the same way and tolerates short ones. The API client raises one error type for a timeout, a connection error, a non-200 status and a body that is not a JSON object with integer `currTemp` and `targTemp`. The coordinator counts consecutive failures: failures 1 to 4 keep the last good data (and log a warning `poll failure n/5`), the 5th raises `UpdateFailed` and all entities become unavailable, and the next good poll resets the counter. The first poll after setup must succeed, otherwise the entry is retried. The token never appears in a log line or an exception text. Code: [coordinator.py lines 81-98](https://github.com/J-Oe-2/ha-adax-direct/blob/v0.1.0/custom_components/adax_direct/coordinator.py#L81-L98) and [api.py](https://github.com/J-Oe-2/ha-adax-direct/blob/v0.1.0/custom_components/adax_direct/api.py#L1-L70).

## Suggested change for core

Make a failed status request raise (in the library, or by checking for the `None` values in the coordinator), then count consecutive failures and raise `UpdateFailed` only at a threshold (we use 5 polls, i.e. five minutes at the 60 s interval); until then return the previous data. In pseudo-code:

```
on poll:
    result = get_status()
    if result has no current temperature:      # the library's silent failure
        failures += 1
        if previous_data is None or failures >= 5:
            raise UpdateFailed
        return previous_data
    failures = 0
    return result
```

## How to test it

With a fake local heater: after a successful setup, switch it to each of three failure modes in turn (no answer in time, HTTP 500, a 200 answer with an HTML body). For each, polls 1 to 4 leave the climate entity, the temperature sensor and any power or energy sensors in their previous states and log `poll failure 4/5` at the fourth; the 5th poll makes all of them unavailable; one good poll afterwards brings the climate entity back to `heat`. With the heater failing before setup, the config entry ends in the setup-retry state.

## Effort and risk

Small, and it removes one inconsistent behaviour. The risk is in the threshold: a user who wants to know quickly that a heater is offline waits five poll intervals before the entity says so. A shorter threshold, or a configurable one, are equally valid choices.
