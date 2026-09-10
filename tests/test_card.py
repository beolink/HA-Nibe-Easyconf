"""The dashboard card's logic, run in node.

The card's pure helpers are loaded into node when it is installed (GitHub's
runners have it); the custom elements are only defined in a browser, so the
DOM part is not tested here. What is pinned is what decides which entities a
user sees and how: that another integration's entities never leak in, that a
disabled entity stays out, and that the device-name prefix Home Assistant adds
to every entity is dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

CARD = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "nibe_local_easyconf"
    / "www"
    / "nibe-easyconf-card.js"
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _run(script: str):
    """Evaluate `script` in node with the card's helpers bound to `c`."""
    program = f"const c = require({json.dumps(str(CARD))});\n{script}"
    out = subprocess.run(
        ["node", "-e", program], capture_output=True, text=True, timeout=30, check=True
    )
    return json.loads(out.stdout)


HASS = """
const hass = {
  locale: {language: "sv"},
  devices: {d1: {name: "NIBE S1155"}, d2: {name: "Pool"}},
  entities: {
    "sensor.nibe_s1155_ute": {entity_id: "sensor.nibe_s1155_ute",
      platform: "nibe_local_easyconf", device_id: "d1", entity_category: null},
    "number.nibe_s1155_kurva": {entity_id: "number.nibe_s1155_kurva",
      platform: "nibe_local_easyconf", device_id: "d1", entity_category: "config"},
    "sensor.nibe_s1155_tillverkad": {entity_id: "sensor.nibe_s1155_tillverkad",
      platform: "nibe_local_easyconf", device_id: "d1", entity_category: "diagnostic"},
    "switch.nibe_s1155_elpatron": {entity_id: "switch.nibe_s1155_elpatron",
      platform: "nibe_local_easyconf", device_id: "d1", entity_category: null},
    "sensor.pool_temp": {entity_id: "sensor.pool_temp",
      platform: "intellipool", device_id: "d2"},
    "sensor.nibe_s1155_disabled": {entity_id: "sensor.nibe_s1155_disabled",
      platform: "nibe_local_easyconf", device_id: "d1"},
  },
  states: {
    "sensor.nibe_s1155_ute": {state: "13.6", attributes: {
      friendly_name: "NIBE S1155 Utetemperatur", unit_of_measurement: "°C",
      description: "Utetemperatur (BT1).", modbus_register: 30002}},
    "number.nibe_s1155_kurva": {state: "6", attributes: {
      friendly_name: "NIBE S1155 Värmekurva", description: "Värmekurvan bestämmer"}},
    "sensor.nibe_s1155_tillverkad": {state: "2022-02-03", attributes: {
      friendly_name: "NIBE S1155 Tillverkad"}},
    "switch.nibe_s1155_elpatron": {state: "off", attributes: {
      friendly_name: "NIBE S1155 Tillåt elpatron"}},
    "sensor.pool_temp": {state: "24", attributes: {friendly_name: "Pool temp"}},
  },
};
"""


def test_only_this_integrations_enabled_entities_appear():
    ids = _run(HASS + "console.log(JSON.stringify(c.collectRows(hass, null).map(r => r.entityId)))")
    assert "sensor.pool_temp" not in ids  # another integration
    assert "sensor.nibe_s1155_disabled" not in ids  # disabled: no state
    assert len(ids) == 4


def test_entities_land_in_the_device_pages_own_sections():
    groups = _run(
        HASS
        + "console.log(JSON.stringify(Object.fromEntries("
        + "c.collectRows(hass, null).map(r => [r.entityId, r.group]))))"
    )
    assert groups["sensor.nibe_s1155_ute"] == "sensor"
    assert groups["number.nibe_s1155_kurva"] == "config"
    assert groups["sensor.nibe_s1155_tillverkad"] == "diagnostic"
    assert groups["switch.nibe_s1155_elpatron"] == "control"


def test_the_device_name_prefix_is_dropped():
    names = _run(HASS + "console.log(JSON.stringify(c.collectRows(hass, null).map(r => r.name)))")
    assert "Utetemperatur" in names
    assert not any(name.startswith("NIBE S1155 ") for name in names)


def test_the_explanation_travels_with_the_row():
    row = _run(
        HASS
        + "console.log(JSON.stringify(c.collectRows(hass, null)"
        + ".find(r => r.entityId === 'sensor.nibe_s1155_ute')))"
    )
    assert row["description"] == "Utetemperatur (BT1)."
    assert row["register"] == 30002


def test_values_read_like_the_device_page():
    text = _run(
        HASS
        + "const t = c.textFor('sv'); console.log(JSON.stringify(["
        + "c.formatState(hass.states['sensor.nibe_s1155_ute'], t),"
        + "c.formatState(hass.states['switch.nibe_s1155_elpatron'], t),"
        + "c.formatState(undefined, t)]))"
    )
    assert text == ["13.6 °C", "av", "ej tillgänglig"]


def test_the_filter_searches_names_and_explanations():
    hits = _run(
        "console.log(JSON.stringify(["
        "c.matchesFilter('kurva', 'Värmekurva', ''),"
        "c.matchesFilter('bt1', 'Utetemperatur', 'Utetemperatur (BT1).'),"
        "c.matchesFilter('ute bt1', 'Utetemperatur', 'Utetemperatur (BT1).'),"
        "c.matchesFilter('pool', 'Utetemperatur', ''),"
        "c.matchesFilter('', 'x', '')]))"
    )
    assert hits == [True, True, True, False, True]


def test_an_unrelated_state_change_does_not_redraw():
    same = _run(
        HASS
        + "const rows = c.collectRows(hass, null); const before = c.signature(hass, rows);"
        + "hass.states['sensor.pool_temp'] = {state: '25', attributes: {}};"
        + "const afterPool = c.signature(hass, rows);"
        + "hass.states['sensor.nibe_s1155_ute'] = {state: '14.0', attributes: {}};"
        + "const afterNibe = c.signature(hass, rows);"
        + "console.log(JSON.stringify([before === afterPool, before === afterNibe]))"
    )
    assert same == [True, False]


def test_language_falls_back_to_english():
    labels = _run(
        "console.log(JSON.stringify([c.textFor('sv').config, c.textFor('en').config,"
        " c.textFor('de').config, c.textFor(undefined).config]))"
    )
    assert labels == ["Inställningar", "Settings", "Settings", "Settings"]
