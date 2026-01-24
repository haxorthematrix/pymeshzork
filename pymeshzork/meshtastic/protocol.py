"""Message protocol for PyMeshZork multiplayer.

Defines compact message format optimized for LoRa bandwidth (~237 bytes max).
Uses numeric IDs for rooms/objects to minimize message size.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# Protocol version for compatibility checking
PROTOCOL_VERSION = 1


class MessageType(str, Enum):
    """Message types for multiplayer communication."""

    # Player presence
    PLAYER_JOIN = "PJ"      # Player enters game
    PLAYER_LEAVE = "PL"     # Player exits game
    HEARTBEAT = "HB"        # Keep-alive

    # Movement and actions
    PLAYER_MOVE = "PM"      # Player changes room
    PLAYER_ACTION = "PA"    # Player performs visible action

    # State synchronization
    ROOM_UPDATE = "RU"      # Room state change
    OBJECT_UPDATE = "OU"    # Object state change
    SYNC_REQUEST = "SY"     # Request full state sync
    SYNC_RESPONSE = "SR"    # Full state response

    # Communication
    CHAT = "CH"             # Chat message (SAY/SHOUT)
    TEAM_CHAT = "TC"        # Team-only chat


@dataclass
class GameMessage:
    """A multiplayer game message."""

    type: MessageType
    player_id: str          # Short player ID hash (6 chars)
    data: dict = field(default_factory=dict)
    sequence: int = 0       # For ordering/deduplication
    timestamp: float = field(default_factory=time.time)

    def to_compact(self) -> dict:
        """Convert to compact format for transmission."""
        return {
            "v": PROTOCOL_VERSION,
            "t": self.type.value,
            "p": self.player_id[:6],  # Truncate to 6 chars
            "s": self.sequence,
            "d": self.data,
        }

    @classmethod
    def from_compact(cls, data: dict) -> "GameMessage":
        """Parse from compact format."""
        msg_type = MessageType(data["t"])
        return cls(
            type=msg_type,
            player_id=data["p"],
            sequence=data.get("s", 0),
            data=data.get("d", {}),
            timestamp=time.time(),
        )


def encode_message(msg: GameMessage) -> str:
    """Encode message to JSON string for transmission."""
    return json.dumps(msg.to_compact(), separators=(",", ":"))


def decode_message(data: str | bytes) -> GameMessage:
    """Decode message from JSON string."""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return GameMessage.from_compact(json.loads(data))


# =============================================================================
# Room ID Mapping - Numeric IDs for bandwidth efficiency
# =============================================================================

ROOM_IDS: dict[str, int] = {
    # House area
    "whous": 1,   # West of House
    "lroom": 2,   # Living Room
    "kitch": 3,   # Kitchen
    "attic": 4,   # Attic
    "cella": 5,   # Cellar

    # Forest/Outside
    "fore1": 10,  # Forest 1
    "fore2": 11,  # Forest 2
    "fore3": 12,  # Forest 3
    "clear": 13,  # Clearing
    "path1": 14,  # Path
    "glade": 15,  # Glade
    "cany1": 16,  # Canyon
    "cany2": 17,  # Rocky Ledge

    # Underground - Main
    "mtrol": 20,  # Troll Room
    "studi": 21,  # Studio
    "mgall": 22,  # Gallery
    "maint": 23,  # Maintenance Room
    "dam": 24,    # Dam
    "damlo": 25,  # Dam Lobby
    "reser": 26,  # Reservoir
    "strea": 27,  # Stream
    "rroom": 28,  # Round Room
    "droom": 29,  # Dome Room
    "torch": 30,  # Torch Room

    # Maze
    "maze1": 40,  # Maze 1
    "maze2": 41,  # Maze 2
    "maze3": 42,  # Maze 3
    "maze4": 43,  # Maze 4
    "maze5": 44,  # Maze 5
    "mazed": 45,  # Dead End

    # Temple/Hades
    "templ": 50,  # Temple
    "egypt": 51,  # Egyptian Room
    "altar": 52,  # Altar
    "cave1": 53,  # Cave
    "entrc": 54,  # Entrance to Hades
    "llair": 55,  # Land of the Dead

    # Coal Mine
    "coal1": 60,  # Coal Mine
    "coal2": 61,  # Ladder Top
    "coal3": 62,  # Ladder Bottom
    "coal4": 63,  # Dead End Coal
    "mmach": 64,  # Machine Room
    "msafe": 65,  # Safe Room

    # Volcano
    "vlbot": 70,  # Volcano Bottom
    "vlair": 71,  # Volcano Ledge
    "vair1": 72,  # Wide Ledge
    "vair2": 73,  # Narrow Ledge

    # Bank
    "bkent": 80,  # Bank Entrance
    "bktel": 81,  # Teller
    "bkvau": 82,  # Vault
    "bksdp": 83,  # Small Room

    # Special
    "carou": 90,  # Carousel Room
    "lld2": 91,   # Loud Room
    "riddl": 92,  # Riddle Room
    "cyclo": 93,  # Cyclops Room
    "treas": 94,  # Treasure Room
    "mirro": 95,  # Mirror Room
}

# Reverse mapping for decoding
ROOM_NAMES: dict[int, str] = {v: k for k, v in ROOM_IDS.items()}


# =============================================================================
# Object ID Mapping
# =============================================================================

OBJECT_IDS: dict[str, int] = {
    # Light sources
    "lamp": 1,    # Brass lantern
    "candl": 2,   # Candles
    "match": 3,   # Matchbook
    "torch": 4,   # Torch

    # Weapons
    "sword": 10,  # Elvish sword
    "knife": 11,  # Nasty knife
    "axe": 12,    # Bloody axe
    "stilet": 13, # Stiletto

    # Treasures
    "egg": 20,    # Jeweled egg
    "jewel": 21,  # Jewels
    "coins": 22,  # Bag of coins
    "bar": 23,    # Platinum bar
    "diamo": 24,  # Diamond
    "trunk": 25,  # Trunk of jewels
    "troph": 26,  # Trophy case
    "paint": 27,  # Painting
    "chalc": 28,  # Chalice
    "sceptr": 29, # Sceptre
    "bauble": 30, # Crystal bauble
    "pot": 31,    # Pot of gold
    "emera": 32,  # Emerald
    "scarab": 33, # Scarab
    "figur": 34,  # Figurine
    "gold": 35,   # Gold coffin

    # Containers
    "mailb": 40,  # Mailbox
    "bag": 41,    # Brown sack
    "chest": 42,  # Treasure chest
    "case": 43,   # Violin case
    "boat": 44,   # Magic boat
    "basket": 45, # Basket
    "safe": 46,   # Safe
    "buoy": 47,   # Buoy

    # Tools/Items
    "leafl": 50,  # Leaflet
    "key": 51,    # Skeleton key
    "keys": 52,   # Set of keys
    "rope": 53,   # Rope
    "food": 54,   # Lunch
    "bottl": 55,  # Bottle
    "water": 56,  # Water
    "garli": 57,  # Garlic
    "coal": 58,   # Lump of coal
    "scrwdr": 59, # Screwdriver
    "wrench": 60, # Wrench
    "pump": 61,   # Air pump
    "label": 62,  # Label
    "guide": 63,  # Guidebook
    "news": 64,   # Newspaper
    "map": 65,    # Ancient map
    "stick": 66,  # Vitreous slag
    "brick": 67,  # Brick
    "skull": 68,  # Crystal skull
    "bell": 69,   # Brass bell
    "book": 70,   # Black book
    "candls": 71, # Pair of candles

    # Doors/Fixed
    "door": 80,   # Door
    "grate": 81,  # Grating
    "trapdoor": 82, # Trap door
    "rug": 83,    # Rug
    "pile": 84,   # Pile of leaves
    "butto": 85,  # Button

    # NPCs
    "thief": 90,  # Thief
    "troll": 91,  # Troll
    "cyclo": 92,  # Cyclops
    "ghost": 93,  # Spirit
    "vampi": 94,  # Vampire bat
}

# Reverse mapping
OBJECT_NAMES: dict[int, str] = {v: k for k, v in OBJECT_IDS.items()}


# =============================================================================
# Message Factory Functions
# =============================================================================

def create_join_message(player_id: str, name: str, room_id: str, seq: int = 0) -> GameMessage:
    """Create a player join message."""
    return GameMessage(
        type=MessageType.PLAYER_JOIN,
        player_id=player_id,
        sequence=seq,
        data={
            "n": name[:16],  # Name truncated to 16 chars
            "r": ROOM_IDS.get(room_id, 0),
        },
    )


def create_leave_message(player_id: str, seq: int = 0) -> GameMessage:
    """Create a player leave message."""
    return GameMessage(
        type=MessageType.PLAYER_LEAVE,
        player_id=player_id,
        sequence=seq,
    )


def create_move_message(
    player_id: str,
    from_room: str,
    to_room: str,
    seq: int = 0
) -> GameMessage:
    """Create a player move message."""
    return GameMessage(
        type=MessageType.PLAYER_MOVE,
        player_id=player_id,
        sequence=seq,
        data={
            "f": ROOM_IDS.get(from_room, 0),
            "r": ROOM_IDS.get(to_room, 0),
        },
    )


def create_action_message(
    player_id: str,
    verb: str,
    obj_id: str | None = None,
    room_id: str | None = None,
    seq: int = 0
) -> GameMessage:
    """Create a player action message."""
    data: dict[str, Any] = {"v": verb[:8]}  # Verb truncated
    if obj_id:
        data["o"] = OBJECT_IDS.get(obj_id, obj_id[:8])
    if room_id:
        data["r"] = ROOM_IDS.get(room_id, 0)

    return GameMessage(
        type=MessageType.PLAYER_ACTION,
        player_id=player_id,
        sequence=seq,
        data=data,
    )


def create_chat_message(
    player_id: str,
    message: str,
    room_id: str | None = None,
    is_team: bool = False,
    seq: int = 0
) -> GameMessage:
    """Create a chat message."""
    data: dict[str, Any] = {"m": message[:128]}  # Message truncated
    if room_id:
        data["r"] = ROOM_IDS.get(room_id, 0)

    return GameMessage(
        type=MessageType.TEAM_CHAT if is_team else MessageType.CHAT,
        player_id=player_id,
        sequence=seq,
        data=data,
    )


def create_heartbeat(player_id: str, room_id: str, seq: int = 0) -> GameMessage:
    """Create a heartbeat message."""
    return GameMessage(
        type=MessageType.HEARTBEAT,
        player_id=player_id,
        sequence=seq,
        data={"r": ROOM_IDS.get(room_id, 0)},
    )


def create_object_update(
    player_id: str,
    obj_id: str,
    location: str | None,
    holder: str | None = None,
    seq: int = 0
) -> GameMessage:
    """Create an object update message."""
    data: dict[str, Any] = {"o": OBJECT_IDS.get(obj_id, 0)}
    if location:
        data["l"] = ROOM_IDS.get(location, 0)
    if holder:
        data["h"] = holder[:6]  # Player ID who has it

    return GameMessage(
        type=MessageType.OBJECT_UPDATE,
        player_id=player_id,
        sequence=seq,
        data=data,
    )


def create_sync_request(player_id: str, room_id: str | None = None, seq: int = 0) -> GameMessage:
    """Create a sync request message."""
    data: dict[str, Any] = {}
    if room_id:
        data["r"] = ROOM_IDS.get(room_id, 0)

    return GameMessage(
        type=MessageType.SYNC_REQUEST,
        player_id=player_id,
        sequence=seq,
        data=data,
    )
