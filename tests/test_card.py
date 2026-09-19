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
        " c.textFor('de').config, c.textFor('nl').config, c.textFor(undefined).config]))"
    )
    assert labels == ["Inställningar", "Settings", "Einstellungen", "Settings", "Settings"]


# ----------------------------------------------------- controls and graphs

#: Names and titles as the two series actually spell them, from the S1155 and
#: the F1255-16 CU this was built against.
CONTROLS = """
const controls = [
  ["Värmekurva", "Heating curve"],
  ["Kurvförskjutning", "Heating offset climate system 1"],
  ["Gradminuter", "Degree Minutes (16 bit)"],
  ["Värmeläge", ""],
  ["Tillåt elpatron", "Allow add. heat"],
  ["Allow heating", "Allow heating"],
  ["Driftläge", "Operating mode"],
  ["Semesterläge", "Holiday mode"],
  ["Varmvattenläge", "Hot water mode"],
  ["Tillfällig lyx", "Temporary lux"],
  ["Varmvattenboost", "Hot water boost"],
  ["Vid larm: sänk VV", "Alarm action lower HW temperature"],
  ["Återställ larm", "Reset alarm"],
  ["KB-pump, läge (ställ)", "Operating mode brine medium pump"],
  ["Frånluftsfläkt, normal", "Exhaust air fan speed normal"],
  ["VB-pump, min varvtal", "Minimum permitted speed"],
  ["Justering BT12", "Adjustment BT12"],
];
"""


def test_controls_are_grouped_by_what_they_do():
    groups = _run(
        CONTROLS
        + "console.log(JSON.stringify(controls.map(([name, title]) =>"
        + " c.controlGroupOf({name, nibeTitle: title}))))"
    )
    assert groups == [
        "heating", "heating", "heating", "heating",
        "operation", "heating", "operation", "operation",
        "hotwater", "hotwater", "hotwater",
        "operation", "operation",
        "air", "air", "air",
        "other",
    ]


def test_a_number_gets_a_slider_only_when_it_can_be_aimed_at():
    kinds = _run(
        "console.log(JSON.stringify(["
        # the heating curve, 0-15 in whole steps
        "c.widgetFor('number.curve', {min: 0, max: 15, step: 1}),"
        # degree minutes, -3000 to 3000 in tenths: 60 000 positions
        "c.widgetFor('number.dm', {min: -3000, max: 3000, step: 0.1}),"
        "c.widgetFor('number.fan', {min: 0, max: 100, step: 1}),"
        "c.widgetFor('number.immersion', {min: 0, max: 45, step: 0.01}),"
        "c.widgetFor('number.unknown', {}),"
        "c.widgetFor('select.mode', {}), c.widgetFor('switch.add', {}),"
        "c.widgetFor('button.reset', {}), c.widgetFor('sensor.bt1', {})]))"
    )
    assert kinds == [
        "slider", "number", "slider", "number", "number",
        "select", "toggle", "button", "text",
    ]


def test_only_writable_entities_reach_the_control_section_and_in_group_order():
    rows = _run(
        "const rows = ["
        "{entityId: 'sensor.bt1', name: 'Utetemperatur', nibeTitle: ''},"
        "{entityId: 'switch.add', name: 'Tillåt elpatron', nibeTitle: ''},"
        "{entityId: 'number.curve', name: 'Värmekurva', nibeTitle: ''},"
        "{entityId: 'select.hw', name: 'Varmvattenläge', nibeTitle: ''},"
        "{entityId: 'number.fan', name: 'Frånluftsfläkt, normal', nibeTitle: ''}];"
        "console.log(JSON.stringify(c.controlRows(rows).map(r => r.entityId)))"
    )
    assert rows == ["number.curve", "select.hw", "switch.add", "number.fan"]


