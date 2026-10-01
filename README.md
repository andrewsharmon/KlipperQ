# KlipperQ: Klipper on Arduino UNO Q

An independent project bringing Klipper's Linux host and real-time motion control together on one Arduino UNO Q.

> **Status:** partial hardware bring-up. This is not a working printer setup and there is no supported install. The firmware port has only moved a single stepper motor (the Y axis, on the bench, through a CNC Shield v3 with a TMC2208 driver). Heaters, endstops, other axes, and the long-run synchronization, clock-wrap, cold-boot and watchdog/recovery tests have not been done. See [`firmware.lock.json`](firmware.lock.json) and [`records/validation/`](records/validation/).

> [!WARNING]
> **Safety:** KlipperQ is experimental firmware for machines with motors and, eventually, heaters. It has not been validated for printing. Do not run it with heaters connected or leave it unattended. Only run it on the bench or on a machine that can't hurt anyone, and keep a way to cut motor and heater power within reach. KlipperQ comes with no warranty (see the GPL).

## Repositories

- [KlipperQ](https://github.com/andrewsharmon/KlipperQ) contains project plans, hardware integration, setup and recovery documentation, and validation records.
- [Klipper firmware fork](https://github.com/andrewsharmon/klipper/tree/uno-q) contains firmware development on the `uno-q` branch, with [Klipper upstream](https://github.com/Klipper3d/klipper) tracked separately.

See [the development workflow](docs/development.md) and [`firmware.lock.json`](firmware.lock.json) for the pinned firmware baseline. The pin records a source revision, not a validated UNO Q release.

## Feasibility

Feasibility assessment, 2026-09-23. **Conditional go: technically plausible, but requires an STM32U585 Klipper firmware port and a printer power/interface carrier. It is not currently a supported installation.**

The intended architecture keeps all printer computing on the UNO Q:

```mermaid
flowchart LR
    UI[Browser] --> L[UNO Q Linux: Moonraker and Klippy]
    L <-->|Internal UART: native Klipper protocol| M[UNO Q STM32U585: Klipper MCU firmware]
    M --> D[External stepper drivers]
    M --> H[External heater and fan power stages]
    S[Thermistors and endstops] --> M
```

The browser can run on another device; it is not required to keep a print running. Motor drivers, heater switches, sensor circuits, and a printer power supply remain necessary. No Raspberry Pi or additional printer-control MCU is required by the proposed design.

Target: Andrew's custom printer, using the **2 GB UNO Q**. There is no identified requirement for the 4 GB model; the plan includes memory validation on 2 GB.

| Area | Assessment |
| --- | --- |
| Linux host | Good fit for normal Klippy, Moonraker, and a web interface; installation still needs board validation. |
| Onboard MCU | Adequate-looking compute and memory, but upstream Klipper has no STM32U585 target. |
| Internal connection | A physical UART exists; direct serial should let the host protocol remain unchanged. |
| Printer I/O | A basic four-motor printer fits a provisional header allocation. Electrical interfacing is required. |
| Main uncertainty | Correct MCU startup, clock/timer behavior, UART integration, ADC, and safe recovery. |

Read the [implementation plan](docs/implementation-plan.md), [ordered implementation and testing checklist](docs/execution-checklist.md), and [source audit](docs/source-audit.md). The original conclusion was based on documentation and source inspection. Subsequent compile, board-inventory, and first-flash results are recorded under `records/validation/`.

Immediate milestone: make unmodified Klippy on the UNO Q identify its onboard STM32 running a minimal Klipper port, maintain clock synchronization, and toggle one unloaded output with measured timing.

Implementation status, 2026-09-25: the sibling `klipper` worktree contains an initial STM32U585 target with startup/clock, generic timing/GPIO, and the internal LPUART1 transport. The clean build and static memory checks pass. That image has also been flashed and verified on the physical 2 GB UNO Q; a dependency-free host probe completed Klipper identify, `get_config`, and repeated `get_clock` requests over `/dev/ttyHS1` at 115200 baud. See the [build guide](docs/firmware-build.md), [flash guide](docs/firmware-flash.md), and [first-flash validation record](records/validation/2026-09-25-stm32u585-first-flash.md). Scheduled GPIO measurement, long synchronization, cold boots, and an executed stock-image restoration remain open.

Host update, 2026-09-26: Klippy, Moonraker, and Mainsail now run on the UNO Q. Stock Klippy connects to and configures the onboard MCU at 115200 baud. Mainsail is available to the attached computer over a USB/ADB forward at `http://127.0.0.1:8181/`; see the [USB web UI guide](docs/usb-web-ui.md) and [validation record](records/validation/2026-09-26-usb-web-ui.md). The initial no-output configuration remains in [`config/uno-q-minimal.cfg`](config/uno-q-minimal.cfg). The active hardware configuration is [`config/uno-q-cnc-shield-v3.cfg`](config/uno-q-cnc-shield-v3.cfg): it maps the complete generic CNC Shield V3.00 interface, exposes X/Y/Z as manual steppers, configures their limit inputs, control buttons, probe input, and safe-low spindle/coolant outputs, and documents the spindle-versus-independent-A multiplex. Physical Y motion and the expanded configuration's controller state have been verified; see the [CNC Shield validation record](records/validation/2026-09-26-cnc-shield-v3-y.md).

All files in the board's live machine configuration directory have byte-for-byte local copies. Run `scripts/sync-machine-configs.sh` to refresh the tracked [`machine-config/uno-q`](machine-config/uno-q) mirror over USB/ADB, and see the [configuration backup manifest](records/validation/2026-09-26-machine-config-backup.md) for the initial snapshot validation.

Run `scripts/connect-mainsail-adb.sh` on the Mac to restore and verify the complete USB path. Add `--restart` to restart the board-side Klipper, Moonraker, and nginx services before reconnecting.

## License

KlipperQ is licensed under the [GNU General Public License v3.0](LICENSE).
