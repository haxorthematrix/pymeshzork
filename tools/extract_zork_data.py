#!/usr/bin/env python3
"""Extract Zork game data from dtextc.dat binary file.

This script parses the original Zork binary data file and extracts:
- All rooms with descriptions and flags
- All exits/travel connections
- All objects with descriptions, flags, and properties
- All messages

The data is output as JSON compatible with PyMeshZork's world.json format.
"""

import json
from pathlib import Path


# Room indices from vars.h rindex_ (name -> number)
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

# Object indices from vars.h oindex_ (name -> number)
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

# Direction codes from vars.h xsrch_
DIRECTIONS = {
    1: "north", 2: "ne", 3: "east", 4: "se",
    5: "south", 6: "sw", 7: "west", 8: "nw",
    9: "up", 10: "down", 11: "land", 12: "launch",
    13: "enter", 14: "exit", 15: "travel",
}


class BinaryReader:
    """Read binary data from dtextc.dat."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def read_int(self) -> int:
        """Read a 2-byte big-endian signed integer."""
        if self.pos + 2 > len(self.data):
            return 0
        b1 = self.data[self.pos]
        b2 = self.data[self.pos + 1]
        self.pos += 2
        # Signed: if high byte > 127, it's negative
        if b1 > 127:
            return (b1 - 256) * 256 + b2
        return b1 * 256 + b2

    def read_ints(self, count: int) -> list:
        """Read multiple 2-byte integers."""
        return [self.read_int() for _ in range(count)]

    def read_partial_ints(self, max_count: int) -> dict:
        """Read sparse array stored as index,value pairs."""
        result = {}
        while True:
            if max_count < 255:
                idx = self.data[self.pos]
                self.pos += 1
                if idx == 255:  # Terminator
                    break
            else:
                idx = self.read_int()
                if idx == -1:  # Terminator
                    break
            value = self.read_int()
            result[idx] = value
        return result

    def read_flags(self, count: int) -> list:
        """Read 1-byte flags."""
        result = []
        for _ in range(count):
            result.append(self.data[self.pos])
            self.pos += 1
        return result


class ZorkExtractor:
    """Extract all data from dtextc.dat."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.data = filepath.read_bytes()
        self.reader = BinaryReader(self.data)

        # Parsed data
        self.version = (0, 0, '')
        self.mxscor = 0
        self.strbit = 0
        self.egmxsc = 0

        # Room data (indexed by room number)
        self.rooms = {}
        # Object data (indexed by object number)
        self.objects = {}
        # Exit/travel table
        self.exits = []
        # Messages (indexed by message number)
        self.messages = {}

    def parse(self):
        """Parse the entire binary file."""
        r = self.reader
        print(f"Parsing {self.filepath} ({len(self.data)} bytes)...")

        # Version: vmaj, vmin, vedit
        vmaj = r.read_int()
        vmin = r.read_int()
        vedit = r.read_int()
        self.version = (vmaj, vmin, chr(vedit) if 32 <= vedit <= 126 else '')
        print(f"Version: {vmaj}.{vmin}{self.version[2]}")

        # Scores
        self.mxscor = r.read_int()
        self.strbit = r.read_int()
        self.egmxsc = r.read_int()
        print(f"Max score: {self.mxscor}, Endgame max: {self.egmxsc}")

        # === ROOMS ===
        rlnt = r.read_int()
        print(f"Rooms: {rlnt}")

        rdesc1 = r.read_ints(rlnt)  # Long description msg indices
        rdesc2 = r.read_ints(rlnt)  # Short description msg indices
        rexit = r.read_ints(rlnt)   # Exit table indices
        ractio = r.read_partial_ints(rlnt)  # Action routines (sparse)
        rval = r.read_partial_ints(rlnt)    # Room values (sparse)
        rflag = r.read_ints(rlnt)   # Flags

        for i in range(rlnt):
            room_num = i + 1  # 1-indexed
            self.rooms[room_num] = {
                "desc1_idx": rdesc1[i],
                "desc2_idx": rdesc2[i],
                "exit_idx": rexit[i],
                "action": ractio.get(i, 0),
                "value": rval.get(i, 0),
                "flags": rflag[i],
            }

        # === EXITS ===
        xlnt = r.read_int()
        print(f"Exit entries: {xlnt}")
        self.exits = r.read_ints(xlnt)

        # === OBJECTS ===
        olnt = r.read_int()
        print(f"Objects: {olnt}")

        odesc1 = r.read_ints(olnt)  # Long description
        odesc2 = r.read_ints(olnt)  # Short/contents description
        odesco = r.read_partial_ints(olnt)  # Object name/description
        oactio = r.read_partial_ints(olnt)  # Action routines
        oflag1 = r.read_ints(olnt)  # Flags set 1
        oflag2 = r.read_partial_ints(olnt)  # Flags set 2
        ofval = r.read_partial_ints(olnt)   # Flag/score values
        otval = r.read_partial_ints(olnt)   # Trophy values
        osize = r.read_ints(olnt)   # Size
        ocapac = r.read_partial_ints(olnt)  # Capacity
        oroom = r.read_ints(olnt)   # Initial room
        oadv = r.read_partial_ints(olnt)    # Adventurer owner
        ocan = r.read_partial_ints(olnt)    # Container object
        oread = r.read_partial_ints(olnt)   # Read message index

        for i in range(olnt):
            obj_num = i + 1  # 1-indexed
            self.objects[obj_num] = {
                "desc1_idx": odesc1[i],
                "desc2_idx": odesc2[i],
                "desco_idx": odesco.get(i, 0),
                "action": oactio.get(i, 0),
                "flag1": oflag1[i],
                "flag2": oflag2.get(i, 0),
                "fval": ofval.get(i, 0),
                "tval": otval.get(i, 0),
                "size": osize[i],
                "capacity": ocapac.get(i, 0),
                "room": oroom[i],
                "adventurer": oadv.get(i, 0),
                "container": ocan.get(i, 0),
                "read_idx": oread.get(i, 0),
            }

        # === ROOM2 (multi-room objects) ===
        r2lnt = r.read_int()
        print(f"Room2 entries: {r2lnt}")
        if r2lnt > 0:
            r.read_ints(r2lnt)  # oroom2
            r.read_ints(r2lnt)  # rroom2

        # === CLOCK EVENTS ===
        clnt = r.read_int()
        print(f"Clock events: {clnt}")
        r.read_ints(clnt)  # ctick
        r.read_ints(clnt)  # cactio
        r.read_flags(clnt)  # cflag

        # === VILLAINS ===
        vlnt = r.read_int()
        print(f"Villains: {vlnt}")
        r.read_ints(vlnt)  # villns
        r.read_partial_ints(vlnt)  # vprob
        r.read_partial_ints(vlnt)  # vopps
        r.read_ints(vlnt)  # vbest
        r.read_ints(vlnt)  # vmelee

        # === ADVENTURERS ===
        alnt = r.read_int()
        print(f"Adventurers: {alnt}")
        r.read_ints(alnt)  # aroom
        r.read_partial_ints(alnt)  # ascore
        r.read_partial_ints(alnt)  # avehic
        r.read_ints(alnt)  # aobj
        r.read_ints(alnt)  # aactio
        r.read_ints(alnt)  # astren
        r.read_partial_ints(alnt)  # aflag

        # === MESSAGES ===
        mbase = r.read_int()
        mlnt = r.read_int()
        print(f"Messages: {mlnt}, base offset: {mbase}")
        msg_offsets = r.read_ints(mlnt)

        # Message text starts right after offsets
        msg_text_start = r.pos
        remaining = self.data[msg_text_start:]

        # Parse messages - offsets are relative to mbase (which is 0-based index)
        for i, offset in enumerate(msg_offsets):
            if offset == 0:
                self.messages[i + 1] = ""
                continue

            # Offset is 1-based position in the text area
            abs_pos = offset - 1
            if abs_pos >= len(remaining):
                self.messages[i + 1] = ""
                continue

            # Read null-terminated string
            end_pos = abs_pos
            while end_pos < len(remaining) and remaining[end_pos] != 0:
                end_pos += 1

            try:
                msg = remaining[abs_pos:end_pos].decode('ascii', errors='replace')
                self.messages[i + 1] = msg
            except Exception:
                self.messages[i + 1] = ""

        print(f"Parsed {len(self.messages)} messages")

    def get_message(self, idx: int) -> str:
        """Get message by index."""
        return self.messages.get(idx, "")

    def decode_room_flags(self, flags: int) -> list:
        """Decode room flags bitfield."""
        result = []
        for bit, name in ROOM_FLAGS.items():
            if flags & bit and name != "RSEEN":  # Skip runtime flag
                result.append(name)
        return result

    def decode_object_flags(self, flag1: int, flag2: int) -> list:
        """Decode object flags."""
        result = []
        for bit, name in OBJECT_FLAGS1.items():
            if flag1 & bit:
                result.append(name)
        for bit, name in OBJECT_FLAGS2.items():
            if flag2 & bit:
                result.append(name)
        return result

    def parse_room_exits(self, room_num: int) -> list:
        """Parse exits for a room from the travel table."""
        room_data = self.rooms.get(room_num)
        if not room_data:
            return []

        exit_idx = room_data["exit_idx"]
        if exit_idx == 0 or exit_idx > len(self.exits):
            return []

        exits = []
        idx = exit_idx - 1  # Convert to 0-indexed

        while idx < len(self.exits):
            entry = self.exits[idx]
            if entry == 0:
                break

            # Check for "last exit" flag (bit 15)
            is_last = (entry & 32768) != 0
            entry = entry & 32767  # Clear last flag

            # Parse exit entry
            # Bits 0-7: destination room
            # Bits 8-9: exit type (0=normal, 1=no-exit, 2=conditional, 3=door)
            # Bits 10-14: direction
            dest_room = entry & 255
            exit_type = (entry >> 8) & 3
            direction = (entry >> 10) & 31

            dir_name = DIRECTIONS.get(direction, f"dir{direction}")
            dest_id = INDEX_TO_ROOM.get(dest_room, f"room{dest_room}")

            exit_data = {
                "direction": dir_name,
                "destination": dest_id,
            }

            # Handle special exit types
            if exit_type == 1:  # No exit
                exit_data["type"] = "no_exit"
                idx += 1
                if idx < len(self.exits):
                    msg_idx = self.exits[idx]
                    msg = self.get_message(msg_idx)
                    if msg:
                        exit_data["message"] = msg
            elif exit_type == 2:  # Conditional
                exit_data["type"] = "conditional"
                idx += 1
                if idx < len(self.exits):
                    cond = self.exits[idx]
                    # Condition can be a message index or a flag
                    if cond > 0:
                        msg = self.get_message(cond)
                        if msg:
                            exit_data["message"] = msg
            elif exit_type == 3:  # Door
                exit_data["type"] = "door"
                idx += 1
                if idx < len(self.exits):
                    door_obj = self.exits[idx]
                    door_id = INDEX_TO_OBJECT.get(door_obj, f"obj{door_obj}")
                    exit_data["door_object"] = door_id

            exits.append(exit_data)

            if is_last:
                break
            idx += 1

        return exits

    def to_world_json(self) -> dict:
        """Convert extracted data to world.json format."""
        result = {
            "meta": {
                "id": "classic_zork",
                "name": "Zork I: The Great Underground Empire",
                "version": "1.0.0",
                "author": "Infocom (converted by PyMeshZork)",
                "description": "The complete classic text adventure game",
                "max_score": self.mxscor,
                "starting_room": "whous",
            },
            "rooms": {},
            "objects": {},
            "messages": {},
        }

        # Convert rooms
        for room_num, room_data in self.rooms.items():
            room_id = INDEX_TO_ROOM.get(room_num, f"room{room_num}")

            desc1 = self.get_message(room_data["desc1_idx"])
            desc2 = self.get_message(room_data["desc2_idx"])
            flags = self.decode_room_flags(room_data["flags"])

            # Skip rooms without descriptions (not real rooms)
            if not desc1 and not desc2:
                continue

            # Parse exits
            exits = self.parse_room_exits(room_num)

            # First line of desc1 is typically the room name
            lines = desc1.strip().split('\n') if desc1 else []
            name = lines[0] if lines else (desc2 or room_id)
            description = '\n'.join(lines[1:]).strip() if len(lines) > 1 else desc1

            room_json = {
                "name": name,
                "description_first": description,
                "description_short": desc2 or name,
                "flags": flags,
                "exits": exits,
            }

            if room_data["value"]:
                room_json["value"] = room_data["value"]

            result["rooms"][room_id] = room_json

        # Convert objects
        for obj_num, obj_data in self.objects.items():
            obj_id = INDEX_TO_OBJECT.get(obj_num, f"obj{obj_num}")

            desc1 = self.get_message(obj_data["desc1_idx"])
            desc2 = self.get_message(obj_data["desc2_idx"])
            desco = self.get_message(obj_data["desco_idx"])
            flags = self.decode_object_flags(obj_data["flag1"], obj_data["flag2"])

            # Skip objects without any description or visibility
            if not desc1 and not desco and "VISIBT" not in flags:
                continue

            obj_json = {
                "name": desco or desc1 or obj_id,
                "description": desc1 or "",
                "examine": desc2 or desc1 or "",
                "flags": flags,
            }

            # Initial location
            if obj_data["room"] > 0:
                room_id = INDEX_TO_ROOM.get(obj_data["room"])
                if room_id:
                    obj_json["initial_room"] = room_id
            if obj_data["container"] > 0:
                cont_id = INDEX_TO_OBJECT.get(obj_data["container"])
                if cont_id:
                    obj_json["initial_container"] = cont_id

            if obj_data["size"] > 0:
                obj_json["size"] = obj_data["size"]
            if obj_data["capacity"] > 0:
                obj_json["capacity"] = obj_data["capacity"]
            if obj_data["tval"] > 0:
                obj_json["value"] = obj_data["fval"]
                obj_json["tval"] = obj_data["tval"]
            elif obj_data["fval"] > 0:
                obj_json["value"] = obj_data["fval"]

            # Read text
            if obj_data["read_idx"] > 0:
                read_text = self.get_message(obj_data["read_idx"])
                if read_text:
                    obj_json["read_text"] = read_text

            result["objects"][obj_id] = obj_json

        return result


def main():
    """Main entry point."""
    # Find dtextc.dat
    script_dir = Path(__file__).parent.parent
    dat_file = script_dir / "dtextc.dat"

    if not dat_file.exists():
        print(f"Error: {dat_file} not found")
        return

    # Parse the binary file
    extractor = ZorkExtractor(dat_file)
    extractor.parse()

    # Convert to world JSON
    world = extractor.to_world_json()

    print(f"\nExtracted {len(world['rooms'])} rooms")
    print(f"Extracted {len(world['objects'])} objects")

    # Save extracted data
    output_dir = script_dir / "tools"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "extracted_zork.json"
    output_file.write_text(json.dumps(world, indent=2))
    print(f"\nWritten to {output_file}")

    # Print summary
    print("\n=== Rooms ===")
    for room_id in sorted(world["rooms"].keys()):
        room = world["rooms"][room_id]
        print(f"  {room_id}: {room['name'][:50]}")

    print("\n=== Objects ===")
    for obj_id in sorted(world["objects"].keys()):
        obj = world["objects"][obj_id]
        print(f"  {obj_id}: {obj['name'][:40]}")


if __name__ == "__main__":
    main()