GRAPH_ROWS = """
const rows = [
  {entityId: "sensor.bt1", name: "Utetemperatur", nibeTitle: "BT1 Outdoor Temperature",
   deviceClass: "temperature", stateClass: "measurement", isCop: false},
  {entityId: "sensor.bt2", name: "Framledning", nibeTitle: "BT2 Supply temp S1",
   deviceClass: "temperature", stateClass: "measurement", isCop: false},
  {entityId: "sensor.bt3", name: "Returledning", nibeTitle: "EB100-EP14-BT3 Return temp",
   deviceClass: "temperature", stateClass: "measurement", isCop: false},
  {entityId: "sensor.bt50", name: "Rumstemperatur", nibeTitle: "BT50 Room Temp S1",
   deviceClass: "temperature", stateClass: "measurement", isCop: false},
  {entityId: "sensor.freq", name: "Kompressorfrekvens", nibeTitle: "Compressor Frequency, Actual",
   deviceClass: "frequency", stateClass: "measurement", isCop: false},
  {entityId: "number.dm", name: "Gradminuter", nibeTitle: "Degree Minutes (16 bit)",
   deviceClass: "", stateClass: "", isCop: false},
  {entityId: "sensor.out", name: "Tot. produktion", nibeTitle: "Tot. production",
   deviceClass: "energy", stateClass: "total_increasing", isCop: false},
  {entityId: "sensor.in", name: "Tot. förbrukning", nibeTitle: "Tot. consumption",
   deviceClass: "energy", stateClass: "total_increasing", isCop: false},
  {entityId: "sensor.cop_day", name: "COP, dygn", nibeTitle: "", isCop: true},
];
"""


def test_graphs_are_picked_from_what_the_pump_reports():
    graphs = _run(GRAPH_ROWS + "console.log(JSON.stringify(c.pickGraphs(rows)))")
    assert [g["key"] for g in graphs] == ["temps", "compressor", "cop", "energy"]
    # The room sensor is a temperature too, but the graph is about the circuit.
    assert graphs[0]["entities"] == ["sensor.bt1", "sensor.bt2", "sensor.bt3"]
    assert graphs[1]["entities"] == ["sensor.freq", "number.dm"]
    assert graphs[2]["entities"] == ["sensor.cop_day"]
    assert graphs[3]["entities"] == ["sensor.out", "sensor.in"]


def test_a_pump_without_a_coefficient_of_performance_gets_no_such_graph():
    keys = _run(
        GRAPH_ROWS
        + "console.log(JSON.stringify(c.pickGraphs(rows.filter(r => !r.isCop))"
        + ".map(g => g.key)))"
    )
    assert "cop" not in keys


def test_counters_are_drawn_from_the_statistics_and_the_rest_from_history():
    configs = _run(
        GRAPH_ROWS
        + "const t = c.textFor('sv');"
        + "console.log(JSON.stringify(c.pickGraphs(rows).map(g => c.graphConfig(g, t))))"
    )
    temps, _compressor, cop, energy = configs
    assert temps["type"] == "history-graph" and temps["hours_to_show"] == 24
    assert temps["title"] == "Temperaturer, ett dygn"
    assert energy["type"] == "statistics-graph"
    assert energy["stat_types"] == ["change"] and energy["chart_type"] == "bar"
    assert energy["period"] == "day" and energy["days_to_show"] == 30
    assert cop["stat_types"] == ["mean"] and cop["chart_type"] == "line"


def test_a_control_writes_through_its_own_service():
    calls = _run(
        "console.log(JSON.stringify(["
        "c.serviceFor('select.hw', 'Luxury'),"
        "c.serviceFor('number.curve', '7'),"
        "c.serviceFor('switch.add', true),"
        "c.serviceFor('switch.add', false),"
        "c.serviceFor('button.reset', null),"
        "c.serviceFor('sensor.bt1', 1)]))"
    )
    assert calls[0] == {
        "domain": "select", "service": "select_option",
        "data": {"entity_id": "select.hw", "option": "Luxury"},
    }
    assert calls[1] == {
        "domain": "number", "service": "set_value",
        "data": {"entity_id": "number.curve", "value": 7},
    }
    assert calls[2]["service"] == "turn_on"
    assert calls[3]["service"] == "turn_off"
    assert calls[4] == {
        "domain": "button", "service": "press", "data": {"entity_id": "button.reset"},
    }
    assert calls[5] is None


OVERVIEW_ROWS = GRAPH_ROWS.replace("];", """
  {entityId: "sensor.alarm", name: "Larm", nibeTitle: "Alarm", isAlarm: true},
  {entityId: "sensor.prio", name: "Driftprioritering", nibeTitle: "Prio",
   deviceClass: "", stateClass: "", isCop: false},
  {entityId: "select.mode", name: "Värmeläge", nibeTitle: "", isCop: false},
];""")


