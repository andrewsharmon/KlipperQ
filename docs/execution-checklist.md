# Implementation and testing checklist

Work through the numbered stages in order. This checklist turns the [implementation plan](implementation-plan.md) into trackable work; that document retains the architecture, provisional pin map, and source references. Follow the [development workflow](development.md) for repository ownership.

Status at creation, 2026-09-25: planning and source inspection only. The firmware pin is an unmodified upstream baseline; no UNO Q build, flash, or hardware test has passed. All execution items below are intentionally unchecked. This document plans future work and does not execute or authorize device operations.

Check an item only when its deliverable and validation evidence exist. Store project test records under `records/validation/` when testing starts. Each record should include date, checklist item, firmware commit, host versions, board identity, configuration, instrument/setup details, procedure, expected limits, measured result, pass/fail, and links to logs or captures. Record blocked and failed tests explicitly; an unrun test is not a pass. Keep secrets out of records.

## 1. Define the acceptance workload

- [ ] Confirm physical UNO Q ownership, 2 GB SKU/revision, printer kinematics, motor count, drivers, sensor models, heaters, fans, and required optional peripherals.
- [ ] Write the printer requirements: travel, maximum speed/acceleration, steps/mm, driver pulse and direction timing, heater ratings, and temperature range/accuracy.
- [ ] Calculate peak per-motor and aggregate step rates from the actual kinematics, including extruder pressure advance; define representative motion files and a synthetic workload with the proposed 2× aggregate margin.
- [ ] Set numerical pass limits for pulse timing/jitter, ADC accuracy, communication/deadline errors, and maximum fault-to-output-off time before collecting acceptance results.
- [ ] Confirm the proposed acceptance targets: one-hour minimal-port run, eight-hour integrated soak, and at least 25% available RAM at peak normal load on 2 GB with no OOM events or sustained swapping.

**Exit gate:** a measurable workload and acceptance table exist. Provisional assumptions are identified and cannot silently become release requirements.

## 2. Establish the development and test baseline

- [ ] Verify the sibling `klipper` checkout, its repository instructions, remotes, development branch, and relationship to `firmware.lock.json`; preserve unrelated local changes.
- [ ] Activate the existing hardware toolchain through `../tools/scripts/activate.sh`; record actual compiler, binutils, Python, and debugging tool versions and access limitations.
- [ ] Prepare a reproducible supported build environment and run the pinned upstream build/regression checks before modifying firmware; record any baseline failures.
- [ ] Define a UNO Q build configuration and CI job location in the firmware fork. Use the existing `test/configs/` and `scripts/ci-build.sh` structure, accounting for its required toolchains and Python environments.
- [ ] Create the validation record structure and a test matrix separating compile/host checks, unloaded MCU tests, dummy-load fault tests, and powered printer tests.

**Exit gate:** the baseline can be rebuilt and tested, and later failures can be compared against recorded results.

## 3. Identify the board and establish recovery

- [ ] Consult the hardware catalog, search for an existing UNO Q entry, and onboard the actual board using its device template; update the catalog index and setup log when identity is verified.
- [ ] Record the Linux image/kernel, Python/architecture, actual UART device, service owners, MCU ID, bootloader, flash layout, security state, and option bytes using documented read operations.
- [ ] Preserve readable factory firmware, option-byte records, installed loader/debug configurations, and restoration artifacts with checksums; document anything that cannot be backed up.
- [ ] Audit router stop/start hooks, upload/App Lab services, reset lines, and SWD access before changing UART ownership or stopping services.
- [ ] Resolve the boot image contract and select retained-loader or standalone startup. Document verified addresses, memory/security assumptions, and an exact restoration procedure; avoid speculative option-byte changes.
- [ ] Establish and verify the available recovery mechanism with printer loads disconnected. Schedule recovery from a deliberately nonresponsive application in Stage 5 before relying on the new firmware.

**Exit gate:** the exact board and boot contract are known, preservation is complete or limitations are resolved, and a documented recovery mechanism is available before the first port flash. Stop if recovery depends on undocumented security changes.

## 4. Write and compile the minimal STM32U585 port

