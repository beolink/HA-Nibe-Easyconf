# Roadmap

What this integration should do next, in the order it pays off. Each item says
what it is, why it is worth doing, and roughly how; the numbers are the
releases the work is planned for, not promises about dates. Finished items are
dropped from here and described in the release notes instead.

The two short items the README's roadmap used to hold (NIBE's MODBUS 40
accessory as an alternative to the gateway; holding stats.py's own keys to the
backend) are under *Later*.

## Where it stands

Both series read and write locally; every register is explained in plain
language; the NIBE page carries the overview, the controls, the graphs and the
full list; the F-series gets a coefficient of performance from a counted
electricity figure; the scan re-reads itself after an update. Tiered polling
through the gateway, block reads over Modbus TCP, bilingual explanations, a
responsive page, read-back after a gateway write, diagnostics, and CI with
hassfest, HACS and the tests against two versions of the `nibe` library are
all in place. Nothing below redoes any of it.

## 1.15 — The pump as Home Assistant knows it

**Climate and water heater entities.** The platforms are sensor,
binary_sensor, number, select and switch; `nibe_heatpump` in core has
`climate` and `water_heater` as well, so a user who moves here loses the
thermostat card, the scheduler helpers and the exposure through Google, Alexa,
HomeKit and Matter. The logic already exists: `heating_mode.py` is exactly a
climate entity's preset modes (blocked, eco, normal, boost), and
`hot_water_boost.py` is a water heater's operation mode. One climate entity per
climate system, with the room sensor (BT50) as the current temperature where
the pump has one, the room setpoint as the target when the pump is told to use
the sensor, and the heating mode as presets; one water heater with the hot
water mode as its operation modes and the one-time increase as the boost. A
pump without a room sensor is offered no mode that would have it use one, and
says why.

**Buttons.** A momentary action presented as a switch is wrong: *Reset alarm*
(45171 / 40023) becomes a button, and *Rescan registers* gets one too, so the
service exists as a thing on the device page. The page already expects the
`button` domain among its controls.

**Read back after a write on the S-series.** The gateway path reads a setting
back after writing it, because the pump may clamp what it stores; the Modbus
TCP path sets the value optimistically and shows it until the next poll. The
32-bit word order incident showed an S-series pump also acknowledges and
drops. Five lines.

## 1.16 — The integration explains its own silences

**Repairs.** The three support questions asked of the development units in
one week - why one pump has no COP, why another shows no indoor temperature,
why a status reads as a number - are things a `repairs.py` answers itself:
*the pump's heat meters have stood still through 25 kWh of compressor, so it is
not measuring the heat it delivers; NIBE's energy metering needs an EMK 300 or
500*; *no room sensor (BT50) is fitted, so no room temperature*; *the scan after
the update failed and the old one is in use*; *the gateway has not answered for
ten minutes*. Cheap to build, and the difference between a sensor that never
appears and a reason.

**The alarm as an event.** It is a text and a red chip, and nothing happens
when one arrives. An event entity, or a persistent notification carrying the
alarm's plain-language title and the reset button from 1.15.

**Sub-devices.** Everything sits on one Home Assistant device
(`identifiers={(DOMAIN, entry_id)}`): 1 196 entities on the S1155. The device
page is unusable, and the NIBE page's *All values* carries the whole load. With
`via_device`, the outdoor unit (EB101), the pool, the FLM/ERS modules and
climate systems 2-4 become devices of their own. Entity ids do not change; the
page's `device_id` filter has to follow the children, which is a small
migration.

## 1.17 — The page shows the machine

**A circuit schematic on the overview.** The temperatures are shown as a list
of numbers; as a circuit - brine in and out, supply and return, the hot water
cylinder, the compressor with its frequency in the middle - they are read in a
second, the way myUplink's flow picture is. An SVG on the theme's variables,
drawing only the parts this pump has: no brine circuit on an exhaust-air pump.

**A strip of the day.** Twenty-four hours of the status register's history as
a coloured strip: heating, hot water, additional heat, defrosting, idle. It is
the answer to "why was yesterday expensive", and Home Assistant has no card
for it.

**A degree-minute gauge.** The one number that explains *why* the pump does
what it does, with the compressor start (-60) and the additional heat limit
marked. Teaches more than any graph.

**The phone.** The 900 px breakpoint exists; the chips and the control row
want checking at 375 px, and a sticky tab bar helps on a long *All values*.

## 1.18 — Energy by part, and the price of heat

**Energy per part.** `power.Parts` already books compressor, additional heat,
circulation pumps and electronics separately; only the sum is shown. Bars per
day split by part, with the coefficient of performance as a line over them.

**Cost per kWh of heat.** COP times the spot price (Nordpool, Tibber, or the
energy dashboard's price entity) gives öre per kWh of heat, and "what direct
electric heating would have cost" gives the saving. Needs a price entity, which
is why it comes after the rest.

## Later

- **Delivered heat on an F-series without an EMK.** The F1255 at the second
  site will never have a COP with the code as it stands: its heat meters do not
  move. ΔT (BT2 - BT3) times the flow gives the heat, with the flow from the
  pump curve at the current speed or a figure the user types in. Opt-in, and
  marked *estimated* in the attributes exactly as the counted electricity is.
- **NIBE's MODBUS 40 accessory as an alternative to the gateway.** The same
  pump protocol behind a real MODBUS 40, reached as Modbus RTU through a
  TCP-to-RTU converter: holding registers only, addressed by their full number
  (40004 is 0x9C44) before MODBUS 40 version 10, writes as Write Multiple
  Registers only, and 2.1 s per register outside LOG.SET.
- **A card editor.** `getConfigElement`, so the card is configured in the
  dashboard editor rather than in YAML.
- **A reconfigure step** in the config flow, for a pump that changed address,
  without removing and re-adding it.
- **Hold stats.py's own keys to the backend as well.** The contract test
  checks what `stats_extra` builds, but not the keys `stats.py` adds itself
  (`ha_id`, `log_errors` and `log_warnings` since 1.7.2). The backend rejects a
  whole report over one unknown top-level key, so a key it does not know yet
  would silence every report without an error on this side.