def test_the_overview_leads_with_the_alarm_and_the_mode():
    picked = _run(OVERVIEW_ROWS + "console.log(JSON.stringify(c.pickOverview(rows)))")
    assert [row["entityId"] for row in picked["status"]] == [
        "sensor.alarm", "sensor.prio", "select.mode",
        # How well it is working is part of "right now" too.
        "sensor.cop_day",
    ]
    # The readings are the circuit, and never repeat what the status shows.
    assert [row["entityId"] for row in picked["readings"]][:3] == [
        "sensor.bt1", "sensor.bt2", "sensor.bt3",
    ]
    assert "sensor.prio" not in [row["entityId"] for row in picked["readings"]]
    assert [row["entityId"] for row in picked["cop"]] == ["sensor.cop_day"]


def test_the_overview_has_no_efficiency_when_the_pump_has_none():
    cop = _run(
        OVERVIEW_ROWS
        + "console.log(JSON.stringify(c.pickOverview(rows.filter(r => !r.isCop)).cop))"
    )
    assert cop == []


def test_the_day_stands_on_the_chip_and_the_year_among_the_key_figures():
    """How the pump is running right now is the day's figure; the year's is one
    key figure among the others, and neither needs a card of its own."""
    picked = _run(
        """const rows = [
          {entityId: "sensor.cop_day", name: "Värmefaktor (COP), dygn",
           isCop: true, copSpan: "day", state: "3.12"},
          {entityId: "sensor.cop_year", name: "Värmefaktor (COP), år",
           isCop: true, copSpan: "year", state: "4.18"},
          {entityId: "sensor.bt1", name: "Utetemperatur", nibeTitle: "BT1 Outdoor Temperature"},
        ];
        const p = c.pickOverview(rows);
        console.log(JSON.stringify(
          [p.status.map(r => r.entityId), p.readings.map(r => r.entityId)]))"""
    )
    status, readings = picked
    assert status == ["sensor.cop_day"]
    assert readings[0] == "sensor.cop_year"


def test_the_span_that_always_has_a_figure_stands_among_the_key_figures():
    """The rolling year waits for a year of samples; the pump's whole life is
    counted from the day it was installed and is there at once."""
    picked = _run(
        """const rows = [
          {entityId: "sensor.cop_day", name: "COP, dygn", isCop: true, copSpan: "day",
           state: "3.12"},
          {entityId: "sensor.cop_year", name: "COP, år", isCop: true, copSpan: "year",
           state: "unknown"},
          {entityId: "sensor.cop_life", name: "COP, livstid", isCop: true,
           copSpan: "lifetime", state: "4.18"},
        ];
        const p = c.pickOverview(rows);
        const graphs = c.pickGraphs(rows).filter(g => g.key === "cop");
        console.log(JSON.stringify([
          p.status.map(r => r.entityId),
          p.readings.map(r => r.entityId),
          graphs.length ? graphs[0].entities : [],
        ]))"""
    )
    status, readings, graphed = picked
    assert status == ["sensor.cop_day"]
    assert readings == ["sensor.cop_life"]
    # The graph is of the two spans that move; a lifetime line barely does.
    assert graphed == ["sensor.cop_day", "sensor.cop_year"]
    source = CARD.read_text(encoding="utf-8")
    assert "copCard" not in source


def test_every_value_on_the_page_carries_its_explanation():
    """The blue "i" is not only for the controls: the chips and the key figures
    carry one too, so nothing on the overview is a number without a meaning."""
    source = CARD.read_text(encoding="utf-8")
    # One button, built in one place, used everywhere.
    assert source.count('why.textContent = "\u24d8"') == 1
    assert source.count("this.explainButton(") == 3  # controls, tiles, chips
    assert "explainButton(row, text, (open) => { note.hidden = !open; })" in source