- [ ] Add U585 target selection, build rules, licensed ST headers, and `internal.h` integration in the firmware fork.
- [ ] Implement startup/vector/linker support for the verified boot address, security state, and SRAM banks; inspect ELF sections, stack placement, vector table, and image size against the actual memory layout.
- [ ] Implement clocks, reset/power helpers, voltage scaling, flash wait states, peripheral clocks, and the internal UART's VDDIO2 setup from the verified board configuration.
- [ ] Integrate the timer and interrupt priorities, establishing DWT/SysTick availability and fixed-clock assumptions; avoid sleep states that stop the timebase.
- [ ] Implement LPUART1 pin mux, clock/divisor setup, interrupt RX/TX, and error recovery through Klipper's serial machinery. Start at 115200 with matching flow-control settings.
- [ ] Implement one unloaded GPIO and minimum shutdown/reset behavior using Klipper's shared command machinery.
- [ ] Add the UNO Q compile configuration to CI. Build from a clean checkout; archive configuration, ELF/binary, protocol dictionary, size report, build log, and artifact checksums.
- [ ] Run whitespace, affected existing STM32 builds, and Klippy import/regression tests. Add focused tests for any new testable calculations or common-code changes; document peripheral behavior that still requires hardware.

**Exit gate:** the minimal image builds reproducibly, fits the verified boot/memory contract, and introduces no unexplained regression. Compilation alone does not establish board compatibility.

## 5. Bring up the host and prove the first milestone

- [ ] Write version-pinned host installation and service configuration for Klippy, Moonraker, and the chosen UI on the supported UNO Q Linux image; build the host C helper and verify imports.
- [ ] Implement printing-mode service ownership and boot order based on Stage 3's audit; verify exclusive access to the actual UART and controlled reset behavior.
- [ ] Write the board-specific flashing procedure using the exact built artifact, verified target, backup, and recovery details. With loads disconnected, flash and record verification results.
- [ ] Demonstrate stock Klippy identify, configuration, clock queries, and shutdown through the native serial protocol.
- [ ] Measure the unloaded GPIO waveform against scheduled timing; verify the timebase through repeated counter wraparound and resets.
- [ ] Run the one-hour synthetic synchronization test; retain host logs, serial statistics, and scope captures against Stage 1 limits.
- [ ] Define and execute a repeatable cold-boot cycle test without a debugger; record every attempt and verify host startup, reconnect behavior, and safe GPIO defaults.
- [ ] Demonstrate restoration from a deliberately nonresponsive application and return to the pinned working image.
- [ ] Pin the minimal-port milestone in `firmware.lock.json` with evidence and a precise validation scope; re-estimate remaining work.

**Exit gate:** unmodified Klippy identifies the onboard MCU, stays synchronized for one hour, and produces measured scheduled output; cold boots and recovery work without relying on an attached debugger. Do not commit to a carrier PCB before this gate.

## 6. Implement and bench-test the printer peripherals

- [ ] Audit header GPIO mapping and implement four step/direction channels, shared or revised enables, and endstops using common Klipper code; revise the provisional pin allocation for the actual printer.
- [ ] Scope simultaneous unloaded step outputs, pulse widths, direction setup/hold, and enable/reset states; verify endstop polarity, triggering, and homing-stop behavior on the bench.
- [ ] Implement U5 ADC calibration, channels, sample times, reference/analog-switch setup, and correct `ADC_MAX`; validate known resistors across the intended sensor range against DMM measurements.
- [ ] Implement heater/fan software PWM and output-duration enforcement; verify duty cycle, default-off behavior, and timeouts with dummy loads.
- [ ] Implement and measure the watchdog timeout and reset behavior, including loss of firmware progress.
- [ ] Qualify higher UART rates only as needed; measure usable bandwidth, errors, and scheduling behavior under simultaneous motion, ADC, and PWM load.
- [ ] Run representative and 2× aggregate step-rate workloads with sensing/PWM active; compare pulse timing and host/MCU statistics against the acceptance table.
- [ ] Implement and test only required additional peripherals, such as TMC configuration, probe, or accelerometer; update pin and workload budgets and repeat affected tests.
- [ ] Repeat clean builds and relevant upstream regressions after the peripheral changes.

