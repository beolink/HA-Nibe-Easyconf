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

## Running alongside another Modbus integration

You can. The pump was measured accepting **14 simultaneous TCP connections**,
and read latency did not degrade under five parallel clients (median 37 ms alone,
21 ms under load). Concurrent *reads* are safe.

Concurrent *writes* are not: if two integrations both write the same setting they
will fight. Keep writes in one place.

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
