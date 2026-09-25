# Development workflow

KlipperQ coordinates the complete UNO Q printer project. Firmware changes live in a separate fork so they can be reviewed against upstream Klipper and potentially contributed back.

## Repository responsibilities

- `KlipperQ`: architecture, carrier hardware, wiring, host setup, recovery procedures, validation evidence, and release manifests.
- `klipper`: STM32U585 target support, firmware changes, relevant tests, and upstream-appropriate board configuration and documentation.

Documented filesystem paths are relative to the `klipperq` project root (`.`). Its GitHub repository and project identity are KlipperQ. The firmware checkout is at `../klipper`.

## Firmware branches and remotes

- `origin`: https://github.com/andrewsharmon/klipper.git
- `upstream`: https://github.com/Klipper3d/klipper.git
- `master`: upstream baseline; keep project development off this branch.
- `uno-q`: development branch for the port.

Keep changes focused and use separate commits for coherent firmware work. Follow upstream's contribution and sign-off requirements when preparing contributions. Experimental development stays in the fork until hardware testing and regression checks establish readiness; upstream acceptance is not guaranteed.

## Reproducible firmware revision

`firmware.lock.json` records the exact firmware revision associated with this project's documentation. The initial revision matches `docs/source-audit.md` and is an unmodified upstream baseline. It has not been built, flashed, or validated on the UNO Q. The source audit remains a historical reference and must be revisited when advancing the pin.

To check out the recorded revision in a firmware clone, copy its `commit` value and run:

```sh
git fetch origin
git checkout --detach <commit-from-firmware.lock.json>
```

For development, return to `uno-q` with `git switch uno-q`. Update the manifest when intentionally advancing the project baseline, recording validation status and linking relevant evidence. Pin a validated commit for releases rather than relying on a moving branch.

Before integrating upstream changes, fetch `upstream` and review the diff. Rebase unpublished work or merge upstream into shared development history as appropriate; avoid force-pushing shared work without coordination. Repeat relevant build, regression, and hardware checks before treating an updated revision as validated.

## First milestone

Implement enough STM32U585 startup, timing, UART, and GPIO support for unmodified Klippy on the UNO Q to identify its onboard MCU, maintain clock synchronization, and toggle an unloaded output with measured timing. See [the implementation plan](implementation-plan.md) for acceptance gates.

No board flashing, motor movement, or heater operation is part of repository setup.
