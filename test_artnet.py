#!/usr/bin/env python3
"""Send test Art-Net DMX packets with 16-bit brightness values."""

import socket
import time
import sys


def build_artnet_dmx_packet(universe: int, channel_high: int, channel_low: int, value_16bit: int) -> bytes:
    """Build an Art-Net DMX packet with 16-bit value across two channels."""
    # Art-Net header
    header = b"Art-Net\x00"
    # OpCode 0x5000 (little-endian)
    opcode = (0x5000).to_bytes(2, byteorder="little")
    # Protocol version (14, big-endian)
    version = (14).to_bytes(2, byteorder="big")
    # Sequence (0 = disabled)
    sequence = bytes([0])
    # Physical port
    physical = bytes([0])
    # Universe (little-endian)
    universe_bytes = universe.to_bytes(2, byteorder="little")

    # Split 16-bit value into high and low bytes
    high_byte = (value_16bit >> 8) & 0xFF
    low_byte = value_16bit & 0xFF

    # DMX data length (big-endian) - send up to the max channel we need
    max_channel = max(channel_high, channel_low)
    dmx_length = max(max_channel, 2)  # Minimum 2 bytes
    length_bytes = dmx_length.to_bytes(2, byteorder="big")

    # Build DMX data array
    dmx_data = [0] * dmx_length
    dmx_data[channel_high - 1] = high_byte
    dmx_data[channel_low - 1] = low_byte

    return header + opcode + version + sequence + physical + universe_bytes + length_bytes + bytes(dmx_data)


def value_to_nits(value_16bit: int) -> int:
    """Convert 16-bit value to nits for display."""
    return round((value_16bit / 65535) * 11000)


def main():
    target_ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    target_port = int(sys.argv[2]) if len(sys.argv) > 2 else 6454
    universe = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    channel_high = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    channel_low = int(sys.argv[5]) if len(sys.argv) > 5 else 2

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"Sending Art-Net to {target_ip}:{target_port}, universe {universe}")
    print(f"Using channels: {channel_high} (high byte), {channel_low} (low byte)")
    print("Ramping through full 16-bit range (0-65535 -> 0-11000 nits)")
    print("Press Ctrl+C to stop\n")

    try:
        value = 0
        step = 2048  # ~32 steps to cover full range
        direction = 1
        while True:
            packet = build_artnet_dmx_packet(universe, channel_high, channel_low, value)
            sock.sendto(packet, (target_ip, target_port))

            high_byte = (value >> 8) & 0xFF
            low_byte = value & 0xFF
            nits = value_to_nits(value)
            print(f"Sent: 16-bit={value:5d} (high={high_byte:3d}, low={low_byte:3d}) -> {nits:5d} nits")

            value += direction * step
            if value >= 65535:
                value = 65535
                direction = -1
            elif value <= 0:
                value = 0
                direction = 1

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
