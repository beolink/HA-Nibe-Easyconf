# Nibe Local Easyconf

A Home Assistant integration for NIBE S-series heat pumps over **local Modbus TCP**.
No cloud, no myUplink account, no gateway hardware.

It differs from the existing options in two ways, both of which came out of
actually probing a pump rather than reading the documentation:

1. **It finds out which registers your pump really has.** NIBE publishes one
   register map per model, but any individual unit implements a subset — and
   answers a *superset* of the published map. The integration probes the pump at
   setup and creates entities only for registers that exist, marking the ones
   that exist but report no value.
2. **It explains every register in plain language.** NIBE's own titles are
   service-manual shorthand; roughly a third of them are nothing but a component
   designation. Register 31624 on the pump this was built against is titled
   exactly `(EB100-EP15-BT28)`. Here it becomes *"Utetemperatur (givare i
   kompressormodulen)"* with a description attached to the entity.

## Why this exists

Home Assistant already ships [`nibe_heatpump`](https://www.home-assistant.io/integrations/nibe_heatpump/),
which supports S-series over Modbus and works. If it covers what you need, use it.

This integration is for the cases it does not cover: registers missing from the
model dropdown, entities you cannot identify, and the timeouts that come from
reading registers the pump does not implement.

## What the probing found

Three behaviours of the S-series Modbus stack shape the whole design:

| Behaviour | Consequence |
|---|---|
| Unimplemented registers answer exception **01 (illegal function)**, where the spec says 02 (illegal data address) | 01 has to be read as "no such register here", not "this device is broken" |
| A block read succeeds **only if every register in the span exists** — one hole fails the whole request | Reads must be grouped into contiguous runs of known-live registers |
| The firmware answers for hardware that is not fitted, returning a per-datatype sentinel (`0x8000`, `0xFFFF`, `-128`, `0xFF`) | "Does the register exist" and "is it reporting" are different questions, and both matter |

That last one is why model detection by register fingerprint does not work.
On the development unit it confidently reported an *exhaust-air S735* for what
the readings plainly showed to be a ground-source pump: brine circuit live at
5.8 °C in / 2.1 °C out, every fan at 0 rpm, no exhaust-air sensors at all. The
S735 map simply happens to be the most complete one published. So the model is
now just a label you pick, and register maps from every S-series model are merged
into one union (only 8 of 1611 shared registers carry a conflicting definition).

## Install

**HACS** → Custom repositories → add `https://github.com/beolink/HA-Nibe-Easyconf`
as an Integration → install → restart Home Assistant.

**Manually**: copy `custom_components/nibe_local_easyconf/` into your
`config/custom_components/` directory and restart.

## Set up

On the pump: enable network (menu **5.2**) and **Modbus TCP** (menu **7.5.9**).

You should not need to know the pump's IP address. There are three ways in:

**It finds you.** NIBE names its pumps `NIBE-<serial>` on the network, so the
integration matches that hostname over DHCP and Home Assistant offers the pump
as a discovered device on its own. The serial is used as the identity, so the
pump is still recognised after its DHCP lease hands it a different address.

> Matching on MAC address was considered and dropped. NIBE holds no IEEE OUI —
> the pump's MAC belongs to whichever network chipset is fitted, so an OUI rule
> would match unrelated hardware.

**You search.** A DHCP lease may not renew for hours, so
**Settings → Devices & services → Add integration → Nibe Local Easyconf →
"Search the network"** sweeps Home Assistant's own subnet. Port 502 alone proves
nothing — inverters and PLCs sit there too — so every hit is confirmed by reading
the outdoor-temperature register, and the reading is shown next to the address.
A /24 takes a couple of seconds.

**You type it in.** Always available, and offered automatically if the search
comes up empty.

Whichever route, it then scans the registers — about a minute, once — and shows
what it found before asking which model to name the device after.

The scan result is cached, so restarts are instant. After a firmware update or
fitting an accessory, call the **`nibe_local_easyconf.rescan_registers`** service.

## Which model is it?

Not something the pump will tell you over Modbus. Every one of the 919 registers
the development unit implements was checked for its serial number — 16-bit and
32-bit, both word orders — and none carries it. A `Heat pump type` register
exists in every S-series map, but no published map says what its values mean.
Home Assistant's own `nibe_heatpump` resolves this by asking you in a dropdown.

The pump does announce its serial, though: it calls itself `NIBE-<serial>` on
the network. That reaches Home Assistant through DHCP, and a reverse DNS lookup
recovers it for pumps added by hand. NIBE
[documents the format](https://www.nibe.eu/sv-se/support/vanliga-fragor/faq-items/vad-betyder-siffrorna-i-serienumret-pa-en-nibe-produkt):

| Digits | Meaning | Development unit |
|---|---|---|
| 1–6 | Article number: model, size and variant | `065443` — S1155-16 |
| 7–8 | Year of manufacture | `22` — 2022 |
| 9–11 | Day of that year (not a week number) | `034` — 3 February |
| 12–14 | Internal sequence number | kept on the device only |

The article number pre-selects the model in setup, and the device page shows the
exact model with its size, the article number, the serial, the control board's
software version, and a *Manufactured* date. The dates check out against the
machine: built 3 February 2022, 25,025 compressor hours at 4.6 years old is a
62 % average duty cycle, which is what a ground-source pump in Sweden does.

The article table covers what could be corroborated. Retailer listings turned
out to mix NIBE's real six-digit `06xxxx` numbers with their own SKUs and
Swedish RSK numbers, so only the former were kept. An unlisted article still
decodes its date, and the anonymous report carries it, so the table can grow
from the fleet.

## Entities

Every register the pump implements becomes an entity, but only about a hundred
are **enabled by default** — the temperatures, compressor, power, energy, alarms,
degree minutes, heat curve and hot water settings a normal installation cares
about. The rest are created disabled; enable any of them from the entity
settings and it joins the next poll cycle.

Only registers backing an *enabled* entity are polled, so the cost of the long
tail is zero until you ask for it.

Each entity carries three attributes:

- `description` — the generated explanation
- `modbus_register` — the NIBE register number
- `nibe_title` — NIBE's original title, unmodified

### Names

NIBE's titles run to 78 characters ("Energy log - Used energy by additional heater
for hot water over the past hour"), and the device page cuts a name off at around
25. The default set therefore gets hand-written short names of at most 24
characters — that one becomes *Elpatron, VV, 1 h*. The full title and the
explanation stay on the entity as attributes, one click away.

NIBE also reuses titles: on the development unit 308 of the 919 registers shared
just 57 names, 21 of them titled only "Permit". Every name is made distinct —
by the component designation that tells them apart where there is one (EP14 and
EP15 are the two refrigerant circuits), by marking the setting when a value
exists both to read and to set, and by the register number when nothing else is
known.

The explanation is in the entity's details rather than a hover tooltip, because
the device page has nowhere to put one: the card that draws its entity rows
binds no `title` and uses no tooltip component, and the only place the frontend
renders a `description` attribute at all is the legacy configurator dialog.
Checked against `home-assistant-frontend==20260826.6`, the version Home
Assistant 2026.9.1 ships.

The number of columns is not the integration's to set either. The page computes
it as `⌊(width + 16) / 336⌋` — each column at least 320 px — from the width of
its own content area, so it follows the browser window. Below about 990 px of
content width you get two columns: narrow the window, keep Home Assistant's
sidebar expanded (it takes its width from the content area), or zoom the
browser in.

## The NIBE page

Setting the integration up adds a **NIBE** entry to the sidebar on its own —
nothing to configure. It lists the pump's enabled entities two to a row with
room for the whole name, grouped the way the device page groups them, with a
filter that searches names and explanations. Hover a row for its explanation;
tap it and the explanation is written out underneath, along with NIBE's
original title and the register number, because a hover text alone never
reaches a phone or a screen reader.

A sidebar panel rather than a generated dashboard, deliberately: Home Assistant
keeps its dashboards collection in a local variable inside the Lovelace
component and exposes it nowhere, so creating one from an integration means
reaching into internals that move between releases. `panel_custom` is the
public way to add a page, and it is how HACS itself gets into the sidebar.
No existing dashboard is ever touched.

The same view is available as a card for your own dashboards — the resource is
registered automatically on storage-mode Lovelace:

```yaml
type: custom:nibe-easyconf-card
device_id: <optional, when you have more than one pump>
```

In YAML mode, add `/nibe_local_easyconf/nibe-easyconf-card.js` as a `module`
resource yourself.

## Running alongside another Modbus integration

You can. The pump was measured accepting **14 simultaneous TCP connections**,
and read latency did not degrade under five parallel clients (median 37 ms alone,
21 ms under load). Concurrent *reads* are safe.

Concurrent *writes* are not: if two integrations both write the same setting they
will fight. Keep writes in one place.

## Anonymous statistics

The integration sends one report per day to <https://stats.rnet.se>: which
version of the integration you run, your Home Assistant version and installation
type, the country you have set in Home Assistant itself, an approximate position
rounded to about 11 km, how many entities and devices it created, which model you
picked, what kind of machine the readings say it is (ground source, exhaust air,
hot water, cooling), how many registers the scan found and how many report a
value, how many block reads a poll cycle costs, the update interval, the control
board's software version, and how many poll cycles failed.

When the serial is known it also carries the article number, among the models,
and the year and week of manufacture. The exact day stays local, and the
serial's sequence number — the one part that identifies a single machine —
never leaves the house.

A contract test pins every field against the backend's own validation rules.
Three fields in v1.3.0 were silently lost or mangled on arrival, among them the
article number, which the backend's four-digit `product_code` range clamped to
9999 without an error; the test now fails on exactly that class of mistake.

The register counts are the reason this exists. NIBE's published maps do not say
which registers a given machine implements, and no single installation can tell
you either — [what the probing found](#what-the-probing-found) came from one
pump. Across a fleet those counts are how the maps get better.

It never sends a name, an address, an exact position, a serial number, an entity
name, **which** registers were found, or any reading from the house. Nothing is
finer-grained than one day, and your IP address is not stored.

It is on by default. Turn it off under **Settings → Devices & services →
Nibe Local Easyconf → Configure**; doing so also erases what has already been
sent, rather than merely going quiet.

What is collected and why: <https://stats.rnet.se/integritet>

## Limitations

- S-series only. Older F-series pumps need a NibeGW gateway and are out of scope.
- Register names come from NIBE's published maps, which are in English. Titles
  are translated to Swedish only where the whole phrase is recognised —
  a partial translation reads worse than the original.
- Descriptions decode component designations that could be pinned down from
  NIBE's own data. Unknown codes get a structural description rather than a guess.

## Licence

[Apache License 2.0](LICENSE).

Register maps come from the [`nibe`](https://github.com/yozik04/nibe) library
(LGPL-3.0), declared as a dependency in `manifest.json` and installed by Home
Assistant. No LGPL code is copied into this repository.
