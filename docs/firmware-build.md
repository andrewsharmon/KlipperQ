# STM32U585 firmware build

The minimal UNO Q firmware target lives in the sibling `../klipper` checkout on its `uno-q` branch. The build currently uses the existing `arducnc` Lima VM and Zephyr SDK 1.0.1 because the host does not have a native Arm embedded toolchain.

Run the clean build and static artifact checks from the KlipperQ root:

```sh
scripts/build-stm32u585.sh
```

The wrapper copies `test/configs/stm32u585.config` to `.config`, performs a clean serial build, checks for software division and whitespace errors, runs `git diff --check`, and verifies the resulting ELF, binary, and protocol dictionary. The serial build avoids a generated-header race caused by millisecond-scale host/VM clock skew on the mounted source tree. The verifier checks the ARM ELF format, vector table and initial stack pointer, declared flash/RAM bounds, required startup/UART symbols, serial configuration, and SHA-256 hashes.

The Zephyr SDK supplies `libc.a` rather than the `libc_nano.a` expected by Klipper's normal GNU Arm toolchain. The STM32 makefile now exposes `STM32_LIBC`, defaulting to `c_nano`; the wrapper selects `STM32_LIBC=c` without replacing Klipper's compile or link flags.

Optional environment variables:

- `KLIPPER_SRC`: firmware checkout; default `../klipper`.
- `LIMA_VM`: Lima VM name; default `arducnc`.
- `LIMACTL`: `limactl` executable; default `../qstep/tools/bin/limactl`.
- `CROSS_PREFIX`: guest-visible compiler prefix; default `/home/andrewharmon.guest/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-`.

To re-run only the artifact checks:

```sh
scripts/verify-stm32u585.py --firmware ../klipper
```

These commands compile and inspect files only. They do not connect to, reset, debug, or flash the UNO Q. After a successful build, follow the board-specific [flash and protocol-check guide](firmware-flash.md).
