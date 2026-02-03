"""Base client interface for Meshtastic multiplayer connections."""

import hashlib
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from pymeshzork.meshtastic.protocol import (
    GameMessage,
    MessageType,
    encode_message,
    decode_message,
    create_join_message,
    create_leave_message,
    create_move_message,
    create_action_message,
    create_chat_message,
    create_heartbeat,
    create_object_update,
    create_sync_request,
)


class ConnectionState(Enum):
    """Connection state for the client."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    ERROR = auto()


@dataclass
class QueuedMessage:
    """A message queued for sending."""

    message: GameMessage
    attempts: int = 0
    queued_at: float = field(default_factory=time.time)


class MeshtasticClient(ABC):
    """Abstract base class for Meshtastic multiplayer clients.

    Subclasses implement specific connection methods (MQTT, Serial, TCP).
    """

    def __init__(
        self,
        player_name: str,
        channel: str = "pymeshzork",
    ):
        self.player_name = player_name
        self.channel = channel

        # Generate player ID from name (6-char hash)
        self.player_id = self._generate_player_id(player_name)

        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._state_lock = threading.Lock()

        # Message handling
        self._sequence = 0
        self._sequence_lock = threading.Lock()
        self._seen_sequences: dict[str, set[int]] = {}  # player_id -> seen sequences

        # Message queue for offline resilience
        self._outgoing_queue: deque[QueuedMessage] = deque(maxlen=100)
        self._queue_lock = threading.Lock()

        # Callbacks
        self._message_callbacks: list[Callable[[GameMessage], None]] = []
        self._state_callbacks: list[Callable[[ConnectionState], None]] = []

        # Current room (for context)
        self._current_room: str = "whous"

        # Heartbeat
        self._heartbeat_interval = 60  # seconds
        self._heartbeat_thread: threading.Thread | None = None
        self._stop_heartbeat = threading.Event()

    def _generate_player_id(self, name: str) -> str:
        """Generate a 6-character player ID from name."""
        hash_bytes = hashlib.sha256(name.encode()).hexdigest()
        return hash_bytes[:6]

    def _next_sequence(self) -> int:
        """Get the next sequence number."""
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        with self._state_lock:
            return self._state

    def _set_state(self, state: ConnectionState) -> None:
        """Set connection state and notify callbacks."""
        with self._state_lock:
            if self._state != state:
                self._state = state
                for callback in self._state_callbacks:
                    try:
                        callback(state)
                    except Exception:
                        pass

    def on_message(self, callback: Callable[[GameMessage], None]) -> None:
        """Register a callback for incoming messages."""
        self._message_callbacks.append(callback)

    def on_state_change(self, callback: Callable[[ConnectionState], None]) -> None:
        """Register a callback for state changes."""
        self._state_callbacks.append(callback)

    def _handle_incoming(self, data: str | bytes) -> None:
        """Handle an incoming message."""
        try:
            msg = decode_message(data)

            # Ignore our own messages
            if msg.player_id == self.player_id:
                return

            # Deduplicate by sequence number
            if msg.player_id not in self._seen_sequences:
                self._seen_sequences[msg.player_id] = set()

            seen = self._seen_sequences[msg.player_id]
            if msg.sequence in seen:
                return  # Already processed

            seen.add(msg.sequence)
            # Keep only recent sequences to avoid memory growth
            if len(seen) > 1000:
                seen.clear()

            # Notify callbacks
            for callback in self._message_callbacks:
                try:
                    callback(msg)
                except Exception:
                    pass

        except Exception as e:
            # Invalid message, ignore
            pass

    def _queue_message(self, msg: GameMessage) -> None:
        """Queue a message for sending."""
        with self._queue_lock:
            self._outgoing_queue.append(QueuedMessage(message=msg))

    def _flush_queue(self) -> None:
        """Attempt to send all queued messages."""
        if self.state != ConnectionState.CONNECTED:
            return

        with self._queue_lock:
            while self._outgoing_queue:
                queued = self._outgoing_queue[0]
                try:
                    self._send_raw(encode_message(queued.message))
                    self._outgoing_queue.popleft()
                except Exception:
                    queued.attempts += 1
                    if queued.attempts >= 3:
                        self._outgoing_queue.popleft()  # Give up after 3 attempts
                    break

    def _start_heartbeat(self) -> None:
        """Start the heartbeat thread."""
        self._stop_heartbeat.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat_thread(self) -> None:
        """Stop the heartbeat thread."""
        self._stop_heartbeat.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)
            self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while not self._stop_heartbeat.wait(self._heartbeat_interval):
            if self.state == ConnectionState.CONNECTED:
                self.send_heartbeat()

    # =========================================================================
    # Abstract methods - must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the Meshtastic network.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the network."""
        pass

    @abstractmethod
    def _send_raw(self, data: str) -> None:
        """Send raw data over the connection.

        Args:
            data: JSON-encoded message string.
        """
        pass

    # =========================================================================
    # Public API - send messages
    # =========================================================================

    def send(self, msg: GameMessage) -> bool:
        """Send a game message.

        Args:
            msg: The message to send.

        Returns:
            True if sent immediately, False if queued.
        """
        msg.sequence = self._next_sequence()

        if self.state == ConnectionState.CONNECTED:
            try:
                self._send_raw(encode_message(msg))
                return True
            except Exception:
                self._queue_message(msg)
                return False
        else:
            self._queue_message(msg)
            return False

    def send_join(self, room_id: str) -> bool:
        """Announce joining the game."""
        self._current_room = room_id
        msg = create_join_message(
            self.player_id,
            self.player_name,
            room_id,
        )
        return self.send(msg)

    def send_leave(self) -> bool:
        """Announce leaving the game."""
        msg = create_leave_message(self.player_id)
        return self.send(msg)

    def send_move(self, from_room: str, to_room: str) -> bool:
        """Announce moving to a new room."""
        self._current_room = to_room
        msg = create_move_message(self.player_id, from_room, to_room, self.player_name)
        return self.send(msg)

    def send_action(
        self,
        verb: str,
        obj_id: str | None = None,
        room_id: str | None = None,
    ) -> bool:
        """Announce performing an action."""
        msg = create_action_message(
            self.player_id,
            verb,
            obj_id,
            room_id or self._current_room,
        )
        return self.send(msg)

    def send_chat(self, message: str, is_team: bool = False) -> bool:
        """Send a chat message."""
        msg = create_chat_message(
            self.player_id,
            message,
            self._current_room,
            is_team,
        )
        return self.send(msg)

    def send_heartbeat(self) -> bool:
        """Send a heartbeat."""
        msg = create_heartbeat(self.player_id, self._current_room)
        return self.send(msg)

    def send_object_update(
        self,
        obj_id: str,
        location: str | None = None,
        holder: str | None = None,
    ) -> bool:
        """Send an object state update."""
        msg = create_object_update(
            self.player_id,
            obj_id,
            location,
            holder,
        )
        return self.send(msg)

    def request_sync(self, room_id: str | None = None) -> bool:
        """Request state synchronization."""
        msg = create_sync_request(self.player_id, room_id)
        return self.send(msg)

    def set_room(self, room_id: str) -> None:
        """Update the current room context."""
        self._current_room = room_id
