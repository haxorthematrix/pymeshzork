"""LoRa client for Adafruit Radio Bonnet (RFM95W) on Raspberry Pi.

This module provides direct LoRa communication for PyMeshZork multiplayer
using the Adafruit Radio + OLED Bonnet connected via SPI to a Raspberry Pi.

Hardware: Adafruit LoRa Radio Bonnet with OLED - RFM95W @ 915MHz
  - Product: https://www.adafruit.com/product/4074
  - SPI for radio, I2C for OLED
  - GPIO pins: CS=CE1, RST=GPIO25, IRQ=GPIO22 (active high)

Pinout (Pi GPIO header):
  - Radio CS: CE1 (GPIO7/Pin 26)
  - Radio RST: GPIO25 (Pin 22)
  - Radio IRQ: GPIO22 (active high, directly under OLED)
  - OLED: I2C (SDA=GPIO2, SCL=GPIO3)
  - Button A: GPIO5
  - Button B: GPIO6
  - Button C: GPIO12
"""

import logging
import struct
import threading
import time
from typing import Callable

from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.protocol import (
    GameMessage,
    MessageType,
    encode_message,
    decode_message,
)

logger = logging.getLogger(__name__)

# LoRa configuration for Meshtastic compatibility
LORA_FREQ = 915.0  # MHz (US frequency, use 868.0 for EU)
LORA_TX_POWER = 23  # dBm (max for RFM95W)
LORA_BANDWIDTH = 125000  # Hz
LORA_SPREADING_FACTOR = 7  # SF7 for faster data rate
LORA_CODING_RATE = 5  # 4/5

# Timing
RECEIVE_TIMEOUT = 0.5  # seconds
CHANNEL_ACTIVITY_TIMEOUT = 0.1  # CAD timeout


