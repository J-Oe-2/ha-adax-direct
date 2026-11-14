# Let heaters paired elsewhere be added: a manual "IP address + token" local step

## The gap today

In Home Assistant core, the `adax` config flow (`homeassistant/components/adax/config_flow.py` at commit `f5a4ea0d`, version 2) has three steps: choose Cloud or Local, a local step that asks for the Wi-Fi name and password and then configures the heater over Bluetooth from the Home Assistant host (`adax_local.AdaxConfig(ssid, pswd).configure_device()`), and the cloud step. There is no step that takes an address and a token, no reconfigure and no import. The documentation states that the machine running Home Assistant needs a Bluetooth adapter and that the heater must be in range during setup. Many Home Assistant installations (a mini PC in a cabinet, a virtual machine, a box without an adapter) cannot do that, and the heater is usually in a different room from the box.

## What ha-adax-direct does

Pairing happens on a laptop with the `adax-direct` tool, using the same library call as core, and the integration's config flow takes what pairing produced: the heater's IP address, its access token, its device id and a name, validated by one status request. Code: the pairing in [ble.py](https://github.com/J-Oe-2/ha-adax-direct/blob/v0.1.0/src/adax_direct_tools/ble.py#L108-L170) and the config step in [config_flow.py lines 46-82](https://github.com/J-Oe-2/ha-adax-direct/blob/v0.1.0/custom_components/adax_direct/config_flow.py#L46-L82). One practical detail for anyone using the library standalone: Adax-local 0.3.0 calls `urllib.parse.quote()` after only `import urllib`; inside Home Assistant another module has already imported `urllib.parse`, but run on its own the library raises `AttributeError` until `urllib.parse` is imported first. This is a defect in the library, not in Home Assistant.

## Suggested change for core

(a) Add a manual local step to core's config flow that takes IP address, access token and device id (validated by one status request, with the device id as the entry's unique id), so heaters paired anywhere can be added. (b) Alternatively or additionally, point the documentation at laptop pairing as an option for hosts without Bluetooth. In pseudo-code:

```
step "local_manual": input host, token, device_id
    set unique id = device_id; abort if already configured
    if status request with host and token fails: show error "cannot_connect"
    create entry(host, token, device_id)
```

## How to test it

With a fake heater answering the status request: submitting host, token and device id creates an entry whose data holds those values; submitting the same device id again aborts as already configured without any request; with the fake answering HTTP 500 or not answering in time, the form is shown again with the error `cannot_connect` and no entry exists.

## Effort and risk

Small for (a): one step reusing the status request core already makes; the entry data would need to match what core's local entries store today. The risk is support load: users will paste tokens from tools of varying quality. (b) is a documentation change only.
