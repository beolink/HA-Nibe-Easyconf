# Nibe Local Easyconf

Local communication between Home Assistant and NIBE heat pumps and indoor
modules. No cloud, no myUplink account.

The S-series has **Modbus TCP** built in, so it needs no extra hardware. The
F-series, which has no Modbus TCP, is reached through a **NibeGW gateway** on the
pump's RS-485 bus, built with
[Nibe F-series ModbusAdapter](https://github.com/beolink/Nibe-F-series-ModbusAdapter).

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

This section is the S-series. For the F1145 up to the VVM 500, see
[F-series through a NibeGW gateway](#f-series-through-a-nibegw-gateway).

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

## F-series through a NibeGW gateway

The F-series - F1145/F1245, F1155/F1255, F1345, F1355, F370/F470, F730, F750,
SMO 20/40 and VVM - has no Modbus TCP. It is reached through a NibeGW gateway on
the pump's RS-485 accessory bus instead: a small ESP32 that stands in for NIBE's
MODBUS 40 accessory, acknowledges the pump's telegrams on its own, and relays
reads and writes over UDP. This path was built and measured on an F1255-16
through a Waveshare ESP32-S3-RS485-CAN running
[esphome-nibe](https://github.com/elupus/esphome-nibe).

### The gateway

The gateway is a project of its own,
[Nibe F-series ModbusAdapter](https://github.com/beolink/Nibe-F-series-ModbusAdapter):
ESPHome firmware for a Waveshare ESP32-S3-RS485-CAN, with how to build it, wire
it to the pump's input board and switch MODBUS 40 on in the pump. This
integration was built and measured against it.

Name the gateway `nibe-<the pump's serial>-gw`, as that project's example does.
The integration reads the model and the build date from the serial just as it
does for the S-series, and the suffix keeps the gateway apart from the pump's
own network name.

### Adding the pump

The gateway is offered as a discovered device, through DHCP or through the mDNS
record every ESPHome device publishes. Otherwise: **Add integration → Nibe Local
Easyconf → F-series through a NibeGW gateway**, with the gateway's address. Home
Assistant's own address has to be among the gateway's allowed sources, or it
drops the requests and says so in its log.

There is no model to pick: the pump announces itself every fifteen seconds as,
for instance, *F1255-16 CU* with its software version. Setup then reads the
registers worth showing by default - 43 on an F1255, in under a minute - and
switches on those that report a value.

### What is different

Measured on the F1255-16 CU:

| | S-series, Modbus TCP | F-series, NibeGW |
|---|---|---|
| A read | a block of up to 125 registers, ~40 ms | one register, ~1.1 s |
| A register the pump does not implement | an exception | answers anyway |
| Hardware that is not fitted | NIBE's "no reading" value | the same, in 71 of 982 registers |
| The model | picked, or from the serial | the pump's own product message |

Since every register answers, which ones exist cannot be probed: 901 of the 982
registers in the F1155/F1255 map returned a value, including an exhaust air
sensor on a pump that has none. So on the F-series:

- **Setup reads only the default set.** The rest of the map still becomes
  entities, switched off, and a scan of all of it would take a quarter of an
  hour.
- **Polling reads what is due, not everything.** Measurements every cycle,
  counters every five and settings every ten, most overdue first; a register
  that fails backs off, doubling up to an hour. A cycle may spend three
  quarters of the update interval reading, so the default minute fits about 40
  reads; what does not fit is read first in the next cycle.
- **Registers in LOG.SET are never read.** Up to 20 registers loaded into the
  pump from a USB stick arrive on their own every two seconds. A ready file for
  the F1155/F1255, a generator for other models and how to load them are in
  [Nibe F-series ModbusAdapter](https://github.com/beolink/Nibe-F-series-ModbusAdapter/blob/main/docs/logset.md).

The device page shows the product message's model and software version.
Through the gateway there is no coefficient of performance: the F-series keeps
no electricity counter to divide by.

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

### Explanations

Every entity carries an explanation, shown on the NIBE page and in its
attributes. For the values a person actually looks at or changes - all the
controls and the readings that say how the pump is doing - the explanation is
written out: what it is, what it does to the house, and what happens if you
change it. The heating curve says to move it one step and wait a day; the
degree minutes explain what the number counts and why it goes negative.

They are written per family rather than per register, because an installation
only shows the registers its own accessories bring: one house has an exhaust
air module, the next a pool, a third eight climate systems. So the pool's start
and stop temperatures, the ERS module's settings and the eighth climate
system's room sensor are all explained here although no pump this was built
against has them - a scan that finds an accessory brings explained values with
it. That covers about seven eighths of the registers in NIBE's maps for both
series, and a little more of the ones you can set.

The rest is built from NIBE's own title and a glossary of designations, which
is how a register NIBE documents as `(EB100-EP15-BT28)` still says what it
measures. A register whose meaning could not be verified keeps that built text
rather than a guess, and a service value from the pump's own electronics says
that is what it is rather than being given an invented purpose.

### Alarms and values in words

Alarm registers read as the alarm's text — *Inget larm*, or *Fel fasföljd alt.
saknad fas har uppmätts.* — from NIBE's published S-series alarm list, with the
number kept as an `alarm_code` attribute for automations. NIBE reuses some codes
for more than one alarm (237 is a short running time in hot water/heating, in
the compressor or in cooling), so those carry every meaning the list gives.

The F-series uses a different list, whose numbers mean other things: 163 is a
missing phase on an S-series pump and a hot condenser inlet on an F1255. Its
alarms read from NIBE's list for products with the Emmy display, 328 codes in
Swedish, via `tools/extract_nibe_alarms_fseries.py`. The English titles come
from NIBE's older English edition, and only where it agrees with the Swedish:
between the two, NIBE gave some numbers new meanings - 150 went from *High
condensor out* to a temporary high pressure alarm - so a code whose English
title disagrees, or is missing, reads as *Alarm 150* in English rather than as
the wrong alarm.

Registers with a value table read as words too, and settings with one become
dropdowns. The tables come from NIBE's own register documentation, which is
more complete and more precise than the library's: it labels the diverter valve
*heating/hot water* where the library says *off/on*, and it documents the brine
pump's *intermittent / continuous / 10 days continuous*, which the library
leaves as a bare number. See [docs/nibe-references.md](docs/nibe-references.md).

### Coefficient of performance

The pump keeps two lifetime energy counters on Modbus — register 33822, heat
delivered, and 33824, electricity consumed — and they become the *Total
produktion* and *Total förbrukning* sensors, ready for Home Assistant's Energy
dashboard. On the development unit they read the same figures myUplink's cloud
reports for the pump, to the tenth of a kWh.

Their ratio is the coefficient of performance, computed the same way as in the
CTC integration so the two are comparable:

- **COP, dygn** — over the last day, from a sample 20–30 hours old. Appears
  about a day after setup.
- **COP, år** — over a rolling year. Until a year of samples exists it shows the
  lifetime figure, and its `basis` attribute says so.

The anonymous report is stricter than the sensor: it sends a yearly figure only
once it really covers a year, since the lifetime figure under the yearly name
would be a different number wearing the wrong label.

**Earlier history is imported automatically.** If Home Assistant already
recorded these two counters through another integration — myUplink reports
them as *Tot. produktion* / *Tot. konsumtion* — that history is read into the
COP once, at startup. Nothing is configured: the series are found because
their latest values match the pump's own counters, and both have to come from
the same device, which rules out a household meter that merely happens to sit
near the pump's consumption. The daily figure is then there at once, and a real
yearly figure arrives a year after the history begins rather than a year after
installation. The `nibe_local_easyconf.import_energy_history` service runs it
again, for instance after adding a source.

### Heating mode

A select, *Värmeläge* (*Heating mode*), offers `blocked`, `eco`, `normal` and
`boost`: exactly the ids an energy manager such as
[EMS Steward](https://github.com/beolink/ha-ems) writes to the heat pump it is
bound to, shown in the interface as words. No NIBE map has a register for it,
so the select steers the one lever every map has, the heat offset of climate
system 1 - *temperatur* in menu 1.1, register 47011 on the F-series and 40031
on the S-series:

| Mode | Offset written |
|---|---|
| `boost` | normal + 1 |
| `normal` | normal |
| `eco` | normal − 1 |
| `blocked` | normal − 3 |

The steps are set under **Configure**. On an F1255 one step moves the supply
temperature 2.5 °C at every outdoor temperature (NIBE's installer manual IHB SE
1614-2). Heating is never switched off: a blocked house coasts on its thermal
mass with the minimum supply temperature still in force, the bounded set-back
EMS asks of a heat pump. The defaults are EMS's own thermostat set-backs
(+1, −1.5 and −3 °C) taken as steps.

Normal is learned: the offset the pump had when the select first saw it. An
offset changed anywhere else - on the display, in myUplink, through the
offset's own entity - is taken as meant. In `normal` it becomes the new normal
and the other modes follow it; in any other mode it holds until the mode next
changes. The select keeps showing the mode last chosen, so an energy manager
does not undo a change made by hand, and its attributes show the normal offset
and what each mode writes.

NIBE's own mechanism would be SG Ready, but on these pumps that is two contacts
on the input board rather than a register, and the F-series' smart home mode
and smart price adaption are read-only over MODBUS 40.

### Hot water boost

On the F-series a switch, *Varmvattenboost* (*Hot water boost*), is the one to
bind as an energy manager's water heater, with EMS's *water heater is a boost*
ticked. On writes temporary lux's *One time increase* (*engångshöjning*) to
register 48132, off writes *Off*. Those are the values myUplink's own
*Tillfällig lyx* switch was seen writing on the F1255-16, so a plan tuned on the
cloud switch behaves the same through the gateway. A 3, 6 or 12 hour lux
started at the pump reads as on.

The S-series calls its boost *More hot water* (40698), and neither the maps nor
NIBE's register documentation give its values, so it has no switch yet.

## The NIBE page

Setting the integration up adds a **NIBE** entry to the sidebar on its own —
nothing to configure. The page has four tabs.

**Overview.** What the pump is doing right now: the alarm, the modes it is
running in and the day's coefficient of performance as chips; beside them the
controls worth reaching for without going further - heating and hot water mode,
holiday, the exhaust air module's fan - and the last day's temperatures as a
graph. Under that, the key figures: the circuit's temperatures, the compressor,
the energy counters and the year's coefficient of performance. Every one of
them carries the same ⓘ as the controls do.

**Controls.** Everything writable, as the thing it is: a dropdown for a mode, a
slider for a setting with a range you can aim at, a field for one that runs from
−3000 to 3000, a toggle for a switch. They are grouped by what they do to the
house — heating, hot water, operation, fans and pumps — rather than by entity
domain, and each keeps its explanation behind the ⓘ. A value written here goes
straight to the pump; the page never waits for a dialog.

**Performance.** The graphs in full: the circuit's temperatures and the
compressor over the last day, the energy counters per day for a month, and the
coefficient of performance. They are drawn by Home Assistant's own history and
statistics cards, and a pump that reports none of it simply has no such tab.

**All values**, last. It opens with **accessories registered**: what the pump
answers about its own modules - a pool, an exhaust air module, a room unit, the
gateway's own settings - the ones it says no to as well, since that is half the
answer. The pump's enabled entities two to a row with room for the whole
name, grouped the way the device page groups them, with a filter that searches
names and explanations. Hover a row for its explanation; tap it and the
explanation is written out underneath, along with NIBE's original title and the
register number, because a hover text alone never reaches a phone or a screen
reader.

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
tabs: [overview, controls, performance, values]   # optional, this is the default
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

- The F-series is supported through a NibeGW gateway, not yet through NIBE's
  own MODBUS 40 accessory, and without a coefficient of performance; see
  [what is different](#what-is-different). About a quarter of its alarms have
  no English title, for the reason given under
  [alarms and values in words](#alarms-and-values-in-words).
- Register names come from NIBE's published maps, which are in English. Titles
  are translated to Swedish only where the whole phrase is recognised —
  a partial translation reads worse than the original.
- Descriptions decode component designations that could be pinned down from
  NIBE's own data. Unknown codes get a structural description rather than a guess.

## Roadmap

- **NIBE's MODBUS 40 accessory as an alternative to the gateway.** The same pump
  protocol behind a real MODBUS 40, reached as Modbus RTU through a TCP-to-RTU
  converter: holding registers only, addressed by their full number (40004 is
  0x9C44) before MODBUS 40 version 10, writes as Write Multiple Registers only,
  and 2.1 s per register outside LOG.SET.
- **Hold stats.py's own keys to the backend as well.** The contract test checks
  what `stats_extra` builds, but not the keys `stats.py` adds itself (`ha_id`,
  `log_errors` and `log_warnings` since 1.7.2). The backend rejects a whole
  report over one unknown top-level key, so a key it does not know yet would
  silence every report without an error on this side.

## Licence

[Apache License 2.0](LICENSE).

Register maps come from the [`nibe`](https://github.com/yozik04/nibe) library
(LGPL-3.0), declared as a dependency in `manifest.json` and installed by Home
Assistant. No LGPL code is copied into this repository.