class LoRaClient(MeshtasticClient):
    """LoRa client using Adafruit RFM95W radio bonnet.

    Provides direct LoRa communication without requiring a Meshtastic device.
    Messages are broadcast to all nodes in range using the same protocol.
    """

    def __init__(
        self,
        player_name: str,
        frequency: float = LORA_FREQ,
        tx_power: int = LORA_TX_POWER,
        node_id: int | None = None,
    ):
        """Initialize LoRa client.

        Args:
            player_name: Display name for the player.
            frequency: LoRa frequency in MHz (915.0 for US, 868.0 for EU).
            tx_power: Transmit power in dBm (5-23).
            node_id: Optional fixed node ID. If None, generates from MAC.
        """
        super().__init__(player_name)

        self.frequency = frequency
        self.tx_power = min(23, max(5, tx_power))  # Clamp to valid range
        self._node_id = node_id

        self._rfm9x = None
        self._receive_thread: threading.Thread | None = None
        self._running = False

        # OLED display (optional)
        self._display = None
        self._display_enabled = False

        # Button callbacks
        self._button_callbacks: dict[str, Callable[[], None]] = {}

    def _get_node_id(self) -> int:
        """Get or generate node ID."""
        if self._node_id is not None:
            return self._node_id

        # Generate from hostname/MAC for consistency
        try:
            import socket
            hostname = socket.gethostname()
            # Use hash of hostname, keep to 16 bits
            return hash(hostname) & 0xFFFF
        except Exception:
            # Random fallback
            import random
            return random.randint(0x1000, 0xFFFF)

    def connect(self) -> bool:
        """Initialize the LoRa radio.

        Returns:
            True if radio initialized successfully.
        """
        if self._state == ConnectionState.CONNECTED:
            return True

        self._state = ConnectionState.CONNECTING

        try:
            # Import here to allow running on non-Pi systems for testing
            import board
            import busio
            import digitalio
            import adafruit_rfm9x

            # Configure SPI
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

            # Configure radio pins (Adafruit Bonnet defaults)
            cs = digitalio.DigitalInOut(board.CE1)
            reset = digitalio.DigitalInOut(board.D25)

            # Initialize radio
            self._rfm9x = adafruit_rfm9x.RFM9x(
                spi, cs, reset,
                self.frequency,
                baudrate=1000000,
            )

            # Configure radio parameters
            self._rfm9x.tx_power = self.tx_power
            self._rfm9x.signal_bandwidth = LORA_BANDWIDTH
            self._rfm9x.spreading_factor = LORA_SPREADING_FACTOR
            self._rfm9x.coding_rate = LORA_CODING_RATE
            self._rfm9x.enable_crc = True

            # Set node address (used for filtering if needed)
            self._rfm9x.node = self._get_node_id() & 0xFF

            # Disable address filtering to receive all broadcasts
            self._rfm9x.destination = 0xFF  # Broadcast

            logger.info(
                f"LoRa radio initialized: {self.frequency}MHz, "
                f"TX power {self.tx_power}dBm, node {self._rfm9x.node}"
            )

            # Try to initialize OLED display
            self._init_display()

            # Start receive thread
            self._running = True
            self._receive_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True,
                name="lora-receive",
            )
            self._receive_thread.start()

            self._state = ConnectionState.CONNECTED
            self._update_display()

            return True

        except ImportError as e:
            logger.error(f"LoRa libraries not available: {e}")
            logger.error("Install with: pip install 'pymeshzork[lora]'")
            self._state = ConnectionState.DISCONNECTED
            return False

        except Exception as e:
            logger.error(f"Failed to initialize LoRa radio: {e}")
            self._state = ConnectionState.DISCONNECTED
            return False

    def disconnect(self) -> None:
        """Shutdown the LoRa radio."""
        self._running = False

        if self._receive_thread:
            self._receive_thread.join(timeout=2.0)
            self._receive_thread = None

        if self._rfm9x:
            # Put radio in sleep mode
            try:
                self._rfm9x.sleep()
            except Exception:
                pass
            self._rfm9x = None

        if self._display:
            try:
                self._display.fill(0)
                self._display.show()
            except Exception:
                pass
            self._display = None

        self._state = ConnectionState.DISCONNECTED
        logger.info("LoRa radio disconnected")

    def _send_raw(self, data: str) -> None:
        """Send raw data over LoRa.

        Args:
            data: JSON-encoded message string.

        Raises:
            RuntimeError: If radio not connected or transmission fails.
        """
        if not self._rfm9x or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("LoRa radio not connected")

        try:
            # Add simple frame header: length + player_id prefix
            # This helps receiving nodes identify message boundaries
            data_bytes = data.encode('utf-8')
            frame = struct.pack(">BH", len(data_bytes), self._get_node_id()) + data_bytes

            # Check if channel is clear (simple CSMA)
            # Wait for channel to be free before transmitting
            for _ in range(5):
                if not self._rfm9x.cad_detected():
                    break
                time.sleep(0.05 + (self._get_node_id() % 50) / 1000)  # Random backoff

            # Transmit
            self._rfm9x.send(frame)

            logger.debug(f"LoRa TX: {len(frame)} bytes")
            self._update_display(tx=True)

        except Exception as e:
            logger.error(f"LoRa TX error: {e}")
            raise

    def _receive_loop(self) -> None:
        """Background thread to receive LoRa packets."""
        logger.info("LoRa receive loop started")

        while self._running:
            try:
                # Check for incoming packet with timeout
                packet = self._rfm9x.receive(timeout=RECEIVE_TIMEOUT)

                if packet is None:
                    continue

                # Parse frame header
                if len(packet) < 3:
                    continue

                length, sender_id = struct.unpack(">BH", packet[:3])
                data = packet[3:3+length]

                # Skip our own messages
                if sender_id == self._get_node_id():
                    continue

                # Decode message
                try:
                    json_str = data.decode('utf-8')
                    message = decode_message(json_str)

                    if message:
                        logger.debug(
                            f"LoRa RX: {len(packet)} bytes from {sender_id:04x}, "
                            f"type={message.msg_type.value}, RSSI={self._rfm9x.last_rssi}dBm"
                        )

                        self._update_display(rx=True, rssi=self._rfm9x.last_rssi)

                        # Dispatch to callbacks
                        for callback in self._message_callbacks:
                            try:
                                callback(message)
                            except Exception as e:
                                logger.error(f"Message callback error: {e}")

                except (UnicodeDecodeError, ValueError) as e:
                    logger.warning(f"Failed to decode LoRa packet: {e}")

            except Exception as e:
                if self._running:
                    logger.error(f"LoRa receive error: {e}")
                    time.sleep(0.5)

        logger.info("LoRa receive loop stopped")

    # =========================================================================
    # OLED Display
    # =========================================================================

    def _init_display(self) -> None:
        """Initialize the OLED display on the bonnet."""
        try:
            import board
            import busio
            import adafruit_ssd1306
            from PIL import Image, ImageDraw, ImageFont

            # I2C for OLED
            i2c = busio.I2C(board.SCL, board.SDA)

            # 128x32 OLED on the bonnet
            self._display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
            self._display.fill(0)
            self._display.show()

            self._display_enabled = True
            logger.info("OLED display initialized")

        except Exception as e:
            logger.warning(f"OLED display not available: {e}")
            self._display_enabled = False

    def _update_display(
        self,
        tx: bool = False,
        rx: bool = False,
        rssi: int | None = None,
    ) -> None:
        """Update the OLED display with current status."""
        if not self._display_enabled or not self._display:
            return

        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create image buffer
            image = Image.new("1", (128, 32))
            draw = ImageDraw.Draw(image)

            # Use default font
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
            except Exception:
                font = ImageFont.load_default()
                font_small = font

            # Line 1: Game title and player name
            draw.text((0, 0), f"ZORK: {self.player_name[:10]}", font=font, fill=255)

            # Line 2: Connection status
            status = "Connected" if self._state == ConnectionState.CONNECTED else "Offline"
            draw.text((0, 12), status, font=font_small, fill=255)

            # TX/RX indicators
            if tx:
                draw.text((80, 12), "TX", font=font_small, fill=255)
            if rx:
                draw.text((100, 12), "RX", font=font_small, fill=255)

            # Line 3: RSSI if available
            if rssi is not None:
                draw.text((0, 22), f"RSSI: {rssi}dBm", font=font_small, fill=255)

            # Current room if we have it
            if hasattr(self, '_current_room') and self._current_room:
                room_text = self._current_room[:12]
                draw.text((70, 22), room_text, font=font_small, fill=255)

            # Display the image
            self._display.image(image)
            self._display.show()

        except Exception as e:
            logger.debug(f"Display update error: {e}")

    def set_room(self, room_id: str) -> None:
        """Update current room for display."""
        super().set_room(room_id)
        self._update_display()

    # =========================================================================
    # Button handling
    # =========================================================================

    def setup_buttons(
        self,
        on_button_a: Callable[[], None] | None = None,
        on_button_b: Callable[[], None] | None = None,
        on_button_c: Callable[[], None] | None = None,
    ) -> None:
        """Set up button callbacks for the bonnet buttons.

        Args:
            on_button_a: Callback for button A (GPIO5).
            on_button_b: Callback for button B (GPIO6).
            on_button_c: Callback for button C (GPIO12).
        """
        try:
            import board
            import digitalio

            buttons = [
                (board.D5, "A", on_button_a),
                (board.D6, "B", on_button_b),
                (board.D12, "C", on_button_c),
            ]

            for pin, name, callback in buttons:
                if callback:
                    btn = digitalio.DigitalInOut(pin)
                    btn.direction = digitalio.Direction.INPUT
                    btn.pull = digitalio.Pull.UP
                    self._button_callbacks[name] = (btn, callback)

            # Start button polling thread if we have callbacks
            if self._button_callbacks:
                thread = threading.Thread(
                    target=self._button_poll_loop,
                    daemon=True,
                    name="button-poll",
                )
                thread.start()

        except Exception as e:
            logger.warning(f"Button setup failed: {e}")

    def _button_poll_loop(self) -> None:
        """Poll buttons and trigger callbacks."""
        button_state = {name: True for name in self._button_callbacks}

        while self._running:
            for name, (btn, callback) in self._button_callbacks.items():
                current = btn.value

                # Detect button press (active low)
                if button_state[name] and not current:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Button {name} callback error: {e}")

                button_state[name] = current

            time.sleep(0.05)  # 50ms polling


def create_lora_client(
    player_name: str,
    frequency: float = LORA_FREQ,
    tx_power: int = LORA_TX_POWER,
) -> LoRaClient:
    """Create a LoRa client for the Adafruit Radio Bonnet.

    Args:
        player_name: Display name for the player.
        frequency: LoRa frequency (915.0 for US, 868.0 for EU).
        tx_power: Transmit power in dBm.

    Returns:
        Configured LoRaClient instance.
    """
    return LoRaClient(
        player_name=player_name,
        frequency=frequency,
        tx_power=tx_power,
    )
