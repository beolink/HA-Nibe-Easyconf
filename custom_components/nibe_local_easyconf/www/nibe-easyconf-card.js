/* Nibe Local Easyconf — the heat pump on one page: control it, see how it is
 * doing, and read every value with its explanation.
 *
 * Served by the integration at /nibe_local_easyconf/nibe-easyconf-card.js and
 * used two ways:
 *
 *   - as the "NIBE" sidebar panel the integration registers on its own, so a
 *     user gets the page without editing any dashboard;
 *   - as a card for their own dashboards (the resource is auto-registered on
 *     storage-mode Lovelace):
 *
 *       type: custom:nibe-easyconf-card
 *       device_id: <optional, when there is more than one pump>
 *       tabs: [overview, controls, performance, values]  # optional, the default
 *
 * The page has four tabs:
 *
 *   1. **Overview.** What the pump is doing right now: its mode, the alarm, the
 *      temperatures around the circuit, the compressor, and the coefficient of
 *      performance, in that order, with one graph of the last day.
 *   2. **Controls.** Everything writable, as the thing it is - a dropdown, a
 *      slider, a toggle - grouped by what it does to the house rather than by
 *      Home Assistant's entity domain: heating, hot water, operation, fans and
 *      pumps. Reading a setting off a list and then hunting for it in a dialog
 *      is what this page existed to avoid.
 *   3. **Performance.** Graphs, built from Home Assistant's own history and
 *      statistics cards through `loadCardHelpers`. They are a bonus: if that
 *      ever goes away the tab hides itself and the rest still works.
 *   4. **All values.** The full list with the filter, each row with its
 *      explanation, as before.
 *
 * Why the page exists at all: Home Assistant's device page cuts entity names at
 * roughly 25 characters, fixes its own column count from the window width, and
 * has no way to show an entity's explanation on hover.
 *
 * The explanation is shown on hover through the title attribute, and also on
 * tap, written out under the row: a title attribute alone is invisible on a
 * phone and to a screen reader, which is the lesson the EMS grid card learned
 * the hard way.
 *
 * Every string from Home Assistant goes into the page as text, never as HTML.
 *
 * The pure helpers at the top are loaded by tests/test_card.py in node, which
 * is why the custom elements are only defined in a browser.
 */

const DOMAIN = "nibe_local_easyconf";

const TEXT = {
  sv: {
    accessories: "Registrerade tillbehör",
    sensor: "Mätvärden",
    control: "Styrning",
    config: "Inställningar",
    diagnostic: "Diagnostik",
    filter: "Filtrera…",
    empty: "Inga entiteter från Nibe Local Easyconf ännu.",
    none: "Inget matchar filtret.",
    details: "Mer info",
    unavailable: "ej tillgänglig",
    on: "på",
    off: "av",
    title: "NIBE värmepump",
    overview: "Översikt",
    controls: "Styrning",
    performance: "Prestanda",
    values: "Alla värden",
    quick: "Snabbstyrning",
    now: "Just nu",
    readings: "Nyckeltal",
    heating: "Värme",
    hotwater: "Varmvatten",
    operation: "Drift",
    air: "Fläkt och pumpar",
    other: "Övrigt",
    graphTemps: "Temperaturer, ett dygn",
    graphCompressor: "Kompressorn, ett dygn",
    graphEnergy: "Energi per dygn",
    graphCop: "Värmefaktor per dygn",
    noControls: "Inget styrbart värde är påslaget.",
    explain: "Förklaring",
  },
  de: {
    accessories: "Registriertes Zubehör",
    sensor: "Messwerte",
    control: "Steuerung",
    config: "Einstellungen",
    diagnostic: "Diagnose",
    filter: "Filtern…",
    empty: "Noch keine Entitäten von Nibe Local Easyconf.",
    none: "Nichts entspricht dem Filter.",
    details: "Mehr Info",
    unavailable: "nicht verfügbar",
    on: "an",
    off: "aus",
    title: "NIBE Wärmepumpe",
    overview: "Übersicht",
    controls: "Steuerung",
    performance: "Leistung",
    values: "Alle Werte",
    quick: "Schnellsteuerung",
    now: "Jetzt",
    readings: "Kennzahlen",
    heating: "Heizung",
    hotwater: "Warmwasser",
    operation: "Betrieb",
    air: "Lüfter und Pumpen",
    other: "Sonstiges",
    graphTemps: "Temperaturen, 24 Stunden",
    graphCompressor: "Der Verdichter, 24 Stunden",
    graphEnergy: "Energie pro Tag",
    graphCop: "Leistungszahl pro Tag",
    noControls: "Kein steuerbarer Wert ist eingeschaltet.",
    explain: "Erklärung",
  },
  fr: {
    accessories: "Accessoires enregistrés",
    sensor: "Mesures",
    control: "Commandes",
    config: "Réglages",
    diagnostic: "Diagnostic",
    filter: "Filtrer…",
    empty: "Aucune entité de Nibe Local Easyconf pour l'instant.",
    none: "Rien ne correspond au filtre.",
    details: "Plus d'infos",
    unavailable: "indisponible",
    on: "activé",
    off: "désactivé",
    title: "Pompe à chaleur NIBE",
    overview: "Vue d'ensemble",
    controls: "Commandes",
    performance: "Performance",
    values: "Toutes les valeurs",
    quick: "Commandes rapides",
    now: "En ce moment",
    readings: "Chiffres clés",
    heating: "Chauffage",
    hotwater: "Eau chaude",
    operation: "Fonctionnement",
    air: "Ventilateurs et pompes",
    other: "Divers",
    graphTemps: "Températures, 24 heures",
    graphCompressor: "Le compresseur, 24 heures",
    graphEnergy: "Énergie par jour",
    graphCop: "Coefficient de performance par jour",
    noControls: "Aucune valeur réglable n'est activée.",
    explain: "Explication",
  },
  en: {
    accessories: "Accessories registered",
    sensor: "Readings",
    control: "Controls",
    config: "Settings",
    diagnostic: "Diagnostics",
    filter: "Filter…",
    empty: "No entities from Nibe Local Easyconf yet.",
    none: "Nothing matches the filter.",
    details: "More info",
    unavailable: "unavailable",
    on: "on",
    off: "off",
    title: "NIBE heat pump",
    overview: "Overview",
    controls: "Controls",
    performance: "Performance",
    values: "All values",
    quick: "Quick controls",
    now: "Right now",
    readings: "Key readings",
    heating: "Heating",
    hotwater: "Hot water",
    operation: "Operation",
    air: "Fans and pumps",
    other: "Other",
    graphTemps: "Temperatures, 24 hours",
    graphCompressor: "The compressor, 24 hours",
    graphEnergy: "Energy per day",
    graphCop: "Coefficient of performance, daily",
    noControls: "No writable value is switched on.",
    explain: "Explanation",
  },
};

const GROUP_ORDER = ["accessories", "sensor", "control", "config", "diagnostic"];

/** What the pump answers about its own accessories: the flags a scan reads to
 *  know whether a pool, an exhaust air module or a room unit is fitted, and the
 *  settings of the gateway it talks through. They stand together at the top of
 *  the list, because "what is registered here" is a question of its own. */
