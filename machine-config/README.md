# Tracked machine configuration

`uno-q/` is a byte-for-byte mirror of the connected board's
`/home/arduino/printer_data/config` directory. Refresh it from the repository
root with:

```sh
scripts/sync-machine-configs.sh
```

The script auto-detects a connected UNO Q over USB/ADB. Use `--serial SERIAL`
when more than one matching board is connected. `ADB` and `UNO_Q_SERIAL` are
also supported as environment overrides.

The sync replaces the tracked snapshot so additions, edits, and deletions all
appear in Git. `uno-q.SHA256SUMS` records the content hash of every copied file.
Review the diff before committing it. The script only reads from the board; it
does not upload configurations or restart services.
