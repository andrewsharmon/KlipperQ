# Implementation plan

Confirmed target: a **custom printer using the 2 GB Arduino UNO Q**, with 4 GB acceptable only if measurements establish a requirement. Planning baseline for the unspecified mechanics: Cartesian XYZ plus one extruder, one hotend, heated bed, three endstops, and two controllable fans. Board ownership/revision, kinematics, drivers, and performance requirements are still unknown. This is an engineering plan, not an executable flashing procedure.

## Decision and architecture

Proceed with a short bring-up investigation before committing to a carrier PCB. The hardware has the right host/MCU split. The Linux side is relatively conventional; the STM32U585 port is the primary engineering task.

Arduino documents a quad-core Cortex-A53 Linux processor and a 160 MHz Cortex-M33 MCU with 2 MB flash and approximately 768 KiB SRAM. Both UNO Q memory variants appear sufficient for a headless printer host; that is a capacity judgment, not a benchmark. [Arduino manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/), [Zephyr board documentation](https://docs.zephyrproject.org/latest/boards/arduino/uno_q/doc/index.html).

Run Klippy and Moonraker as native Linux services, with Mainsail or Fluidd for the interface. Use Arduino's supported Linux image and kernel initially. Install Python dependencies in virtual environments and compile Klipper's host C helper on the board. Validate the image's Python version against the pinned requirements; do not assume a Raspberry Pi OS image or an installer written for another board will work. [Klipper installation](https://www.klipper3d.org/Installation.html), [Moonraker installation](https://moonraker.readthedocs.io/en/latest/installation/).

Treat 2 GB as the acceptance platform. Run headless, serve the browser interface to another device, and keep optional camera/AI/desktop workloads out of the initial printing workload. Measure available memory, service peak RSS, swap activity, OOM events, and scheduling errors during the representative soak. Proposed target: at least 25% RAM available at peak normal load, no OOM events, and no sustained swapping. Reconsider 4 GB only if the required workload cannot meet this after removing unnecessary services; extra RAM will not resolve MCU timing or UART defects.

Keep Klipper's existing division of responsibility: Linux performs G-code interpretation, planning, kinematics, and heater control calculations; the MCU executes queued step timing, samples inputs, schedules outputs, and enforces MCU shutdown behavior. PID is not simply moved wholesale to the MCU. [Klipper code overview](https://www.klipper3d.org/Code_Overview.html).

Replace the Arduino/Zephyr application environment on the MCU with bare-metal Klipper firmware. Preserve the existing bootloader only if its image contract can be established and supported cleanly. Arduino sketches and RouterBridge will not run alongside this firmware. A Zephyr-hosted Klipper port is an alternative, but adds scheduler/interrupt integration and is not the recommended first implementation.

## Host-to-MCU transport

Use the onboard UART first:

- Arduino's Linux router configuration selects `/dev/ttyHS1` at 115200 baud.
- Arduino's MCU overlay selects LPUART1 for RouterBridge. Zephyr assigns TX/RX to PG7/PG8, with optional RTS/CTS on PG6/PG5.
- The schematic places PG2–PG15 on the 1.8 V VDDIO2 domain. The port must initialize that I/O supply domain correctly; ordinary external UNO header GPIO is a different voltage domain.

Evidence and exact source revisions are in [the audit](source-audit.md). The TTY name and Linux GPIO numbering must be confirmed on the actual image.

Send the native binary Klipper protocol directly over the UART. Do not wrap step commands in Arduino MessagePack RPC or issue per-step Linux GPIO writes. Klipper already supports queued, timestamped commands and serial error handling. [Protocol documentation](https://www.klipper3d.org/Protocol.html).

Start communication bring-up at 115200, then qualify 250000 and higher rates supported by both devices. A nominal 250000-baud 8N1 link provides 25000 bytes/s before protocol overhead; this is not a step-rate limit because Klipper compresses groups of steps. Measure actual workload bandwidth and deadline behavior. Begin without hardware flow control on both sides; verify that the Linux driver and wiring permit it. Add flow control only if testing demonstrates a need and host support is implemented.

Before taking ownership of the UART, inspect and replace conflicting service behavior. Arduino's current router unit has stop hooks that change Linux GPIOs and pulse an MCU control line. Stopping the service is not necessarily a passive serial close. Also audit App Lab/upload services and anything else capable of resetting or reflashing the MCU. Define a dedicated printing mode with exclusive UART ownership and predictable boot order.

Keep SPI3 as a contingency. An internal SPI bus is documented, but the MCU-slave transport, host integration, buffering, and readiness signaling would require additional work. Klipper's sensor-SPI support is not automatically a host-to-MCU SPI transport. USB-C should not be assumed to expose a direct MCU USB serial link.

## Firmware work packages

Upstream commit `ce7002bedf37e938bb483572949f3703ac6476cb` has no STM32U5 selection, headers, or platform implementation. Cortex-M33 itself is already used by Klipper's RP2350 target, so the CPU architecture is not a fundamental obstacle. See the pinned [STM32 build rules](https://github.com/Klipper3d/klipper/blob/ce7002bedf37e938bb483572949f3703ac6476cb/src/stm32/Makefile) and [RP2350 build rules](https://github.com/Klipper3d/klipper/blob/ce7002bedf37e938bb483572949f3703ac6476cb/src/rp2040/Makefile).

| Work package | Expected changes and acceptance evidence |
| --- | --- |
| Target and startup | Add STM32U585 selection in `src/stm32/Kconfig`, build rules, ST device headers with license attribution, `internal.h` selection, vector/linker and SRAM-bank setup. Verify actual boot address, TrustZone state, option bytes, and reset entry. |
| Clocks and power | Add U5 clock/reset helpers and startup, likely `stm32u5.c`. Verify oscillator source, PLL, voltage scaling, flash wait states, peripheral clocks, and VDDIO2 enable. The board has a 16 MHz HSE, while Zephyr's published PLL configuration uses MSI; do not copy a guessed HSE recipe. |
| Timebase | Evaluate `generic/armcm_timer.c` with U585 DWT/SysTick, interrupt priorities, and security permissions. Prove operation after power-on with no debugger. Keep CPU clock fixed and avoid sleep states that stop the timebase. At 160 MHz a 32-bit counter wraps about every 26.8 seconds; test repeated wraparound. |
| Serial | Implement LPUART1 pin mux, clock, baud divisor, RX/TX interrupts, and error recovery using `generic/serial_irq.c`. U5 LPUART is not a drop-in selection of the existing USART code. Pass identify, configuration, and clock queries from stock Klippy. |
| GPIO and motion | Audit GPIO register compatibility and port lookup, then reuse common stepper/endstop code. Check pulse widths, direction setup/hold, shutdown states, and simultaneous axes on a scope. |
| Temperature | Implement/audit U5 ADC1 calibration, channel selection, sample times, reference supply and board analog switch. Export the correct `ADC_MAX`; do not reuse a 12-bit constant with a differently configured ADC. Validate known resistor values and open/short faults. |
| Outputs and watchdog | Start with Klipper software PWM for heaters/fans. Verify U5 watchdog initialization, measured timeout, reset behavior, output-duration enforcement, and safe output defaults. Hardware PWM can follow. |
| Optional peripherals | Add SPI/I2C, TMC configuration, accelerometer, probe, and CAN only as required after the core printer path passes. |

Retain Klipper's common protocol, scheduler, stepper, endstop, and heater-output machinery. Avoid cloning application-level behavior into a separate Arduino program. Keep target-specific changes small enough to maintain and potentially submit upstream.

## Flashing and recovery

Arduino's `remoteocd` supports MCU flashing from the UNO Q's Linux environment. This is evidence that another permanent controller is unnecessary; it is not proof that any arbitrary binary is bootable. [remoteocd](https://github.com/arduino/remoteocd).

The current Arduino upload script writes the sketch at `0x08100000` and may also rewrite the loader. The overlay has separate boot, image, animation, sketch, and storage regions. A Klipper binary must not simply be passed through the ordinary sketch upload path. [Pinned upload script](https://github.com/arduino/ArduinoCore-zephyr/blob/39f8354ffc80883d595746abe6b6e16b69a5efa8/variants/arduino_uno_q_stm32u585xx/flash_sketch.cfg).

First record the exact chip ID, flash contents where readable, option bytes, bootloader version, security state, and installed OpenOCD configuration. Preserve original artifacts and checksums. Establish either a valid image compatible with the retained bootloader or an explicitly selected standalone boot image and restoration procedure. Do not change security/option bytes speculatively. Test recovery from a deliberately nonresponsive application before connecting printer loads. Keep reset/SWD accessible; an external debug probe can be a development recovery aid without becoming part of the printer architecture.

## Printer interface and provisional pin allocation

The UNO Q needs a carrier with four 3.3 V-compatible step/dir drivers, appropriate heater/fan power stages, thermistor pull-ups/filtering, protected endstop inputs, connectors, and fused printer power distribution. It cannot directly power motors or heaters. A classic UNO shield's form factor alone does not establish electrical compatibility.

This proposal uses 18 unique header GPIOs and a shared enable for all four drivers. It is a planning allocation, not an approved wiring diagram or ready-to-run `printer.cfg`. Mappings are checked against the [Arduino overlay](https://github.com/arduino/ArduinoCore-zephyr/blob/39f8354ffc80883d595746abe6b6e16b69a5efa8/variants/arduino_uno_q_stm32u585xx/arduino_uno_q_stm32u585xx.overlay) and [pinout](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf).

| Function | Header | MCU GPIO |
| --- | --- | --- |
| X step / direction | D2 / D3 | PB3 / PB0 |
| Y step / direction | D4 / D5 | PA12 / PA11 |
| Z step / direction | D6 / D7 | PB1 / PB2 |
| E step / direction | D8 / D9 | PB4 / PB8 |
| Shared driver enable | D10 | PB9 |
| X / Y / Z endstops | D11 / D12 / D13 | PB15 / PB14 / PB13 |
| Hotend / bed thermistors | A0 / A1 | PA4 / PA5 |
| Hotend / bed switch control | A2 / A3 | PA6 / PA7 |
| Two fan switch controls | A4 / A5 | PC1 / PC0 |
| Unallocated | D0 / D1 / D20 / D21 | PB7 / PB6 / PB11 / PB10 |

This gives up alternate SPI/CAN/I2C functions on the allocated pins. A4/A5 are used as digital outputs. Shared enable prevents independent motor power disable; reserve three more pins or use the expansion connector if independent enable is required. Additional Z motors, probes, filament sensors, and TMC buses require a revised allocation. Do not use slow I/O expanders for step signals.

Use hardware pull-downs for heater controls and appropriate pull-ups for active-low driver enables so reset/high-impedance states are safe. Establish thermistor reference voltage and pull-up resistance before choosing Klipper sensor settings. External sensors must not feed 5 V into 3.3 V ADC/GPIO, or into 1.8 V MPU pins. Heater power needs an independent thermal cutoff; firmware cannot turn off a failed-short MOSFET. Select the UNO Q power path after reviewing supply sequencing and backfeed behavior.

## Milestones and go/no-go gates

| Stage | Work | Exit gate |
| --- | --- | --- |
| 0. Identify and recover | Inventory board/image, UART owner, reset/SWD controls, boot state; preserve firmware and recovery assets. | Known recovery path and exact electrical/boot facts recorded. |
| 1. Linux services | Install pinned Klippy/Moonraker and UI; test host imports/helper build and reboot behavior. | Host starts reproducibly; actual UART is accessible exclusively. |
| 2. Minimal MCU port | Startup, clock, timer, UART, one unloaded GPIO, reset/shutdown. | Stock Klippy identifies MCU and stays synchronized for a one-hour synthetic run; repeated cold boots work without debugger. |
| 3. Motion and sensing bench | Four unloaded step outputs, endstop inputs, resistor-simulated thermistors, dummy output loads. | Measured pulse timing meets chosen driver specs; target workload plus proposed 2× aggregate step-rate margin runs with ADC/PWM enabled. |
| 4. Fault tests | Stop/kill host, interrupt communication, reset either processor, inject ADC faults and scheduler/watchdog failures, reboot under load simulation. | Heater controls reliably return off within documented bounds; no reset pulse energizes a load; restart requires deliberate reconfiguration. |
| 5. Printer integration | Fit carrier, check directions/endstops, home slowly, verify temperatures, PID tune and supervised first print. | Repeatable homing, temperature agreement, first print and an eight-hour representative soak without timing or communication faults. |
| 6. Release | Pin software versions, package services/firmware/config, document installation and restoration. | Reproduce setup from a clean supported image and recover the MCU without manual guesswork. |

One-hour/eight-hour durations and 2× margin are proposed project acceptance criteria, not guarantees from Arduino or Klipper. Derive the real workload from each motor's steps/mm × maximum motor speed, accounting for kinematics and extruder pressure advance. At 80 steps/mm and 300 mm/s one motor needs 24000 steps/s; a CoreXY transform can produce a higher motor speed than the requested toolhead component. A maximum-rate synthetic benchmark alone is insufficient. [Klipper benchmarks](https://www.klipper3d.org/Benchmarks.html).

Use the cataloged oscilloscope and DMM for timing and ADC checks once equipment access is established. Follow [Klipper configuration checks](https://www.klipper3d.org/Config_checks.html) during printer integration. Preserve Klipper's MCU output timeouts/ADC bounds and host heater verification; test all three layers.

Stop and reassess if recovery requires undocumented security changes, the UART cannot sustain the workload, the timebase is unstable without a debugger, or output fault behavior is unsafe. SPI or a Zephyr-based port are research alternatives. An external supported printer MCU would simplify development but would not meet this project's central requirement.

## Effort and first implementation deliverable

Planning estimate for one experienced embedded developer with hardware access: **4–8 engineer-weeks** for a basic validated prototype, with substantial uncertainty in boot/recovery and U5 peripheral bring-up. Rough allocation: 2–4 days discovery/host, 1–2 weeks minimal port, 1–2 weeks motion/ADC/fault validation, and 1–2 weeks carrier integration/printing/documentation. PCB lead time and additional board spins are extra. Re-estimate after Stage 2; product-level qualification is outside this range.

The first deliverable should be a pinned Klipper branch with a minimal STM32U585 target, reproducible build configuration, MCU recovery notes, and captured host-identify/timing evidence. Firmware flashing and live heater/motor tests are future implementation work, not performed by this feasibility assessment.
