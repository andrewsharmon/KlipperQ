# STM32U585 first flash and native-UART protocol validation

- Date: 2026-09-25
- Checklist scope: Stage 5 board-specific flash; partial protocol bring-up
- Board: Arduino UNO Q 2 GB; device-specific USB serial intentionally omitted
- Result: **PASS for flash verification, identify, configuration query, and short repeated clock queries**
- Not established: stock Klippy runtime, long synchronization, scheduled GPIO timing, cold boot, watchdog/fault behavior, or executed stock restoration

## Firmware and host

- Klipper source branch: sibling `klipper` checkout, branch `uno-q`, based on `ce7002bedf37e938bb483572949f3703ac6476cb`
- Reported firmware version: `v0.13.0-770-gce7002bed-dirty-20260925_190446-lima-arducnc`
- Toolchain: Zephyr SDK 1.0.1 GCC 14.3.0, binutils 2.43.1
- Binary size: 22,596 bytes
- Binary SHA-256: `48e37002434867991b5db76f2ec8dbddee2430f7ab85671d114c106af8a89282`
- Linux UART: `/dev/ttyHS1`, 115200 baud, no hardware flow control
- Probe: `scripts/probe-klipper-uart.py`, Python standard library only

## Preconditions and recovery assets

Printer loads were disconnected. The stock 2 MiB flash backup was present on the board and in the hardware catalog, and both copies matched SHA-256 `c550fc1a0bfa988014af6c877e5e5ab31c54e63b34be55b318ebc216ac4062d0`. The MCU had previously reported TrustZone disabled and RDP level 0. No option bytes were changed.

## Flash procedure and result

The stock `arduino-app-cli` and `arduino-router` services were stopped. OpenOCD used the board's installed GPIO-SWD configuration and wrote the standalone binary at `0x08000000` with erase and `verify_image`. OpenOCD identified STM32U585 revision U, 2,048 KiB dual-bank flash, padded the final write to the flash alignment, and completed verification before reset and shutdown. Both Arduino services were intentionally left inactive to avoid UART contention.

The first attempted OpenOCD invocation omitted `-s /opt/openocd`, failed while locating `stm32u5x.cfg`, and performed no erase. Its failure path restarted both stock services. The corrected invocation matched Arduino's installed wrapper search path and passed.

## Protocol results

The dependency-free probe synchronized to the MCU's current four-bit sequence number, downloaded and decompressed the Klipper identify dictionary, and reported:

- MCU: `stm32u585xx`
- Clock constant: 160,000,000 Hz
- Serial baud constant: 115,200
- Commands: 66
- `get_config`: `is_config=0`, `crc=0`, `is_shutdown=0`, `move_count=0`

Two clock queries separated by approximately 109 ms advanced by about 16.7 million ticks, consistent with a 160 MHz clock plus host/protocol timing. Ten successive complete probe processes passed, followed by five more after correcting and reference-testing the probe's unsigned VLQ decoder. Reference vectors matched Klipper's `PT_uint32` encoder/decoder, including high uint32 values.

A final probe used a 25-second clock interval. The counter moved from `3867032384` to `3570416773`, a modulo-32-bit advance of `3998351685` ticks over 25.009 host seconds. The end value being lower than the start directly observes one natural 32-bit counter wrap while communication remained functional.

This proves startup, the fixed clock, one natural DWT counter wrap, LPUART1 RX/TX interrupts, framing/CRC, identify transfer, and basic command dispatch. It does not satisfy the one-hour synchronization or repeated-wrap acceptance gate.

## Recovery status

A proposed full stock restore was not executed because it is an additional destructive write requiring explicit authorization. The verified backup and prepared command are documented in `docs/firmware-flash.md`; restoration remains untested. At the end of this validation the MCU was running Klipper and `arduino-router` / `arduino-app-cli` were inactive.
