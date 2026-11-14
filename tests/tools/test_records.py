"""U-01, U-02: the record file and the record choice."""
import json
import stat

import pytest

from adax_direct_tools.records import append_record, select_record

R1 = {"name": "Test Heater", "unique_id": "900000000000001", "timestamp": "2026-01-01T00:00:00+00:00"}
R2 = {"name": "Test Heater", "unique_id": "900000000000002", "timestamp": "2026-01-02T00:00:00+00:00"}


def test_append_record_mode_and_keep(tmp_path):
    path = tmp_path / "sub" / "heaters.json"
    append_record(path, R1)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == {"heaters": [R1]}
    append_record(path, R2)
    assert json.loads(path.read_text()) == {"heaters": [R1, R2]}

    other = tmp_path / "other.json"
    other.write_text('{"x": 1}')
    before = other.read_bytes()
    with pytest.raises(SystemExit) as exc:
        append_record(other, R1)
    assert exc.value.code == 2
    assert other.read_bytes() == before


def test_select_record_newest():
    assert select_record([R1, R2], name="Test Heater", device_id=None) == R2
    assert select_record([R2, R1], name="Test Heater", device_id=None) == R2
    assert select_record([R1, R2], name=None, device_id="900000000000001") == R1
    with pytest.raises(SystemExit) as exc:
        select_record([R1, R2], name="Unknown", device_id=None)
    assert exc.value.code == 2
