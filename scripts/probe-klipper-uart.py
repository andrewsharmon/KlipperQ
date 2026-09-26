#!/usr/bin/env python3
"""Probe a Klipper MCU over a native UART using only Python's stdlib."""

import argparse
import json
import os
import select
import termios
import time
import zlib


MESSAGE_MIN = 5
MESSAGE_MAX = 64
MESSAGE_DEST = 0x10
MESSAGE_SEQ_MASK = 0x0F
MESSAGE_SYNC = 0x7E


class ProbeError(Exception):
    pass


def crc16_ccitt(data):
    crc = 0xFFFF
    for value in data:
        value ^= crc & 0xFF
        value ^= (value & 0x0F) << 4
        crc = ((value << 8) | (crc >> 8)) ^ (value >> 4) ^ (value << 3)
    return bytes(((crc >> 8) & 0xFF, crc & 0xFF))


def encode_uint(value):
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError("unsigned integer outside uint32 range")
    encoded = bytearray()
    if value >= 0x0C000000:
        encoded.append(((value >> 28) & 0x7F) | 0x80)
    if value >= 0x00180000:
        encoded.append(((value >> 21) & 0x7F) | 0x80)
    if value >= 0x00003000:
        encoded.append(((value >> 14) & 0x7F) | 0x80)
    if value >= 0x00000060:
        encoded.append(((value >> 7) & 0x7F) | 0x80)
    encoded.append(value & 0x7F)
    return encoded


def decode_uint(data, position):
    if position >= len(data):
        raise ProbeError("truncated variable-length integer")
    current = data[position]
    value = current & 0x7F
    if (current & 0x60) == 0x60:
        value |= -0x20
    position += 1
    while current & 0x80:
        if position >= len(data):
            raise ProbeError("truncated variable-length integer")
        current = data[position]
        position += 1
        value = (value << 7) | (current & 0x7F)
    return value & 0xFFFFFFFF, position


def frame_message(sequence, payload):
    message = bytearray((MESSAGE_MIN + len(payload),
                         MESSAGE_DEST | (sequence & MESSAGE_SEQ_MASK)))
    message.extend(payload)
    message.extend(crc16_ccitt(message))
    message.append(MESSAGE_SYNC)
    return message


def extract_packet(buffer):
    while buffer:
        length = buffer[0]
        if length < MESSAGE_MIN or length > MESSAGE_MAX:
            del buffer[0]
            continue
        if len(buffer) < length:
            return None
        candidate = bytes(buffer[:length])
        if (candidate[1] & ~MESSAGE_SEQ_MASK) != MESSAGE_DEST:
            del buffer[0]
            continue
        if candidate[-1] != MESSAGE_SYNC:
            del buffer[0]
            continue
        if candidate[-3:-1] != crc16_ccitt(candidate[:-3]):
            del buffer[0]
            continue
        del buffer[:length]
        return candidate
    return None


def read_packet(fd, buffer, deadline):
    while time.monotonic() < deadline:
        packet = extract_packet(buffer)
        if packet is not None:
            return packet
        remaining = max(0.0, deadline - time.monotonic())
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            break
        chunk = os.read(fd, 4096)
        if chunk:
            buffer.extend(chunk)
    raise ProbeError("timed out waiting for a valid Klipper response")


def parse_identify_response(packet):
    payload = packet[2:-3]
    if not payload:
        # The MCU acknowledges each accepted host block with an empty frame.
        return None
    message_id, position = decode_uint(payload, 0)
    if message_id != 0:
        # Startup and shutdown responses use dictionary-assigned ids that are
        # unavailable until identify completes. They are safe to skip here.
        return None
    offset, position = decode_uint(payload, position)
    if position >= len(payload):
        raise ProbeError("identify_response is missing its data length")
    length, position = decode_uint(payload, position)
    data = bytes(payload[position:position + length])
    if len(data) != length or position + length != len(payload):
        raise ProbeError("malformed identify_response payload")
    return packet[1] & MESSAGE_SEQ_MASK, offset, data


def configure_uart(path, baud):
    baud_constant = getattr(termios, "B%d" % baud, None)
    if baud_constant is None:
        raise ProbeError("unsupported termios baud rate: %d" % baud)
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    original = termios.tcgetattr(fd)
    settings = termios.tcgetattr(fd)
    settings[0] = 0
    settings[1] = 0
    settings[2] = termios.CLOCAL | termios.CREAD | termios.CS8
    settings[3] = 0
    settings[4] = baud_constant
    settings[5] = baud_constant
    settings[6][termios.VMIN] = 0
    settings[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, settings)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd, original


