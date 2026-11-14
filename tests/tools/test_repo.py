"""U-07, U-08, U-09, U-11, U-13: the repository's own files agree with each other."""
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import adax_direct_tools

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "custom_components" / "adax_direct"
FULL_NAME = "Jo" + "sef Oe" + "hmen"
VERSION = "0.1.0"

README_HEADINGS = [
    "# Adax Direct (unofficial) — set up Adax heaters from your laptop",
    "## What you get",
    "## Consequences of local control — read first",
    "## Install the integration",
    "## Pair a heater from your laptop",
    "## Add the heater to Home Assistant",
    "## Options",
    "## Energy model and accuracy",
    "## Calibrate with a smart plug",
    "## Tested on",
    "## Local API (for developers)",
    "## Suggestions for the official integration",
    "## Licence and attribution",
]
UPSTREAM_HEADINGS = [
    "## The gap today",
    "## What ha-adax-direct does",
    "## Suggested change for core",
    "## How to test it",
    "## Effort and risk",
]


def headings(text: str) -> list[str]:
    """`#` and `##` headings outside code fences."""
    found, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"##? ", line):
            found.append(line)
    return found


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def test_manifest_strings_versions():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest == {
        "domain": "adax_direct",
        "name": "Adax Direct (unofficial)",
        "codeowners": ["@J-Oe-2"],
        "config_flow": True,
        "documentation": "https://github.com/J-Oe-2/ha-adax-direct",
        "integration_type": "device",
        "iot_class": "local_polling",
        "issue_tracker": "https://github.com/J-Oe-2/ha-adax-direct/issues",
        "requirements": [],
        "version": VERSION,
    }
    assert list(manifest)[:2] == ["domain", "name"]
    assert list(manifest)[2:] == sorted(list(manifest)[2:])      # hassfest key order
    strings = json.loads((INTEGRATION / "strings.json").read_text())
    assert strings == json.loads((INTEGRATION / "translations" / "en.json").read_text())
    assert strings["config"]["step"]["user"]["description"] == (
        "Address and access token of one heater, as stored by `adax-direct pair` (see the README). "
        "The heater must already be on your Wi-Fi."
    )
    assert strings["config"]["step"]["user"]["data"]["name"] == "Name (e.g. Living room)"
    assert json.loads((ROOT / "hacs.json").read_text()) == {"name": "Adax Direct (unofficial)", "homeassistant": "2026.9.0"}
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["version"] == manifest["version"] == adax_direct_tools.__version__ == VERSION


def test_docs_structure():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert headings(readme) == README_HEADINGS
    paragraphs = [p for p in readme.split("\n\n")][1:4]
    assert paragraphs == [
        "Set up Adax heaters from your laptop — no need to carry Home Assistant to each heater. Local control, no cloud.",
        "**Not actively maintained.** This is published as is, from one household's private use. "
        "Issues and pull requests may go unanswered. Fork freely (Apache-2.0).",
        "Not affiliated with, endorsed by or supported by Adax AS.",
    ]
    assert "ha-adax-direct" in readme.split(README_HEADINGS[1])[0]

    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert notice.startswith(f"ha-adax-direct\nCopyright 2026 {FULL_NAME}\n\n")
    markers = [
        'This project is not affiliated with, endorsed by or supported by Adax AS. "Adax" is used only\n'
        "to name the heaters this software works with.",
        "Not actively maintained beyond the author's private use.\nProvided as is (see LICENSE).",
        "decode_adv) follows Adax-local (https://github.com/Danielhiversen/pyAdaxLocal), MIT License, Copyright (c) 2021",
        "Permission is hereby granted, free of charge",
    ]
    positions = [notice.index(m) for m in markers]
    assert positions == sorted(positions)

    for number, slug in enumerate(("modelled-energy", "unavailable-debounce", "write-guard", "laptop-ble-setup"), 1):
        text = (ROOT / "docs" / "upstream" / f"{number:02d}-{slug}.md").read_text(encoding="utf-8")
        assert [h for h in headings(text) if h.startswith("## ")] == UPSTREAM_HEADINGS, slug


def test_icon_reproducible(tmp_path):
    out = tmp_path / "icon.png"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_icon.py"), str(out)], check=True, capture_output=True)
    committed = (INTEGRATION / "brand" / "icon.png").read_bytes()
    assert out.read_bytes() == committed
    assert committed[:8] == b"\x89PNG\r\n\x1a\n"
    assert committed[12:16] == b"IHDR"
    assert int.from_bytes(committed[16:20], "big") == 256
    assert int.from_bytes(committed[20:24], "big") == 256
    assert committed[25] == 6                       # colour type RGBA


def test_workflows():
    validate = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
    tests = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    for needle in ("hacs/action@main", "category: integration", "home-assistant/actions/hassfest@master",
                   "actions/checkout@v7", "permissions: {}", "name: Validate", 'cron: "0 0 * * *"', "workflow_dispatch"):
        assert needle in validate, needle
    assert "ignore:" not in validate
    for needle in ("actions/checkout@v7", "actions/setup-python@v7", 'python-version: "3.14"',
                   "pytest tests/integration -q", "pytest tests/tools -q -k 'not git_history'",
                   "name: Tests", "contents: read"):
        assert needle in tests, needle


def test_git_history_single_commit():
    assert git("rev-list", "--all", "--count").strip() == "1"
    refs = set(git("for-each-ref", "--format=%(refname)").split())
    assert refs == {"refs/heads/main", "refs/tags/v0.1.0"}
    assert git("log", "-1", "--format=%B", "main").rstrip("\n") == (
        "Initial public release v0.1.0\n\n"
        "adax_direct integration, adax-direct setup tool, tests, CI and upstream suggestions.\n\n"
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    )
    assert git("for-each-ref", "refs/tags/v0.1.0", "--format=%(contents)").strip() == "v0.1.0"