def test_an_explanation_that_arrives_late_still_gets_its_i():
    """An unavailable entity carries no attributes, so a card built during a
    restart has no explanations. The structure counts them, so it is built
    again when they arrive, and the page remembers the ones it has seen."""
    marks = _run(
        """const quiet = [{entityId: "sensor.bt1", name: "Ute", description: ""}];
        const loud = [{entityId: "sensor.bt1", name: "Ute", description: "Mäter ute."}];
        console.log(JSON.stringify([c.structureOf(quiet), c.structureOf(loud)]))"""
    )
    assert marks == ["sensor.bt1", "sensor.bt1!"]
    source = CARD.read_text(encoding="utf-8")
    # The explanation is kept over the entity's quiet spells.
    assert "this.descriptions.set(row.entityId, row.description)" in source
    assert 'row.description = this.descriptions.get(row.entityId) || ""' in source
    assert "this.remember(collectRows(this.hass, this.deviceId))" in source


def test_the_performance_graphs_keep_their_own_heights():
    """A grid row is as tall as its tallest card, which left a day of
    temperatures stretched out beside a taller graph. The tab fills two columns
    itself instead, so the next graph follows directly underneath."""
    source = CARD.read_text(encoding="utf-8")
    assert 'this.graphsBody.className = "graphs flow"' in source
    assert ".graphs.flow > .column { display: flex; flex-direction: column;" in source
    assert "columns[index % columns.length]" in source


def test_the_registered_accessories_stand_under_their_own_heading():
    """What the pump answers about its own accessories is a question of its
    own - a pool flag that says no is half the answer - so the flags are
    gathered rather than left among three hundred settings."""
    groups = _run(
        """const entry = {entity_category: "config"};
        console.log(JSON.stringify([
          c.groupOf(entry, "switch", "Pool 1 accessory"),
          c.groupOf(entry, "switch", "FLM 2 accessory"),
          c.groupOf(entry, "switch", "MODBUS40 Disable LOG.SET"),
          c.groupOf(entry, "select", "RMU System 1"),
          c.groupOf(entry, "number", "Heat Curve S1"),
          c.groupOf({entity_category: "diagnostic"}, "sensor", "Prio"),
        ]))"""
    )
    assert groups == [
        "accessories", "accessories", "accessories", "accessories", "config", "diagnostic",
    ]
    assert _run("console.log(JSON.stringify(c.GROUP_ORDER))")[0] == "accessories"
    words = _run(
        "console.log(JSON.stringify([c.textFor('sv').accessories, c.textFor('en').accessories]))"
    )
    assert words == ["Registrerade tillbehör", "Accessories registered"]


def test_an_accessory_the_pump_has_reads_green_and_one_it_lacks_red():
    """The point of the section is which is which, so the answer is coloured
    rather than left as another word in a list."""
    answers = _run(
        """const flag = {group: "accessories"};
        console.log(JSON.stringify([
          c.accessoryAnswer(flag, {state: "on"}),
          c.accessoryAnswer(flag, {state: "off"}),
          c.accessoryAnswer(flag, {state: "Off"}),
          c.accessoryAnswer(flag, {state: "Use LOG.SET"}),
          c.accessoryAnswer(flag, {state: "unavailable"}),
          c.accessoryAnswer({group: "sensor"}, {state: "on"}),
        ]))"""
    )
    assert answers == ["found", "missing", "missing", "found", "", ""]
    source = CARD.read_text(encoding="utf-8")
    assert ".value.found { color: var(--success-color" in source
    assert ".value.missing { color: var(--error-color" in source


def test_the_tabs_end_with_every_value():
    tabs = _run("console.log(JSON.stringify(c.TAB_ORDER))")
    assert tabs[0] == "overview"
    assert tabs[-1] == "values"


def test_the_page_speaks_the_language_the_entities_were_named_in():
    """Home Assistant in English with a Swedish viewer: the entity names are
    English, so the headings have to be too, or the page reads as two."""
    languages = _run(
        "console.log(JSON.stringify(["
        "c.languageOf({config: {language: 'en'}, locale: {language: 'sv'}}),"
        "c.languageOf({config: {language: 'sv'}, locale: {language: 'en'}}),"
        "c.languageOf({locale: {language: 'sv'}}),"
        "c.languageOf({}),"
        "c.textFor(c.languageOf({config: {language: 'en'}, locale: {language: 'sv'}})).controls]))"
    )
    assert languages == ["en", "sv", "sv", "", "Controls"]