**Exit gate:** motion, sensing, outputs, and watchdog meet recorded limits together, with no unexplained communication or timing failures.

## 7. Prove fault handling with dummy loads

- [ ] Create a fault matrix specifying injection method, expected host/MCU response, output-off deadline, reset-state behavior, and recovery action for each fault.
- [ ] Test host stop/kill, UART interruption, host reboot, MCU reset, and loss/restoration of relevant power rails under load simulation.
- [ ] Test thermistor open/short and out-of-range ADC values; verify MCU bounds and host heater verification separately, including a simulated heater that fails to warm.
- [ ] Inject scheduler overload and firmware stalls through a controlled test build; prove scheduled output-duration enforcement and watchdog shutdown independently.
- [ ] Measure heater and driver control lines through boot, reset, shutdown, and recovery; verify no transient energizes a dummy load and restart requires deliberate reconfiguration.
- [ ] Record worst-case fault-to-off times against Stage 1 limits; fix failures and rerun affected cases on the final production build where applicable.

**Exit gate:** every required fault case passes with measured evidence. Do not connect real heaters or proceed to powered printer integration with an unresolved failure.

## 8. Build and validate the carrier

- [ ] Finalize schematic, BOM, connector/pin assignments, driver compatibility, thermistor circuits, protected inputs, heater/fan stages, fusing, and independent thermal cutoff for the actual printer.
- [ ] Review voltage domains, power sequencing/backfeed, heater pull-downs, active-low enable pull-ups, grounding, and accessible reset/SWD; check against the verified UNO Q revision and instrument procedures.
- [ ] Assemble and inspect the carrier; perform unpowered continuity/short checks, then current-limited rail and interface checks before attaching printer loads.
- [ ] Repeat GPIO, ADC, PWM, reset, and fault tests through the assembled carrier using dummy loads, including verification of the independent cutoff path.
- [ ] Write the reviewed wiring diagram and board-specific configuration with verified pin names, polarities, sensor settings, and conservative operating limits.

**Exit gate:** the assembled interface meets the electrical and fault requirements; the wiring and configuration match the tested hardware.

## 9. Integrate the printer and run acceptance tests

- [ ] Follow the pinned Klipper configuration-check procedure: verify sensors and endstops, then driver currents, motor directions, and low-speed motion before homing.
- [ ] Verify repeatable homing and travel limits; increase motion limits gradually while checking pulse timing, missed steps, and communication statistics.
- [ ] Verify temperature agreement with an independent measurement, then supervised low-power heating, heater verification, and PID tuning within the confirmed hardware limits.
- [ ] Complete a supervised first print and record dimensional/print-quality observations and required configuration corrections.
- [ ] Run the eight-hour representative printing soak on the 2 GB model; capture available memory, peak service RSS, swap, OOM events, serial errors, and scheduling/shutdown events.
- [ ] Evaluate the soak against all acceptance limits and rerun affected tests after fixes. Consider 4 GB only if the required workload still fails the memory target after unnecessary services are removed.

**Exit gate:** repeatable homing, validated temperatures, a successful print, and the eight-hour soak pass with no unresolved timing, communication, or safety faults.

## 10. Package and reproduce the release

- [ ] Pin the tested firmware commit, build configuration/toolchain, host packages/image, service files, UI, carrier revision, and printer configuration; include artifact checksums and validation links.
- [ ] Update `firmware.lock.json`, installation/recovery instructions, source audit where the baseline changed, and the hardware catalog/setup log with accurately scoped results.
- [ ] Reproduce installation from a clean supported Linux image and the recorded artifacts; verify boot, UART ownership, identify, and the applicable acceptance checks.
- [ ] Rehearse restoration/rollback from the documented release procedure and record the resulting firmware and host versions.
- [ ] Run the final firmware build/regression suite and review remaining issues. Publish a release only when required gates pass; label any narrower milestone by its actual validation scope.

**Exit gate:** another setup can be built, installed, tested, and recovered from the recorded instructions without undocumented steps.
