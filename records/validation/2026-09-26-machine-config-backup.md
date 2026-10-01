# UNO Q machine configuration backup

- Date: 2026-09-26
- Board: Arduino UNO Q 2 GB; device-specific ADB serial intentionally omitted
- Source: `/home/arduino/printer_data/config`
- Result: **PASS: every regular file in the live machine configuration directory has a byte-for-byte local copy**

The live directory was inventoried over USB/ADB without changing the board.
All five regular files were copied to a temporary staging directory and
verified by SHA-256. Three files already matched tracked repository sources;
the two missing historical files were then added to the repository.

| Board-side file | Tracked mirror | SHA-256 |
| --- | --- | --- |
| `moonraker.conf` | `machine-config/uno-q/moonraker.conf` | `5d4811dcc02e482bb576c0358e8a1b2e43e1498cc04c09159ae361e5c78c8b2d` |
| `.moonraker.conf.bkp` | `machine-config/uno-q/.moonraker.conf.bkp` | `f5d842fbf1cd9cd86ad3c7e3b4abf23c4428e5256600c08dd2e224208a8a3f75` |
| `printer.cfg` | `machine-config/uno-q/printer.cfg` | `bfd9b04aa01e3eb4bcd9537603903a12f13d09e76f5200540f609ba206ec8adb` |
| `printer.cfg.pre-cnc-shield-v3` | `machine-config/uno-q/printer.cfg.pre-cnc-shield-v3` | `09a201813fb0e4f252765a53c27a875437193e5786fae4cfab58cbb216576eb9` |
| `printer.cfg.y-only-verified` | `machine-config/uno-q/printer.cfg.y-only-verified` | `2b75adc04d71a388068b89cbe6cfc6a158119b95b9003c6740a4671579d2dba4` |

The generated Moonraker backup is semantically equivalent to
`host/moonraker.conf`; Moonraker rewrote its separators and indentation. The
tracked mirror preserves the exact bytes found on the board. Run
`scripts/sync-machine-configs.sh` to refresh the complete mirror and checksum
manifest.
