# STM32U585 minimal-port build

- Date: 2026-09-25
- Checklist scope: Stage 4 compile-only progress
- Firmware baseline: `ce7002bedf37e938bb483572949f3703ac6476cb` plus the uncommitted `uno-q` worktree changes described below
- STM32 HAL source: Zephyr `hal_stm32` commit `fc11896dd39cfca37bf9b4aeaaa2df8861b81875`
- Zephyr board-reference source: commit `1743741760ee5d2d58da50d504855d43f9f8e826`
- Build environment: local `arducnc` Lima VM
- Compiler: `arm-zephyr-eabi-gcc (Zephyr SDK 1.0.1) 14.3.0`
- Binutils: GNU ld 2.43.1
- Python: 3.13.5
- Hardware: no hardware required for this build; see the separate [board inventory](2026-09-25-uno-q-board-inventory.md)

## Implemented scope

The sibling `../klipper` worktree now contains a minimal STM32U585 target:

- Kconfig selection, Cortex-M33 build rules, and `test/configs/stm32u585.config`.
- Official STM32U5 CMSIS device/system and required LL headers, with license and source revision.
- A standalone `0x08000000` image using the 2 MiB flash and contiguous 768 KiB SRAM1+SRAM2+SRAM3 map recorded by the board's Zephyr description.
- The published UNO Q 160 MHz clock tree: 4 MHz MSIS calibrated by the 32.768 kHz LSE, then PLL1 `/1 *80 /2`, voltage scale 1, EPOD boost, and four flash wait states.
- Cortex-M33 DWT/SysTick through Klipper's existing generic timer implementation.
- Basic GPIO through Klipper's existing STM32 GPIO implementation.
- LPUART1 at 115200 baud on PG8/PG7, including the UNO Q VDDIO2 enable and native Klipper serial interrupt machinery.
- A generic Cortex-M cache guard fix so M33 does not enter the M7-only data-cache path.

ADC, SPI, I2C, hardware PWM, and USB are intentionally not advertised by this minimal target.

## Build and static verification

Result: **PASS for compile and static layout only**.

- `scripts/check_whitespace.sh`: pass.
- `git diff --check`: pass.
- `scripts/check-software-div.sh .config out/klipper.elf`: pass.
- Clean STM32U585 compile/link: pass.
- `scripts/build-stm32u585.sh` clean end-to-end build and verification: pass.
- `scripts/verify-stm32u585.py`: pass for dictionary, ELF/vector, memory bounds, required symbols, and hashes.
- Clean existing `test/configs/stm32g431.config` regression compile/link: pass.
- ELF format: ELF32 little-endian ARM, soft-float ABI.
- Entry/vector-table address: `0x08000000`.
- Initial stack pointer encoded in vector table: `0x200c0000`.
- `.data`: starts at `0x20000000`.
- `.stack`: `0x200bfe00` through `0x200c0000`.
- Protocol dictionary: MCU `stm32u585xx`, clock 160 MHz, serial 115200 baud, reserved pins PG8/PG7.
- Allocated sections: `.text` 22,544 bytes; `.data` 52 bytes; `.bss` 544 bytes; stack 512 bytes.
- `klipper.elf` SHA-256: `f7500326847bb5e4e40ff287d5247e9a3f5e5a6c6c667dbd23a4d620f485b40d`.
- `klipper.bin` SHA-256: `48e37002434867991b5db76f2ec8dbddee2430f7ab85671d114c106af8a89282`.
- `klipper.dict` SHA-256: `b06af268feed5a534f15206121b1b5226201a67eff51bef9d4c3013dba20c46f`.

The Zephyr SDK provides embedded `libc.a`, not the `libc_nano.a` name expected by Klipper's normal GNU Arm toolchain. The STM32 makefile now exposes `STM32_LIBC`, defaulting to `c_nano`; this validation selected `STM32_LIBC=c` while retaining Klipper's normal Cortex-M33, Thumb, LTO, garbage-collection, and linker-script flags. The SDK also emits pre-existing `__noreturn` redefinition warnings from its C library headers.

The VM-mounted macOS source tree showed millisecond-scale clock-skew warnings. An initial parallel wrapper run raced generated headers and failed; the wrapper now builds serially, and the subsequent clean run passed. The warnings remain visible but did not omit or stale any artifact in the passing serial run.

The Klippy import check was attempted but not run because this VM's Python environment lacks `greenlet`. No dependency was installed as part of this compile-only task.

## Not validated

No image was flashed. Startup, HSE/LSE/MSI behavior, DWT access, UART electrical behavior, Klippy identification, clock synchronization, GPIO timing, cold boots, watchdog timing, shutdown behavior, and recovery remain untested. The firmware lock remains at the unmodified upstream baseline until the implementation is committed and its validation scope can be pinned precisely.
