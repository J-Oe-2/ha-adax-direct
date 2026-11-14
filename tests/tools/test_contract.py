"""U-06, U-06c, U-06d: the contract check against the test double."""
import json

import pytest

from adax_direct_tools.contract import ContractError, run_contract
from tests.fake_heater import FakeHeater


def adapter(fake):
    return lambda command, **params: fake.handle(command, params.get("value"))


def test_contract_passes_on_fake():
    fake = FakeHeater()
    run_contract(adapter(fake), allow_writes=True, log=lambda *_: None, settle_s=0)
    assert fake.targTemp == 900


def test_contract_detects_wrong_clamp():
    class WrongClamp(FakeHeater):
        def clamp(self, value):
            return 0 if value == 450 else super().clamp(value)

    with pytest.raises(ContractError) as exc:
        run_contract(adapter(WrongClamp()), allow_writes=True, log=lambda *_: None, settle_s=0)
    assert "set_target 450" in str(exc.value)


def test_contract_detects_extra_key():
    fake = FakeHeater()

    def get(command, **params):
        status, ctype, body = fake.handle(command, params.get("value"))
        if command == "stat":
            body = json.dumps({**json.loads(body), "x": 1}).encode()
        return status, ctype, body

    with pytest.raises(ContractError) as exc:
        run_contract(get, allow_writes=False, log=lambda *_: None, settle_s=0)
    assert "keys" in str(exc.value)
