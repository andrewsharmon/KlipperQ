# Mainsail over USB/ADB

The UNO Q runs Klippy, Moonraker, and Mainsail locally. Both Moonraker and nginx listen only on the board's loopback interface; the browser connection is carried over USB with an ADB forward.

Connect the board over USB and run from the KlipperQ checkout:

```sh
scripts/connect-mainsail-adb.sh
```

The script waits for the identified UNO Q, starts any inactive board services,
recreates the Mac-side ADB forward, and verifies the Mainsail page, Moonraker
API, Klippy connection, and WebSocket upgrade through nginx. It exits nonzero
instead of reporting success when any layer is unavailable.

For a quick recovery that restarts the complete board-side stack first:

```sh
scripts/connect-mainsail-adb.sh --restart
```

The restart form resets the Klipper MCU connection and restarts Moonraker and
nginx. The normal form does not disrupt services that are already running.
Klipper's systemd unit uses `/usr/local/sbin/klipperq-start-mcu` to reset the
STM32, validate the application vectors at `0x08000000`, and explicitly start
the flashed application. This is necessary because the verified board enters
STM32 system ROM after a plain hardware reset.

Then open:

```text
http://127.0.0.1:8181/
```

The default Mac-side port is 8181 because port 8080 was already occupied. To choose another free port:

```sh
MAINSAIL_PORT=8282 scripts/connect-mainsail-adb.sh
```

The equivalent command-line option is `--port 8282`. The script discovers a
unique attached board using the UNO Q device-tree identity and installed stack
paths. If multiple matching boards are attached, select one at runtime with
`--serial SERIAL` or `UNO_Q_SERIAL=SERIAL`; do not save the value in the repo.

The script uses `adb` from `PATH` when available. The currently verified
temporary installation is used as a fallback. Set `ADB=/absolute/path/to/adb`
after installing Android platform-tools at a persistent location.

ADB forwards are host-session state. Run the connection script again after disconnecting/reconnecting USB, restarting the ADB server, or rebooting the computer. The board-side services are enabled through systemd and do not require Wi-Fi.

Installed paths:

- Klipper: `/home/arduino/klipper`, virtual environment `/home/arduino/klippy-env`
- Moonraker: `/home/arduino/moonraker`, virtual environment `/home/arduino/moonraker-env`
- Mainsail: `/home/arduino/mainsail`
- Runtime data and configuration: `/home/arduino/printer_data`

The active `printer.cfg` uses `kinematics: none` and maps a generic CNC Shield V3.00. X/Y/Z are manual steppers; the endstops, control buttons, probe, spindle direction/enable, and coolant signals are also defined. Power-capable outputs start low and return low on shutdown. The repository source is `config/uno-q-cnc-shield-v3.cfg`; `config/uno-q-minimal.cfg` remains the no-output communication baseline.

Moonraker uses the `systemd_dbus` machine provider with its official PolicyKit rules. Mainsail can manage approved system services and request reboot, shutdown, or poweroff of the UNO Q. Access remains restricted to the local board services and the USB/ADB-forwarded web endpoint.