const ACCESSORY_PATTERN =
  /\baccessory\b|\btillbehör\b|^rmu system|^opt$|modbus ?40|sms ?40|^ers [1-4]$|^hts [1-4]$/i;
const TAB_ORDER = ["overview", "controls", "performance", "values"];
const CONTROL_DOMAINS = ["select", "number", "switch", "button"];
const CONTROL_GROUP_ORDER = ["heating", "hotwater", "operation", "air", "other"];

/** Which part of the house a writable value belongs to. The first rule that
 *  matches decides, and the order is what makes it right: an alarm action that
 *  lowers the hot water is about operation, a brine pump whose title is
 *  "operating mode brine medium pump" is a pump, and "allow additional heat"
 *  is about operation rather than heating even though it says heat. Matched
 *  against the entity's name and NIBE's own title, so both languages and both
 *  series land in the same places. */
const CONTROL_RULES = [
  ["operation", /larm|alarm/i],
  ["hotwater", /varmvatten|hot ?water|\bvv\b|\bhw\b|lyx|lux/i],
  ["air", /fläkt|\bfan\b|frånluft|exhaust|pump|brine|köldbärar|\bkb-|\bvb-|defrost|avfrost|filter/i],
  ["operation", /driftläge|operating mode|elpatron|immersion|add(?:itional)?\.? ?heat|tillskott|semester|holiday|smart ?(?:control|price)/i],
  ["heating", /värme|heat|kurv|curve|gradminut|degree ?minute|framledning|supply|\brum\b|room|kyla|cooling/i],
];

//: The overview, in the order the questions come: what is the pump doing, how
//: warm is everything, and how hard is the compressor working. Each line is
//: matched by several spellings, since the S- and F-series maps word their
//: registers differently.
const STATUS_PATTERNS = [
  // What the pump is doing, by the name it was given: NIBE titles two S-series
  // registers "Priority" and only one of them answers in words, so matching
  // the title would put the other on the chip. See names.REGISTER_NAMES.
  /^status$|driftprioritering/i,
  /värmeläge|heating mode/i,
  /driftläge|operating mode/i,
  /varmvattenläge|hot ?water mode/i,
];

const READING_PATTERNS = [
  // The temperature the house is about, on a pump that has a room sensor. The
  // S-series answers it as an average per climate system, so both spellings -
  // and anchored, because "alarm action, lower room temperature" is a switch.
  /\(BT50\)|^BT50\b|^room average temp|^rumstemperatur/i,
  /BT1 Outdoor|outdoor temperature|utetemperatur/i,
  /BT2 Supply|^supply line|^framledning/i,
  /BT3 Return|^return line|^returledning/i,
  /calc\.? supply|beräknad framledning|calculated supply/i,
  /BT7 HW|hot water top|varmvatten topp/i,
  /BT6 HW|hot water charging|varmvattenladdning/i,
  /BT10 Brine|brine in|köldbärare in/i,
  /BT11 Brine|brine out|köldbärare ut/i,
  /compressor frequency, actual|^compressor frequency$|^kompressorfrekvens$/i,
  /compr\.? in power|compressor power input$/i,
  /degree ?minutes|^gradminuter$/i,
];

//: The handful of controls the overview carries, in the order they matter to
//: someone standing in the house: how the heating runs, how the hot water runs,
//: whether anybody is home, and the exhaust air module's fans. Only what the
//: pump actually has shows up, so a ground source pump without a module simply
//: has no fans here.
const QUICK_CONTROLS = [
  { pattern: /värmeläge|heating mode/i, limit: 1 },
  { pattern: /varmvattenläge|hot ?water (comfort |demand )?mode/i, limit: 1 },
  { pattern: /varmvattenboost|hot ?water boost|tillfällig lyx|temporary lux/i, limit: 1 },
  { pattern: /semester|holiday|vacation/i, limit: 1 },
  // The exhaust air module belongs here through the control that runs it, its
  // fan selector, and not through its service settings.
  { pattern: /frånluftsmodul|exhaust air module|\bflm\b\s*\d*\s*(?:fan|fläkt)|fan ?mode(?!\s*\d)|fläktläge(?!\s*\d)/i, limit: 1 },
  // Normal airflow, the one figure an owner changes; speeds 1 to 4 belong to
  // the schedule and stay under Controls.
  { pattern: /(frånluftsfläkt|exhaust air fan|exhaust fan speed|fläkthastighet)(?!.*\b[1-4]\b)/i, limit: 1 },
];

/** The controls the overview puts at the top, in QUICK_CONTROLS' order. */
function pickQuickControls(rows) {
  const writable = controlRows(rows);
  const picked = [];
  for (const { pattern, limit } of QUICK_CONTROLS) {
    const matches = writable.filter(
      (row) =>
        !picked.includes(row) &&
        (pattern.test(row.nibeTitle || "") || pattern.test(row.name || ""))
    );
    picked.push(...matches.slice(0, limit));
  }
  return picked;
}

/** What the overview shows: the pump's own state, and the numbers that say how
 *  it is doing. The coefficient of performance has no card of its own; how the
 *  pump is running right now is the day's figure, and the year's is one key
 *  figure among the others. */
function pickOverview(rows) {
  const modes = pickByPatterns(rows, STATUS_PATTERNS, 4);
  const alarm = rows.filter((row) => row.isAlarm).slice(0, 1);
  const cop = rows.filter((row) => row.isCop);
  const day = cop.filter((row) => row.copSpan === "day");
  // A pump whose sensors carry no span keeps the old rule: the figure that has
  // a number stands on the chip, rather than an empty "unavailable".
  const chip = day.length
    ? day.slice(0, 1)
    : cop.slice().sort((a, b) => Number(hasNumber(b)) - Number(hasNumber(a))).slice(0, 1);
  const status = alarm.concat(modes, chip);
  const rest = cop.filter((row) => !status.includes(row));
  // Of the longer spans, the one that always has a figure: the whole lifetime,
  // which an S-series pump has counted since it was installed. The rolling
  // year waits for a year of samples, and stands on the performance tab and in
  // the list until it has them.
  const lifetime = rest.filter((row) => row.copSpan === "lifetime");
  const readings = (lifetime.length ? lifetime : rest).concat(
    pickByPatterns(
      rows.filter((row) => !status.includes(row) && !rest.includes(row)),
      READING_PATTERNS,
      9
    )
  );
  return { status, readings, cop };
}

/** The language the page speaks. Home Assistant has two: the system language,
 *  which is the one the integration named the entities in, and the language of
 *  the person looking. Following the viewer would leave English entity names
 *  under Swedish headings on an English installation, so the system language
 *  wins and the whole page reads as one. */
function languageOf(hass) {
  const config = (hass && hass.config && hass.config.language) || "";
  const viewer = (hass && hass.locale && hass.locale.language) || "";
  return config || viewer;
}

/** The chosen language's words, falling back to English for anything else. */
function textFor(language) {
  const code = String(language || "").slice(0, 2).toLowerCase();
  return TEXT[code] || TEXT.en;
}

