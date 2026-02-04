"""Art-Net UDP listener for receiving DMX data."""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Art-Net protocol constants
ARTNET_HEADER = b"Art-Net\x00"
ARTNET_OPCODE_DMX = 0x5000

# Maximum nits value for display
MAX_NITS = 11000


def calculate_nits(value_16bit: int) -> int:
    """Convert 16-bit DMX value (0-65535) to nits (0-11000)."""
    return round((value_16bit / 65535) * MAX_NITS)


class ArtNetListener:
    """Listens for Art-Net DMX packets and extracts channel values."""

    def __init__(
        self,
        port: int = 6454,
        universe: int = 0,
        channel_high: int = 1,
        channel_low: int = 2,
        callback: Optional[Callable[[int], None]] = None,
    ):
        """
        Initialize the Art-Net listener.

        Args:
            port: UDP port to listen on (default 6454)
            universe: Art-Net universe to filter (default 0)
            channel_high: DMX channel for high byte of 16-bit value (1-512)
            channel_low: DMX channel for low byte of 16-bit value (1-512)
            callback: Async function called when brightness value changes (receives nits)
        """
        self.port = port
        self.universe = universe
        self.channel_high = channel_high
        self.channel_low = channel_low
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
        )
        print(f"[ArtNet] Listener started on port {self.port}, universe {self.universe}, "
              f"channels {self.channel_high} (high) / {self.channel_low} (low)")

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

        # Check if both channels are within the DMX data
        max_channel = max(self.channel_high, self.channel_low)
        if max_channel < 1 or max_channel > dmx_length:
            return None

        # Extract channel values (DMX channels are 1-indexed, array is 0-indexed)
        dmx_data = data[18:]
        high_index = self.channel_high - 1
        low_index = self.channel_low - 1

        if high_index >= len(dmx_data) or low_index >= len(dmx_data):
            return None

        high_byte = dmx_data[high_index]
        low_byte = dmx_data[low_index]

        # Combine into 16-bit value
        value_16bit = (high_byte * 256) + low_byte
        return value_16bit

    async def handle_value(self, value_16bit: int) -> None:
        """Handle a new 16-bit value, converting to nits and calling callback if changed."""
        nits = calculate_nits(value_16bit)
        if nits != self._last_value:
            self._last_value = nits
            logger.debug(f"Art-Net 16-bit value {value_16bit} -> {nits} nits")
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
        print(f"[ArtNet] UDP packet: {len(data)} bytes from {addr}")
        value_16bit = self.listener.parse_packet(data)
        if value_16bit is not None:
            nits = calculate_nits(value_16bit)
            print(f"[ArtNet] Channels {self.listener.channel_high}/{self.listener.channel_low} "
                  f"= {value_16bit} (16-bit) -> {nits} nits")
            # Schedule the async callback
            asyncio.create_task(self.listener.handle_value(value_16bit))
        elif len(data) >= 8:
            # Log why packet was ignored
            header = data[:8]
            if header == ARTNET_HEADER and len(data) >= 10:
                opcode = int.from_bytes(data[8:10], byteorder="little")
                if opcode != ARTNET_OPCODE_DMX:
                    print(f"[ArtNet] Ignoring opcode 0x{opcode:04x}")
                elif len(data) >= 16:
                    universe = int.from_bytes(data[14:16], byteorder="little")
                    print(f"[ArtNet] Ignoring universe {universe} (listening for {self.listener.universe})")
            else:
                print(f"[ArtNet] Not an Art-Net packet (header: {header[:8]})")

    def error_received(self, exc: Exception) -> None:
        """Called when a send or receive error occurs."""
        logger.error(f"Art-Net error: {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when the connection is lost or closed."""
        if exc:
            logger.error(f"Art-Net connection lost: {exc}")
