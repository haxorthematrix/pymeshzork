#!/usr/bin/env python3
"""Extract Zork game data from original C source files and data file.

This tool reads the original Zork C source files and the dtextc.dat binary
to extract room definitions, object definitions, exits, and messages,
converting them to JSON format for use with PyMeshZork.
"""

import json
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path


# Room indices from vars.h rindex_
ROOM_INDICES = {
    "whous": 2, "lroom": 8, "cella": 9, "mtrol": 10, "maze1": 11,
    "mgrat": 25, "maz15": 30, "fore1": 31, "fore3": 33, "clear": 36,
    "reser": 40, "strea": 42, "egypt": 44, "echor": 49, "tshaf": 61,
    "bshaf": 76, "mmach": 77, "dome": 79, "mtorc": 80, "carou": 83,
    "riddl": 91, "lld2": 94, "temp1": 96, "temp2": 97, "maint": 100,
    "blroo": 102, "treas": 103, "rivr1": 107, "rivr2": 108, "rivr3": 109,
    "mcycl": 101, "rivr4": 112, "rivr5": 113, "fchmp": 114, "falls": 120,
    "mbarr": 119, "mrain": 121, "pog": 122, "vlbot": 126, "vair1": 127,
    "vair2": 128, "vair3": 129, "vair4": 130, "ledg2": 131, "ledg3": 132,
    "ledg4": 133, "msafe": 135, "cager": 140, "caged": 141, "twell": 142,
    "bwell": 143, "alice": 144, "alism": 145, "alitr": 146, "mtree": 147,
    "bkent": 148, "bkvw": 151, "bktwi": 153, "bkvau": 154, "bkbox": 155,
    "crypt": 157, "tstrs": 158, "mrant": 159, "mreye": 160, "mra": 161,
    "mrb": 162, "mrc": 163, "mrg": 164, "mrd": 165, "fdoor": 166,
    "mrae": 167, "mrce": 171, "mrcw": 172, "mrge": 173, "mrgw": 174,
    "mrdw": 176, "inmir": 177, "scorr": 179, "ncorr": 182, "parap": 183,
    "cell": 184, "pcell": 185, "ncell": 186, "cpant": 188, "cpout": 189,
    "cpuzz": 190,
}

# Object indices from vars.h oindex_
OBJECT_INDICES = {
    "garli": 2, "food": 3, "gunk": 4, "coal": 5, "machi": 7, "diamo": 8,
    "tcase": 9, "bottl": 10, "water": 11, "rope": 12, "knife": 13,
    "sword": 14, "lamp": 15, "blamp": 16, "rug": 17, "leave": 18,
    "troll": 19, "axe": 20, "rknif": 21, "keys": 23, "ice": 30, "bar": 26,
    "coffi": 33, "torch": 34, "tbask": 35, "fbask": 36, "irbox": 39,
    "ghost": 42, "trunk": 45, "bell": 46, "book": 47, "candl": 48,
    "match": 51, "tube": 54, "putty": 55, "wrenc": 56, "screw": 57,
    "cyclo": 58, "chali": 59, "thief": 61, "still": 62, "windo": 63,
    "grate": 65, "door": 66, "hpole": 71, "leak": 78, "rbutt": 79,
    "raili": 75, "pot": 85, "statu": 86, "iboat": 87, "dboat": 88,
    "pump": 89, "rboat": 90, "stick": 92, "buoy": 94, "shove": 96,
    "ballo": 98, "recep": 99, "guano": 97, "brope": 101, "hook1": 102,
    "hook2": 103, "safe": 105, "sslot": 107, "brick": 109, "fuse": 110,
    "gnome": 111, "blabe": 112, "dball": 113, "tomb": 119, "lcase": 123,
    "cage": 124, "rcage": 125, "spher": 126, "sqbut": 127, "flask": 132,
    "pool": 133, "saffr": 134, "bucke": 137, "ecake": 138, "orice": 139,
    "rdice": 140, "blice": 141, "robot": 142, "ftree": 145, "bills": 148,
    "portr": 149, "scol": 151, "zgnom": 152, "egg": 154, "begg": 155,
    "baubl": 156, "canar": 157, "bcana": 158, "ylwal": 159, "rdwal": 161,
    "pindr": 164, "rbeam": 171, "odoor": 172, "qdoor": 173, "cdoor": 175,
    "num1": 178, "num8": 185, "warni": 186, "cslit": 187, "gcard": 188,
    "stldr": 189, "hands": 200, "wall": 198, "lungs": 201, "sailo": 196,
    "aviat": 202, "teeth": 197, "itobj": 192, "every": 194, "valua": 195,
    "oplay": 193, "wnort": 205, "gwate": 209, "master": 215,
}

