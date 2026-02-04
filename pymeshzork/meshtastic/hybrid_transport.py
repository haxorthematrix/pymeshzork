"""Hybrid transport layer for PyMeshZork multiplayer.

Manages multiple simultaneous transports (Meshtastic mesh, MQTT) with
automatic detection, fallback, and message deduplication.

Architecture:
    - Primary transport: Meshtastic mesh (LoRa) for offline/field use
    - Fallback transport: MQTT (WiFi/Internet) when LoRa unavailable
    - Hybrid mode: Both active with deduplication

Message Deduplication:
    - Each message has unique ID: {player_id}:{sequence_number}
    - LRU cache tracks recently seen message IDs
    - Messages received from any transport are deduplicated
    - Outgoing messages sent via primary transport only
"""

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any

from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.protocol import GameMessage

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Available transport types."""
    MESHTASTIC_NATIVE = auto()  # meshtasticd on Radio Bonnet
    MESHTASTIC_SERIAL = auto()  # USB serial to Meshtastic device
    MQTT = auto()               # MQTT broker (WiFi/Internet)


@dataclass
class TransportStatus:
    """Status of a transport."""
    transport_type: TransportType
    available: bool = False
    connected: bool = False
    last_check: float = 0
    error_message: str = ""


class LRUCache:
    """Simple LRU cache for message deduplication."""

    def __init__(self, maxsize: int = 1000, ttl: float = 300):
        """Initialize LRU cache.

        Args:
            maxsize: Maximum number of items to store.
            ttl: Time-to-live in seconds for cached items.
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache and not expired."""
        with self._lock:
            if key not in self._cache:
                return False
            # Check TTL
            if time.time() - self._cache[key] > self.ttl:
                del self._cache[key]
                return False
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return True

    def add(self, key: str) -> None:
        """Add key to cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                self._cache[key] = time.time()
                # Evict oldest if over capacity
                while len(self._cache) > self.maxsize:
                    self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()


@dataclass
class HybridConfig:
    """Configuration for hybrid transport."""
    # Transport priorities (first = primary)
    transport_priority: list[TransportType] = field(default_factory=lambda: [
        TransportType.MESHTASTIC_NATIVE,
        TransportType.MESHTASTIC_SERIAL,
        TransportType.MQTT,
    ])

    # Deduplication settings
    dedup_cache_size: int = 1000
    dedup_ttl: float = 300  # 5 minutes

    # Detection settings
    auto_detect: bool = True
    detection_interval: float = 30  # Re-check availability every 30s

    # Fallback behavior
    enable_fallback: bool = True
    mqtt_as_bridge: bool = True  # Use MQTT to bridge LoRa islands


