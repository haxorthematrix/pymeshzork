"""Tests for the Meshtastic multiplayer module."""

import json
import time
import pytest

from pymeshzork.meshtastic.protocol import (
    MessageType,
    GameMessage,
    PROTOCOL_VERSION,
    encode_message,
    decode_message,
    create_join_message,
    create_leave_message,
    create_move_message,
    create_action_message,
    create_chat_message,
    create_heartbeat,
    create_object_update,
    ROOM_IDS,
    ROOM_NAMES,
    OBJECT_IDS,
    OBJECT_NAMES,
)
from pymeshzork.meshtastic.presence import PresenceManager, PlayerInfo


class TestProtocol:
    """Tests for message protocol."""

    def test_message_type_values(self):
        """Verify message type codes are compact."""
        assert MessageType.PLAYER_JOIN.value == "PJ"
        assert MessageType.PLAYER_MOVE.value == "PM"
        assert MessageType.CHAT.value == "CH"
        assert len(MessageType.PLAYER_JOIN.value) == 2

    def test_room_id_mapping(self):
        """Test room ID mapping is bidirectional."""
        assert ROOM_IDS["whous"] == 1
        assert ROOM_IDS["lroom"] == 2
        assert ROOM_NAMES[1] == "whous"
        assert ROOM_NAMES[2] == "lroom"

    def test_object_id_mapping(self):
        """Test object ID mapping is bidirectional."""
        assert OBJECT_IDS["lamp"] == 1
        assert OBJECT_IDS["sword"] == 10
        assert OBJECT_NAMES[1] == "lamp"
        assert OBJECT_NAMES[10] == "sword"

    def test_game_message_to_compact(self):
        """Test message compaction."""
        msg = GameMessage(
            type=MessageType.PLAYER_MOVE,
            player_id="abc123def",
            sequence=42,
            data={"f": 1, "r": 2},
        )
        compact = msg.to_compact()

        assert compact["v"] == PROTOCOL_VERSION
        assert compact["t"] == "PM"
        assert compact["p"] == "abc123"  # Truncated to 6 chars
        assert compact["s"] == 42
        assert compact["d"] == {"f": 1, "r": 2}

    def test_game_message_from_compact(self):
        """Test message parsing."""
        compact = {
            "v": 1,
            "t": "PJ",
            "p": "xyz789",
            "s": 100,
            "d": {"n": "TestPlayer", "r": 1},
        }
        msg = GameMessage.from_compact(compact)

        assert msg.type == MessageType.PLAYER_JOIN
        assert msg.player_id == "xyz789"
        assert msg.sequence == 100
        assert msg.data["n"] == "TestPlayer"

    def test_encode_decode_roundtrip(self):
        """Test encode/decode roundtrip."""
        original = GameMessage(
            type=MessageType.CHAT,
            player_id="player1",
            sequence=1,
            data={"m": "Hello world!"},
        )

        encoded = encode_message(original)
        decoded = decode_message(encoded)

        assert decoded.type == original.type
        assert decoded.player_id == original.player_id[:6]
        assert decoded.sequence == original.sequence
        assert decoded.data == original.data

    def test_encode_produces_compact_json(self):
        """Test that encoding produces compact JSON."""
        msg = GameMessage(
            type=MessageType.HEARTBEAT,
            player_id="test",
            sequence=1,
            data={"r": 1},
        )
        encoded = encode_message(msg)

        # Should have no spaces (compact JSON)
        assert " " not in encoded
        # Should be valid JSON
        parsed = json.loads(encoded)
        assert parsed["t"] == "HB"


class TestMessageFactories:
    """Tests for message factory functions."""

    def test_create_join_message(self):
        """Test join message creation."""
        msg = create_join_message("player1", "TestPlayer", "whous", seq=1)

        assert msg.type == MessageType.PLAYER_JOIN
        assert msg.player_id == "player1"
        assert msg.sequence == 1
        assert msg.data["n"] == "TestPlayer"
        assert msg.data["r"] == 1  # ROOM_IDS["whous"]

    def test_create_join_message_truncates_name(self):
        """Test that long names are truncated."""
        msg = create_join_message("p1", "VeryLongPlayerName123", "whous")
        assert len(msg.data["n"]) <= 16

    def test_create_leave_message(self):
        """Test leave message creation."""
        msg = create_leave_message("player1", seq=5)

        assert msg.type == MessageType.PLAYER_LEAVE
        assert msg.player_id == "player1"
        assert msg.sequence == 5
        assert msg.data == {}

    def test_create_move_message(self):
        """Test move message creation."""
        msg = create_move_message("player1", "whous", "lroom", seq=2)

        assert msg.type == MessageType.PLAYER_MOVE
        assert msg.data["f"] == 1  # whous
        assert msg.data["r"] == 2  # lroom

    def test_create_action_message(self):
        """Test action message creation."""
        msg = create_action_message("player1", "take", "lamp", "lroom", seq=3)

        assert msg.type == MessageType.PLAYER_ACTION
        assert msg.data["v"] == "take"
        assert msg.data["o"] == 1  # OBJECT_IDS["lamp"]
        assert msg.data["r"] == 2  # ROOM_IDS["lroom"]

    def test_create_chat_message(self):
        """Test chat message creation."""
        msg = create_chat_message("player1", "Hello!", "whous", is_team=False, seq=4)

        assert msg.type == MessageType.CHAT
        assert msg.data["m"] == "Hello!"
        assert msg.data["r"] == 1

    def test_create_team_chat_message(self):
        """Test team chat message creation."""
        msg = create_chat_message("player1", "Team msg", is_team=True)

        assert msg.type == MessageType.TEAM_CHAT

    def test_create_heartbeat(self):
        """Test heartbeat creation."""
        msg = create_heartbeat("player1", "mtrol", seq=10)

        assert msg.type == MessageType.HEARTBEAT
        assert msg.data["r"] == 20  # ROOM_IDS["mtrol"]

    def test_create_object_update(self):
        """Test object update creation."""
        msg = create_object_update("player1", "sword", "lroom", holder="abc123")

        assert msg.type == MessageType.OBJECT_UPDATE
        assert msg.data["o"] == 10  # OBJECT_IDS["sword"]
        assert msg.data["l"] == 2   # ROOM_IDS["lroom"]
        assert msg.data["h"] == "abc123"