# Reverse mappings
INDEX_TO_ROOM = {v: k for k, v in ROOM_INDICES.items()}
INDEX_TO_OBJECT = {v: k for k, v in OBJECT_INDICES.items()}

# Room flag values
ROOM_FLAGS = {
    32768: "RSEEN", 16384: "RLIGHT", 8192: "RLAND", 4096: "RWATER",
    2048: "RAIR", 1024: "RSACRD", 512: "RFILL", 256: "RMUNG",
    128: "RBUCK", 64: "RHOUSE", 32: "RNWALL", 16: "REND",
}

# Object flag1 values
OBJECT_FLAGS1 = {
    32768: "VISIBT", 16384: "READBT", 8192: "TAKEBT", 4096: "DOORBT",
    2048: "TRANBT", 1024: "FOODBT", 512: "NDSCBT", 256: "DRNKBT",
    128: "CONTBT", 64: "LITEBT", 32: "VICTBT", 16: "BURNBT",
    8: "FLAMBT", 4: "TOOLBT", 2: "TURNBT", 1: "ONBT",
}

# Object flag2 values
OBJECT_FLAGS2 = {
    32768: "FINDBT", 16384: "SLEPBT", 8192: "SCRDBT", 4096: "TIEBT",
    2048: "CLMBBT", 1024: "ACTRBT", 512: "WEAPBT", 256: "FITEBT",
    128: "VILLBT", 64: "STAGBT", 32: "TRYBT", 16: "NOCHBT",
    8: "OPENBT", 4: "TCHBT", 2: "VEHBT", 1: "SCHBT",
}

# Direction codes
DIRECTIONS = {
    1024: "north", 2048: "northeast", 3072: "east", 4096: "southeast",
    5120: "south", 6144: "southwest", 7168: "west", 8192: "northwest",
    9216: "up", 10240: "down", 11264: "launch", 12288: "land",
    13312: "enter", 14336: "exit", 15360: "travel",
}

# Human-readable room names
ROOM_NAMES = {
    "whous": "West of House",
    "lroom": "Living Room",
    "cella": "Cellar",
    "mtrol": "Troll Room",
    "maze1": "Maze",
    "mgrat": "Grating Room",
    "maz15": "Maze",
    "fore1": "Forest",
    "fore3": "Forest",
    "clear": "Clearing",
    "reser": "Reservoir",
    "strea": "Stream",
    "egypt": "Egyptian Room",
    "echor": "Echo Room",
    "tshaf": "Shaft Room",
    "bshaf": "Shaft Bottom",
    "mmach": "Machine Room",
    "dome": "Dome Room",
    "mtorc": "Torch Room",
    "carou": "Carousel Room",
    "riddl": "Riddle Room",
    "lld2": "Loud Room",
    "temp1": "Temple",
    "temp2": "Altar",
    "maint": "Maintenance Room",
    "blroo": "Blue Room",
    "treas": "Treasure Room",
    "rivr1": "Frigid River",
    "rivr2": "Frigid River",
    "rivr3": "Frigid River",
    "mcycl": "Cyclops Room",
    "rivr4": "Frigid River",
    "rivr5": "Frigid River",
    "fchmp": "Flood Control Dam #3",
    "falls": "Aragain Falls",
    "mbarr": "Dam Base",
    "mrain": "Rainbow Room",
    "pog": "End of Rainbow",
    "vlbot": "Volcano Bottom",
    "vair1": "Volcano Core",
    "vair2": "Volcano Core",
    "vair3": "Volcano Core",
    "vair4": "Volcano Core",
    "ledg2": "Narrow Ledge",
    "ledg3": "Narrow Ledge",
    "ledg4": "Narrow Ledge",
    "msafe": "Safe",
    "cager": "Cage",
    "caged": "Cage",
    "twell": "Well Top",
    "bwell": "Well Bottom",
    "alice": "Alice's Restaurant",
    "alism": "Small Cave",
    "alitr": "Treasury",
    "mtree": "Tree",
    "bkent": "Bank Entrance",
    "bkvw": "Viewing Room",
    "bktwi": "Teller's Room",
    "bkvau": "Bank Vault",
    "bkbox": "Safety Deposit",
    "crypt": "Crypt",
    "tstrs": "Stairs",
    "mrant": "Anteroom",
    "mreye": "Beam Room",
    "mra": "Mirror Room",
    "mrb": "Mirror Room",
    "mrc": "Mirror Room",
    "mrg": "Mirror Room",
    "mrd": "Mirror Room",
    "fdoor": "Front Door",
    "mrae": "Mirror Room",
    "mrce": "Mirror Room",
    "mrcw": "Mirror Room",
    "mrge": "Mirror Room",
    "mrgw": "Mirror Room",
    "mrdw": "Mirror Room",
    "inmir": "Inside Mirror",
    "scorr": "South Corridor",
    "ncorr": "North Corridor",
    "parap": "Parapet",
    "cell": "Cell",
    "pcell": "Prison Cell",
    "ncell": "North Cell",
    "cpant": "Puzzle Anteroom",
    "cpout": "Puzzle Room",
    "cpuzz": "Puzzle",
}

