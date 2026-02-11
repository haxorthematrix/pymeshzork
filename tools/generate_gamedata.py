#!/usr/bin/env python3
"""
Generate C++ GameData.h from PyMeshZork JSON files.
This creates static room and object definitions for the T-Deck firmware.
"""

import json
import sys
from pathlib import Path

# Direction mapping
DIRECTIONS = {
    "north": "DIR_NORTH",
    "south": "DIR_SOUTH",
    "east": "DIR_EAST",
    "west": "DIR_WEST",
    "northeast": "DIR_NORTHEAST",
    "northwest": "DIR_NORTHWEST",
    "southeast": "DIR_SOUTHEAST",
    "southwest": "DIR_SOUTHWEST",
    "up": "DIR_UP",
    "down": "DIR_DOWN",
    "enter": "DIR_IN",
    "in": "DIR_IN",
    "out": "DIR_OUT",
    "exit": "DIR_OUT"
}

# Room flag mapping
ROOM_FLAGS = {
    "RLIGHT": "RFLAG_LIGHT",
    "RLAND": "RFLAG_LAND",
    "RWATER": "RFLAG_WATER",
    "RSACRED": "RFLAG_SACRED",
    "RMAZE": "RFLAG_MAZE",
    "RHOUSE": "RFLAG_LIGHT",  # Treat as lit
    "RAIR": "RFLAG_LIGHT"     # Treat as lit
}

# Object flag mapping
OBJ_FLAGS = {
    "VISIBT": "OFLAG_VISIBLE",
    "TAKEBT": "OFLAG_TAKEABLE",
    "CONTBT": "OFLAG_CONTAINER",
    "OPENBT": "OFLAG_OPEN",
    "TRANBT": "OFLAG_TRANSPARENT",
    "DOORBT": "OFLAG_DOOR",
    "READBT": "OFLAG_READABLE",
    "LITEBT": "OFLAG_LIGHTSOURCE",
    "WEAPBT": "OFLAG_WEAPON",
    "FOODBT": "OFLAG_FOOD",
    "DRNKBT": "OFLAG_DRINKABLE",
    "TIEBT": "OFLAG_TIEABLE",
    "VICTBT": "OFLAG_TREASURE",
    "ACTRBT": "OFLAG_ACTOR",
    "VILLBT": "OFLAG_VILLAIN",
    "FITEBT": "OFLAG_FIGHTER"
}


def escape_string(s):
    """Escape a string for C++."""
    if not s:
        return ""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def generate_room_exits(exits):
    """Generate exit array for a room."""
    exit_map = {}
    for exit_info in exits:
        direction = exit_info.get("direction", "").lower()
        if direction not in DIRECTIONS:
            continue

        dir_enum = DIRECTIONS[direction]
        dest = exit_info.get("destination", "")
        exit_type = exit_info.get("type", "normal")
        message = exit_info.get("message", "")

        blocked = exit_type in ("no_exit", "conditional")

        exit_map[dir_enum] = {
            "destination": dest if not blocked or exit_type == "conditional" else None,
            "blocked": blocked,
            "message": message
        }

    return exit_map


def generate_rooms(rooms_data):
    """Generate C++ room definitions."""
    lines = []
    room_ids = list(rooms_data.keys())

    lines.append(f"// Number of rooms: {len(room_ids)}")
    lines.append(f"#define ROOM_COUNT {len(room_ids)}")
    lines.append("")
    lines.append("// Room ID to index mapping")
    for i, rid in enumerate(room_ids):
        lines.append(f"#define ROOM_{rid.upper()} {i}")
    lines.append("")

    lines.append("// Room data")
    lines.append("static const Room ROOMS[ROOM_COUNT] = {")

    for rid, room in rooms_data.items():
        name = escape_string(room.get("name", rid))
        desc = escape_string(room.get("description_first", ""))
        short = escape_string(room.get("description_short", name))

        # Build flags
        flags = room.get("flags", [])
        flag_str = " | ".join(ROOM_FLAGS.get(f, "0") for f in flags if f in ROOM_FLAGS)
        if not flag_str:
            flag_str = "0"

        # Build exits
        exits = generate_room_exits(room.get("exits", []))

        lines.append(f"    // {name}")
        lines.append("    {")
        lines.append(f'        "{rid}",  // id')
        lines.append(f'        "{name}",  // name')
        lines.append(f'        "{desc}",  // description')
        lines.append(f'        "{short}",  // shortDesc')
        lines.append(f'        {flag_str},  // flags')
        lines.append("        {  // exits")

        for dir_name in ["DIR_NORTH", "DIR_SOUTH", "DIR_EAST", "DIR_WEST",
                         "DIR_NORTHEAST", "DIR_NORTHWEST", "DIR_SOUTHEAST", "DIR_SOUTHWEST",
                         "DIR_UP", "DIR_DOWN", "DIR_IN", "DIR_OUT"]:
            if dir_name in exits:
                ex = exits[dir_name]
                dest = f'"{ex["destination"]}"' if ex["destination"] else "nullptr"
                blocked = "true" if ex["blocked"] else "false"
                msg = f'"{escape_string(ex["message"])}"' if ex["message"] else "nullptr"
            else:
                dest = "nullptr"
                blocked = "false"
                msg = "nullptr"
            lines.append(f"            {{ {dir_name}, {dest}, {blocked}, {msg} }},")

        lines.append("        },")

        # Count valid exits
        num_exits = sum(1 for ex in exits.values() if ex["destination"])
        lines.append(f"        {num_exits}  // numExits")
        lines.append("    },")
        lines.append("")

    lines.append("};")
    return lines