class TestPresenceManager:
    """Tests for presence manager."""

    def test_handle_join(self):
        """Test handling player join."""
        manager = PresenceManager("local123")

        # Track join events
        joins = []
        manager.on_join(lambda p: joins.append(p))

        # Simulate join message
        msg = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="remote1",
            data={"n": "RemotePlayer", "r": 1},
        )
        manager.handle_message(msg)

        # Should have one player
        assert manager.get_player_count() == 1
        assert len(joins) == 1
        assert joins[0].name == "RemotePlayer"
        assert joins[0].room_id == "whous"

    def test_handle_leave(self):
        """Test handling player leave."""
        manager = PresenceManager("local123")

        # Add a player first
        join_msg = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="remote1",
            data={"n": "RemotePlayer", "r": 1},
        )
        manager.handle_message(join_msg)

        # Track leave events
        leaves = []
        manager.on_leave(lambda p: leaves.append(p))

        # Simulate leave
        leave_msg = GameMessage(
            type=MessageType.PLAYER_LEAVE,
            player_id="remote1",
        )
        manager.handle_message(leave_msg)

        assert manager.get_player_count() == 0
        assert len(leaves) == 1

    def test_handle_move(self):
        """Test handling player move."""
        manager = PresenceManager("local123")

        # Add a player first
        join_msg = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="remote1",
            data={"n": "RemotePlayer", "r": 1},
        )
        manager.handle_message(join_msg)

        # Track moves
        moves = []
        manager.on_move(lambda p, f, t: moves.append((p, f, t)))

        # Simulate move
        move_msg = GameMessage(
            type=MessageType.PLAYER_MOVE,
            player_id="remote1",
            data={"f": 1, "r": 2},
        )
        manager.handle_message(move_msg)

        player = manager.get_player("remote1")
        assert player.room_id == "lroom"
        assert len(moves) == 1
        assert moves[0][1] == "whous"  # from
        assert moves[0][2] == "lroom"  # to

    def test_get_players_in_room(self):
        """Test getting players in a specific room."""
        manager = PresenceManager("local123")

        # Add players in different rooms
        msg1 = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="player1",
            data={"n": "Player1", "r": 1},
        )
        msg2 = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="player2",
            data={"n": "Player2", "r": 1},
        )
        msg3 = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="player3",
            data={"n": "Player3", "r": 2},
        )

        manager.handle_message(msg1)
        manager.handle_message(msg2)
        manager.handle_message(msg3)

        # Two players in whous
        in_whous = manager.get_players_in_room("whous")
        assert len(in_whous) == 2

        # One player in lroom
        in_lroom = manager.get_players_in_room("lroom")
        assert len(in_lroom) == 1

    def test_ignores_local_player(self):
        """Test that local player messages are ignored."""
        manager = PresenceManager("local123")

        msg = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="local123",  # Same as local
            data={"n": "LocalPlayer", "r": 1},
        )
        manager.handle_message(msg)

        # Should not add local player
        assert manager.get_player_count() == 0

    def test_heartbeat_updates_last_seen(self):
        """Test that heartbeat updates last seen time."""
        manager = PresenceManager("local123")

        # Add player
        join_msg = GameMessage(
            type=MessageType.PLAYER_JOIN,
            player_id="remote1",
            data={"n": "RemotePlayer", "r": 1},
        )
        manager.handle_message(join_msg)

        player = manager.get_player("remote1")
        initial_seen = player.last_seen

        # Small delay
        time.sleep(0.01)

        # Send heartbeat
        hb_msg = GameMessage(
            type=MessageType.HEARTBEAT,
            player_id="remote1",
            data={"r": 1},
        )
        manager.handle_message(hb_msg)

        # Last seen should be updated
        assert player.last_seen > initial_seen

    def test_player_stale_detection(self):
        """Test stale player detection."""
        player = PlayerInfo(
            player_id="test",
            name="Test",
            room_id="whous",
        )

        # Not stale immediately
        assert not player.is_stale(timeout=180)

        # Manually set old timestamp
        player.last_seen = time.time() - 200

        # Now stale
        assert player.is_stale(timeout=180)


class TestMessageSize:
    """Tests to verify message sizes stay within LoRa limits."""

    def test_typical_message_size(self):
        """Test that typical messages are under 100 bytes."""
        msg = create_move_message("abc123", "whous", "lroom", seq=9999)
        encoded = encode_message(msg)

        # Typical messages should be well under 100 bytes
        assert len(encoded) < 100

    def test_chat_message_size(self):
        """Test chat message with max length text."""
        # 128 char message
        long_msg = "A" * 128
        msg = create_chat_message("abc123", long_msg, "whous", seq=9999)
        encoded = encode_message(msg)

        # Even with max text, should be under 200 bytes
        assert len(encoded) < 200

    def test_join_message_size(self):
        """Test join message with max length name."""
        msg = create_join_message("abc123", "A" * 16, "whous", seq=9999)
        encoded = encode_message(msg)

        assert len(encoded) < 80
