# NIBE's own Modbus documentation

Everything here is published by NIBE for installers at
[professional.nibe.eu → Tjänster → Verktyg → Kommunikation → NIBE Modbus](https://professional.nibe.eu/sv-se/tjanster/verktyg/kommunikation/nibe-modbus).
The documents are NIBE's and are linked rather than copied into this repository.

## S-series — what this integration uses

| Document | What it gave this integration |
|---|---|
| [Modbus S-serien, M12676SV (2026-02-19)](https://headless.nibe.eu/download/18.1eeb10f19c59bc9548221/1771504846754/M12676SV(2026-02-19).pdf) | Official confirmation of two things first found by probing: 32-bit values come back low word first, and must be written with *write multiple holding registers*. Its register table supplies the value labels in `official.py`. |
| [Modbus register S-serien (version 202601)](https://headless.nibe.eu/download/18.13db0fae19bbf569bbb157/1769065468801/Modbusregister%20.pdf) | NIBE's firmware enumeration of every register, with its data type in the name (`eMbInput_eS16BT1Outdoor_0 = 1`). The numbering matches the addressing used here: entry 1 is register 30002. |
| [Larmlista S-serien](https://headless.nibe.eu/download/18.63a538118cfe56782c1087/1705998315513/Kopia%20av%20Alarmslist%20A-Larm.pdf) | The class A alarm list, source of `alarms.json` via `tools/extract_nibe_alarms.py`. |

Not yet used: eight registers where the register table's data type differs
from the `nibe` library's (for example the alarm number is `u16`, not `s16`),
and 77 registers the table documents that no published map carries. For the
values seen on the development unit the type differences give identical
readings, so they have not been applied.

## F-series — for a future MODBUS 40 connection

The older F-series pumps and SMO 40 do not speak Modbus TCP; they need NIBE's
MODBUS 40 accessory. These describe that path.

| Document | |
|---|---|
| [Modbus 40 NIBE SMO 40](https://headless.nibe.eu/download/18.9a97aba184a9b5f272c79/1669796426064/Modbus%2040%20NIBE%20SMO%2040.pdf) | Parameter list |
| [Modbus 40 NIBE F1355](https://headless.nibe.eu/download/18.9a97aba184a9b5f272c80/1669796538703/F1355.pdf) | Parameter list |
| [Modbus 40 NIBE F1345](https://headless.nibe.eu/download/18.9a97aba184a9b5f272c86/1669796955280/Modbus40%20F1345%201720-2.pdf) | Parameter list |
| [Modbus 40 A3 F1345, dockningsprincip](https://headless.nibe.eu/download/18.9a97aba184a9b5f272c92/1669797336609/ModbusDockning_A3_1345_Svenska.pdf) | Wiring |
| [Vanliga frågor och svar, MODBUS 40](https://headless.nibe.eu/download/18.9a97aba184a9b5f272c51/1669796001070/FAQ_SE_MODBUS40-2.pdf) | FAQ |
| [Vanliga frågor om Log.Set](https://headless.nibe.eu/download/18.9a97aba184a9b5f272c5c/1669796068500/DOH%2014-262-36%20FAQ%20LogSet%201722-3.pdf) | Choosing which parameters MODBUS 40 prioritises |
| [Larmlista (F-series)](https://headless.nibe.eu/download/18.9a97aba184a9b5f272c66/1669796147755/Larms%C3%B6k%20Emmy%202044-5.pdf) | Alarm list |

NIBE also offers *ModbusManager*, a Windows program for building MODBUS 40
log.set files. It is not needed for the S-series.