def generate_objects(objects_data):
    """Generate C++ object definitions."""
    lines = []
    obj_ids = list(objects_data.keys())

    lines.append(f"// Number of objects: {len(obj_ids)}")
    lines.append(f"#define OBJECT_COUNT {len(obj_ids)}")
    lines.append("")
    lines.append("// Object ID to index mapping")
    for i, oid in enumerate(obj_ids):
        lines.append(f"#define OBJ_{oid.upper()} {i}")
    lines.append("")

    lines.append("// Object data")
    lines.append("static const GameObjectData OBJECTS[OBJECT_COUNT] = {")

    for oid, obj in objects_data.items():
        name = escape_string(obj.get("name", oid))
        desc = escape_string(obj.get("description", ""))
        examine = escape_string(obj.get("examine", ""))
        read_text = escape_string(obj.get("read_text", ""))

        # Location
        initial_room = obj.get("initial_room")
        initial_container = obj.get("initial_container")
        if initial_room:
            location = f'"{initial_room}"'
        elif initial_container:
            location = f'"{initial_container}"'
        else:
            location = 'nullptr'

        # Flags
        flags = obj.get("flags", [])
        flag_str = " | ".join(OBJ_FLAGS.get(f, "0") for f in flags if f in OBJ_FLAGS)
        if not flag_str:
            flag_str = "0"

        # Size and capacity
        size = obj.get("size", 0)
        capacity = obj.get("capacity", 0)
        value = obj.get("value", 0)

        lines.append(f"    // {name}")
        lines.append("    {")
        lines.append(f'        "{oid}",  // id')
        lines.append(f'        "{name}",  // name')
        lines.append(f'        "{desc}",  // description')
        lines.append(f'        "{examine}",  // examineText')
        lines.append(f'        "{read_text}",  // readText')
        lines.append(f'        {location},  // initialLocation')
        lines.append(f'        {flag_str},  // flags')
        lines.append(f'        {size},  // size')
        lines.append(f'        {capacity},  // capacity')
        lines.append(f'        {value}  // value')
        lines.append("    },")
        lines.append("")

    lines.append("};")
    return lines


def main():
    data_dir = Path(__file__).parent.parent / "data" / "worlds" / "classic_zork"

    # Load from world.json which has complete data
    with open(data_dir / "world.json") as f:
        world_data = json.load(f)

    rooms_data = world_data["rooms"]
    objects_data = world_data["objects"]

    # Generate header
    output = []
    output.append("#pragma once")
    output.append("")
    output.append("/**")
    output.append(" * GameData.h - Auto-generated from PyMeshZork JSON data")
    output.append(" *")
    output.append(f" * Rooms: {len(rooms_data)}")
    output.append(f" * Objects: {len(objects_data)}")
    output.append(" */")
    output.append("")
    output.append('#include "GameEngine.h"')
    output.append("")

    # Add extended object flags not in original GameEngine.h
    output.append("// Extended object flags")
    output.append("#define OFLAG_VISIBLE      0x0001")
    output.append("#define OFLAG_TRANSPARENT  0x0002")
    output.append("#define OFLAG_DOOR         0x0004")
    output.append("#define OFLAG_LIGHTSOURCE  0x0008")
    output.append("#define OFLAG_FOOD         0x0010")
    output.append("#define OFLAG_DRINKABLE    0x0020")
    output.append("#define OFLAG_TIEABLE      0x0040")
    output.append("#define OFLAG_TREASURE     0x0080")
    output.append("#define OFLAG_ACTOR        0x0100")
    output.append("#define OFLAG_VILLAIN      0x0200")
    output.append("#define OFLAG_FIGHTER      0x0400")
    output.append("")

    # Add object data structure
    output.append("// Object data structure for static initialization")
    output.append("struct GameObjectData {")
    output.append("    const char* id;")
    output.append("    const char* name;")
    output.append("    const char* description;")
    output.append("    const char* examineText;")
    output.append("    const char* readText;")
    output.append("    const char* initialLocation;")
    output.append("    uint16_t flags;")
    output.append("    uint8_t size;")
    output.append("    uint8_t capacity;")
    output.append("    uint8_t value;")
    output.append("};")
    output.append("")

    # Generate rooms
    output.extend(generate_rooms(rooms_data))
    output.append("")

    # Generate objects
    output.extend(generate_objects(objects_data))

    print("\n".join(output))


if __name__ == "__main__":
    main()
