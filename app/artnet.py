"""Art-Net UDP listener for receiving DMX data."""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Art-Net protocol constants
ARTNET_HEADER = b"Art-Net\x00"
ARTNET_OPCODE_DMX = 0x5000

def calculate_nits(value: int, max_value: int, max_nits: int) -> int:
    """Convert a DMX value to nits."""
    return round(min(value / max_value, 1.0) * max_nits)


class ArtNetListener:
    """Listens for Art-Net DMX packets and extracts channel values."""

    def __init__(
        self,
        port: int = 6454,
        universe: int = 0,
        bit_depth: int = 16,
        channel: int = 1,
        channel_high: int = 1,
        channel_low: int = 2,
        max_nits: int = 11000,
        callback: Optional[Callable[[int], None]] = None,
    ):
        """
        Initialize the Art-Net listener.

        Args:
            port: UDP port to listen on (default 6454)
            universe: Art-Net universe to filter (default 0)
            bit_depth: 8 for single-channel (0-255) or 16 for high/low byte pair (default 16)
            channel: DMX channel for 8-bit mode (1-512)
            channel_high: DMX channel for high byte in 16-bit mode (1-512)
            channel_low: DMX channel for low byte in 16-bit mode (1-512)
            callback: Async function called when brightness value changes (receives nits)
        """
        self.port = port
        self.universe = universe
        self.bit_depth = bit_depth
        self.channel = channel
        self.channel_high = channel_high
        self.channel_low = channel_low
        self.max_nits = max_nits
        self.callback = callback
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional["ArtNetProtocol"] = None
        self._last_value: Optional[int] = None  # Stores nits value

    async def start(self) -> None:
        """Start listening for Art-Net packets."""
        loop = asyncio.get_event_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: ArtNetProtocol(self),
            local_addr=("0.0.0.0", self.port),
            allow_broadcast=True,
        )
        if self.bit_depth == 8:
            ch_info = f"channel {self.channel} (8-bit)"
        else:
            ch_info = f"channels {self.channel_high} (high) / {self.channel_low} (low) (16-bit)"
        print(f"Art-Net listener started on port {self.port}, universe {self.universe}, {ch_info}", flush=True)
        logger.info(f"Art-Net listener started on port {self.port}, universe {self.universe}, {ch_info}")

    def stop(self) -> None:
        """Stop listening for Art-Net packets."""
        if self._transport:
            self._transport.close()
            self._transport = None
            self._protocol = None
            logger.info("Art-Net listener stopped")

    def parse_packet(self, data: bytes) -> Optional[int]:
        """
        Parse an Art-Net DMX packet and extract the 16-bit brightness value.

        Art-Net DMX packet structure (OpDmx 0x5000):
        Bytes 0-7:   "Art-Net\0" (ID)
        Bytes 8-9:   OpCode 0x5000 (little-endian)
        Bytes 10-11: Protocol version (14)
        Byte 12:     Sequence
        Byte 13:     Physical port
        Bytes 14-15: Universe (little-endian)
        Bytes 16-17: Length (big-endian)
        Bytes 18+:   DMX data (512 bytes max)

        Returns:
            16-bit combined value (0-65535) if valid packet for our universe, None otherwise
        """
        # Check minimum packet length
        if len(data) < 18:
            return None

        # Check Art-Net header
        if data[:8] != ARTNET_HEADER:
            return None

        # Check OpCode (little-endian)
        opcode = int.from_bytes(data[8:10], byteorder="little")
        if opcode != ARTNET_OPCODE_DMX:
            return None

        # Get universe (little-endian)
        universe = int.from_bytes(data[14:16], byteorder="little")
        if universe != self.universe:
            return None

        # Get DMX data length (big-endian)
        dmx_length = int.from_bytes(data[16:18], byteorder="big")

        dmx_data = data[18:]

        if self.bit_depth == 8:
            idx = self.channel - 1
            if idx < 0 or idx >= dmx_length or idx >= len(dmx_data):
                return None
            return dmx_data[idx]
        else:
            max_channel = max(self.channel_high, self.channel_low)
            if max_channel < 1 or max_channel > dmx_length:
                return None
            high_index = self.channel_high - 1
            low_index = self.channel_low - 1
            if high_index >= len(dmx_data) or low_index >= len(dmx_data):
                return None
            return (dmx_data[high_index] * 256) + dmx_data[low_index]

    async def handle_value(self, value: int) -> None:
        """Handle a new DMX value, converting to nits and calling callback if changed."""
        max_value = 255 if self.bit_depth == 8 else 65535
        nits = calculate_nits(value, max_value, self.max_nits)
        if nits != self._last_value:
            self._last_value = nits
            logger.debug(f"Art-Net value {value} -> {nits} nits")
            if self.callback:
                await self.callback(nits)

    @property
    def current_value(self) -> int:
        """Get the current brightness value in nits."""
        return self._last_value if self._last_value is not None else 0


class ArtNetProtocol(asyncio.DatagramProtocol):
    """asyncio protocol for receiving Art-Net UDP packets."""

    def __init__(self, listener: ArtNetListener):
        self.listener = listener

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Called when the UDP socket is ready."""
        pass

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        """Called when a UDP packet is received."""
        print(f"Art-Net packet from {addr}, {len(data)} bytes", flush=True)
        logger.debug(f"Art-Net packet from {addr}, {len(data)} bytes, header={data[:8]}")
        value_16bit = self.listener.parse_packet(data)
        if value_16bit is not None:
            asyncio.create_task(self.listener.handle_value(value_16bit))
        else:
            # Log why packet was rejected to aid troubleshooting
            if len(data) >= 8 and data[:8] == b"Art-Net\x00":
                universe = int.from_bytes(data[14:16], byteorder="little") if len(data) >= 16 else "?"
                logger.debug(f"Art-Net packet rejected: universe={universe} (expected {self.listener.universe})")
            else:
                logger.debug(f"Non-Art-Net packet from {addr}")

    def error_received(self, exc: Exception) -> None:
        """Called when a send or receive error occurs."""
        logger.error(f"Art-Net error: {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when the connection is lost or closed."""
        if exc:
            logger.error(f"Art-Net connection lost: {exc}")
