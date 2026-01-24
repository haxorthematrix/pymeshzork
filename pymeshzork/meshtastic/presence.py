"""Player presence management for multiplayer."""

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from pymeshzork.meshtastic.protocol import (
    GameMessage,
    MessageType,
    ROOM_NAMES,
)


@dataclass
class PlayerInfo:
    """Information about a remote player."""

    player_id: str
    name: str
    room_id: str
    last_seen: float = field(default_factory=time.time)
    score: int = 0
    team_id: str | None = None

    def is_stale(self, timeout: float = 180) -> bool:
        """Check if player hasn't been seen recently."""
        return time.time() - self.last_seen > timeout

    def update_seen(self) -> None:
        """Update last seen timestamp."""
        self.last_seen = time.time()


class PresenceManager:
    """Manages presence of other players in the game.

    Tracks player locations, handles join/leave, and detects timeouts.
    """

    def __init__(
        self,
        local_player_id: str,
        heartbeat_timeout: float = 180,  # 3 missed heartbeats at 60s
    ):
        """Initialize presence manager.

        Args:
            local_player_id: The local player's ID (to ignore own messages).
            heartbeat_timeout: Seconds without heartbeat before marking stale.
        """
        self.local_player_id = local_player_id
        self.heartbeat_timeout = heartbeat_timeout

        # Player registry
        self._players: dict[str, PlayerInfo] = {}
        self._lock = threading.Lock()

        # Callbacks
        self._on_join: list[Callable[[PlayerInfo], None]] = []
        self._on_leave: list[Callable[[PlayerInfo], None]] = []
        self._on_move: list[Callable[[PlayerInfo, str, str], None]] = []
        self._on_action: list[Callable[[PlayerInfo, str, str | None], None]] = []
        self._on_chat: list[Callable[[PlayerInfo, str, bool], None]] = []

        # Cleanup thread
        self._cleanup_interval = 30  # seconds
        self._stop_cleanup = threading.Event()
        self._cleanup_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the presence manager."""
        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
        )
        self._cleanup_thread.start()

    def stop(self) -> None:
        """Stop the presence manager."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=2)
            self._cleanup_thread = None

    def _cleanup_loop(self) -> None:
        """Periodically clean up stale players."""
        while not self._stop_cleanup.wait(self._cleanup_interval):
            self._cleanup_stale()

    def _cleanup_stale(self) -> None:
        """Remove stale players and notify callbacks."""
        with self._lock:
            stale_ids = [
                pid for pid, player in self._players.items()
                if player.is_stale(self.heartbeat_timeout)
            ]

            for pid in stale_ids:
                player = self._players.pop(pid)
                for callback in self._on_leave:
                    try:
                        callback(player)
                    except Exception:
                        pass

    def handle_message(self, msg: GameMessage) -> None:
        """Process an incoming game message for presence tracking.

        Args:
            msg: The received game message.
        """
        # Ignore our own messages
        if msg.player_id == self.local_player_id:
            return

        if msg.type == MessageType.PLAYER_JOIN:
            self._handle_join(msg)
        elif msg.type == MessageType.PLAYER_LEAVE:
            self._handle_leave(msg)
        elif msg.type == MessageType.PLAYER_MOVE:
            self._handle_move(msg)
        elif msg.type == MessageType.HEARTBEAT:
            self._handle_heartbeat(msg)
        elif msg.type == MessageType.PLAYER_ACTION:
            self._handle_action(msg)
        elif msg.type in (MessageType.CHAT, MessageType.TEAM_CHAT):
            self._handle_chat(msg)

    def _handle_join(self, msg: GameMessage) -> None:
        """Handle player join message."""
        room_num = msg.data.get("r", 0)
        room_id = ROOM_NAMES.get(room_num, "whous")
        name = msg.data.get("n", msg.player_id)

        with self._lock:
            is_new = msg.player_id not in self._players
            player = PlayerInfo(
                player_id=msg.player_id,
                name=name,
                room_id=room_id,
            )
            self._players[msg.player_id] = player

        if is_new:
            for callback in self._on_join:
                try:
                    callback(player)
                except Exception:
                    pass

    def _handle_leave(self, msg: GameMessage) -> None:
        """Handle player leave message."""
        with self._lock:
            player = self._players.pop(msg.player_id, None)

        if player:
            for callback in self._on_leave:
                try:
                    callback(player)
                except Exception:
                    pass

    def _handle_move(self, msg: GameMessage) -> None:
        """Handle player move message."""
        from_room = ROOM_NAMES.get(msg.data.get("f", 0), "")
        to_room = ROOM_NAMES.get(msg.data.get("r", 0), "whous")

        with self._lock:
            player = self._players.get(msg.player_id)
            if player:
                player.room_id = to_room
                player.update_seen()
            else:
                # New player we haven't seen - create entry
                player = PlayerInfo(
                    player_id=msg.player_id,
                    name=msg.player_id,  # Unknown name
                    room_id=to_room,
                )
                self._players[msg.player_id] = player

        for callback in self._on_move:
            try:
                callback(player, from_room, to_room)
            except Exception:
                pass

    def _handle_heartbeat(self, msg: GameMessage) -> None:
        """Handle heartbeat message."""
        room_num = msg.data.get("r", 0)
        room_id = ROOM_NAMES.get(room_num, "whous")

        with self._lock:
            player = self._players.get(msg.player_id)
            if player:
                player.room_id = room_id
                player.update_seen()

    def _handle_action(self, msg: GameMessage) -> None:
        """Handle player action message."""
        verb = msg.data.get("v", "")
        obj_id = msg.data.get("o")
        if isinstance(obj_id, int):
            from pymeshzork.meshtastic.protocol import OBJECT_NAMES
            obj_id = OBJECT_NAMES.get(obj_id)

        with self._lock:
            player = self._players.get(msg.player_id)
            if player:
                player.update_seen()

        if player:
            for callback in self._on_action:
                try:
                    callback(player, verb, obj_id)
                except Exception:
                    pass

    def _handle_chat(self, msg: GameMessage) -> None:
        """Handle chat message."""
        message = msg.data.get("m", "")
        is_team = msg.type == MessageType.TEAM_CHAT

        with self._lock:
            player = self._players.get(msg.player_id)
            if player:
                player.update_seen()
            else:
                # Create temporary player info for chat
                player = PlayerInfo(
                    player_id=msg.player_id,
                    name=msg.player_id,
                    room_id=ROOM_NAMES.get(msg.data.get("r", 0), ""),
                )

        for callback in self._on_chat:
            try:
                callback(player, message, is_team)
            except Exception:
                pass

    # =========================================================================
    # Callback registration
    # =========================================================================

    def on_join(self, callback: Callable[[PlayerInfo], None]) -> None:
        """Register callback for player joins."""
        self._on_join.append(callback)

    def on_leave(self, callback: Callable[[PlayerInfo], None]) -> None:
        """Register callback for player leaves."""
        self._on_leave.append(callback)

    def on_move(self, callback: Callable[[PlayerInfo, str, str], None]) -> None:
        """Register callback for player moves (player, from_room, to_room)."""
        self._on_move.append(callback)

    def on_action(self, callback: Callable[[PlayerInfo, str, str | None], None]) -> None:
        """Register callback for player actions (player, verb, obj_id)."""
        self._on_action.append(callback)

    def on_chat(self, callback: Callable[[PlayerInfo, str, bool], None]) -> None:
        """Register callback for chat messages (player, message, is_team)."""
        self._on_chat.append(callback)

    # =========================================================================
    # Query methods
    # =========================================================================

    def get_player(self, player_id: str) -> PlayerInfo | None:
        """Get info for a specific player."""
        with self._lock:
            return self._players.get(player_id)

    def get_all_players(self) -> list[PlayerInfo]:
        """Get all known players."""
        with self._lock:
            return list(self._players.values())

    def get_players_in_room(self, room_id: str) -> list[PlayerInfo]:
        """Get all players in a specific room."""
        with self._lock:
            return [
                p for p in self._players.values()
                if p.room_id == room_id
            ]

    def get_player_count(self) -> int:
        """Get total number of known players."""
        with self._lock:
            return len(self._players)

    def is_player_online(self, player_id: str) -> bool:
        """Check if a player is online."""
        with self._lock:
            player = self._players.get(player_id)
            return player is not None and not player.is_stale(self.heartbeat_timeout)
