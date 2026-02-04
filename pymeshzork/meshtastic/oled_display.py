"""OLED display module for Adafruit Radio Bonnet.

Provides a status display for PyMeshZork game state, showing:
- Player name and current room
- Connection status and backend type
- Other players in room
- Recent messages
- TX/RX activity indicators
- Signal quality (RSSI/SNR)
- Mesh node count

Hardware: Adafruit Radio + OLED Bonnet (128x32 SSD1306 I2C display)
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymeshzork.meshtastic.client import ConnectionState

logger = logging.getLogger(__name__)

# Display dimensions
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 32

# Display modes cycle through different info screens
class DisplayMode(Enum):
    STATUS = auto()      # Player, room, connection
    PLAYERS = auto()     # Other players in room
    MESSAGES = auto()    # Recent chat messages
    MESH_INFO = auto()   # Mesh node info and signal


@dataclass
class DisplayState:
    """Current state to display."""
    player_name: str = "Adventurer"
    current_room: str = ""
    room_name: str = ""  # Human-readable room name
    backend: str = "Offline"
    connected: bool = False

    # Players in current room
    players_in_room: list[str] = field(default_factory=list)

    # Recent messages (newest first)
    recent_messages: deque = field(default_factory=lambda: deque(maxlen=5))

    # Signal info
    last_rssi: int | None = None
    last_snr: float | None = None

    # Mesh info
    mesh_node_count: int = 0

    # Activity indicators (auto-clear after timeout)
    tx_active: bool = False
    rx_active: bool = False
    tx_time: float = 0
    rx_time: float = 0


class OLEDDisplay:
    """OLED display manager for the Radio Bonnet.

    Provides a multi-screen display that cycles through game information.
    Thread-safe for updates from multiple sources.

    Example usage:
        display = OLEDDisplay()
        if display.initialize():
            display.update_player("Adventurer", "whous", "West of House")
            display.set_connected(True, "Native")
            display.show_tx()
    """

    # Activity indicator timeout (seconds)
    ACTIVITY_TIMEOUT = 1.0

    # Auto-cycle interval (seconds) - 0 to disable
    AUTO_CYCLE_INTERVAL = 5.0

    def __init__(self):
        """Initialize display manager."""
        self._display = None
        self._initialized = False
        self._lock = threading.Lock()

        # Display state
        self._state = DisplayState()
        self._mode = DisplayMode.STATUS

        # Update thread
        self._running = False
        self._update_thread: threading.Thread | None = None
        self._last_cycle_time = 0

        # Font cache
        self._font = None
        self._font_small = None

    @property
    def initialized(self) -> bool:
        """Check if display is initialized."""
        return self._initialized

    def initialize(self) -> bool:
        """Initialize the OLED display hardware.

        Returns:
            True if display initialized successfully.
        """
        if self._initialized:
            return True

        try:
            import adafruit_ssd1306
            from PIL import Image, ImageDraw, ImageFont

            i2c = self._get_i2c()
            if i2c is None:
                logger.warning("Could not initialize I2C for OLED display")
                return False

            # 128x32 OLED on the bonnet at address 0x3C
            self._display = adafruit_ssd1306.SSD1306_I2C(
                DISPLAY_WIDTH, DISPLAY_HEIGHT, i2c, addr=0x3C
            )
            self._display.fill(0)
            self._display.show()

            # Load fonts
            self._load_fonts()

            self._initialized = True

            # Start update thread
            self._running = True
            self._update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name="oled-display",
            )
            self._update_thread.start()

            logger.info("OLED display initialized")
            return True

        except ImportError as e:
            logger.warning(f"OLED libraries not available: {e}")
            return False
        except Exception as e:
            logger.warning(f"OLED display initialization failed: {e}")
            return False

    def _get_i2c(self):
        """Get I2C interface, trying multiple methods for compatibility."""
        i2c = None

        # Method 1: Try board.I2C() which auto-detects
        try:
            import board
            i2c = board.I2C()
            return i2c
        except Exception:
            pass

        # Method 2: Try explicit busio with board pins
        try:
            import board
            import busio
            i2c = busio.I2C(board.SCL, board.SDA)
            return i2c
        except Exception:
            pass

        # Method 3: Try direct I2C bus numbers (for Pi 5 / newer systems)
        try:
            import os
            for bus_num in [1, 20, 21]:
                if os.path.exists(f"/dev/i2c-{bus_num}"):
                    try:
                        from adafruit_blinka.microcontroller.generic_linux.i2c import I2C as LinuxI2C
                        i2c = LinuxI2C(bus_num)
                        return i2c
                    except Exception:
                        continue
        except Exception:
            pass

        return None

    def _load_fonts(self) -> None:
        """Load fonts for display."""
        from PIL import ImageFont

        # Try DejaVu fonts (common on Pi)
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]

        for path in font_paths:
            try:
                self._font = ImageFont.truetype(path, 10)
                self._font_small = ImageFont.truetype(path, 8)
                return
            except Exception:
                continue

        # Fall back to default
        self._font = ImageFont.load_default()
        self._font_small = self._font

    def shutdown(self) -> None:
        """Shutdown display and cleanup."""
        self._running = False

        if self._update_thread:
            self._update_thread.join(timeout=1.0)
            self._update_thread = None

        if self._display:
            try:
                self._display.fill(0)
                self._display.show()
            except Exception:
                pass
            self._display = None

        self._initialized = False

    def _update_loop(self) -> None:
        """Background thread for display updates."""
        while self._running:
            try:
                now = time.time()

                # Clear stale activity indicators
                with self._lock:
                    if self._state.tx_active and now - self._state.tx_time > self.ACTIVITY_TIMEOUT:
                        self._state.tx_active = False
                    if self._state.rx_active and now - self._state.rx_time > self.ACTIVITY_TIMEOUT:
                        self._state.rx_active = False

                # Auto-cycle display mode
                if self.AUTO_CYCLE_INTERVAL > 0:
                    if now - self._last_cycle_time > self.AUTO_CYCLE_INTERVAL:
                        self._cycle_mode()
                        self._last_cycle_time = now

                # Refresh display
                self._render()

                time.sleep(0.2)  # 5 FPS

            except Exception as e:
                logger.debug(f"Display update error: {e}")
                time.sleep(1.0)

    def _cycle_mode(self) -> None:
        """Cycle to next display mode."""
        modes = list(DisplayMode)
        current_idx = modes.index(self._mode)
        self._mode = modes[(current_idx + 1) % len(modes)]

    def set_mode(self, mode: DisplayMode) -> None:
        """Set display mode manually."""
        with self._lock:
            self._mode = mode
            self._last_cycle_time = time.time()

    def _render(self) -> None:
        """Render current display mode."""
        if not self._initialized or not self._display:
            return

        try:
            from PIL import Image, ImageDraw

            # Create image buffer
            image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
            draw = ImageDraw.Draw(image)

            with self._lock:
                if self._mode == DisplayMode.STATUS:
                    self._render_status(draw)
                elif self._mode == DisplayMode.PLAYERS:
                    self._render_players(draw)
                elif self._mode == DisplayMode.MESSAGES:
                    self._render_messages(draw)
                elif self._mode == DisplayMode.MESH_INFO:
                    self._render_mesh_info(draw)

                # Always show activity indicators in corner
                self._render_activity(draw)

            # Display the image
            self._display.image(image)
            self._display.show()

        except Exception as e:
            logger.debug(f"Render error: {e}")

    def _render_status(self, draw) -> None:
        """Render main status screen."""
        # Line 1: Player name (left) + Backend (right)
        draw.text((0, 0), self._state.player_name[:12], font=self._font, fill=255)

        backend_text = self._state.backend if self._state.connected else "Offline"
        # Right-align backend text
        bbox = draw.textbbox((0, 0), backend_text, font=self._font_small)
        text_width = bbox[2] - bbox[0]
        draw.text((DISPLAY_WIDTH - text_width - 20, 0), backend_text, font=self._font_small, fill=255)

        # Line 2: Current room
        room_display = self._state.room_name or self._state.current_room
        if room_display:
            draw.text((0, 11), room_display[:20], font=self._font_small, fill=255)
        else:
            draw.text((0, 11), "No room", font=self._font_small, fill=255)

        # Line 3: Player count + signal
        info_parts = []
        if self._state.players_in_room:
            count = len(self._state.players_in_room)
            info_parts.append(f"{count} player{'s' if count != 1 else ''}")
        if self._state.last_rssi is not None:
            info_parts.append(f"RSSI:{self._state.last_rssi}")
        if self._state.mesh_node_count > 0:
            info_parts.append(f"Mesh:{self._state.mesh_node_count}")

        if info_parts:
            draw.text((0, 22), " | ".join(info_parts)[:22], font=self._font_small, fill=255)

    def _render_players(self, draw) -> None:
        """Render players in room screen."""
        draw.text((0, 0), "Players Here:", font=self._font_small, fill=255)

        if not self._state.players_in_room:
            draw.text((0, 11), "None", font=self._font_small, fill=255)
        else:
            # Show up to 2 player names
            y = 11
            for i, name in enumerate(self._state.players_in_room[:2]):
                draw.text((0, y), f"- {name[:16]}", font=self._font_small, fill=255)
                y += 10

            if len(self._state.players_in_room) > 2:
                more = len(self._state.players_in_room) - 2
                draw.text((70, 22), f"+{more} more", font=self._font_small, fill=255)

    def _render_messages(self, draw) -> None:
        """Render recent messages screen."""
        draw.text((0, 0), "Messages:", font=self._font_small, fill=255)

        if not self._state.recent_messages:
            draw.text((0, 11), "No messages", font=self._font_small, fill=255)
        else:
            # Show most recent 2 messages
            y = 11
            for msg in list(self._state.recent_messages)[:2]:
                # Truncate to fit
                draw.text((0, y), msg[:22], font=self._font_small, fill=255)
                y += 10

    def _render_mesh_info(self, draw) -> None:
        """Render mesh network info screen."""
        draw.text((0, 0), "Mesh Network", font=self._font, fill=255)

        # Line 2: Node count
        draw.text((0, 11), f"Nodes: {self._state.mesh_node_count}", font=self._font_small, fill=255)

        # Line 3: Signal quality
        signal_parts = []
        if self._state.last_rssi is not None:
            signal_parts.append(f"RSSI: {self._state.last_rssi}dBm")
        if self._state.last_snr is not None:
            signal_parts.append(f"SNR: {self._state.last_snr:.1f}dB")

        if signal_parts:
            draw.text((0, 22), "  ".join(signal_parts), font=self._font_small, fill=255)
        else:
            draw.text((0, 22), "No signal data", font=self._font_small, fill=255)

    def _render_activity(self, draw) -> None:
        """Render TX/RX activity indicators in top-right corner."""
        x = DISPLAY_WIDTH - 18

        if self._state.tx_active:
            draw.text((x, 0), "TX", font=self._font_small, fill=255)
        if self._state.rx_active:
            draw.text((x + 10 if self._state.tx_active else x, 0), "RX", font=self._font_small, fill=255)

    # =========================================================================
    # Public update methods (thread-safe)
    # =========================================================================

    def update_player(self, name: str, room_id: str = "", room_name: str = "") -> None:
        """Update player and room info.

        Args:
            name: Player display name.
            room_id: Current room ID.
            room_name: Human-readable room name.
        """
        with self._lock:
            self._state.player_name = name
            self._state.current_room = room_id
            self._state.room_name = room_name

    def set_connected(self, connected: bool, backend: str = "") -> None:
        """Update connection status.

        Args:
            connected: Whether currently connected.
            backend: Backend name (Native, Serial, MQTT, etc.)
        """
        with self._lock:
            self._state.connected = connected
            if backend:
                self._state.backend = backend

    def set_players_in_room(self, players: list[str]) -> None:
        """Update list of other players in current room.

        Args:
            players: List of player names.
        """
        with self._lock:
            self._state.players_in_room = list(players)

    def add_message(self, message: str) -> None:
        """Add a recent message to display.

        Args:
            message: Message text (will be truncated).
        """
        with self._lock:
            self._state.recent_messages.appendleft(message[:40])

    def update_signal(self, rssi: int | None = None, snr: float | None = None) -> None:
        """Update signal quality info.

        Args:
            rssi: RSSI in dBm.
            snr: Signal-to-noise ratio in dB.
        """
        with self._lock:
            if rssi is not None:
                self._state.last_rssi = rssi
            if snr is not None:
                self._state.last_snr = snr

    def update_mesh_info(self, node_count: int) -> None:
        """Update mesh network info.

        Args:
            node_count: Number of nodes in mesh.
        """
        with self._lock:
            self._state.mesh_node_count = node_count

    def show_tx(self) -> None:
        """Flash TX indicator."""
        with self._lock:
            self._state.tx_active = True
            self._state.tx_time = time.time()

    def show_rx(self) -> None:
        """Flash RX indicator."""
        with self._lock:
            self._state.rx_active = True
            self._state.rx_time = time.time()


# Global display instance
_display: OLEDDisplay | None = None


def get_display() -> OLEDDisplay | None:
    """Get or create the global OLED display instance.

    Returns:
        OLEDDisplay instance if available, None otherwise.
    """
    global _display

    if _display is None:
        _display = OLEDDisplay()
        if not _display.initialize():
            _display = None

    return _display


def shutdown_display() -> None:
    """Shutdown the global display instance."""
    global _display

    if _display:
        _display.shutdown()
        _display = None