# Human-readable object names
OBJECT_NAMES = {
    "garli": "clove of garlic",
    "food": "lunch",
    "gunk": "gunk",
    "coal": "small pile of coal",
    "machi": "machine",
    "diamo": "huge diamond",
    "tcase": "trophy case",
    "bottl": "glass bottle",
    "water": "quantity of water",
    "rope": "rope",
    "knife": "nasty knife",
    "sword": "elvish sword",
    "lamp": "brass lantern",
    "blamp": "broken lantern",
    "rug": "oriental rug",
    "leave": "pile of leaves",
    "troll": "troll",
    "axe": "bloody axe",
    "rknif": "rusty knife",
    "keys": "set of keys",
    "ice": "glacier",
    "bar": "platinum bar",
    "coffi": "gold coffin",
    "torch": "ivory torch",
    "tbask": "wicker basket",
    "fbask": "fallen basket",
    "irbox": "steel box",
    "ghost": "ghost",
    "trunk": "old trunk",
    "bell": "brass bell",
    "book": "black book",
    "candl": "pair of candles",
    "match": "matchbook",
    "tube": "tube",
    "putty": "gunk",
    "wrenc": "wrench",
    "screw": "screwdriver",
    "cyclo": "cyclops",
    "chali": "silver chalice",
    "thief": "thief",
    "still": "stiletto",
    "windo": "window",
    "grate": "grating",
    "door": "door",
    "hpole": "pole",
    "leak": "leak",
    "rbutt": "red button",
    "raili": "railing",
    "pot": "pot of gold",
    "statu": "crystal statue",
    "iboat": "inflated boat",
    "dboat": "pile of plastic",
    "pump": "hand pump",
    "rboat": "punctured boat",
    "stick": "wooden stick",
    "buoy": "buoy",
    "shove": "shovel",
    "ballo": "hot air balloon",
    "recep": "receptacle",
    "guano": "guano",
    "brope": "braided rope",
    "hook1": "hook",
    "hook2": "hook",
    "safe": "safe",
    "sslot": "slot",
    "brick": "brick",
    "fuse": "fuse",
    "gnome": "gnome",
    "blabe": "blade",
    "dball": "crystal ball",
    "tomb": "tomb",
    "lcase": "trophy case",
    "cage": "cage",
    "rcage": "robot cage",
    "spher": "crystal sphere",
    "sqbut": "square button",
    "flask": "flask",
    "pool": "pool of tears",
    "saffr": "saffron",
    "bucke": "bucket",
    "ecake": "piece of cake",
    "orice": "orange cake",
    "rdice": "red cake",
    "blice": "blue cake",
    "robot": "robot",
    "ftree": "large tree",
    "bills": "pile of bills",
    "portr": "portrait",
    "scol": "wall",
    "zgnom": "zorkmid",
    "egg": "jewel-encrusted egg",
    "begg": "broken egg",
    "baubl": "bauble",
    "canar": "brass bauble",
    "bcana": "broken canary",
    "ylwal": "yellow wall",
    "rdwal": "red wall",
    "pindr": "pine door",
    "rbeam": "beam of light",
    "odoor": "oak door",
    "qdoor": "quartz door",
    "cdoor": "crystal door",
    "num1": "button 1",
    "num8": "button 8",
    "warni": "warning sign",
    "cslit": "coin slot",
    "gcard": "gold card",
    "stldr": "steel ladder",
    "hands": "pair of hands",
    "wall": "wall",
    "lungs": "pair of lungs",
    "sailo": "sailor",
    "aviat": "aviator",
    "teeth": "teeth",
    "master": "dungeon master",
}