/** Which section an entity belongs in, mirroring the device page's own. */
function groupOf(entry, domain, title) {
  // Before the entity category, since NIBE's flags are configuration and would
  // otherwise disappear among three hundred settings.
  if (ACCESSORY_PATTERN.test(title || "")) return "accessories";
  if (entry && entry.entity_category === "diagnostic") return "diagnostic";
  if (entry && entry.entity_category === "config") return "config";
  if (CONTROL_DOMAINS.includes(domain)) return "control";
  return "sensor";
}

/** Whether an accessory flag says the pump has that accessory. The flags are
 *  switches, selects and the odd sensor, so the state is read as a word: what
 *  is not a "no" is a "yes", which also colours a setting like the gateway's
 *  word swap. Anything without a value yet is neither. */
function accessoryAnswer(row, stateObj) {
  if (!row || row.group !== "accessories") return "";
  const state = String((stateObj && stateObj.state) || "").toLowerCase();
  if (!state || state === "unavailable" || state === "unknown") return "";
  return ["off", "av", "no", "nej", "0", "false", "aus", "non"].includes(state)
    ? "missing"
    : "found";
}

/** Which control group a writable row belongs to. */
function controlGroupOf(row) {
  const haystack = `${(row && row.name) || ""} ${(row && row.nibeTitle) || ""}`;
  for (const [group, pattern] of CONTROL_RULES) {
    if (pattern.test(haystack)) return group;
  }
  return "other";
}

/** The control a value deserves. A number gets a slider when its range has few
 *  enough steps to aim at; degree minutes, which run from -3000 to 3000 in
 *  tenths, would be a lottery, so those get a field to type in. */
function widgetFor(entityId, attributes) {
  const domain = String(entityId || "").split(".")[0];
  if (domain === "select") return "select";
  if (domain === "switch") return "toggle";
  if (domain === "button") return "button";
  if (domain !== "number") return "text";
  const attrs = attributes || {};
  const min = Number(attrs.min);
  const max = Number(attrs.max);
  const step = Number(attrs.step) || 1;
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return "number";
  return (max - min) / step <= 120 ? "slider" : "number";
}

/** A state as a person reads it: the value with its unit, or a word. */
function formatState(stateObj, text) {
  if (!stateObj) return text.unavailable;
  const value = stateObj.state;
  if (value === "unavailable" || value === "unknown") return text.unavailable;
  if (value === "on") return text.on;
  if (value === "off") return text.off;
  const unit = stateObj.attributes && stateObj.attributes.unit_of_measurement;
  return unit ? `${value} ${unit}` : String(value);
}

/** True when every word of the filter appears in the name or explanation. */
function matchesFilter(filter, name, description) {
  const words = String(filter || "").toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const haystack = `${name || ""} ${description || ""}`.toLowerCase();
  return words.every((word) => haystack.includes(word));
}

/** Collect this integration's entities from hass, grouped and sorted.
 *
 * `hass.entities` is the entity registry as the frontend sees it; only
 * entities present in `hass.states` are enabled, so disabled ones - most of
 * the ~900 registers - never appear here.
 */
function collectRows(hass, deviceId) {
  const rows = [];
  const registry = (hass && hass.entities) || {};
  for (const entry of Object.values(registry)) {
    if (!entry || entry.platform !== DOMAIN) continue;
    if (deviceId && entry.device_id !== deviceId) continue;
    const stateObj = hass.states[entry.entity_id];
    if (!stateObj) continue;
    const domain = entry.entity_id.split(".")[0];
    const attributes = stateObj.attributes || {};
    const device = entry.device_id && hass.devices ? hass.devices[entry.device_id] : null;
    const deviceName = device ? device.name_by_user || device.name : null;
    rows.push({
      entityId: entry.entity_id,
      group: groupOf(entry, domain, attributes.nibe_title || ""),
      // Home Assistant prefixes the device name to every entity name; on a
      // page that is already about the pump it only pushes the value off.
      name: stripDeviceName(attributes.friendly_name || entry.entity_id, deviceName),
      description: attributes.description || "",
      nibeTitle: attributes.nibe_title || "",
      register: attributes.modbus_register,
      deviceClass: attributes.device_class || "",
      stateClass: attributes.state_class || "",
      // The coefficient of performance sensors are the only ones carrying a
      // basis, and they are what the performance graph is really about.
      isCop: attributes.basis !== undefined,
      // "day" or "year" on the coefficient of performance sensors: the day's
      // figure belongs to right now, the year's among the key figures.
      copSpan: attributes.span || "",
      // The state as a string, for picking between two of the same kind: the
      // day's coefficient of performance has no value on a mild day, when too
      // little electricity has been used to divide by.
      state: stateObj.state,
      // The alarm sensor is the one that reads out an alarm code in words.
      isAlarm: attributes.alarm_code !== undefined,
    });
  }
  rows.sort((a, b) => a.name.localeCompare(b.name));
  return rows;
}

/** The writable rows, in the order the control section shows them. */
function controlRows(rows) {
  const writable = rows.filter((row) =>
    CONTROL_DOMAINS.includes(row.entityId.split(".")[0])
  );
  return writable.sort((a, b) => {
    const left = CONTROL_GROUP_ORDER.indexOf(controlGroupOf(a));
    const right = CONTROL_GROUP_ORDER.indexOf(controlGroupOf(b));
    return left === right ? a.name.localeCompare(b.name) : left - right;
  });
}

/** The first row matching each pattern, at most `limit`, never twice.
 *  Patterns are matched against NIBE's title first, since that is the same
 *  wording on every installation, and then the user-visible name. */
/** How many component designations a title carries. A pump names the same
 *  reading twice - "Return line (BT3)" for the house's return and "Return line
 *  (EB100-BT3)" for the compressor module's - and the one with fewer
 *  designations is the one the house is about. */
function qualifiers(row) {
  return ((row && row.nibeTitle) || "").match(/\b[A-Z]{2}\d{1,3}\b/g)?.length || 0;
}

function pickByPatterns(rows, patterns, limit) {
  const picked = [];
  for (const pattern of patterns) {
    if (picked.length >= limit) break;
    const matches = rows.filter(
      (row) =>
        !picked.includes(row) &&
        (pattern.test(row.nibeTitle || "") || pattern.test(row.name || ""))
    );
    // Least qualified first, and among equals the order they came in.
    const hit = matches.length > 1
      ? matches.reduce((best, row) => (qualifiers(row) < qualifiers(best) ? row : best))
      : matches[0];
    if (hit) picked.push(hit);
  }
  return picked;
}

//: The series name their registers differently - "BT1 Outdoor Temperature" on
//: the F-series, "Current outdoor temperature (BT1)" on the S-series - so each
//: line is matched by several spellings, most wanted first.
const TEMPERATURE_PATTERNS = [
  /\(BT50\)|^BT50\b|^room average temp|^rumstemperatur/i,
  /BT1 Outdoor|outdoor temperature|utetemperatur/i,
  /BT2 Supply|^supply line|^framledning/i,
  /BT3 Return|^return line|^returledning/i,
  /BT7 HW|hot water top|varmvatten topp/i,
  /BT6 HW|hot water charging|varmvattenladdning/i,
  /BT10 Brine|brine in|köldbärare in/i,
  /BT11 Brine|brine out|köldbärare ut/i,
];