def test_the_page_is_ready_for_more_languages():
    """German and French are there in full; an unknown one reads as English."""
    words = _run(
        "console.log(JSON.stringify(["
        "c.textFor('de').overview, c.textFor('fr').overview,"
        "c.textFor('nl').overview,"
        "Object.keys(c.textFor('en')).every(k => k in c.textFor('de')),"
        "Object.keys(c.textFor('en')).every(k => k in c.textFor('fr'))]))"
    )
    assert words == ["Übersicht", "Vue d'ensemble", "Overview", True, True]


QUICK_ROWS = """
const rows = [
  {entityId: "select.heating_mode", name: "Värmeläge", nibeTitle: ""},
  {entityId: "select.hot_water", name: "Varmvattenläge", nibeTitle: "Hot water comfort mode"},
  {entityId: "switch.boost", name: "Varmvattenboost", nibeTitle: ""},
  {entityId: "select.holiday", name: "Semesterläge", nibeTitle: "Holiday mode"},
  {entityId: "select.flm_fan", name: "FLM 1 fläkt", nibeTitle: "FLM 1 fan"},
  {entityId: "number.defrost_time", name: "Avfrostningstid", nibeTitle: "Defrosting time (FLM 1)"},
  {entityId: "number.fan_normal", name: "Frånluftsfläkt, normal",
   nibeTitle: "Exhaust air fan speed normal"},
  {entityId: "number.fan_1", name: "Fläkthastighet 1", nibeTitle: "Exhaust air fan speed 1"},
  {entityId: "number.fan_2", name: "Fläkthastighet 2", nibeTitle: "Exhaust air fan speed 2"},
  {entityId: "number.curve", name: "Värmekurva", nibeTitle: "Heating curve"},
  {entityId: "sensor.bt1", name: "Utetemperatur", nibeTitle: "BT1 Outdoor Temperature"},
];
"""


def test_the_overview_carries_the_controls_that_matter():
    picked = _run(
        QUICK_ROWS
        + "console.log(JSON.stringify(c.pickQuickControls(rows).map(r => r.entityId)))"
    )
    assert picked == [
        "select.heating_mode",      # how the heating runs
        "select.hot_water", "switch.boost",  # how the hot water runs, then the boost
        "select.holiday",           # whether anybody is home
        "select.flm_fan",           # what the exhaust air module's fan is doing
        "number.fan_normal",        # and the airflow it holds at normal speed
    ]
    # A reading is not a control, and the curve belongs on the controls tab.
    assert "sensor.bt1" not in picked
    assert "number.curve" not in picked
    # The scheduled speeds and the module's service settings belong there too:
    # the overview keeps the two controls an owner actually reaches for.
    assert "number.fan_1" not in picked
    assert "number.fan_2" not in picked
    assert "number.defrost_time" not in picked


def test_a_pump_without_an_exhaust_air_module_gets_no_fans():
    """A ground source pump has no exhaust air module; nothing is shown for it."""
    picked = _run(
        QUICK_ROWS
        + "console.log(JSON.stringify(c.pickQuickControls("
        + "rows.filter(r => !/fan|fläkt/i.test(r.entityId + r.name))).map(r => r.entityId)))"
    )
    assert picked == ["select.heating_mode", "select.hot_water", "switch.boost", "select.holiday"]


def test_the_overview_shows_the_figure_that_has_a_number():
    """On a mild day the daily coefficient of performance has nothing to divide
    by; the chip then carries the yearly one instead of an empty value."""
    picked = _run(
        """const rows = [
          {entityId: "sensor.cop_day", name: "COP, dygn", isCop: true, state: "unknown"},
          {entityId: "sensor.cop_year", name: "COP, år", isCop: true, state: "4.18"},
        ];
        console.log(JSON.stringify(c.pickOverview(rows).status.map(r => r.entityId)))"""
    )
    assert picked == ["sensor.cop_year"]


def test_the_overview_puts_the_controls_beside_the_graph():
    """The card's own layout, checked in the source: the controls and the graph
    share one row, controls to the left, and both boxes take the same height."""
    source = CARD.read_text(encoding="utf-8")
    assert 'this.overviewRow.className = "beside"' in source
    assert "this.overviewRow.append(this.quickCard, this.overviewGraphs)" in source
    assert (
        ".beside { display: grid; gap: 16px; align-items: stretch; margin-bottom: 16px;"
        in source
    )
    assert ".beside > .graphs > * { height: 100%; }" in source
