"""U-06a, U-06b: the decoding of an advertisement."""
from types import SimpleNamespace

import adax_local

from adax_direct_tools.ble import decode_adv

PAYLOAD = bytes([0, 3, 0x3B, 0x9A, 0xCA, 0, 0, 1])


def test_decode_adv_available():
    d = decode_adv(SimpleNamespace(manufacturer_data={11: PAYLOAD}))
    assert d["decoded"] is True
    assert d["type_id"] == 11
    assert d["is_heater"] is True
    assert d["registered"] is False
    assert d["managed"] is False
    assert d["mac_id"] == adax_local.find_mac_id([11, 0, 0, 3, 0x3B, 0x9A, 0xCA, 0, 0, 1])


def test_decode_adv_registered():
    d = decode_adv(SimpleNamespace(manufacturer_data={11 + (1 << 8): PAYLOAD}))
    assert d["registered"] is True
    assert d["managed"] is False