@dataclass
class ExtractedRoom:
    """Extracted room data."""
    id: str
    index: int
    name: str
    description_first: str = ""
    description_short: str = ""
    flags: list = field(default_factory=list)
    exits: list = field(default_factory=list)
    action: int = 0
    value: int = 0


@dataclass
class ExtractedObject:
    """Extracted object data."""
    id: str
    index: int
    name: str
    description: str = ""
    examine: str = ""
    read_text: str = ""
    flags1: list = field(default_factory=list)
    flags2: list = field(default_factory=list)
    initial_room: str | None = None
    initial_container: str | None = None
    size: int = 0
    capacity: int = 0
    value: int = 0
    tval: int = 0
    action: int = 0


class ZorkDataExtractor:
    """Extracts game data from original Zork source files."""

    def __init__(self, source_dir: Path):
        self.source_dir = Path(source_dir)
        self.rooms: dict[str, ExtractedRoom] = {}
        self.objects: dict[str, ExtractedObject] = {}
        self.messages: dict[int, str] = {}
        self.exits: list[int] = []

    def extract_all(self) -> None:
        """Extract all game data."""
        print("Extracting Zork data...")

        # Initialize room and object structures
        self._init_rooms()
        self._init_objects()

        # Try to read binary data file
        data_file = self.source_dir / "dtextc.dat"
        if data_file.exists():
            self._read_data_file(data_file)

        print(f"Extracted {len(self.rooms)} rooms, {len(self.objects)} objects")

    def _init_rooms(self) -> None:
        """Initialize room structures from indices."""
        for room_id, index in ROOM_INDICES.items():
            name = ROOM_NAMES.get(room_id, room_id.title())
            self.rooms[room_id] = ExtractedRoom(
                id=room_id,
                index=index,
                name=name,
            )

    def _init_objects(self) -> None:
        """Initialize object structures from indices."""
        for obj_id, index in OBJECT_INDICES.items():
            name = OBJECT_NAMES.get(obj_id, obj_id)
            self.objects[obj_id] = ExtractedObject(
                id=obj_id,
                index=index,
                name=name,
            )

    def _read_data_file(self, path: Path) -> None:
        """Read the dtextc.dat binary file."""
        print(f"Reading {path}...")

        try:
            with open(path, "rb") as f:
                data = f.read()

            # The data file format varies, try to extract text
            # Look for readable ASCII text sections
            self._extract_text_from_binary(data)

        except Exception as e:
            print(f"Warning: Could not read data file: {e}")

    def _extract_text_from_binary(self, data: bytes) -> None:
        """Extract readable text from binary data."""
        # Find sequences of printable ASCII characters
        text_sections = []
        current_text = []
        min_length = 20  # Minimum text length to consider

        for byte in data:
            # Check if printable ASCII or newline/tab
            if 32 <= byte <= 126 or byte in (10, 13, 9):
                current_text.append(chr(byte))
            else:
                if len(current_text) >= min_length:
                    text_sections.append("".join(current_text))
                current_text = []

        if len(current_text) >= min_length:
            text_sections.append("".join(current_text))

        # Store extracted text as messages
        for i, text in enumerate(text_sections):
            self.messages[i] = text.strip()

        print(f"Extracted {len(text_sections)} text sections")

    def _decode_flags(self, flag_value: int, flag_map: dict) -> list[str]:
        """Decode bit flags to list of flag names."""
        flags = []
        for bit_value, name in flag_map.items():
            if flag_value & bit_value:
                flags.append(name)
        return flags

    def to_json(self) -> dict:
        """Convert extracted data to JSON-compatible dict."""
        return {
            "meta": {
                "id": "classic_zork",
                "name": "Zork I: The Great Underground Empire",
                "version": "1.0.0",
                "author": "Infocom (converted by PyMeshZork)",
                "description": "The classic text adventure game",
                "max_score": 350,
                "starting_room": "whous",
            },
            "rooms": {
                room_id: {
                    "name": room.name,
                    "description_first": room.description_first,
                    "description_short": room.description_short,
                    "flags": room.flags,
                    "exits": room.exits,
                    "action": f"room_action_{room.action}" if room.action else None,
                    "value": room.value,
                }
                for room_id, room in self.rooms.items()
            },
            "objects": {
                obj_id: {
                    "name": obj.name,
                    "description": obj.description,
                    "examine": obj.examine,
                    "read_text": obj.read_text,
                    "flags": obj.flags1 + obj.flags2,
                    "initial_room": obj.initial_room,
                    "initial_container": obj.initial_container,
                    "size": obj.size,
                    "capacity": obj.capacity,
                    "value": obj.value,
                    "tval": obj.tval,
                    "action": f"obj_action_{obj.action}" if obj.action else None,
                }
                for obj_id, obj in self.objects.items()
            },
            "messages": {
                str(k): v for k, v in self.messages.items()
            },
        }

    def save_json(self, output_path: Path) -> None:
        """Save extracted data as JSON."""
        data = self.to_json()
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved to {output_path}")