def request_identify(fd, timeout, retries, verbose=False):
    compressed = bytearray()
    receive_buffer = bytearray()
    sequence = 0
    while True:
        payload = bytearray((1,))
        payload.extend(encode_uint(len(compressed)))
        payload.extend(encode_uint(40))
        failures = 0
        resyncs = 0
        while True:
            request = frame_message(sequence, payload)
            expected_sequence = (sequence + 1) & MESSAGE_SEQ_MASK
            if verbose:
                print("TX[%d]: %s" % (failures + 1, request.hex()))
            os.write(fd, request)
            deadline = time.monotonic() + timeout
            try:
                while True:
                    packet = read_packet(fd, receive_buffer, deadline)
                    if verbose:
                        print("RX:    %s" % packet.hex())
                    packet_sequence = packet[1] & MESSAGE_SEQ_MASK
                    if len(packet) == MESSAGE_MIN:
                        if packet_sequence == sequence:
                            # A response may be transmitted before the ACK for
                            # the preceding request. Ignore that stale ACK (or
                            # wait for a timeout if this is a current NAK).
                            continue
                        if packet_sequence != expected_sequence:
                            # A NAK reports the next sequence the MCU expects.
                            sequence = packet_sequence
                            resyncs += 1
                            if resyncs > 16:
                                raise ProbeError("unable to synchronize sequence")
                            break
                        continue
                    response = parse_identify_response(packet)
                    if response is None:
                        continue
                    response_sequence, offset, data = response
                    if response_sequence != expected_sequence:
                        continue
                    if offset != len(compressed):
                        raise ProbeError(
                            "identify offset mismatch: expected %d, received %d"
                            % (len(compressed), offset))
                    break
                if (len(packet) == MESSAGE_MIN
                        and packet_sequence != expected_sequence):
                    continue
                break
            except ProbeError:
                failures += 1
                if failures > retries:
                    raise
        compressed.extend(data)
        sequence = response_sequence
        if not data:
            return bytes(compressed), sequence


def parse_uint_response(packet, expected_id):
    payload = packet[2:-3]
    if not payload:
        return None
    message_id, position = decode_uint(payload, 0)
    if message_id != expected_id:
        return None
    values = []
    while position < len(payload):
        value, position = decode_uint(payload, position)
        values.append(value)
    return values


def request_noarg(fd, sequence, command_id, response_id, timeout, retries,
                  verbose=False):
    failures = 0
    receive_buffer = bytearray()
    while failures <= retries:
        request = frame_message(sequence, encode_uint(command_id))
        expected_sequence = (sequence + 1) & MESSAGE_SEQ_MASK
        if verbose:
            print("TX query: %s" % request.hex())
        os.write(fd, request)
        deadline = time.monotonic() + timeout
        accepted = False
        try:
            while True:
                packet = read_packet(fd, receive_buffer, deadline)
                if verbose:
                    print("RX:       %s" % packet.hex())
                packet_sequence = packet[1] & MESSAGE_SEQ_MASK
                if len(packet) == MESSAGE_MIN:
                    if packet_sequence == expected_sequence:
                        accepted = True
                    continue
                values = parse_uint_response(packet, response_id)
                if values is not None and packet_sequence == expected_sequence:
                    return expected_sequence, values
        except ProbeError:
            failures += 1
            if accepted:
                # The command was accepted but its untracked response was
                # lost. Advance and issue a fresh query.
                sequence = expected_sequence
    raise ProbeError("timed out waiting for response id %d" % response_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="/dev/ttyHS1")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--clock-wait", type=float, default=0.1,
                        help="seconds between the two get_clock queries")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.clock_wait < 0:
        parser.error("--clock-wait must not be negative")

    fd = None
    original = None
    try:
        fd, original = configure_uart(args.device, args.baud)
        compressed, sequence = request_identify(
            fd, args.timeout, args.retries, verbose=args.verbose)
        identify = json.loads(zlib.decompress(compressed).decode("utf-8"))
        commands = identify.get("commands", {})
        responses = identify.get("responses", {})
        sequence, config_values = request_noarg(
            fd, sequence, commands["get_config"],
            responses["config is_config=%c crc=%u is_shutdown=%c move_count=%hu"],
            args.timeout, args.retries, verbose=args.verbose)
        clock_start_wall = time.monotonic()
        sequence, clock_start_values = request_noarg(
            fd, sequence, commands["get_clock"],
            responses["clock clock=%u"], args.timeout, args.retries,
            verbose=args.verbose)
        time.sleep(args.clock_wait)
        sequence, clock_end_values = request_noarg(
            fd, sequence, commands["get_clock"],
            responses["clock clock=%u"], args.timeout, args.retries,
            verbose=args.verbose)
        clock_elapsed_wall = time.monotonic() - clock_start_wall
    except (OSError, ValueError, zlib.error, json.JSONDecodeError, ProbeError) as exc:
        parser.exit(1, "Klipper UART probe failed: %s\n" % exc)
    finally:
        if fd is not None:
            if original is not None:
                termios.tcsetattr(fd, termios.TCSANOW, original)
            os.close(fd)

    constants = identify.get("config", {})
    commands = identify.get("commands", {})
    print("Klipper identify succeeded")
    print("  MCU: %s" % constants.get("MCU", "unknown"))
    print("  Clock: %s Hz" % constants.get("CLOCK_FREQ", "unknown"))
    print("  Serial baud: %s" % constants.get("SERIAL_BAUD", "unknown"))
    print("  Version: %s" % identify.get("version", "unknown"))
    print("  Build: %s" % identify.get("build_versions", "unknown"))
    print("  Commands: %d" % len(commands))
    print("  Config: is_config=%d crc=%d is_shutdown=%d move_count=%d"
          % tuple(config_values))
    clock_start = clock_start_values[0]
    clock_end = clock_end_values[0]
    clock_ticks = (clock_end - clock_start) & 0xFFFFFFFF
    print("  Clock query: %d -> %d (%d ticks in %.3f s)"
          % (clock_start, clock_end, clock_ticks, clock_elapsed_wall))


if __name__ == "__main__":
    main()
