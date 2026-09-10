/* Nibe Local Easyconf — the heat pump's entities, each with its explanation.
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
 *
 * Why it exists: Home Assistant's device page cuts entity names at roughly 25
 * characters, fixes its own column count from the window width, and has no
 * way to show an entity's explanation on hover. This lays the same entities
 * out two to a row with room for the whole name, and shows each one's
 * `description` attribute.
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
  },
  en: {
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
  },
};

const GROUP_ORDER = ["sensor", "control", "config", "diagnostic"];

/** The viewing user's language, falling back to English for anything else. */
function textFor(language) {
  const code = String(language || "").slice(0, 2).toLowerCase();
  return TEXT[code] || TEXT.en;
}

/** Which section an entity belongs in, mirroring the device page's own. */
function groupOf(entry, domain) {
  if (entry && entry.entity_category === "diagnostic") return "diagnostic";
  if (entry && entry.entity_category === "config") return "config";
  if (["number", "select", "switch", "button"].includes(domain)) return "control";
  return "sensor";
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
      group: groupOf(entry, domain),
      // Home Assistant prefixes the device name to every entity name; on a
      // page that is already about the pump it only pushes the value off.
      name: stripDeviceName(attributes.friendly_name || entry.entity_id, deviceName),
      description: attributes.description || "",
      nibeTitle: attributes.nibe_title || "",
      register: attributes.modbus_register,
    });
  }
  rows.sort((a, b) => a.name.localeCompare(b.name));
  return rows;
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

if (typeof module !== "undefined") {
  module.exports = {
    textFor, groupOf, formatState, matchesFilter, collectRows, stripDeviceName,
    signature, GROUP_ORDER, DOMAIN,
  };
}

/* ------------------------------------------------------------------ DOM -- */

if (typeof customElements !== "undefined") {
  const STYLE = `
    :host { display: block; }
    .wrap { padding: 16px; }
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

  /** Shared rendering: one instance per card or panel. */
  class NibeEasyconfView {
    constructor(root) {
      this.root = root;
      this.filter = "";
      this.open = new Set();
      this.hass = null;
      this.deviceId = null;
      this.built = false;
      this.lastSignature = null;
    }

    build() {
      this.root.innerHTML = "";
      const style = document.createElement("style");
      style.textContent = STYLE;
      this.root.appendChild(style);
      this.wrap = document.createElement("div");
      this.wrap.className = "wrap";
      const toolbar = document.createElement("div");
      toolbar.className = "toolbar";
      this.input = document.createElement("input");
      this.input.type = "search";
      this.input.addEventListener("input", () => {
        this.filter = this.input.value;
        this.render(true);
      });
      this.count = document.createElement("span");
      this.count.className = "count";
      toolbar.append(this.input, this.count);
      this.body = document.createElement("div");
      this.wrap.append(toolbar, this.body);
      this.root.appendChild(this.wrap);
      this.built = true;
    }

    moreInfo(entityId) {
      this.root.host.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId }, bubbles: true, composed: true,
      }));
    }

    render(force = false) {
      if (!this.hass) return;
      if (!this.built) this.build();
      const text = textFor(this.hass.locale && this.hass.locale.language);
      this.input.placeholder = text.filter;

      const all = collectRows(this.hass, this.deviceId);
      const current = signature(this.hass, all);
      if (!force && current === this.lastSignature) return;
      this.lastSignature = current;
      const rows = all.filter((row) => matchesFilter(this.filter, row.name, row.description));
      this.count.textContent = `${rows.length} / ${all.length}`;

      this.body.innerHTML = "";
      if (!all.length || !rows.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = all.length ? text.none : text.empty;
        this.body.appendChild(empty);
        return;
      }

      for (const group of GROUP_ORDER) {
        const members = rows.filter((row) => row.group === group);
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
      value.textContent = formatState(this.hass.states[row.entityId], text);
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
        this.render(true);
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

  class NibeEasyconfCard extends HTMLElement {
    constructor() {
      super();
      this.view = new NibeEasyconfView(this.attachShadow({ mode: "open" }));
    }
    setConfig(config) {
      this.view.deviceId = (config && config.device_id) || null;
      this.view.lastSignature = null;
    }
    set hass(hass) {
      this.view.hass = hass;
      this.view.render();
    }
    getCardSize() {
      return 12;
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
      description: "The heat pump's entities with the explanation for each.",
    });
  }
}
