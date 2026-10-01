# STM32U585 firmware flashing and first protocol check

This procedure is specific to the inventoried Arduino UNO Q. Its device-specific USB serial is intentionally not stored in the repository; discover and select the attached board at runtime. The procedure uses the OpenOCD installation already present on the board and writes a standalone image at `0x08000000`. Disconnect printer loads before using it. It does not change option bytes.

The stock MCU flash was preserved before the first write:

- Board: `/home/arduino/uno-q-stock-stm32u585-2026-09-25.bin`
- Catalog copy: `uno-q-stock-stm32u585-2026-09-25.bin` in the maintainer's private board-backup catalog (not published)
- Size: 2,097,152 bytes
- SHA-256: `c550fc1a0bfa988014af6c877e5e5ab31c54e63b34be55b318ebc216ac4062d0`

Build and statically verify the firmware first:

```sh
scripts/build-stm32u585.sh
```

Transfer the resulting binary and dependency-free protocol probe:

```sh
adb push ../klipper/out/klipper.bin /home/arduino/klipper-stm32u585.bin
adb push scripts/probe-klipper-uart.py /home/arduino/probe-klipper-uart.py
adb shell sha256sum /home/arduino/klipper-stm32u585.bin
```

The firmware binary for the pinned commit has SHA-256 `e39002fa78c0119182e5a7dd86e415b04c2b0f8171b9e1a69e18bdb9160c2a44` (the earlier uncommitted bring-up image was `48e37002434867991b5db76f2ec8dbddee2430f7ab85671d114c106af8a89282`). Stop both stock UART owners, then program and verify the exact image:

```sh
adb shell 'systemctl stop arduino-app-cli arduino-router; /opt/openocd/bin/openocd -d2 -s /opt/openocd -f openocd_gpiod.cfg -c "reset_config srst_only srst_push_pull; init; reset halt; flash write_image erase /home/arduino/klipper-stm32u585.bin 0x08000000 bin; verify_image /home/arduino/klipper-stm32u585.bin 0x08000000 bin; reset; shutdown"'
```

Do not restart `arduino-router` while Klipper owns the MCU UART. Validate identify, configuration, and two clock samples with:

```sh
adb shell 'python3 /home/arduino/probe-klipper-uart.py --device /dev/ttyHS1 --baud 115200 --timeout 3 --retries 3'
```

The probe uses only Python's standard library. It is a bring-up diagnostic, not a substitute for the remaining stock-Klippy integration and synchronization tests.

Use `--clock-wait SECONDS` to select the interval between its two clock queries. A 25-second interval is useful for observing a natural wrap of the 32-bit 160 MHz counter when the starting phase permits it.

## Prepared stock restoration

The following restoration command is prepared from the verified full-flash backup, but restoration has **not yet been executed**. Do not describe it as tested until a full restore, stock protocol check, Klipper reflash, and repeat probe have all passed.

```sh
adb shell 'systemctl stop arduino-app-cli arduino-router; /opt/openocd/bin/openocd -d2 -s /opt/openocd -f openocd_gpiod.cfg -c "reset_config srst_only srst_push_pull; init; reset halt; flash write_image erase /home/arduino/uno-q-stock-stm32u585-2026-09-25.bin 0x08000000 bin; verify_image /home/arduino/uno-q-stock-stm32u585-2026-09-25.bin 0x08000000 bin; reset; shutdown"'
```

Restart `arduino-router` and `arduino-app-cli` only after the stock image is restored and verified. If any write or verification command fails, leave printer loads disconnected and do not start a service whose protocol does not match the active MCU image.
