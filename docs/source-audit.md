# Source audit

Inspected 2026-09-23 America/Chicago. This records source-level evidence separately from hardware verification.

| Repository | Inspected commit |
| --- | --- |
| [Klipper](https://github.com/Klipper3d/klipper) | `ce7002bedf37e938bb483572949f3703ac6476cb` |
| [ArduinoCore-zephyr](https://github.com/arduino/ArduinoCore-zephyr) | `39f8354ffc80883d595746abe6b6e16b69a5efa8` |
| [arduino-router](https://github.com/arduino/arduino-router) | `cb7b2cecee1c04e0ba0a7fb48da63a8a7a1dba71` |

These repositories were downloaded for read-only inspection. None is a deployed firmware version. Web documentation and Zephyr main-branch links are moving references and must be pinned again during implementation.

## Findings

1. **No upstream U585 target in the inspected Klipper revision.** `src/stm32/Kconfig`, `Makefile`, and `internal.h` enumerate supported families without U5. This is a target/peripheral port, not a printer configuration change. It does not rule out unpublished or third-party ports.
2. **M33 and common timing code have precedent.** `src/rp2040/Makefile` builds RP2350 with `-mcpu=cortex-m33` and `generic/armcm_timer.c`. That timer reads `DWT->CYCCNT` and dispatches through SysTick. Reuse on U585 remains a bench-validation item.
3. **Direct Linux serial is plausible.** [Router's imola configuration](https://github.com/arduino/arduino-router/blob/cb7b2cecee1c04e0ba0a7fb48da63a8a7a1dba71/debian/arduino-router/var/lib/arduino-router/config/10-imola.conf) opens `/dev/ttyHS1` at 115200. It also uses GPIOs 37, 70, and 38 in lifecycle hooks. Their exact electrical identities and image-specific numbering must be confirmed before running any commands.
4. **RouterBridge uses LPUART1.** The Arduino UNO Q overlay declares `arduino,router-serial = <&lpuart1>`. [Zephyr common board description](https://github.com/zephyrproject-rtos/zephyr/blob/main/boards/arduino/uno_q/arduino_uno_q-common.dtsi) supplies PG7 TX, PG8 RX, PG6 RTS, PG5 CTS. Host and MCU source agree on an internal serial route, but an actual byte exchange has not been tested.
5. **Internal I/O needs special voltage handling.** [Arduino schematic](https://docs.arduino.cc/resources/schematics/ABX00162-schematics.pdf), MCU sheet (PDF page 19), labels PG2–PG15 as VDDIO2 at 1.8 V. This includes the LPUART pins. Ordinary header pins in the proposed allocation are MCU-domain signals; avoid treating every MCU port as 3.3 V.
6. **Sketch uploading is not standalone firmware uploading.** [flash_sketch.cfg](https://github.com/arduino/ArduinoCore-zephyr/blob/39f8354ffc80883d595746abe6b6e16b69a5efa8/variants/arduino_uno_q_stm32u585xx/flash_sketch.cfg) verifies/writes the loader, writes the sketch at `0x08100000`, resets, and writes a boot-control marker. The variant overlay puts image-0 at offset `0x10000`, animation at `0xd0000`, sketch at `0x100000`, and storage at `0x1c0000`. None of those offsets is established as a valid Klipper entry point.
7. **Upstream Zephyr and Arduino layouts differ.** [Zephyr board DTS](https://github.com/zephyrproject-rtos/zephyr/blob/main/boards/arduino/uno_q/arduino_uno_q.dts) describes a 64 KiB boot partition and different application slots, with a TZEN=0 comment. This comment does not establish the option bytes on a purchased board. The installed Arduino artifacts and actual MCU state take precedence.
8. **Shutdown support must survive the port.** Klipper `src/gpiocmds.c` enforces scheduled output duration/defaults; `src/adccmds.c` can shut down on ADC bounds; `src/stm32/watchdog.c` services IWDG. Register compatibility, timeout, and post-reset output state must be verified for U585.
9. **ADC is not just a pin map.** The Arduino overlay uses ADC1 channels 9/10/11/12/2/1 for A0–A5 and includes an analog-reference switch on PA2. Existing Klipper STM32 ADC code can export a 4095 maximum. Reference selection and chosen resolution require deliberate U5 implementation.

## What remains unverified

- Physical UNO Q SKU/revision, installed Linux image/kernel, architecture and Python versions.
- UART device path, supported baud rates, flow-control behavior, exclusive access, and latency under printing load.
- MCU ID, security/option bytes, bootloader contract, accessible flash backup, debug access, and recovery.
- Firmware compilation for the new target, all timing/ADC/output behavior, and first print.
- Printer electronics, motor currents, heater ratings, sensor models, wiring, and target step rate.

The existing hardware catalog was consulted at `../tools`. It contains a generic Arduino onboarding entry, but no identified UNO Q record. No catalog entry was invented for an unverified device. A model-specific record and setup log should be created when the actual board is onboarded.

Follow-up, 2026-09-25: the physical 2 GB board was identified over USB ADB and added to the hardware catalog at `../tools/boards/arduino-uno-q/`. See the [passive board inventory](../records/validation/2026-09-25-uno-q-board-inventory.md). This does not change the source-audit facts or establish the MCU boot/recovery contract.

User requirement confirmed during this assessment: a custom printer; prioritize the 2 GB model and consider 4 GB only if necessary. At the time of the audit, actual board ownership and revision were unconfirmed; the follow-up inventory confirms ownership and the 2 GB SKU, while the PCB revision remains open.

## Primary references

- [UNO Q user manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/)
- [UNO Q pinout](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)
- [UNO Q schematic](https://docs.arduino.cc/resources/schematics/ABX00162-schematics.pdf)
- [STM32U585AI device documentation and reference manual downloads](https://www.st.com/en/microcontrollers-microprocessors/stm32u585ai.html)
- [Zephyr UNO Q board documentation](https://docs.zephyrproject.org/latest/boards/arduino/uno_q/doc/index.html)
- [Arduino remoteocd](https://github.com/arduino/remoteocd)
- [Klipper code overview](https://www.klipper3d.org/Code_Overview.html)
- [Klipper protocol](https://www.klipper3d.org/Protocol.html)
- [Klipper benchmarks](https://www.klipper3d.org/Benchmarks.html)