const COMPRESSOR_PATTERNS = [
  /compressor frequency, actual|^compressor frequency$|^kompressorfrekvens$/i,
  /compr\.? in power|compressor power input$|kompressor.*effekt/i,
  /degree ?minutes|^gradminuter$/i,
];

/** What the performance section draws, given what this pump reports.
 *
 * Each graph names the entities it needs; an empty one is left out, which is
 * how an F-series pump ends up without the coefficient of performance and a
 * pump without brine sensors without its brine lines.
 */
function pickGraphs(rows) {
  const graphs = [];
  const temps = pickByPatterns(
    rows.filter((row) => row.deviceClass === "temperature"),
    TEMPERATURE_PATTERNS,
    6
  );
  if (temps.length) graphs.push({ key: "temps", title: "graphTemps", entities: ids(temps) });

  const compressor = pickByPatterns(rows, COMPRESSOR_PATTERNS, 3);
  if (compressor.length) {
    graphs.push({ key: "compressor", title: "graphCompressor", entities: ids(compressor) });
  }

  // The day against the year: two spans that move. The lifetime figure is a
  // near-flat line and belongs among the key figures rather than in a graph.
  const cop = rows.filter((row) => row.isCop && row.copSpan !== "lifetime").slice(0, 2);
  if (cop.length) {
    graphs.push({ key: "cop", title: "graphCop", entities: ids(cop), statistic: "mean" });
  }

  const energy = rows
    .filter((row) => row.deviceClass === "energy" && row.stateClass === "total_increasing")
    .slice(0, 3);
  if (energy.length) {
    graphs.push({ key: "energy", title: "graphEnergy", entities: ids(energy), statistic: "change" });
  }
  return graphs;
}

function hasNumber(row) {
  return row && Number.isFinite(Number(row.state));
}

function ids(rows) {
  return rows.map((row) => row.entityId);
}

/** The same ids, marking which rows carry an explanation. A card built while
 *  its entities were unavailable - right after a restart, say - has none, and
 *  has to be built again once they arrive, or it keeps its missing ⓘ. */
function structureOf(rows) {
  return rows.map((row) => row.entityId + (row.description ? "!" : "")).join(",");
}

/** A graph as a Home Assistant card configuration. Counters are drawn from the
 *  long-term statistics, which is the only place a year of them survives; the
 *  rest come from the recorder's own history. */
function graphConfig(graph, text) {
  if (graph.statistic) {
    return {
      type: "statistics-graph",
      title: text[graph.title],
      entities: graph.entities,
      period: "day",
      days_to_show: 30,
      stat_types: [graph.statistic],
      chart_type: graph.statistic === "change" ? "bar" : "line",
    };
  }
  return {
    type: "history-graph",
    title: text[graph.title],
    hours_to_show: 24,
    entities: graph.entities,
  };
}

/** What the list currently shows, as one string. Home Assistant hands the card
 *  a new `hass` on every state change anywhere in the house - often several a
 *  second - and redrawing ~100 rows each time makes the hover text flicker.
 *  Comparing this skips every update that changes nothing on screen. */
function signature(hass, rows) {
  return rows
    .map((row) => {
      const stateObj = hass.states[row.entityId];
      return `${row.entityId}=${stateObj ? stateObj.state : ""}`;
    })
    .join("|");
}

/** Drop the device name that Home Assistant prefixes to every entity name. */
function stripDeviceName(name, deviceName) {
  if (deviceName && name.startsWith(`${deviceName} `)) {
    return name.slice(deviceName.length + 1);
  }
  return name;
}

/** The service call a control makes. Returned rather than called, so the
 *  mapping from widget to service is testable without Home Assistant. */
function serviceFor(entityId, value) {
  const domain = String(entityId || "").split(".")[0];
  if (domain === "select") {
    return { domain: "select", service: "select_option", data: { entity_id: entityId, option: value } };
  }
  if (domain === "number") {
    return { domain: "number", service: "set_value", data: { entity_id: entityId, value: Number(value) } };
  }
  if (domain === "switch") {
    return { domain: "switch", service: value ? "turn_on" : "turn_off", data: { entity_id: entityId } };
  }
  if (domain === "button") {
    return { domain: "button", service: "press", data: { entity_id: entityId } };
  }
  return null;
}

if (typeof module !== "undefined") {
  module.exports = {
    textFor, groupOf, formatState, matchesFilter, collectRows, stripDeviceName,
    signature, controlGroupOf, controlRows, widgetFor, pickGraphs, graphConfig,
    languageOf,
    pickByPatterns, serviceFor, pickOverview, pickQuickControls, hasNumber, structureOf,
    ACCESSORY_PATTERN, accessoryAnswer,
    GROUP_ORDER, CONTROL_GROUP_ORDER, TAB_ORDER, DOMAIN,
  };
}

/* ------------------------------------------------------------------ DOM -- */

