# Arduino UNO Q board inventory

- Date: 2026-09-25
- Scope: initial read-only discovery followed by stock-image recovery inventory before the separately recorded first Klipper flash
- Result: **PASS for board discovery, stock-state confirmation, SWD read access, and factory-flash preservation**
- Firmware operation: the initial section below preserves the first passive observation; the follow-up stopped/restarted stock services, halted/read the MCU over SWD, and created a full flash backup without changing option bytes

## Host connection

- USB product: `Arduino Uno Q - uno-q`
- USB VID:PID: `2341:0078`
- USB serial: verified at runtime and intentionally omitted from repository files
- macOS CDC node at the time of testing: `/dev/cu.usbmodem*` (device-specific suffix omitted)
- USB interface 0: vendor-specific ADB (`ff/42/01`) with bulk endpoints `0x01` and `0x81`
- USB interfaces 1/2: CDC control/data
- ADB client: Google platform-tools 37.0.1, downloaded to a temporary directory; `adb devices -l` reported state `device`

The CDC node did not emit a prompt. Arduino's documented access path for this USB interface is ADB; `adb shell` connected as root without modifying the board.

## Board and OS identity

- Device-tree model: `Arduino SA,Imola`
- Compatible strings: `arduino,imola`, `qcom,qcm2290`, `qcom,qrb2210`
- Host CPU architecture: AArch64, four processors
- Memory: `MemTotal: 1777272 kB`, consistent with the 2 GB UNO Q SKU
- eMMC: 14.6 GiB block device, consistent with nominal 16 GB storage
- OS: Debian GNU/Linux 13 (trixie)
- Kernel: `6.16.0-rt-qstep1`, PREEMPT_RT, build dated 2026-09-24
- Python: 3.13.5
- Normal non-root account: `arduino`, home `/home/arduino`

## Internal MCU path and active workload

- Internal UART device: `/dev/ttyHS1`, group `dialout`; no process held it during the check.
- Installed `arduino-router` 0.1.13 service configuration selects `/dev/ttyHS1` at 115200 baud.
- `arduino-router.service` and `arduino-app-cli.service` were both disabled; the router was inactive.
- A QStep/LinuxCNC workload was active. Passive HAL reads reported watchdog false, zero link errors, zero late frames, zero MCU bad frames, and 2.1 microseconds maximum recorded MCU ISR time.

The active QStep workload is user state and was left untouched. Before any Klipper flash or UART takeover, stop/recovery sequencing and preservation must be planned explicitly.

## Installed tools

- Arduino CLI 1.2.3-rc.3
- Arduino Router 0.1.13
- Arduino App CLI 0.1.13
- LinuxCNC userspace 2.9.4 package
- OpenOCD `0.12.0+dev-ge6a2c12f4` at `/opt/openocd/bin/openocd`
- No `remoteocd` executable was found in `/usr` or `/opt`

## Remaining gates

Hardware revision/label inspection, a complete option-byte record, bootloader/image partition interpretation, and an executed stock restoration remain open. The subsequent Klipper write and protocol results are in `2026-09-25-stm32u585-first-flash.md`.

## Stock-reset and recovery follow-up

After the user returned the board to its stock image, the host reported Debian 13 with kernel `6.16.0-geffa8626771a`. `arduino-router.service` and `arduino-app-cli.service` were enabled and active, the router owned `/dev/ttyHS1` at 115200 baud, and no QStep/LinuxCNC process was running.

The installed recovery path is `/opt/openocd/bin/openocd` with `/opt/openocd/openocd_gpiod.cfg`. The configuration uses Linux GPIO SWD with reset on gpiochip 1 line 38, SWCLK line 26, and SWDIO line 25. A halt/read/reset/shutdown check identified STM32 device ID `0x30076482`, revision U, 2,048 KiB dual-bank flash, TrustZone disabled (`TZEN=0`), and readout protection level 0 (`0xAA`). Both stock services were restarted successfully after the read-only check.

The complete readable MCU flash was then backed up with printer loads disconnected:

- Board copy: `/home/arduino/uno-q-stock-stm32u585-2026-09-25.bin`
- Catalog copy: `/Users/andrewharmon/git/tools/boards/arduino-uno-q/backups/uno-q-stock-stm32u585-2026-09-25.bin`
- Size: 2,097,152 bytes
- SHA-256 on both copies: `c550fc1a0bfa988014af6c877e5e5ab31c54e63b34be55b318ebc216ac4062d0`

The backup and OpenOCD write/verify mechanism are available, but a full stock-image restoration has not been executed. This is preserved as an explicit remaining recovery test.
