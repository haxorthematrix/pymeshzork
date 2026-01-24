"""Multiplayer integration for PyMeshZork game engine.

Bridges the Meshtastic client with the game engine to enable:
- Seeing other players in rooms
- Broadcasting actions to other players
- Receiving and displaying remote player actions
- Chat functionality
"""

import logging
from typing import TYPE_CHECKING, Callable

from pymeshzork.config import get_config, MQTTConfig
from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.mqtt_client import MQTTClient
from pymeshzork.meshtastic.presence import PresenceManager, PlayerInfo
from pymeshzork.meshtastic.protocol import MessageType, GameMessage

if TYPE_CHECKING:
    from pymeshzork.engine.game import Game

logger = logging.getLogger(__name__)


class MultiplayerManager:
    """Manages multiplayer functionality for the game.

    Handles connection, presence tracking, and message routing.
    """

    def __init__(self, player_name: str | None = None):
        """Initialize multiplayer manager.

        Args:
            player_name: Player display name. If None, uses config.
        """
        config = get_config()
        self.player_name = player_name or config.game.player_name
        self.mqtt_config = config.mqtt

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

    @property
    def is_enabled(self) -> bool:
        """Check if multiplayer is enabled in config."""
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
            # Create MQTT client
            self._client = MQTTClient(
                player_name=self.player_name,
                broker=self.mqtt_config.broker,
                port=self.mqtt_config.port,
                username=self.mqtt_config.username or None,
                password=self.mqtt_config.password or None,
                use_tls=self.mqtt_config.use_tls,
                channel=self.mqtt_config.channel,
            )

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
                logger.info(f"Connected to multiplayer as {self.player_name}")
                return True
            else:
                logger.error("Failed to connect to multiplayer server")
                return False

        except Exception as e:
            logger.error(f"Multiplayer connection error: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from multiplayer server."""
        if self._presence:
            self._presence.stop()
            self._presence = None

        if self._client:
            self._client.disconnect()
            self._client = None

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

    def update_room(self, room_id: str) -> None:
        """Update the current room context."""
        if self._client:
            self._client.set_room(room_id)

    # =========================================================================
    # Incoming message handlers
    # =========================================================================

    def _handle_player_join(self, player: PlayerInfo) -> None:
        """Handle remote player joining."""
        msg = f"\n[{player.name} has entered the game]"
        self._pending_messages.append(msg)

        for callback in self._on_player_join:
            try:
                callback(player)
            except Exception:
                pass

    def _handle_player_leave(self, player: PlayerInfo) -> None:
        """Handle remote player leaving."""
        msg = f"\n[{player.name} has left the game]"
        self._pending_messages.append(msg)

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