if (typeof customElements !== "undefined") {
  const STYLE = `
    :host { display: block; }
    .wrap { padding: 16px; max-width: 1600px; margin: 0 auto; }
    .head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 16px; }
    h1 { font-size: 1.4rem; font-weight: 500; margin: 4px 0; color: var(--primary-text-color); }
    h3 { font-size: .95rem; font-weight: 500; margin: 0 0 8px; color: var(--primary-text-color); }
    .tabs {
      display: flex; gap: 4px; margin: 12px 0 16px; overflow-x: auto;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .tabs button {
      font: inherit; padding: 10px 16px; border: none; background: none; cursor: pointer;
      color: var(--secondary-text-color); border-bottom: 2px solid transparent; white-space: nowrap;
    }
    .tabs button[aria-selected="true"] {
      color: var(--primary-color, #03a9f4); border-bottom-color: var(--primary-color, #03a9f4);
    }
    .tabs button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: -2px; }
    .cards { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }
    .card {
      background: var(--ha-card-background, var(--card-background-color, #fff));
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.08));
      border: var(--ha-card-border-width, 0) solid var(--ha-card-border-color, transparent);
      padding: 14px 16px; margin-bottom: 16px;
    }
    .value.found { color: var(--success-color, #2e7d32); font-weight: 500; }
    .value.missing { color: var(--error-color, #db4437); }
    .chips { display: flex; flex-wrap: wrap; gap: 10px; }
    .chip {
      display: flex; gap: 8px; align-items: baseline; padding: 8px 14px; border-radius: 999px;
      background: var(--secondary-background-color, #f1f3f4);
    }
    .chip .label { color: var(--secondary-text-color); font-size: .8em; }
    .chip .value { color: var(--primary-text-color); font-weight: 500; }
    .chip.alarm-on { background: var(--error-color, #db4437); }
    .chip.alarm-on .label, .chip.alarm-on .value { color: #fff; }
    .tiles { display: grid; gap: 16px 24px; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
    .tile .label { color: var(--secondary-text-color); font-size: .8em; overflow-wrap: anywhere; }
    .tile .note, .chips-note { grid-column: auto; padding-top: 4px; }
    .chips-note { color: var(--secondary-text-color); font-size: .85em; line-height: 1.45; }
    .tile .big { font-size: 1.6rem; font-weight: 500; color: var(--primary-text-color); }
    .tile .sub { color: var(--secondary-text-color); font-size: .75em; }
    .control {
      display: grid; grid-template-columns: 1fr auto; align-items: center;
      gap: 6px 12px; padding: 8px 0; border-bottom: 1px solid var(--divider-color, #eee);
    }
    .control:last-of-type { border-bottom: none; }
    .control .name { color: var(--primary-text-color); overflow-wrap: break-word; min-width: 0; }
    .control .widget { display: flex; align-items: center; gap: 8px; justify-self: end; }
    .control .widget[data-pending="1"] { opacity: .5; }
    .control select, .control input[type="number"] {
      font: inherit; padding: 6px 8px; border-radius: 8px; max-width: 190px;
      border: 1px solid var(--divider-color, #ccc);
      background: var(--card-background-color, #fff); color: var(--primary-text-color);
    }
    .control input[type="range"] { width: 130px; accent-color: var(--primary-color, #03a9f4); }
    .control .reading { color: var(--primary-text-color); font-weight: 500; min-width: 64px; text-align: right; }
    .control .widget button {
      font: inherit; padding: 6px 14px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--primary-color, #03a9f4);
      background: transparent; color: var(--primary-color, #03a9f4);
    }
    .switch { position: relative; width: 44px; height: 24px; }
    .switch input { opacity: 0; width: 100%; height: 100%; margin: 0; cursor: pointer; }
    .switch .track {
      position: absolute; inset: 0; border-radius: 12px; pointer-events: none;
      background: var(--divider-color, #ccc); transition: background .15s;
    }
    .switch .knob {
      position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%;
      background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: transform .15s; pointer-events: none;
    }
    .switch input:checked ~ .track { background: var(--primary-color, #03a9f4); }
    .switch input:checked ~ .knob { transform: translateX(20px); }
    .switch input:focus-visible ~ .track { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
    .why {
      background: none; border: none; cursor: pointer; padding: 0 2px;
      color: var(--primary-color, #03a9f4); font: inherit; line-height: 1;
    }
    .why:focus-visible { outline: 1px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
    .note {
      grid-column: 1 / -1; color: var(--secondary-text-color); font-size: .85em;
      line-height: 1.45; padding-bottom: 4px;
    }
    .graphs { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); }
    /* The performance tab fills two columns itself, so each graph keeps its
       own height and the next one follows directly under it. */
    .graphs.flow { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
    .graphs.flow > .column { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
    @media (max-width: 900px) { .graphs.flow { grid-template-columns: 1fr; } }
    /* The overview reads left to right: what to change, and how it has run.
       Both boxes take the height of the taller one, so the row lines up. */
    .beside { display: grid; gap: 16px; align-items: stretch; margin-bottom: 16px;
              grid-template-columns: minmax(280px, 1fr) minmax(0, 2fr); }
    .beside > * { min-width: 0; margin-bottom: 0; }
    .beside > .graphs { grid-template-columns: minmax(0, 1fr); }
    .beside > .graphs > * { height: 100%; }
    @media (max-width: 900px) { .beside { grid-template-columns: 1fr; } }
    .toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
    .toolbar input {
      flex: 1; max-width: 420px; padding: 8px 12px; font: inherit;
      border: 1px solid var(--divider-color, #ccc); border-radius: 8px;
      background: var(--card-background-color, #fff); color: var(--primary-text-color);
    }
    .count { color: var(--secondary-text-color); font-size: .9em; }
    h2 {
      font-size: 1rem; font-weight: 500; margin: 20px 0 8px;
      color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .04em;
    }
    .grid {
      display: grid; gap: 1px 24px;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    }
    .row {
      display: grid; grid-template-columns: 1fr auto; gap: 4px 12px;
      padding: 10px 4px; border-bottom: 1px solid var(--divider-color, #eee);
      cursor: pointer; border-radius: 4px;
    }
    .row:hover, .row:focus-visible { background: var(--secondary-background-color, #f5f5f5); outline: none; }
    .name { color: var(--primary-text-color); overflow-wrap: anywhere; }
    .value { color: var(--primary-text-color); font-weight: 500; white-space: nowrap; text-align: right; }
    .info { color: var(--secondary-text-color); font-size: .75em; margin-left: 4px; }
    .detail {
      grid-column: 1 / -1; color: var(--secondary-text-color); font-size: .9em;
      line-height: 1.45; padding-top: 2px;
    }
    .detail .meta { display: block; margin-top: 6px; font-size: .85em; opacity: .8; }
    .detail a { color: var(--primary-color); cursor: pointer; text-decoration: underline; }
    .empty { color: var(--secondary-text-color); padding: 24px 4px; }
  `;

  //: Where the chosen tab is remembered, so a reload comes back to it.
  const TAB_STORAGE = "nibe-easyconf-tab";

  /** Shared rendering: one instance per card or panel. */
  class NibeEasyconfView {
    constructor(root) {
      this.root = root;
      this.filter = "";
      this.open = new Set();
      this.hass = null;
      this.deviceId = null;
      this.tabs = TAB_ORDER;
      this.tab = restoreTab();
      this.built = false;
      this.lastSignature = null;
      this.controlSignature = null;
      //: entity id -> explanation, kept over an entity's quiet spells.
      this.descriptions = new Map();
      this.graphSignature = null;
      this.overviewSignature = null;
      this.quickSignature = null;
      this.overviewGraphSignature = null;
      this.widgets = new Map();
      this.quickWidgets = new Map();
      this.readingTiles = new Map();
      this.statusChips = new Map();
      this.graphCards = [];
      this.overviewCards = [];
      this.explained = new Set();
    }

    build() {
      this.root.innerHTML = "";
      const style = document.createElement("style");
      style.textContent = STYLE;
      this.root.appendChild(style);

      this.wrap = document.createElement("div");
      this.wrap.className = "wrap";

      const head = document.createElement("div");
      head.className = "head";
      this.heading = document.createElement("h1");
      head.appendChild(this.heading);

      this.tabBar = document.createElement("div");
      this.tabBar.className = "tabs";
      this.tabBar.setAttribute("role", "tablist");
      this.tabButtons = new Map();
      for (const tab of this.tabs) {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("role", "tab");
        button.addEventListener("click", () => this.showTab(tab));
        this.tabBar.appendChild(button);
        this.tabButtons.set(tab, button);
      }

      // Overview
      this.overviewPanel = document.createElement("div");
      this.quickCard = document.createElement("div");
      this.quickCard.className = "card";
      this.quickHeading = document.createElement("h3");
      this.quickBody = document.createElement("div");
      this.quickCard.append(this.quickHeading, this.quickBody);
      this.statusCard = document.createElement("div");
      this.statusCard.className = "card";
      this.statusChipsRow = document.createElement("div");
      this.statusChipsRow.className = "chips";
      this.statusHeading = document.createElement("h3");
      this.statusNote = document.createElement("div");
      this.statusNote.className = "chips-note";
      this.statusNote.hidden = true;
      this.statusCard.append(this.statusHeading, this.statusChipsRow, this.statusNote);
      this.readingsCard = document.createElement("div");
      this.readingsCard.className = "card";
      this.readingsHeading = document.createElement("h3");
      this.readingsGrid = document.createElement("div");
      this.readingsGrid.className = "tiles";
      this.readingsCard.append(this.readingsHeading, this.readingsGrid);
      this.overviewGraphs = document.createElement("div");
      this.overviewGraphs.className = "graphs";
      // The graph and the controls share a row: the graph takes the width it
      // needs to be readable, the controls stand beside it rather than under.
      this.overviewRow = document.createElement("div");
      this.overviewRow.className = "beside";
      this.overviewRow.append(this.quickCard, this.overviewGraphs);
      this.overviewPanel.append(
        this.statusCard, this.overviewRow, this.readingsCard
      );

      // Controls
      this.controlsPanel = document.createElement("div");
      this.controlsBody = document.createElement("div");
      this.controlsBody.className = "cards";
      this.controlsPanel.appendChild(this.controlsBody);

      // Performance
      this.performancePanel = document.createElement("div");
      this.graphsBody = document.createElement("div");
      this.graphsBody.className = "graphs flow";
      this.performancePanel.appendChild(this.graphsBody);

      // All values
      this.valuesPanel = document.createElement("div");
      const toolbar = document.createElement("div");
      toolbar.className = "toolbar";
      this.input = document.createElement("input");
      this.input.type = "search";
      this.input.addEventListener("input", () => {
        this.filter = this.input.value;
        this.renderList(true);
      });
      this.count = document.createElement("span");
      this.count.className = "count";
      toolbar.append(this.input, this.count);
      this.body = document.createElement("div");
      this.valuesPanel.append(toolbar, this.body);

      this.panels = {
        overview: this.overviewPanel,
        controls: this.controlsPanel,
        performance: this.performancePanel,
        values: this.valuesPanel,
      };
      this.wrap.append(head, this.tabBar);
      for (const tab of this.tabs) this.wrap.appendChild(this.panels[tab]);
      this.root.appendChild(this.wrap);
      this.built = true;
      if (!this.tabs.includes(this.tab)) this.tab = this.tabs[0];
    }

    showTab(tab) {
      this.tab = tab;
      try {
        window.localStorage.setItem(TAB_STORAGE, tab);
      } catch (err) {
        // A browser that refuses storage still gets the tab for this visit.
      }
      this.render();
    }

    moreInfo(entityId) {
      this.root.host.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId }, bubbles: true, composed: true,
      }));
    }

    call(entityId, value) {
      const call = serviceFor(entityId, value);
      if (!call) return;
      this.hass.callService(call.domain, call.service, call.data);
    }

    /** An entity that is unavailable carries no attributes at all, so its
     *  explanation goes with it - and the page would drop the ⓘ for as long as
     *  the pump is quiet. An explanation never changes, so the last one seen is
     *  kept and handed back. */
    remember(rows) {
      for (const row of rows) {
        if (row.description) this.descriptions.set(row.entityId, row.description);
        else row.description = this.descriptions.get(row.entityId) || "";
      }
      return rows;
    }

    render() {
      if (!this.hass) return;
      if (!this.built) this.build();
      const text = textFor(languageOf(this.hass));
      this.input.placeholder = text.filter;
      const rows = this.remember(collectRows(this.hass, this.deviceId));
      this.heading.textContent = this.deviceNames() || text.title;

      for (const [tab, button] of this.tabButtons) {
        button.textContent = text[tab];
        button.setAttribute("aria-selected", String(tab === this.tab));
        this.panels[tab].hidden = tab !== this.tab;
      }

      // Only the tab in front is drawn; the others keep what they had.
      if (this.tab === "overview") this.renderOverview(rows, text);
      if (this.tab === "controls") this.renderControls(rows, text);
      if (this.tab === "performance") this.renderGraphs(rows, text);
      if (this.tab === "values") this.renderList(false, rows, text);
    }

    deviceNames() {
      const devices = this.hass.devices || {};
      const names = new Set();
      for (const entry of Object.values(this.hass.entities || {})) {
        if (!entry || entry.platform !== DOMAIN || !entry.device_id) continue;
        if (this.deviceId && entry.device_id !== this.deviceId) continue;
        const device = devices[entry.device_id];
        if (device) names.add(device.name_by_user || device.name);
      }
      return [...names].join(" · ");
    }

    /* ----------------------------------------------------------- overview */

    renderOverview(rows, text) {
      const picked = pickOverview(rows);
      const structure = [
        structureOf(picked.status), structureOf(picked.readings), ids(picked.cop).join(","),
      ].join("|");
      this.statusHeading.textContent = text.now;
      this.quickHeading.textContent = text.quick;
      this.readingsHeading.textContent = text.readings;

      if (structure !== this.overviewSignature) {
        this.overviewSignature = structure;
        this.statusChips.clear();
        this.readingTiles.clear();
        this.statusChipsRow.innerHTML = "";
        this.readingsGrid.innerHTML = "";
        this.statusNote.hidden = true;
        for (const row of picked.status) {
          const chip = document.createElement("div");
          chip.className = "chip";
          const label = document.createElement("span");
          label.className = "label";
          label.textContent = row.name;
          const value = document.createElement("span");
          value.className = "value";
          chip.append(label, value);
          if (row.description) {
            chip.title = row.description;
            label.appendChild(this.explainButton(row, text, (open) => {
              this.statusNote.textContent = open ? row.description : "";
              this.statusNote.hidden = !open;
            }));
          }
          this.statusChipsRow.appendChild(chip);
          this.statusChips.set(row.entityId, { chip, value, isAlarm: row.isAlarm });
        }
        for (const row of picked.readings) {
          this.readingsGrid.appendChild(this.buildTile(row, row.isCop));
        }
      }
      this.statusCard.hidden = !picked.status.length;
      this.readingsCard.hidden = !picked.readings.length;

      for (const [entityId, chip] of this.statusChips) {
        const stateObj = this.hass.states[entityId];
        chip.value.textContent = formatState(stateObj, text);
        // An alarm that is not "no alarm" is the one thing on this page that
        // should be impossible to miss.
        const raised = chip.isAlarm && stateObj &&
          stateObj.attributes.alarm_code !== 0 && stateObj.state !== "unavailable";
        chip.chip.classList.toggle("alarm-on", Boolean(raised));
      }
      for (const [entityId, tile] of this.readingTiles) {
        const stateObj = this.hass.states[entityId];
        tile.value.textContent = formatState(stateObj, text);
        if (tile.sub) {
          tile.sub.textContent = (stateObj && stateObj.attributes.basis) || "";
        }
      }
      this.renderQuickControls(rows, text);
      this.renderOverviewGraph(rows, text);
    }

    /** The most important controls, on the overview, as the same widgets the
     *  controls tab uses. They keep their own map: both tabs can hold a widget
     *  for the same entity, and each has to update its own. */
    renderQuickControls(rows, text) {
      const controls = pickQuickControls(rows);
      const structure = structureOf(controls);
      if (structure !== this.quickSignature) {
        this.quickSignature = structure;
        this.quickWidgets.clear();
        this.quickBody.innerHTML = "";
        for (const row of controls) {
          this.quickBody.appendChild(this.buildControl(row, text, this.quickWidgets));
        }
      }
      this.quickCard.hidden = !controls.length;
      for (const widget of this.quickWidgets.values()) widget.update();
    }

    buildTile(row, withBasis = false, text = null) {
      text = text || textFor(languageOf(this.hass));
      const tile = document.createElement("div");
      tile.className = "tile";
      const label = document.createElement("div");
      label.className = "label";
      label.textContent = row.name;
      const value = document.createElement("div");
      value.className = "big";
      tile.append(label, value);
      let note = null;
      if (row.description) {
        tile.title = row.description;
        note = document.createElement("div");
        note.className = "note";
        note.textContent = row.description;
        note.hidden = !this.explained.has(row.entityId);
        label.appendChild(
          this.explainButton(row, text, (open) => { note.hidden = !open; })
        );
      }
      let sub = null;
      if (withBasis) {
        sub = document.createElement("div");
        sub.className = "sub";
        tile.appendChild(sub);
      }
      // The explanation stands under the figure and what it rests on.
      if (note) tile.appendChild(note);
      this.readingTiles.set(row.entityId, { value, sub });
      return tile;
    }

    /** One graph on the overview: the circuit over the last day. */
    async renderOverviewGraph(rows, text) {
      const temps = pickGraphs(rows).filter((graph) => graph.key === "temps");
      const structure = temps.map((graph) => graph.entities.join(",")).join("|");
      if (structure === this.overviewGraphSignature) {
        for (const card of this.overviewCards) card.hass = this.hass;
        return;
      }
      this.overviewGraphSignature = structure;
      this.overviewCards = await this.fillGraphs(this.overviewGraphs, temps, text);
    }

    /* ----------------------------------------------------------- controls */

    renderControls(rows, text) {
      const controls = controlRows(rows);
      const structure = structureOf(controls);
      if (structure !== this.controlSignature) {
        this.controlSignature = structure;
        this.buildControls(controls, text);
      }
      for (const widget of this.widgets.values()) widget.update();
    }

    buildControls(controls, text) {
      this.controlsBody.innerHTML = "";
      this.widgets.clear();
      if (!controls.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = text.noControls;
        this.controlsBody.appendChild(empty);
        return;
      }
      for (const group of CONTROL_GROUP_ORDER) {
        const members = controls.filter((row) => controlGroupOf(row) === group);
        if (!members.length) continue;
        const card = document.createElement("div");
        card.className = "card";
        const heading = document.createElement("h3");
        heading.textContent = text[group];
        card.appendChild(heading);
        for (const row of members) card.appendChild(this.buildControl(row, text, this.widgets));
        this.controlsBody.appendChild(card);
      }
    }

    /** The blue "i" that opens an explanation. Everything the page shows has
     *  one: a value is only worth reading if you know what it is. */
    explainButton(row, text, toggle) {
      const why = document.createElement("button");
      why.className = "why";
      why.type = "button";
      why.textContent = "ⓘ";
      why.setAttribute("aria-label", text.explain);
      why.addEventListener("click", (event) => {
        event.stopPropagation();
        if (this.explained.has(row.entityId)) this.explained.delete(row.entityId);
        else this.explained.add(row.entityId);
        toggle(this.explained.has(row.entityId));
      });
      return why;
    }

    buildControl(row, text, registry) {
      const el = document.createElement("div");
      el.className = "control";

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = row.name;
      const note = document.createElement("div");
      note.className = "note";
      note.textContent = row.description;
      note.hidden = !this.explained.has(row.entityId);
      if (row.description) {
        name.title = row.description;
        name.appendChild(
          this.explainButton(row, text, (open) => { note.hidden = !open; })
        );
      }

      const widget = document.createElement("span");
      widget.className = "widget";
      el.append(name, widget, note);
      registry.set(row.entityId, this.fillWidget(widget, row, text));
      return el;
    }

    /** Build the widget itself and return how to keep it current. A widget the
     *  user is holding is left alone: Home Assistant sends a new state while a
     *  slider is being dragged, and writing it back would fight the thumb. */
    fillWidget(container, row, text) {
      const entityId = row.entityId;
      const kind = widgetFor(entityId, (this.hass.states[entityId] || {}).attributes);
      const send = (value) => {
        container.dataset.pending = "1";
        this.call(entityId, value);
        setTimeout(() => { container.dataset.pending = "0"; }, 6000);
      };

      if (kind === "select") {
        const select = document.createElement("select");
        select.addEventListener("change", () => send(select.value));
        container.appendChild(select);
        return { update: () => {
          const stateObj = this.hass.states[entityId];
          const options = (stateObj && stateObj.attributes.options) || [];
          if (select.options.length !== options.length ||
              [...select.options].some((option, i) => option.value !== options[i])) {
            select.innerHTML = "";
            for (const option of options) {
              const item = document.createElement("option");
              item.value = option;
              item.textContent = option;
              select.appendChild(item);
            }
          }
          if (document.activeElement !== select && stateObj) {
            select.value = stateObj.state;
            if (select.value === stateObj.state) container.dataset.pending = "0";
          }
          select.disabled = !stateObj || stateObj.state === "unavailable";
        } };
      }

      if (kind === "toggle") {
        const label = document.createElement("label");
        label.className = "switch";
        const input = document.createElement("input");
        input.type = "checkbox";
        const track = document.createElement("span");
        track.className = "track";
        const knob = document.createElement("span");
        knob.className = "knob";
        input.addEventListener("change", () => send(input.checked));
        label.append(input, track, knob);
        container.appendChild(label);
        return { update: () => {
          const stateObj = this.hass.states[entityId];
          if (document.activeElement !== input) input.checked = Boolean(stateObj && stateObj.state === "on");
          input.disabled = !stateObj || stateObj.state === "unavailable";
          if (stateObj && (stateObj.state === "on") === input.checked) container.dataset.pending = "0";
        } };
      }

      if (kind === "button") {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text.details;
        button.addEventListener("click", () => send(null));
        container.appendChild(button);
        return { update: () => {} };
      }

      if (kind === "slider") {
        const attrs = (this.hass.states[entityId] || {}).attributes || {};
        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = attrs.min;
        slider.max = attrs.max;
        slider.step = attrs.step || 1;
        const reading = document.createElement("span");
        reading.className = "reading";
        slider.addEventListener("input", () => {
          reading.textContent = withUnit(slider.value, attrs.unit_of_measurement);
        });
        slider.addEventListener("change", () => send(slider.value));
        container.append(slider, reading);
        return { update: () => {
          const stateObj = this.hass.states[entityId];
          if (!stateObj) return;
          if (document.activeElement !== slider) {
            slider.value = stateObj.state;
            reading.textContent = formatState(stateObj, text);
            if (String(slider.value) === String(stateObj.state)) container.dataset.pending = "0";
          }
          slider.disabled = stateObj.state === "unavailable";
        } };
      }

      const attrs = (this.hass.states[entityId] || {}).attributes || {};
      const field = document.createElement("input");
      field.type = "number";
      if (attrs.min !== undefined) field.min = attrs.min;
      if (attrs.max !== undefined) field.max = attrs.max;
      field.step = attrs.step || "any";
      const unit = document.createElement("span");
      unit.className = "reading";
      unit.textContent = attrs.unit_of_measurement || "";
      field.addEventListener("change", () => send(field.value));
      container.append(field, unit);
      return { update: () => {
        const stateObj = this.hass.states[entityId];
        if (!stateObj) return;
        if (document.activeElement !== field) {
          field.value = stateObj.state;
          if (String(field.value) === String(stateObj.state)) container.dataset.pending = "0";
        }
        field.disabled = stateObj.state === "unavailable";
      } };
    }

    /* ------------------------------------------------------------- graphs */

    async renderGraphs(rows, text) {
      const graphs = pickGraphs(rows);
      const structure = graphs.map((graph) => `${graph.key}:${graph.entities.join(",")}`).join("|");
      if (structure === this.graphSignature) {
        for (const card of this.graphCards) card.hass = this.hass;
        return;
      }
      this.graphSignature = structure;
      this.graphCards = await this.fillGraphs(this.graphsBody, graphs, text);
    }

    /** Put Home Assistant's own history and statistics cards in a container.
     *  They are reached the way every custom card reaches them; if that ever
     *  fails the graphs are left out, since the page is useful without them. */
    async fillGraphs(container, graphs, text) {
      container.innerHTML = "";
      if (!graphs.length) return [];
      let helpers = null;
      try {
        helpers = window.loadCardHelpers ? await window.loadCardHelpers() : null;
      } catch (err) {
        helpers = null;
      }
      if (!helpers) return [];
      // Two columns filled by hand rather than by the grid: a grid row is as
      // tall as its tallest card, which would leave a day of temperatures
      // stretched out beside a taller graph instead of letting the next one up.
      const flow = container.classList.contains("flow");
      const columns = [];
      if (flow) {
        for (let i = 0; i < Math.min(2, graphs.length); i += 1) {
          const column = document.createElement("div");
          column.className = "column";
          container.appendChild(column);
          columns.push(column);
        }
      }
      const cards = [];
      graphs.forEach((graph, index) => {
        try {
          const card = helpers.createCardElement(graphConfig(graph, text));
          card.hass = this.hass;
          (columns.length ? columns[index % columns.length] : container).appendChild(card);
          cards.push(card);
        } catch (err) {
          // One graph the frontend cannot build must not take the others.
        }
      });
      return cards;
    }

    /* --------------------------------------------------------- all values */

    renderList(force = false, rows = null, text = null) {
      if (!this.hass) return;
      text = text || textFor(languageOf(this.hass));
      const all = rows || this.remember(collectRows(this.hass, this.deviceId));

      const current = signature(this.hass, all);
      if (!force && current === this.lastSignature) return;
      this.lastSignature = current;
      const shown = all.filter((row) => matchesFilter(this.filter, row.name, row.description));
      this.count.textContent = `${shown.length} / ${all.length}`;

      this.body.innerHTML = "";
      if (!all.length || !shown.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = all.length ? text.none : text.empty;
        this.body.appendChild(empty);
        return;
      }

      for (const group of GROUP_ORDER) {
        const members = shown.filter((row) => row.group === group);
        if (!members.length) continue;
        const heading = document.createElement("h2");
        heading.textContent = text[group];
        const grid = document.createElement("div");
        grid.className = "grid";
        for (const row of members) grid.appendChild(this.renderRow(row, text));
        this.body.append(heading, grid);
      }
    }

    renderRow(row, text) {
      const el = document.createElement("div");
      el.className = "row";
      el.tabIndex = 0;
      el.setAttribute("role", "button");
      el.setAttribute("aria-expanded", String(this.open.has(row.entityId)));
      // Hover, for a mouse. The same text is written out on tap below.
      if (row.description) el.title = row.description;

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = row.name;
      if (row.description) {
        const info = document.createElement("span");
        info.className = "info";
        info.textContent = "ⓘ";
        info.setAttribute("aria-hidden", "true");
        name.appendChild(info);
      }

      const value = document.createElement("span");
      value.className = "value";
      const stateObj = this.hass.states[row.entityId];
      value.textContent = formatState(stateObj, text);
      // Green for an accessory the pump has, red for one it has not: the point
      // of the section is which is which, at a glance.
      const answer = accessoryAnswer(row, stateObj);
      if (answer) value.classList.add(answer);
      el.append(name, value);

      if (this.open.has(row.entityId)) {
        const detail = document.createElement("div");
        detail.className = "detail";
        detail.textContent = row.description || row.nibeTitle || "";
        const meta = document.createElement("span");
        meta.className = "meta";
        if (row.nibeTitle) meta.append(`NIBE: ${row.nibeTitle}`);
        if (row.register !== undefined) meta.append(`${row.nibeTitle ? " · " : ""}register ${row.register}`);
        const link = document.createElement("a");
        link.textContent = text.details;
        link.addEventListener("click", (event) => {
          event.stopPropagation();
          this.moreInfo(row.entityId);
        });
        meta.append(" · ", link);
        detail.appendChild(meta);
        el.appendChild(detail);
      }

      const toggle = () => {
        if (this.open.has(row.entityId)) this.open.delete(row.entityId);
        else this.open.add(row.entityId);
        this.renderList(true);
      };
      el.addEventListener("click", toggle);
      el.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle();
        }
      });
      return el;
    }
  }

  function withUnit(value, unit) {
    return unit ? `${value} ${unit}` : String(value);
  }

  function restoreTab() {
    try {
      const saved = window.localStorage.getItem(TAB_STORAGE);
      if (saved && TAB_ORDER.includes(saved)) return saved;
    } catch (err) {
      // No storage: start on the overview, like a first visit.
    }
    return TAB_ORDER[0];
  }

  class NibeEasyconfCard extends HTMLElement {
    constructor() {
      super();
      this.view = new NibeEasyconfView(this.attachShadow({ mode: "open" }));
    }
    setConfig(config) {
      this.view.deviceId = (config && config.device_id) || null;
      const tabs = config && config.tabs;
      this.view.tabs = Array.isArray(tabs) && tabs.length
        ? TAB_ORDER.filter((tab) => tabs.includes(tab))
        : TAB_ORDER;
      this.view.built = false;
      this.view.lastSignature = null;
      this.view.controlSignature = null;
      this.view.graphSignature = null;
      this.view.overviewSignature = null;
      this.view.quickSignature = null;
      this.view.overviewGraphSignature = null;
    }
    set hass(hass) {
      this.view.hass = hass;
      this.view.render();
    }
    getCardSize() {
      return 20;
    }
    static getStubConfig() {
      return {};
    }
  }

  class NibeEasyconfPanel extends HTMLElement {
    constructor() {
      super();
      this.view = new NibeEasyconfView(this.attachShadow({ mode: "open" }));
    }
    set hass(hass) {
      this.view.hass = hass;
      this.view.render();
    }
    set panel(_panel) {}
    set narrow(_narrow) {}
  }

  if (!customElements.get("nibe-easyconf-card")) {
    customElements.define("nibe-easyconf-card", NibeEasyconfCard);
  }
  if (!customElements.get("nibe-easyconf-panel")) {
    customElements.define("nibe-easyconf-panel", NibeEasyconfPanel);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "nibe-easyconf-card")) {
    window.customCards.push({
      type: "nibe-easyconf-card",
      name: "Nibe Local Easyconf",
      description: "The pump's controls, a few graphs, and every value with its explanation.",
    });
  }
}
