# Generic CNC Shield V3.00 mapping and Y-channel bring-up

- Date: 2026-09-26 CDT
- Controller: Arduino UNO Q 2 GB, onboard STM32U585 running KlipperQ
- Shield: generic Arduino CNC Shield V3.00; exact manufacturer unknown
- Populated hardware: one unidentified stepper driver in Y and one unloaded,
  freely rotating stepper motor
- Result: **PASS for complete shield configuration, physical Y motion,
  scheduled return move, automatic driver disable, safe output states, and
  post-test controller health**

## Pin mapping

Arduino's UNO Q full pinout maps the classic Uno header signals used by the
shield as follows:

| Shield signal | Uno header | STM32U585 GPIO |
| --- | --- | --- |
| X STEP | D2 | PB3 |
| Y STEP | D3 | PB0 |
| Z STEP | D4 | PA12 |
| X DIR | D5 | PA11 |
| Y DIR | D6 | PB1 |
| Z DIR | D7 | PB2 |
| shared active-low ENABLE | D8 | PB4 |
| X limit pair | D9 | PB8 |
| Y limit pair | D10 | PB9 |
| Z limit pair | D11 | PB15 |
| spindle enable / independent A STEP | D12 | PB14 |
| spindle direction / independent A DIR | D13 | PB13 |
| abort | A0 | PA4 |
| hold | A1 | PA5 |
| resume | A2 | PA6 |
| coolant | A3 | PA7 |
| auxiliary / SDA | A4 | PC1 |
| probe / SCL | A5 | PC0 |

Source: Arduino `ABX00162-full-pinout.pdf`, revision dated 2026-02-17. The
generic shield signal assignments are the conventional CNC Shield V3 mapping.

## Configuration

`config/uno-q-cnc-shield-v3.cfg` was installed as
`/home/arduino/printer_data/config/printer.cfg`. The previous no-output file is
preserved on the board as `printer.cfg.pre-cnc-shield-v3`.

X, Y, and Z are configured as manual steppers and share the inverted PB4
enable with Klipper's shared-enable tracking. Each uses its paired limit input
with an MCU pull-up and active-low switch sense. A 4 microsecond step pulse is
specified conservatively. Microsteps is set to 1 and rotation distance to 40
solely as a bring-up scale because the driver models, motor geometry, and
M0/M1/M2 jumper states have not been identified.

Abort, hold, resume, and probe are configured as active-low pull-up inputs.
Abort executes `M112`; hold and resume execute Klipper `PAUSE` and `RESUME`.
Spindle enable, spindle direction, and coolant are configurable outputs with
initial and shutdown values of zero. An independent A axis would reuse D12 and
D13, so it is documented but not simultaneously enabled with spindle control.
The A socket may instead clone X, Y, or Z using the shield's hardware jumpers.

## Test

After installation, Klipper restarted and reported `Printer is ready`. The
`CNC_Y_TEST` macro was submitted through Moonraker. It scheduled 25 configured
full-step equivalents forward at 1 unit/s, paused 500 ms, scheduled the same
distance back, and disabled the driver. Moonraker returned `ok`.

After the motion queue drained:

- Klipper remained `ready`.
- MCU statistics reported zero invalid frames and zero print stalls.
- No shutdown or configuration error was logged.
- The queue's print time advanced to 16.208 seconds and returned to zero
  buffer time, confirming that both scheduled moves completed at the
  controller level.

The user subsequently confirmed that the physical Y motor moved successfully.

After expanding the configuration, Klipper again restarted ready and the Y
test completed without a fault. The post-test object query showed:

- X, Y, and Z stepper enable states all false.
- Spindle enable, spindle direction, and coolant values all `0.0`.
- Abort, hold, resume, and probe inputs all released.
- X, Y, and Z limit inputs all open/untriggered.
- Klipper still ready, with no shutdown or error in the regression log.

## Open items

- Identify the installed driver model and set/verify its current limit before
  loaded or extended operation.
- Record the Y motor step angle and physical M0/M1/M2 jumper state, then update
  `microsteps` and `rotation_distance` for calibrated motion.
- Electrically validate each newly used input/output before attaching spindle,
  coolant, probe, or safety-control hardware.
- Populate and test X/Z only after their drivers, motors, current limits, and
  safe mechanics are known.