class HybridTransport:
    """Multi-transport manager with automatic fallback and deduplication.

    Manages multiple transports simultaneously, ensuring messages are
    delivered via the best available transport while preventing duplicates.

    Example usage:
        transport = HybridTransport(player_name="Adventurer")
        transport.on_message(handle_game_message)
        transport.connect()
        transport.send(game_message)
    """

    def __init__(
        self,
        player_name: str,
        config: HybridConfig | None = None,
    ):
        """Initialize hybrid transport.

        Args:
            player_name: Display name for this player.
            config: Optional configuration. Uses defaults if None.
        """
        self.player_name = player_name
        self.config = config or HybridConfig()

        # Active transports
        self._transports: dict[TransportType, MeshtasticClient] = {}
        self._transport_status: dict[TransportType, TransportStatus] = {}
        self._primary_transport: TransportType | None = None

        # Message deduplication
        self._seen_messages = LRUCache(
            maxsize=self.config.dedup_cache_size,
            ttl=self.config.dedup_ttl,
        )
        self._duplicate_count = 0

        # Callbacks
        self._message_callbacks: list[Callable[[GameMessage], None]] = []
        self._state_callbacks: list[Callable[[TransportType, ConnectionState], None]] = []

        # Threading
        self._lock = threading.Lock()
        self._detection_thread: threading.Thread | None = None
        self._stop_detection = threading.Event()

    @property
    def is_connected(self) -> bool:
        """Check if any transport is connected."""
        return any(
            t.state == ConnectionState.CONNECTED
            for t in self._transports.values()
        )

    @property
    def primary_transport(self) -> TransportType | None:
        """Get the primary (highest priority connected) transport."""
        return self._primary_transport

    @property
    def connected_transports(self) -> list[TransportType]:
        """Get list of connected transport types."""
        return [
            tt for tt, t in self._transports.items()
            if t.state == ConnectionState.CONNECTED
        ]

    def on_message(self, callback: Callable[[GameMessage], None]) -> None:
        """Register callback for incoming messages (after deduplication)."""
        self._message_callbacks.append(callback)

    def on_state_change(
        self,
        callback: Callable[[TransportType, ConnectionState], None],
    ) -> None:
        """Register callback for transport state changes."""
        self._state_callbacks.append(callback)

    def detect_available_transports(self) -> list[TransportType]:
        """Detect which transports are available.

        Returns:
            List of available transport types.
        """
        available = []

        # Check for Meshtastic Native (meshtasticd running)
        if self._check_meshtastic_native():
            available.append(TransportType.MESHTASTIC_NATIVE)
            self._update_status(TransportType.MESHTASTIC_NATIVE, available=True)
        else:
            self._update_status(TransportType.MESHTASTIC_NATIVE, available=False)

        # Check for USB Meshtastic device
        if self._check_meshtastic_serial():
            available.append(TransportType.MESHTASTIC_SERIAL)
            self._update_status(TransportType.MESHTASTIC_SERIAL, available=True)
        else:
            self._update_status(TransportType.MESHTASTIC_SERIAL, available=False)

        # Check MQTT broker connectivity
        if self._check_mqtt():
            available.append(TransportType.MQTT)
            self._update_status(TransportType.MQTT, available=True)
        else:
            self._update_status(TransportType.MQTT, available=False)

        return available

    def _check_meshtastic_native(self) -> bool:
        """Check if meshtasticd is running and accessible."""
        try:
            import socket
            # Try to connect to meshtasticd TCP port (default 4403)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 4403))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _check_meshtastic_serial(self) -> bool:
        """Check if a USB Meshtastic device is connected."""
        try:
            from pymeshzork.meshtastic.serial_client import list_serial_devices
            devices = list_serial_devices()
            # Look for known Meshtastic device VID/PIDs
            for dev in devices:
                if dev.get('vid') in [0x10C4, 0x1A86, 0x303A]:  # CP210x, CH9102, ESP32
                    return True
            return False
        except Exception:
            return False

    def _check_mqtt(self) -> bool:
        """Check if MQTT broker is reachable."""
        try:
            from pymeshzork.config import get_config
            config = get_config()
            if not config.mqtt.enabled:
                return False

            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((config.mqtt.broker, config.mqtt.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _update_status(
        self,
        transport_type: TransportType,
        available: bool | None = None,
        connected: bool | None = None,
        error: str | None = None,
    ) -> None:
        """Update transport status."""
        if transport_type not in self._transport_status:
            self._transport_status[transport_type] = TransportStatus(
                transport_type=transport_type
            )

        status = self._transport_status[transport_type]
        status.last_check = time.time()

        if available is not None:
            status.available = available
        if connected is not None:
            status.connected = connected
        if error is not None:
            status.error_message = error

    def connect(self, transport_types: list[TransportType] | None = None) -> bool:
        """Connect to transports.

        Args:
            transport_types: Specific transports to connect. If None, auto-detects.

        Returns:
            True if at least one transport connected.
        """
        if transport_types is None:
            if self.config.auto_detect:
                transport_types = self.detect_available_transports()
            else:
                transport_types = self.config.transport_priority

        connected_any = False

        for tt in self.config.transport_priority:
            if tt not in transport_types:
                continue

            try:
                client = self._create_client(tt)
                if client and client.connect():
                    self._transports[tt] = client
                    self._update_status(tt, connected=True)
                    client.on_message(lambda msg, src=tt: self._handle_message(msg, src))

                    logger.info(f"Connected to {tt.name}")
                    connected_any = True

                    # Set primary transport if not set
                    if self._primary_transport is None:
                        self._primary_transport = tt

            except Exception as e:
                logger.error(f"Failed to connect {tt.name}: {e}")
                self._update_status(tt, connected=False, error=str(e))

        # Start detection thread for auto-reconnect
        if self.config.auto_detect and not self._detection_thread:
            self._start_detection_thread()

        return connected_any

    def _create_client(self, transport_type: TransportType) -> MeshtasticClient | None:
        """Create a client for the given transport type."""
        from pymeshzork.config import get_config
        config = get_config()

        if transport_type == TransportType.MESHTASTIC_NATIVE:
            # TODO: Implement MeshtasticNativeClient
            logger.warning("Meshtastic Native client not yet implemented")
            return None

        elif transport_type == TransportType.MESHTASTIC_SERIAL:
            from pymeshzork.meshtastic.serial_client import SerialClient
            return SerialClient(
                player_name=self.player_name,
                port=config.serial.port or None,
            )

        elif transport_type == TransportType.MQTT:
            from pymeshzork.meshtastic.mqtt_client import MQTTClient
            return MQTTClient(
                player_name=self.player_name,
                broker=config.mqtt.broker,
                port=config.mqtt.port,
                username=config.mqtt.username or None,
                password=config.mqtt.password or None,
                use_tls=config.mqtt.use_tls,
            )

        return None

    def disconnect(self) -> None:
        """Disconnect all transports."""
        self._stop_detection.set()
        if self._detection_thread:
            self._detection_thread.join(timeout=2)
            self._detection_thread = None

        for tt, client in self._transports.items():
            try:
                client.disconnect()
            except Exception as e:
                logger.debug(f"Error disconnecting {tt.name}: {e}")

        self._transports.clear()
        self._primary_transport = None

    def send(self, message: GameMessage) -> bool:
        """Send a message via the primary transport.

        Args:
            message: The game message to send.

        Returns:
            True if sent successfully.
        """
        if self._primary_transport is None:
            logger.warning("No primary transport available")
            return False

        client = self._transports.get(self._primary_transport)
        if client and client.state == ConnectionState.CONNECTED:
            return client.send(message)

        # Try fallback transports
        if self.config.enable_fallback:
            for tt in self.config.transport_priority:
                if tt == self._primary_transport:
                    continue
                client = self._transports.get(tt)
                if client and client.state == ConnectionState.CONNECTED:
                    logger.debug(f"Using fallback transport: {tt.name}")
                    return client.send(message)

        return False

    def _handle_message(self, message: GameMessage, source: TransportType) -> None:
        """Handle incoming message with deduplication.

        Args:
            message: The received game message.
            source: Which transport delivered the message.
        """
        # Generate message ID for deduplication
        msg_id = f"{message.player_id}:{message.sequence}"

        # Check if we've already seen this message
        if msg_id in self._seen_messages:
            self._duplicate_count += 1
            logger.debug(f"Duplicate message from {source.name}: {msg_id}")
            return

        # Mark as seen
        self._seen_messages.add(msg_id)

        # Dispatch to callbacks
        for callback in self._message_callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Message callback error: {e}")

    def _start_detection_thread(self) -> None:
        """Start background thread for transport detection/reconnection."""
        self._stop_detection.clear()
        self._detection_thread = threading.Thread(
            target=self._detection_loop,
            daemon=True,
            name="transport-detection",
        )
        self._detection_thread.start()

    def _detection_loop(self) -> None:
        """Background loop for detecting and reconnecting transports."""
        while not self._stop_detection.wait(self.config.detection_interval):
            try:
                # Check for newly available transports
                available = self.detect_available_transports()

                for tt in available:
                    if tt not in self._transports:
                        # Try to connect to newly available transport
                        logger.info(f"Detected new transport: {tt.name}")
                        try:
                            client = self._create_client(tt)
                            if client and client.connect():
                                self._transports[tt] = client
                                self._update_status(tt, connected=True)
                                client.on_message(
                                    lambda msg, src=tt: self._handle_message(msg, src)
                                )

                                # Update primary if higher priority
                                if self._primary_transport is None:
                                    self._primary_transport = tt
                                else:
                                    current_idx = self.config.transport_priority.index(
                                        self._primary_transport
                                    )
                                    new_idx = self.config.transport_priority.index(tt)
                                    if new_idx < current_idx:
                                        self._primary_transport = tt
                                        logger.info(f"Switched to higher priority: {tt.name}")

                        except Exception as e:
                            logger.debug(f"Failed to connect {tt.name}: {e}")

                # Check for disconnected transports
                for tt in list(self._transports.keys()):
                    client = self._transports[tt]
                    if client.state != ConnectionState.CONNECTED:
                        logger.warning(f"Transport disconnected: {tt.name}")
                        self._update_status(tt, connected=False)

                        # Update primary if needed
                        if tt == self._primary_transport:
                            self._primary_transport = None
                            for candidate in self.config.transport_priority:
                                if candidate in self._transports:
                                    c = self._transports[candidate]
                                    if c.state == ConnectionState.CONNECTED:
                                        self._primary_transport = candidate
                                        logger.info(f"Switched to: {candidate.name}")
                                        break

            except Exception as e:
                logger.error(f"Detection loop error: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get status of all transports.

        Returns:
            Dictionary with transport status information.
        """
        return {
            "primary": self._primary_transport.name if self._primary_transport else None,
            "connected": [tt.name for tt in self.connected_transports],
            "duplicate_count": self._duplicate_count,
            "transports": {
                tt.name: {
                    "available": status.available,
                    "connected": status.connected,
                    "error": status.error_message,
                }
                for tt, status in self._transport_status.items()
            },
        }