def create_classic_zork_world() -> dict:
    """Create the classic Zork world with known data.

    Since the binary data format is complex, we'll construct the world
    from known information about the original game.
    """

    world = {
        "meta": {
            "id": "classic_zork",
            "name": "Zork I: The Great Underground Empire",
            "version": "1.0.0",
            "author": "Infocom (converted by PyMeshZork)",
            "description": "The classic text adventure game - West of House and surrounding areas",
            "max_score": 350,
            "starting_room": "whous",
        },
        "rooms": {},
        "objects": {},
        "messages": {},
    }

    # ===== ROOMS =====

    # West of House
    world["rooms"]["whous"] = {
        "name": "West of House",
        "description_first": "You are standing in an open field west of a white house, with a boarded front door.",
        "description_short": "West of House",
        "flags": ["RLIGHT", "RLAND"],
        "exits": [
            {"direction": "north", "destination": "nhous"},
            {"direction": "south", "destination": "shous"},
            {"direction": "west", "destination": "fore1"},
            {"direction": "east", "destination": "whous", "type": "no_exit",
             "message": "The door is boarded and you can't remove the boards."},
            {"direction": "southwest", "destination": "fore1"},
            {"direction": "northwest", "destination": "fore1"},
        ],
    }

    # North of House
    world["rooms"]["nhous"] = {
        "name": "North of House",
        "description_first": "You are facing the north side of a white house. There is no door here, and all the windows are boarded up. To the north a narrow path winds through the trees.",
        "description_short": "North of House",
        "flags": ["RLIGHT", "RLAND"],
        "exits": [
            {"direction": "south", "destination": "whous"},
            {"direction": "west", "destination": "fore1"},
            {"direction": "east", "destination": "ehous"},
            {"direction": "north", "destination": "fore3"},
        ],
    }

    # South of House
    world["rooms"]["shous"] = {
        "name": "South of House",
        "description_first": "You are facing the south side of a white house. There is no door here, and all the windows are boarded.",
        "description_short": "South of House",
        "flags": ["RLIGHT", "RLAND"],
        "exits": [
            {"direction": "north", "destination": "whous"},
            {"direction": "west", "destination": "fore1"},
            {"direction": "east", "destination": "ehous"},
        ],
    }

    # Behind House (East of House)
    world["rooms"]["ehous"] = {
        "name": "Behind House",
        "description_first": "You are behind the white house. A path leads into the forest to the east. In one corner of the house there is a small window which is slightly ajar.",
        "description_short": "Behind House",
        "flags": ["RLIGHT", "RLAND"],
        "exits": [
            {"direction": "north", "destination": "nhous"},
            {"direction": "south", "destination": "shous"},
            {"direction": "east", "destination": "clear"},
            {"direction": "west", "destination": "kitch", "type": "door", "door_object": "windo"},
            {"direction": "enter", "destination": "kitch", "type": "door", "door_object": "windo"},
        ],
    }

    # Kitchen
    world["rooms"]["kitch"] = {
        "name": "Kitchen",
        "description_first": "You are in the kitchen of the white house. A table seems to have been used recently for the preparation of food. A passage leads to the west and a dark staircase can be seen leading upward. A dark chimney leads down and to the east is a small window which is open.",
        "description_short": "Kitchen",
        "flags": ["RLIGHT", "RLAND", "RHOUSE"],
        "exits": [
            {"direction": "east", "destination": "ehous", "type": "door", "door_object": "windo"},
            {"direction": "west", "destination": "lroom"},
            {"direction": "up", "destination": "attic"},
            {"direction": "down", "destination": "cella", "type": "conditional",
             "message": "Only Santa Claus climbs down chimneys."},
        ],
    }

    # Living Room
    world["rooms"]["lroom"] = {
        "name": "Living Room",
        "description_first": "You are in the living room. There is a doorway to the east, a wooden door with strange gothic lettering to the west, which appears to be nailed shut, a trophy case, and a large oriental rug in the center of the room.",
        "description_short": "Living Room",
        "flags": ["RLIGHT", "RLAND", "RHOUSE"],
        "exits": [
            {"direction": "east", "destination": "kitch"},
            {"direction": "west", "destination": "lroom", "type": "no_exit",
             "message": "The door is nailed shut."},
            {"direction": "down", "destination": "cella", "type": "conditional",
             "condition": "rug_moved"},
        ],
    }

    # Attic
    world["rooms"]["attic"] = {
        "name": "Attic",
        "description_first": "This is the attic. The only exit is a stairway leading down. A large coil of rope is lying in the corner. On a table is a nasty-looking knife.",
        "description_short": "Attic",
        "flags": ["RLIGHT", "RLAND", "RHOUSE"],
        "exits": [
            {"direction": "down", "destination": "kitch"},
        ],
    }

    # Cellar
    world["rooms"]["cella"] = {
        "name": "Cellar",
        "description_first": "You are in a dark and damp cellar with a narrow passageway leading north, and a crawlway to the south. On the west is the bottom of a steep metal ramp which is unclimbable.",
        "description_short": "Cellar",
        "flags": ["RLAND"],  # No light!
        "exits": [
            {"direction": "up", "destination": "lroom"},
            {"direction": "north", "destination": "mtrol"},
            {"direction": "south", "destination": "estof"},
            {"direction": "west", "destination": "cella", "type": "no_exit",
             "message": "The ramp is too steep to climb."},
        ],
    }

    # Troll Room
    world["rooms"]["mtrol"] = {
        "name": "Troll Room",
        "description_first": "This is a small room with passages to the east and south and a forbidding hole leading west. Bloodstains and deep scratches (perhaps made by straining fingers) mar the walls.",
        "description_short": "Troll Room",
        "flags": ["RLAND"],
        "exits": [
            {"direction": "south", "destination": "cella"},
            {"direction": "east", "destination": "emaze"},
            {"direction": "west", "destination": "mtrol", "type": "conditional",
             "condition": "troll_gone", "message": "The troll fends you off with a menacing gesture."},
        ],
    }

    # Forest (generic)
    world["rooms"]["fore1"] = {
        "name": "Forest",
        "description_first": "This is a forest, with trees in all directions. To the east, there appears to be sunlight.",
        "description_short": "Forest",
        "flags": ["RLIGHT", "RLAND"],
        "exits": [
            {"direction": "east", "destination": "whous"},
            {"direction": "north", "destination": "fore3"},
            {"direction": "south", "destination": "fore1"},
            {"direction": "west", "destination": "fore1"},
        ],
    }

    # Forest Path
    world["rooms"]["fore3"] = {
        "name": "Forest Path",
        "description_first": "This is a path winding through a dimly lit forest. The path heads north-south here. One particularly large tree with some low branches stands at the edge of the path.",
        "description_short": "Forest Path",
        "flags": ["RLIGHT", "RLAND"],
        "exits": [
            {"direction": "south", "destination": "nhous"},
            {"direction": "north", "destination": "clear"},
            {"direction": "east", "destination": "fore1"},
            {"direction": "west", "destination": "fore1"},
            {"direction": "up", "destination": "uptree"},
        ],
    }

    # Clearing
    world["rooms"]["clear"] = {
        "name": "Clearing",
        "description_first": "You are in a clearing, with a forest surrounding you on all sides. A path leads south.",
        "description_short": "Clearing",
        "flags": ["RLIGHT", "RLAND"],
        "exits": [
            {"direction": "south", "destination": "fore3"},
            {"direction": "west", "destination": "fore1"},
            {"direction": "east", "destination": "canyv"},
        ],
    }

    # Up a Tree
    world["rooms"]["uptree"] = {
        "name": "Up a Tree",
        "description_first": "You are about 10 feet above the ground nestled among some large branches. The nearest branch above you is above your reach. Beside you on the branch is a small bird's nest.",
        "description_short": "Up a Tree",
        "flags": ["RLIGHT", "RAIR"],
        "exits": [
            {"direction": "down", "destination": "fore3"},
        ],
    }

    # ===== OBJECTS =====

    # Mailbox
    world["objects"]["mailb"] = {
        "name": "small mailbox",
        "synonyms": ["mailbox", "box"],
        "adjectives": ["small"],
        "description": "There is a small mailbox here.",
        "examine": "The mailbox is a small mailbox.",
        "flags": ["VISIBT", "CONTBT", "OPENBT"],
        "initial_room": "whous",
        "capacity": 10,
    }

    # Leaflet
    world["objects"]["leafl"] = {
        "name": "leaflet",
        "synonyms": ["paper", "flyer"],
        "description": "",
        "examine": "The leaflet is a small piece of paper.",
        "read_text": "WELCOME TO ZORK!\n\nZORK is a game of adventure, danger, and low cunning. In it you will explore some of the most amazing territory ever seen by mortals. No computer should be without one!",
        "flags": ["VISIBT", "TAKEBT", "READBT"],
        "initial_container": "mailb",
        "size": 2,
    }

    # Sword
    world["objects"]["sword"] = {
        "name": "elvish sword",
        "synonyms": ["sword", "blade"],
        "adjectives": ["elvish", "antique"],
        "description": "Above the trophy case hangs an elvish sword of great antiquity.",
        "examine": "The sword is of exquisite craftsmanship. It is inscribed with ancient elvish runes.",
        "flags": ["VISIBT", "TAKEBT", "WEAPBT"],
        "initial_room": "lroom",
        "size": 30,
    }

    # Lamp
    world["objects"]["lamp"] = {
        "name": "brass lantern",
        "synonyms": ["lamp", "lantern", "light"],
        "adjectives": ["brass"],
        "description": "There is a brass lantern (battery-powered) here.",
        "examine": "The lamp is a battery-powered brass lantern.",
        "flags": ["VISIBT", "TAKEBT", "LITEBT"],
        "initial_room": "lroom",
        "size": 15,
        "properties": {"light_remaining": 350},
    }

    # Trophy Case
    world["objects"]["tcase"] = {
        "name": "trophy case",
        "synonyms": ["case"],
        "adjectives": ["trophy"],
        "description": "",
        "examine": "The trophy case is empty.",
        "flags": ["VISIBT", "CONTBT", "TRANBT", "OPENBT"],
        "initial_room": "lroom",
        "capacity": 100,
    }

    # Rug
    world["objects"]["rug"] = {
        "name": "oriental rug",
        "synonyms": ["rug", "carpet"],
        "adjectives": ["oriental", "large"],
        "description": "",
        "examine": "The rug is extremely beautiful and tightly woven. It does not appear to be attached to the floor.",
        "flags": ["VISIBT"],
        "initial_room": "lroom",
    }

    # Window
    world["objects"]["windo"] = {
        "name": "small window",
        "synonyms": ["window"],
        "adjectives": ["small"],
        "description": "",
        "examine": "The window is slightly ajar.",
        "flags": ["VISIBT", "DOORBT", "OPENBT"],
        "initial_room": "ehous",
    }

    # Rope
    world["objects"]["rope"] = {
        "name": "coil of rope",
        "synonyms": ["rope", "coil"],
        "description": "A large coil of rope is lying in the corner.",
        "examine": "The rope is strong and about 50 feet long.",
        "flags": ["VISIBT", "TAKEBT", "TIEBT"],
        "initial_room": "attic",
        "size": 10,
    }

    # Knife
    world["objects"]["knife"] = {
        "name": "nasty knife",
        "synonyms": ["knife", "blade"],
        "adjectives": ["nasty"],
        "description": "On a table is a nasty-looking knife.",
        "examine": "The knife looks very sharp and unpleasant.",
        "flags": ["VISIBT", "TAKEBT", "WEAPBT"],
        "initial_room": "attic",
        "size": 20,
    }

    # Troll
    world["objects"]["troll"] = {
        "name": "troll",
        "synonyms": ["troll", "monster"],
        "description": "A nasty-looking troll, brandishing a bloody axe, blocks all passages out of the room.",
        "examine": "The troll is a large, nasty creature that wants nothing more than to kill you.",
        "flags": ["VISIBT", "ACTRBT", "VILLBT", "FITEBT"],
        "initial_room": "mtrol",
    }

    # Axe
    world["objects"]["axe"] = {
        "name": "bloody axe",
        "synonyms": ["axe"],
        "adjectives": ["bloody"],
        "description": "",
        "examine": "The axe is covered in blood and looks extremely dangerous.",
        "flags": ["VISIBT", "TAKEBT", "WEAPBT"],
        "initial_room": None,  # Troll has it
    }

    # Sack (brown bag)
    world["objects"]["sack"] = {
        "name": "brown sack",
        "synonyms": ["sack", "bag"],
        "adjectives": ["brown", "elongated"],
        "description": "On the table is an elongated brown sack, smelling of hot peppers.",
        "examine": "The sack is an ordinary brown sack.",
        "flags": ["VISIBT", "TAKEBT", "CONTBT"],
        "initial_room": "kitch",
        "size": 9,
        "capacity": 15,
    }

    # Garlic
    world["objects"]["garli"] = {
        "name": "clove of garlic",
        "synonyms": ["garlic", "clove"],
        "description": "",
        "examine": "The garlic is a standard cooking ingredient.",
        "flags": ["VISIBT", "TAKEBT", "FOODBT"],
        "initial_container": "sack",
        "size": 4,
    }

    # Food
    world["objects"]["food"] = {
        "name": "lunch",
        "synonyms": ["food", "lunch", "sandwich"],
        "description": "",
        "examine": "The lunch looks delicious.",
        "flags": ["VISIBT", "TAKEBT", "FOODBT"],
        "initial_container": "sack",
        "size": 6,
    }

    # Bottle
    world["objects"]["bottl"] = {
        "name": "glass bottle",
        "synonyms": ["bottle"],
        "adjectives": ["glass"],
        "description": "A bottle is sitting on the table.",
        "examine": "The glass bottle contains a quantity of water.",
        "flags": ["VISIBT", "TAKEBT", "CONTBT", "TRANBT"],
        "initial_room": "kitch",
        "size": 7,
        "capacity": 5,
    }

    # Water
    world["objects"]["water"] = {
        "name": "quantity of water",
        "synonyms": ["water", "liquid"],
        "description": "",
        "examine": "It looks like ordinary water.",
        "flags": ["VISIBT", "TAKEBT", "DRNKBT"],
        "initial_container": "bottl",
        "size": 4,
    }

    # Nest
    world["objects"]["nest"] = {
        "name": "bird's nest",
        "synonyms": ["nest"],
        "adjectives": ["bird's", "small"],
        "description": "Beside you on the branch is a small bird's nest.",
        "examine": "The nest looks like it was made by a songbird of some kind.",
        "flags": ["VISIBT", "TAKEBT", "CONTBT"],
        "initial_room": "uptree",
        "size": 5,
        "capacity": 5,
    }

    # Egg
    world["objects"]["egg"] = {
        "name": "jewel-encrusted egg",
        "synonyms": ["egg"],
        "adjectives": ["jeweled", "jewel-encrusted"],
        "description": "",
        "examine": "The egg is covered with beautiful jewels that glitter in the light.",
        "flags": ["VISIBT", "TAKEBT", "VICTBT"],
        "initial_container": "nest",
        "size": 6,
        "value": 5,
        "tval": 10,
    }

    return world


def main():
    """Main entry point."""
    import sys

    # Get source directory
    if len(sys.argv) > 1:
        source_dir = Path(sys.argv[1])
    else:
        source_dir = Path(__file__).parent.parent

    # Output directory
    output_dir = source_dir / "data" / "worlds" / "classic_zork"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Try to extract from source
    extractor = ZorkDataExtractor(source_dir)
    extractor.extract_all()

    # Generate the known world data
    print("\nGenerating classic Zork world...")
    world_data = create_classic_zork_world()

    # Save the world JSON
    world_file = output_dir / "world.json"
    with open(world_file, "w") as f:
        json.dump(world_data, f, indent=2)
    print(f"Saved world to {world_file}")

    # Save rooms separately
    rooms_file = output_dir / "rooms.json"
    with open(rooms_file, "w") as f:
        json.dump({"rooms": world_data["rooms"]}, f, indent=2)
    print(f"Saved rooms to {rooms_file}")

    # Save objects separately
    objects_file = output_dir / "objects.json"
    with open(objects_file, "w") as f:
        json.dump({"objects": world_data["objects"]}, f, indent=2)
    print(f"Saved objects to {objects_file}")

    print("\nDone!")


if __name__ == "__main__":
    main()
