"""Multiplayer integration for PyMeshZork game engine.

Bridges the Meshtastic client with the game engine to enable:
- Seeing other players in rooms
- Broadcasting actions to other players
- Receiving and displaying remote player actions
- Chat functionality

Supports multiple backends:
- MQTT: For Raspberry Pi/Linux with network access
- LoRa: For Raspberry Pi with Adafruit Radio Bonnet (direct RF)
"""

import logging
from enum import Enum
from typing import TYPE_CHECKING, Callable

from pymeshzork.config import get_config
from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.mqtt_client import MQTTClient
from pymeshzork.meshtastic.presence import PresenceManager, PlayerInfo
from pymeshzork.meshtastic.protocol import MessageType, GameMessage
from pymeshzork.meshtastic.oled_display import get_display

if TYPE_CHECKING:
    from pymeshzork.engine.game import Game

logger = logging.getLogger(__name__)


class MultiplayerBackend(Enum):
    """Available multiplayer backends."""
    MQTT = "mqtt"
    LORA = "lora"  # Legacy direct RFM9x (not Meshtastic compatible)
    SERIAL = "serial"  # USB serial to Meshtastic device
    NATIVE = "native"  # meshtasticd on Radio Bonnet (Meshtastic compatible)


class MultiplayerManager:
    """Manages multiplayer functionality for the game.

    Handles connection, presence tracking, and message routing.
    Supports multiple backends (MQTT, LoRa).
    """

    def __init__(
        self,
        player_name: str | None = None,
        backend: MultiplayerBackend | str | None = None,
    ):
        """Initialize multiplayer manager.

        Args:
            player_name: Player display name. If None, uses config.
            backend: Which backend to use (mqtt, lora). If None, auto-detects.
        """
        config = get_config()
        self.player_name = player_name or config.game.player_name
        self.mqtt_config = config.mqtt
        self.lora_config = config.lora
        self.serial_config = config.serial

        # Determine backend
        if backend is None:
            # Auto-detect: prefer Serial, then LoRa, fall back to MQTT
            if self.serial_config.enabled:
                self._backend = MultiplayerBackend.SERIAL
            elif self.lora_config.enabled:
                self._backend = MultiplayerBackend.LORA
            else:
                self._backend = MultiplayerBackend.MQTT
        elif isinstance(backend, str):
            self._backend = MultiplayerBackend(backend.lower())
        else:
            self._backend = backend

        self._client: MeshtasticClient | None = None
        self._presence: PresenceManager | None = None
        self._game: "Game | None" = None

        # Message callbacks for the game to register
        self._on_player_join: list[Callable[[PlayerInfo], None]] = []
        self._on_player_leave: list[Callable[[PlayerInfo], None]] = []
        self._on_player_move: list[Callable[[PlayerInfo, str, str], None]] = []
        self._on_player_action: list[Callable[[PlayerInfo, str, str | None], None]] = []
        self._on_chat: list[Callable[[PlayerInfo, str, bool], None]] = []

        # Pending messages to display
        self._pending_messages: list[str] = []

        # OLED display reference
        self._display = None

    @property
    def backend(self) -> MultiplayerBackend:
        """Get the current backend type."""
        return self._backend

    @property
    def is_enabled(self) -> bool:
        """Check if multiplayer is enabled in config."""
        if self._backend == MultiplayerBackend.NATIVE:
            # Native uses meshtasticd - check if it's running
            from pymeshzork.meshtastic.native_client import check_meshtasticd_running
            return check_meshtasticd_running()
        elif self._backend == MultiplayerBackend.SERIAL:
            return self.serial_config.enabled
        elif self._backend == MultiplayerBackend.LORA:
            return self.lora_config.enabled
        else:
            return self.mqtt_config.enabled and self.mqtt_config.is_configured()

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to multiplayer."""
        return (
            self._client is not None
            and self._client.state == ConnectionState.CONNECTED
        )

    @property
    def player_id(self) -> str | None:
        """Get the local player's ID."""
        return self._client.player_id if self._client else None

    def connect(self) -> bool:
        """Connect to the multiplayer server.

        Returns:
            True if connection successful, False otherwise.
        """
        if not self.is_enabled:
            logger.info("Multiplayer not enabled in config")
            return False

        if self.is_connected:
            return True

        try:
            # Create appropriate client based on backend
            if self._backend == MultiplayerBackend.NATIVE:
                self._client = self._create_native_client()
            elif self._backend == MultiplayerBackend.SERIAL:
                self._client = self._create_serial_client()
            elif self._backend == MultiplayerBackend.LORA:
                self._client = self._create_lora_client()
            else:
                self._client = self._create_mqtt_client()

            if self._client is None:
                return False

            # Set up presence manager
            self._presence = PresenceManager(self._client.player_id)
            self._presence.start()

            # Wire up callbacks
            self._presence.on_join(self._handle_player_join)
            self._presence.on_leave(self._handle_player_leave)
            self._presence.on_move(self._handle_player_move)
            self._presence.on_action(self._handle_player_action)
            self._presence.on_chat(self._handle_chat)

            self._client.on_message(self._presence.handle_message)

            # Connect
            if self._client.connect():
                backend_name = self._backend.value.upper()
                logger.info(f"Connected to multiplayer ({backend_name}) as {self.player_name}")

                # Initialize OLED display
                self._display = get_display()
                if self._display:
                    self._display.update_player(self.player_name)
                    self._display.set_connected(True, backend_name)

                return True
            else:
                logger.error("Failed to connect to multiplayer")
                return False

        except Exception as e:
            logger.error(f"Multiplayer connection error: {e}")
            return False

    def _create_mqtt_client(self) -> MQTTClient:
        """Create an MQTT client."""
        return MQTTClient(
            player_name=self.player_name,
            broker=self.mqtt_config.broker,
            port=self.mqtt_config.port,
            username=self.mqtt_config.username or None,
            password=self.mqtt_config.password or None,
            use_tls=self.mqtt_config.use_tls,
            channel=self.mqtt_config.channel,
        )

    def _create_lora_client(self) -> "MeshtasticClient | None":
        """Create a LoRa client."""
        try:
            from pymeshzork.meshtastic.lora_client import LoRaClient
            return LoRaClient(
                player_name=self.player_name,
                frequency=self.lora_config.frequency,
                tx_power=self.lora_config.tx_power,
            )
        except ImportError as e:
            logger.error(f"LoRa client not available: {e}")
            logger.error("Install with: pip install 'pymeshzork[lora]'")
            return None

    def _create_serial_client(self) -> "MeshtasticClient | None":
        """Create a serial client for Meshtastic devices."""
        try:
            from pymeshzork.meshtastic.serial_client import SerialClient
            return SerialClient(
                player_name=self.player_name,
                port=self.serial_config.port or None,  # Empty string -> auto-detect
            )
        except ImportError as e:
            logger.error(f"Serial client not available: {e}")
            logger.error("Install with: pip install 'pymeshzork[mesh]'")
            return None

    def _create_native_client(self) -> "MeshtasticClient | None":
        """Create a native client for meshtasticd (Meshtastic on Radio Bonnet)."""
        try:
            from pymeshzork.meshtastic.native_client import NativeClient
            return NativeClient(
                player_name=self.player_name,
            )
        except ImportError as e:
            logger.error(f"Native client not available: {e}")
            logger.error("Install with: pip install 'pymeshzork[mesh]'")
            return None

    def disconnect(self) -> None:
        """Disconnect from multiplayer server."""
        if self._presence:
            self._presence.stop()
            self._presence = None

        if self._client:
            self._client.disconnect()
            self._client = None

        # Update OLED display
        if self._display:
            self._display.set_connected(False)
            self._display = None

    def set_game(self, game: "Game") -> None:
        """Set the game instance for integration."""
        self._game = game

    # =========================================================================
    # Outgoing messages (game -> network)
    # =========================================================================

    def send_join(self, room_id: str) -> None:
        """Announce joining the game."""
        if self._client and self.is_connected:
            self._client.send_join(room_id)

    def send_move(self, from_room: str, to_room: str) -> None:
        """Announce moving to a new room."""
        if self._client and self.is_connected:
            self._client.send_move(from_room, to_room)

    def send_action(self, verb: str, obj_id: str | None = None) -> None:
        """Announce performing an action."""
        if self._client and self.is_connected:
            room_id = self._game.state.current_room if self._game else None
            self._client.send_action(verb, obj_id, room_id)

    def send_chat(self, message: str, is_team: bool = False) -> None:
        """Send a chat message."""
        if self._client and self.is_connected:
            self._client.send_chat(message, is_team)

    def update_room(self, room_id: str, room_name: str = "") -> None:
        """Update the current room context.

        Args:
            room_id: Room ID.
            room_name: Human-readable room name for display.
        """
        if self._client:
            # Check if client supports room_name parameter
            if hasattr(self._client, 'set_room'):
                try:
                    self._client.set_room(room_id, room_name)
                except TypeError:
                    self._client.set_room(room_id)

        # Update OLED display with room and players
        if self._display:
            self._display.update_player(self.player_name, room_id, room_name)
            players = self.get_players_in_room(room_id)
            player_names = [p.name for p in players]
            self._display.set_players_in_room(player_names)

    # =========================================================================
    # Incoming message handlers
    # =========================================================================

    def _handle_player_join(self, player: PlayerInfo) -> None:
        """Handle remote player joining."""
        msg = f"\n[{player.name} has entered the game]"
        self._pending_messages.append(msg)

        # Update OLED display
        if self._display:
            self._display.add_message(f"{player.name} joined")
            # Update player list if in same room
            if self._game:
                current_room = self._game.state.current_room
                players = self.get_players_in_room(current_room)
                player_names = [p.name for p in players]
                self._display.set_players_in_room(player_names)

        for callback in self._on_player_join:
            try:
                callback(player)
            except Exception:
                pass

    def _handle_player_leave(self, player: PlayerInfo) -> None:
        """Handle remote player leaving."""
        msg = f"\n[{player.name} has left the game]"
        self._pending_messages.append(msg)

        # Update OLED display
        if self._display:
            self._display.add_message(f"{player.name} left")
            # Update player list if in same room
            if self._game:
                current_room = self._game.state.current_room
                players = self.get_players_in_room(current_room)
                player_names = [p.name for p in players]
                self._display.set_players_in_room(player_names)

        for callback in self._on_player_leave:
            try:
                callback(player)
            except Exception:
                pass

    def _handle_player_move(self, player: PlayerInfo, from_room: str, to_room: str) -> None:
        """Handle remote player moving."""
        if self._game:
            current_room = self._game.state.current_room

            # Player entered our room
            if to_room == current_room:
                msg = f"\n{player.name} has arrived."
                self._pending_messages.append(msg)

            # Player left our room
            elif from_room == current_room:
                msg = f"\n{player.name} has left."
                self._pending_messages.append(msg)

            # Update OLED display with current room players
            if self._display:
                players = self.get_players_in_room(current_room)
                player_names = [p.name for p in players]
                self._display.set_players_in_room(player_names)

        for callback in self._on_player_move:
            try:
                callback(player, from_room, to_room)
            except Exception:
                pass

    def _handle_player_action(self, player: PlayerInfo, verb: str, obj_id: str | None) -> None:
        """Handle remote player performing action."""
        if self._game:
            current_room = self._game.state.current_room

            # Only show actions in same room
            if player.room_id == current_room:
                if obj_id:
                    msg = f"\n{player.name} {verb}s the {obj_id}."
                else:
                    msg = f"\n{player.name} {verb}s."
                self._pending_messages.append(msg)

        for callback in self._on_player_action:
            try:
                callback(player, verb, obj_id)
            except Exception:
                pass

    def _handle_chat(self, player: PlayerInfo, message: str, is_team: bool) -> None:
        """Handle chat message."""
        if is_team:
            msg = f"\n[Team] {player.name}: {message}"
        else:
            msg = f"\n{player.name} says: \"{message}\""
        self._pending_messages.append(msg)

        # Update OLED display with message
        if self._display:
            display_msg = f"{player.name}: {message}"
            self._display.add_message(display_msg)

        for callback in self._on_chat:
            try:
                callback(player, message, is_team)
            except Exception:
                pass

    # =========================================================================
    # Game integration
    # =========================================================================

    def get_pending_messages(self) -> list[str]:
        """Get and clear pending messages for display."""
        messages = self._pending_messages.copy()
        self._pending_messages.clear()
        return messages

    def get_players_in_room(self, room_id: str) -> list[PlayerInfo]:
        """Get other players in a room."""
        if self._presence:
            return self._presence.get_players_in_room(room_id)
        return []

    def get_all_players(self) -> list[PlayerInfo]:
        """Get all known players."""
        if self._presence:
            return self._presence.get_all_players()
        return []

    def get_player_count(self) -> int:
        """Get number of other players online."""
        if self._presence:
            return self._presence.get_player_count()
        return 0

    def format_players_in_room(self, room_id: str) -> str | None:
        """Format a string describing other players in the room."""
        players = self.get_players_in_room(room_id)
        if not players:
            return None

        names = [p.name for p in players]
        if len(names) == 1:
            return f"{names[0]} is here."
        elif len(names) == 2:
            return f"{names[0]} and {names[1]} are here."
        else:
            return f"{', '.join(names[:-1])}, and {names[-1]} are here."

    # =========================================================================
    # Callback registration
    # =========================================================================

    def on_player_join(self, callback: Callable[[PlayerInfo], None]) -> None:
        """Register callback for player joins."""
        self._on_player_join.append(callback)

    def on_player_leave(self, callback: Callable[[PlayerInfo], None]) -> None:
        """Register callback for player leaves."""
        self._on_player_leave.append(callback)

    def on_player_move(self, callback: Callable[[PlayerInfo, str, str], None]) -> None:
        """Register callback for player moves."""
        self._on_player_move.append(callback)

    def on_player_action(self, callback: Callable[[PlayerInfo, str, str | None], None]) -> None:
        """Register callback for player actions."""
        self._on_player_action.append(callback)

    def on_chat(self, callback: Callable[[PlayerInfo, str, bool], None]) -> None:
        """Register callback for chat messages."""
        self._on_chat.append(callback)


# Global multiplayer instance
_multiplayer: MultiplayerManager | None = None


def get_multiplayer() -> MultiplayerManager | None:
    """Get the global multiplayer manager, if enabled."""
    global _multiplayer
    config = get_config()

    if not config.mqtt.enabled:
        return None

    if _multiplayer is None:
        _multiplayer = MultiplayerManager()

    return _multiplayer


def init_multiplayer(player_name: str | None = None) -> MultiplayerManager | None:
    """Initialize and connect multiplayer.

    Args:
        player_name: Optional player name override.

    Returns:
        MultiplayerManager if connected, None otherwise.
    """
    global _multiplayer
    config = get_config()

    if not config.mqtt.enabled:
        return None

    _multiplayer = MultiplayerManager(player_name)
    if _multiplayer.connect():
        return _multiplayer
    else:
        _multiplayer = None
        return None
