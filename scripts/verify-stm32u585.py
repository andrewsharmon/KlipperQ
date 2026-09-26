#!/usr/bin/env python3
"""Verify the Klipper STM32U585 build without external Python packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


FLASH_START = 0x08000000
FLASH_END = 0x08200000
RAM_START = 0x20000000
RAM_END = 0x200C0000
SHF_ALLOC = 0x2
SHT_NOBITS = 8
SHT_SYMTAB = 2


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def c_string(table: bytes, offset: int) -> str:
    require(0 <= offset < len(table), f"string-table offset {offset} is invalid")
    end = table.find(b"\0", offset)
    require(end >= 0, "unterminated ELF string-table entry")
    return table[offset:end].decode("ascii", "strict")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_elf(path: Path) -> tuple[int, dict[str, dict[str, int]], dict[str, int], bytes]:
    data = path.read_bytes()
    require(len(data) >= 52, f"{path} is too small to be an ELF32 file")
    require(data[:4] == b"\x7fELF", f"{path} has no ELF magic")
    require(data[4] == 1, "firmware must be ELF32")
    require(data[5] == 1, "firmware must be little-endian")

    header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    (_etype, machine, version, entry, _phoff, shoff, _flags, ehsize,
     _phentsize, _phnum, shentsize, shnum, shstrndx) = header
    require(machine == 40, f"ELF machine is {machine}, expected ARM (40)")
    require(version == 1 and ehsize == 52, "unexpected ELF32 header")
    require(shentsize == 40 and shnum > 0, "unexpected ELF section table")
    require(shoff + shentsize * shnum <= len(data), "ELF section table is truncated")
    require(shstrndx < shnum, "ELF section-name table index is invalid")

    raw_sections = [
        struct.unpack_from("<IIIIIIIIII", data, shoff + index * shentsize)
        for index in range(shnum)
    ]
    name_section = raw_sections[shstrndx]
    names = data[name_section[4]:name_section[4] + name_section[5]]
    require(len(names) == name_section[5], "ELF section-name table is truncated")

    sections: dict[str, dict[str, int]] = {}
    for index, section in enumerate(raw_sections):
        (name_offset, section_type, flags, address, offset, size, link, info,
         alignment, entry_size) = section
        name = c_string(names, name_offset)
        require(section_type == SHT_NOBITS or offset + size <= len(data),
                f"ELF section {name!r} is truncated")
        sections[name] = {
            "index": index,
            "type": section_type,
            "flags": flags,
            "address": address,
            "offset": offset,
            "size": size,
            "link": link,
            "info": info,
            "alignment": alignment,
            "entry_size": entry_size,
        }

    symbols: dict[str, int] = {}
    for section in sections.values():
        if section["type"] != SHT_SYMTAB:
            continue
        require(section["link"] < len(raw_sections), "symbol string table index is invalid")
        strings_section = raw_sections[section["link"]]
        strings = data[strings_section[4]:strings_section[4] + strings_section[5]]
        entry_size = section["entry_size"]
        require(entry_size == 16 and section["size"] % entry_size == 0,
                "unexpected ELF32 symbol-table layout")
        start = section["offset"]
        for offset in range(start, start + section["size"], entry_size):
            name_offset, value, _size, _info, _other, _shndx = struct.unpack_from(
                "<IIIBBH", data, offset)
            if name_offset:
                symbols[c_string(strings, name_offset)] = value

    return entry, sections, symbols, data


def verify_dictionary(path: Path) -> None:
    try:
        dictionary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse {path}: {exc}") from exc
    config = dictionary.get("config", {})
    expected = {
        "MCU": "stm32u585xx",
        "CLOCK_FREQ": 160_000_000,
        "SERIAL_BAUD": 115_200,
        "RESERVE_PINS_serial": "PG8,PG7",
    }
    for key, value in expected.items():
        require(config.get(key) == value,
                f"dictionary {key} is {config.get(key)!r}, expected {value!r}")


def verify_elf(path: Path) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    entry, sections, symbols, data = parse_elf(path)
    require(entry == FLASH_START,
            f"ELF entry is 0x{entry:08x}, expected 0x{FLASH_START:08x}")

    for name in (".text", ".data", ".bss", ".stack"):
        require(name in sections, f"required ELF section {name} is missing")

    for name, section in sections.items():
        if not section["flags"] & SHF_ALLOC or not section["size"]:
            continue
        start = section["address"]
        end = start + section["size"]
        in_flash = FLASH_START <= start < end <= FLASH_END
        in_ram = RAM_START <= start < end <= RAM_END
        require(in_flash or in_ram,
                f"allocated section {name} at 0x{start:08x}..0x{end:08x} "
                "is outside the declared flash/RAM map")

    text = sections[".text"]
    require(text["address"] == FLASH_START, ".text/vector table is not at 0x08000000")
    require(text["size"] >= 8, ".text does not contain the first two vectors")
    initial_sp, reset_vector = struct.unpack_from("<II", data, text["offset"])
    require(initial_sp == RAM_END,
            f"initial SP is 0x{initial_sp:08x}, expected 0x{RAM_END:08x}")
    require(reset_vector & 1, "reset vector is not a Thumb address")
    require(FLASH_START <= (reset_vector & ~1) < FLASH_END,
            f"reset vector 0x{reset_vector:08x} is outside flash")

    expected_symbols = {
        "VectorTable": FLASH_START,
        "_stack_start": RAM_END - 0x200,
        "_stack_end": RAM_END,
    }
    for name, address in expected_symbols.items():
        require(symbols.get(name) == address,
                f"symbol {name} is {symbols.get(name)!r}, expected 0x{address:08x}")
    for name in ("ResetHandler", "LPUART1_IRQHandler"):
        address = symbols.get(name)
        require(address is not None, f"required symbol {name} is missing")
        require(FLASH_START <= (address & ~1) < FLASH_END,
                f"symbol {name} at 0x{address:08x} is outside flash")

    stack = sections[".stack"]
    require(stack["address"] == RAM_END - 0x200 and stack["size"] == 0x200,
            "stack section does not occupy 0x200bfe00..0x200c0000")
    return sections, symbols


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_firmware = Path(__file__).resolve().parents[2] / "klipper"
    parser.add_argument("--firmware", type=Path, default=default_firmware,
                        help=f"Klipper source tree (default: {default_firmware})")
    args = parser.parse_args()

    output = args.firmware.resolve() / "out"
    elf = output / "klipper.elf"
    binary = output / "klipper.bin"
    dictionary = output / "klipper.dict"
    for path in (elf, binary, dictionary):
        require(path.is_file(), f"required build artifact is missing: {path}")

    verify_dictionary(dictionary)
    sections, _symbols = verify_elf(elf)
    text = sections[".text"]
    data = sections[".data"]
    bss = sections[".bss"]
    print("STM32U585 artifact verification: PASS")
    print(f"  flash image: 0x{text['address']:08x}..0x{text['address'] + text['size']:08x}")
    print(f"  RAM data/BSS/stack: {data['size']} / {bss['size']} / "
          f"{sections['.stack']['size']} bytes")
    for path in (elf, binary, dictionary):
        print(f"  {path.name} sha256 {sha256(path)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        print(f"STM32U585 artifact verification: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
