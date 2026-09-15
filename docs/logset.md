# LOG.SET: registers the F-series pump sends on its own

Through a NibeGW gateway every register the integration reads costs about a
second. LOG.SET is NIBE's way around that: a file loaded into the pump from a
USB stick that names up to 20 registers, which the pump then sends to MODBUS 40
- or to the gateway standing in for it - without being asked. The integration
takes those values as they arrive and stops reading those registers.

## Making the file

NIBE's tool for it, ModbusManager, is Windows only. `tools/make_logset.py`
writes the same file:

```bash
python tools/make_logset.py --list                          # show the selection
python tools/make_logset.py --out /Volumes/USBSTICK/LOG.SET  # F1155/F1255
python tools/make_logset.py --model F750 --out LOG.SET       # another model
```

A ready file for the F1155 and F1255 is in `esphome/LOG.SET`. Its 20 registers
are the most changeable of those shown by default: the temperatures around the
compressor, degree minutes, compressor frequency and state, both pump speeds,
electric additional heat, priority and the alarm. All are 16-bit: a 32-bit
register takes two of the 20 slots, and 32-bit values have been seen arriving
broken in pushes on several firmware versions.

The layout, as ModbusManager writes it (TAB-separated, CRLF line endings, ASCII):

```text
[NIBL;20260914;9696]
Divisors<TAB><TAB>10<TAB>10<TAB>...
Date<TAB>Time<TAB>BT1 Outdoor Temperature [C]<TAB>...
40004
40008
...
```

The pump uses the register lines. The two header rows are copied into its own
USB log files, which LOG.SET also configures - one file serves both.

## Loading it into an F1155/F1255

1. Copy the file to the root of a FAT32 USB stick, named exactly `LOG.SET`.
   On a Mac, run `dot_clean /Volumes/<stick>` before ejecting, so no `._LOG.SET`
   companion file is left beside it.
2. Put the stick in the USB port on the pump's display unit. Menu 7, USB,
   appears.
3. In menu 7.2, loggning, tick **aktiverad**. If an option to ignore LOG.SET is
   shown, leave it unticked.
4. Wait fifteen seconds, untick **aktiverad**, and remove the stick.

The selection stays in the pump after the stick is removed. Register 48889,
*MODBUS40 Disable LOG.SET*, must read *använd LOG.SET*; the integration creates
it as a switched-off entity named *LOG.SET-fil*. To clear the selection, load a
file with no register lines the same way.

## What to expect

Measured through an ESP32 gateway on an F1255, a telegram with all 20 values
arrives about every 2.1 seconds - not the twice a second NIBE's MODBUS 40 manual
gives, which is how quickly MODBUS 40 answers its own Modbus master from the
values it holds. Before a LOG.SET is loaded the telegrams still arrive, with
every slot empty.

The gateway relays these telegrams only to hosts that sent it a request within
the last two minutes, so the integration reads one register at least once a
minute even when LOG.SET covers everything shown.

## Not verified

- Whether the selection survives a power cut. One F750 owner found broken
  32-bit values after outages until the file was loaded again.
- Whether writing register 48889 switches pushing off without the USB menu.
- Whether files with LF line endings or UTF-8 titles work; the tool avoids both.

## Sources

- NIBE, MODBUS 40 installer manual IHB 1822-10: LOG.SET, loading steps, 20 parameters.
  <https://professional.nibe.eu/document/Installer%20manual%20(IHB)/031725-10.pdf>
- NIBE, FAQ LOG.SET (SE):
  <https://headless.nibe.eu/download/18.9a97aba184a9b5f272c5c/1669796068500/DOH%2014-262-36%20FAQ%20LogSet%201722-3.pdf>
- NIBE, F1255 installer manual IHB SE 1614-2: menu 7.2, loggning.
- ModbusManager-made files and bus captures: yozik04/nibe-mqtt#15 (F1245),
  yozik04/nibe#185, elupus/esphome-nibe#56 (F1255, telegram timing).
- An independent generator the format was cross-checked against:
  <https://github.com/per42/nibe-log-set>
