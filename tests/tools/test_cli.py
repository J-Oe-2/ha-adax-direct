"""U-03, U-04, U-05, U-05b, U-10: the command line never prints a secret, reads no environment."""
import getpass
import io
import json
import re
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import adax_local
import pytest

from adax_direct_tools.cli import main
from tests.fake_heater import TOKEN

SRC = Path(__file__).resolve().parents[2] / "src"


def test_pair_never_prints_secrets(tmp_path, monkeypatch, capsys):
    token = "fake" * 5                               # 20 chars, built at run time
    password = "s3cret-wifi-pass"

    class FakeConfig:
        mac_id = 0x00033B9ACA000001
        device_ip = "192.0.2.5"
        access_token = token

        def __init__(self, ssid, pswd):
            self.ssid, self.pswd = ssid, pswd

        async def configure_device(self):
            return True

    async def fake_scan(*args, **kwargs):
        return SimpleNamespace(address="00000000-0000-0000-0000-000000000001", name="Adax"), FakeConfig.mac_id

    monkeypatch.setattr(adax_local, "AdaxConfig", FakeConfig)
    monkeypatch.setattr(adax_local, "scan_for_available_ble_device", fake_scan)
    monkeypatch.setattr(getpass, "getpass", lambda *a, **k: password)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    records = tmp_path / "heaters.json"

    code = main(["pair", "--name", "Test Heater", "--ssid", "TestNet", "--records", str(records)])

    captured = capsys.readouterr()
    assert code == 0
    assert token not in captured.out + captured.err
    assert password not in captured.out + captured.err
    assert "token=<20 chars, stored, not shown>" in captured.out
    assert token in records.read_text()


def test_no_password_option():
    with pytest.raises(SystemExit) as exc:
        main(["pair", "--name", "x", "--ssid", "y", "--password", "z"])
    assert exc.value.code == 2


RECORD = {
    "name": "Test Heater",
    "unique_id": "900000000000001",
    "mac_id_hex": "00033b9aca000001",
    "ble_address": "00000000-0000-0000-0000-000000000001",
    "ip_address": "192.0.2.5",
    "token": TOKEN,
    "timestamp": "2026-01-01T00:00:00+00:00",
}


class FakeResponse:
    def __init__(self, status, body):
        self.status, self._body = status, json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def add_entry_argv(tmp_path, rated="1000"):
    records = tmp_path / "heaters.json"
    records.write_text(json.dumps({"heaters": [RECORD]}))
    ha_token = tmp_path / "ha-token-file"
    ha_token.write_text("ha-test-token-XYZ\n")
    return ["add-entry", "--name", "Test Heater", "--rated-power", rated,
            "--ha-url", "http://homeassistant.example:8123", "--ha-token-file", str(ha_token),
            "--records", str(records)]


def test_add_entry_never_prints_tokens(tmp_path, monkeypatch, capsys):
    sent = []

    def fake_urlopen(req, timeout=None):
        sent.append(req)
        if len(sent) == 1:
            return FakeResponse(200, {"type": "form", "flow_id": "f1"})
        return FakeResponse(200, {"type": "create_entry", "title": "Test Heater", "result": {"entry_id": "abc123"}})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    code = main(add_entry_argv(tmp_path))

    captured = capsys.readouterr()
    assert code == 0
    assert "entry_id: abc123" in captured.out
    for secret in (TOKEN, "ha-test-token-XYZ"):
        assert secret not in captured.out + captured.err
    body = json.loads(sent[1].data)
    assert body["token"] == TOKEN
    assert body["device_id"] == "900000000000001"
    assert body["host"] == "192.0.2.5"
    assert body["rated_power_w"] == 1000
    assert body["name"] == "Test Heater"


@pytest.mark.parametrize("rated", ["99", "3001"])
def test_add_entry_rated_power_range(tmp_path, monkeypatch, rated):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    with pytest.raises(SystemExit) as exc:
        main(add_entry_argv(tmp_path, rated))
    assert exc.value.code == 2
    assert calls == []


def test_no_environment_coupling():
    environ, getenv = "os." + "environ", "os." + "getenv"
    dotenv = re.compile(r"(?<![\w])\." + "env" + r"\b")
    parents = "parents" + "[2]"
    mkdir = ".mkdir" + "("
    files = sorted(SRC.rglob("*.py"))
    assert files
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{path.name}:{number}"
            if environ in line or getenv in line:
                assert "XDG_CONFIG_HOME" in line, where
            assert not dotenv.search(line), where
            assert parents not in line, where
            assert mkdir not in line, where
