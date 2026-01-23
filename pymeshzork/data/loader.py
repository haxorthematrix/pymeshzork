"""Data loader for PyMeshZork - loads world from JSON files."""

import json
from pathlib import Path
from typing import Any

from pymeshzork.engine.models import (
    Direction,
    Exit,
    ExitType,
    Object,
    ObjectFlag1,
    ObjectFlag2,
    Room,
    RoomFlag,
)
from pymeshzork.engine.world import World


class WorldLoader:
    """Loads game world from JSON files."""

    # Map flag names to enum values
    ROOM_FLAGS = {
        "REND": RoomFlag.REND,
        "RNWALL": RoomFlag.RNWALL,
        "RHOUSE": RoomFlag.RHOUSE,
        "RBUCK": RoomFlag.RBUCK,
        "RMUNG": RoomFlag.RMUNG,
        "RFILL": RoomFlag.RFILL,
        "RSACRD": RoomFlag.RSACRD,
        "RAIR": RoomFlag.RAIR,
        "RWATER": RoomFlag.RWATER,
        "RLAND": RoomFlag.RLAND,
        "RLIGHT": RoomFlag.RLIGHT,
        "RSEEN": RoomFlag.RSEEN,
    }

    OBJECT_FLAGS1 = {
        "ONBT": ObjectFlag1.ONBT,
        "TURNBT": ObjectFlag1.TURNBT,
        "TOOLBT": ObjectFlag1.TOOLBT,
        "FLAMBT": ObjectFlag1.FLAMBT,
        "BURNBT": ObjectFlag1.BURNBT,
        "VICTBT": ObjectFlag1.VICTBT,
        "LITEBT": ObjectFlag1.LITEBT,
        "CONTBT": ObjectFlag1.CONTBT,
        "DRNKBT": ObjectFlag1.DRNKBT,
        "NDSCBT": ObjectFlag1.NDSCBT,
        "FOODBT": ObjectFlag1.FOODBT,
        "TRANBT": ObjectFlag1.TRANBT,
        "DOORBT": ObjectFlag1.DOORBT,
        "TAKEBT": ObjectFlag1.TAKEBT,
        "READBT": ObjectFlag1.READBT,
        "VISIBT": ObjectFlag1.VISIBT,
    }

    OBJECT_FLAGS2 = {
        "SCHBT": ObjectFlag2.SCHBT,
        "VEHBT": ObjectFlag2.VEHBT,
        "TCHBT": ObjectFlag2.TCHBT,
        "OPENBT": ObjectFlag2.OPENBT,
        "NOCHBT": ObjectFlag2.NOCHBT,
        "TRYBT": ObjectFlag2.TRYBT,
        "STAGBT": ObjectFlag2.STAGBT,
        "VILLBT": ObjectFlag2.VILLBT,
        "FITEBT": ObjectFlag2.FITEBT,
        "WEAPBT": ObjectFlag2.WEAPBT,
        "ACTRBT": ObjectFlag2.ACTRBT,
        "CLMBBT": ObjectFlag2.CLMBBT,
        "TIEBT": ObjectFlag2.TIEBT,
        "SCRDBT": ObjectFlag2.SCRDBT,
        "SLEPBT": ObjectFlag2.SLEPBT,
        "FINDBT": ObjectFlag2.FINDBT,
    }

    DIRECTIONS = {
        "n": Direction.NORTH,
        "north": Direction.NORTH,
        "s": Direction.SOUTH,
        "south": Direction.SOUTH,
        "e": Direction.EAST,
        "east": Direction.EAST,
        "w": Direction.WEST,
        "west": Direction.WEST,
        "ne": Direction.NE,
        "northeast": Direction.NE,
        "nw": Direction.NW,
        "northwest": Direction.NW,
        "se": Direction.SE,
        "southeast": Direction.SE,
        "sw": Direction.SW,
        "southwest": Direction.SW,
        "u": Direction.UP,
        "up": Direction.UP,
        "d": Direction.DOWN,
        "down": Direction.DOWN,
        "enter": Direction.ENTER,
        "in": Direction.ENTER,
        "exit": Direction.EXIT,
        "out": Direction.EXIT,
    }

    EXIT_TYPES = {
        "normal": ExitType.NORMAL,
        "no_exit": ExitType.NO_EXIT,
        "conditional": ExitType.CONDITIONAL,
        "door": ExitType.DOOR,
    }

    def load_world(self, path: Path) -> World:
        """Load a world from a JSON file or directory."""
        path = Path(path)

        if path.is_dir():
            return self._load_world_dir(path)
        else:
            return self._load_world_file(path)

    def _load_world_file(self, path: Path) -> World:
        """Load world from a single JSON file."""
        with open(path) as f:
            data = json.load(f)
        return self._parse_world(data)

    def _load_world_dir(self, path: Path) -> World:
        """Load world from a directory with multiple JSON files."""
        # Prefer combined world.json if it exists (most complete)
        world_file = path / "world.json"
        if world_file.exists():
            return self._load_world_file(world_file)

        # Fall back to separate files
        world = World()

        # Load rooms
        rooms_file = path / "rooms.json"
        if rooms_file.exists():
            with open(rooms_file) as f:
                rooms_data = json.load(f)
            for room_id, room_data in rooms_data.get("rooms", {}).items():
                room = self._parse_room(room_id, room_data)
                world.add_room(room)

        # Load objects
        objects_file = path / "objects.json"
        if objects_file.exists():
            with open(objects_file) as f:
                objects_data = json.load(f)
            for obj_id, obj_data in objects_data.get("objects", {}).items():
                obj = self._parse_object(obj_id, obj_data)
                world.add_object(obj)

        # Load messages
        messages_file = path / "messages.json"
        if messages_file.exists():
            with open(messages_file) as f:
                messages_data = json.load(f)
            world.messages = messages_data.get("messages", {})

        return world

    def _parse_world(self, data: dict) -> World:
        """Parse world from combined JSON data."""
        world = World()

        # Parse rooms
        for room_id, room_data in data.get("rooms", {}).items():
            room = self._parse_room(room_id, room_data)
            world.add_room(room)

        # Parse objects
        for obj_id, obj_data in data.get("objects", {}).items():
            obj = self._parse_object(obj_id, obj_data)
            world.add_object(obj)

        # Parse messages
        world.messages = data.get("messages", {})

        return world

    def _parse_room(self, room_id: str, data: dict) -> Room:
        """Parse a room from JSON data."""
        # Parse flags
        flags = RoomFlag.NONE
        for flag_name in data.get("flags", []):
            if flag_name in self.ROOM_FLAGS:
                flags |= self.ROOM_FLAGS[flag_name]

        # Parse exits
        exits = []
        for exit_data in data.get("exits", []):
            exits.append(self._parse_exit(exit_data))

        # Also parse simple direction-based exits
        for dir_name, dest in data.get("simple_exits", {}).items():
            if dir_name in self.DIRECTIONS:
                exits.append(Exit(
                    direction=self.DIRECTIONS[dir_name],
                    destination_id=dest,
                ))

        return Room(
            id=room_id,
            name=data.get("name", room_id),
            description_first=data.get("description_first", ""),
            description_short=data.get("description_short", ""),
            flags=flags,
            exits=exits,
            action=data.get("action"),
            value=data.get("value", 0),
        )

    def _parse_exit(self, data: dict) -> Exit:
        """Parse an exit from JSON data."""
        direction_str = data.get("direction", "north").lower()
        direction = self.DIRECTIONS.get(direction_str, Direction.NORTH)

        exit_type_str = data.get("type", "normal").lower()
        exit_type = self.EXIT_TYPES.get(exit_type_str, ExitType.NORMAL)

        return Exit(
            direction=direction,
            destination_id=data.get("destination", ""),
            exit_type=exit_type,
            door_id=data.get("door_object"),
            condition=data.get("condition"),
            message=data.get("message"),
        )

    def _parse_object(self, obj_id: str, data: dict) -> Object:
        """Parse an object from JSON data."""
        # Parse flags1
        flags1 = ObjectFlag1.NONE
        for flag_name in data.get("flags1", []):
            if flag_name in self.OBJECT_FLAGS1:
                flags1 |= self.OBJECT_FLAGS1[flag_name]
        # Also check combined "flags" field
        for flag_name in data.get("flags", []):
            if flag_name in self.OBJECT_FLAGS1:
                flags1 |= self.OBJECT_FLAGS1[flag_name]

        # Parse flags2
        flags2 = ObjectFlag2.NONE
        for flag_name in data.get("flags2", []):
            if flag_name in self.OBJECT_FLAGS2:
                flags2 |= self.OBJECT_FLAGS2[flag_name]
        for flag_name in data.get("flags", []):
            if flag_name in self.OBJECT_FLAGS2:
                flags2 |= self.OBJECT_FLAGS2[flag_name]

        return Object(
            id=obj_id,
            name=data.get("name", obj_id),
            adjectives=data.get("adjectives", []),
            synonyms=data.get("synonyms", []),
            description=data.get("description", ""),
            examine=data.get("examine", ""),
            read_text=data.get("read_text", ""),
            flags1=flags1,
            flags2=flags2,
            initial_room=data.get("initial_room"),
            size=data.get("size", 0),
            capacity=data.get("capacity", 0),
            value=data.get("value", 0),
            tval=data.get("tval", 0),
            action=data.get("action"),
            properties=data.get("properties", {}),
        )

    def save_world(self, world: World, path: Path) -> None:
        """Save a world to JSON file(s)."""
        path = Path(path)

        if path.suffix == ".json":
            self._save_world_file(world, path)
        else:
            self._save_world_dir(world, path)

    def _save_world_file(self, world: World, path: Path) -> None:
        """Save world to a single JSON file."""
        data = {
            "rooms": {},
            "objects": {},
            "messages": world.messages,
        }

        for room_id, room in world.rooms.items():
            data["rooms"][room_id] = self._serialize_room(room)

        for obj_id, obj in world.objects.items():
            data["objects"][obj_id] = self._serialize_object(obj)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _save_world_dir(self, world: World, path: Path) -> None:
        """Save world to a directory with multiple JSON files."""
        path.mkdir(parents=True, exist_ok=True)

        # Save rooms
        rooms_data = {"rooms": {}}
        for room_id, room in world.rooms.items():
            rooms_data["rooms"][room_id] = self._serialize_room(room)

        with open(path / "rooms.json", "w") as f:
            json.dump(rooms_data, f, indent=2)

        # Save objects
        objects_data = {"objects": {}}
        for obj_id, obj in world.objects.items():
            objects_data["objects"][obj_id] = self._serialize_object(obj)

        with open(path / "objects.json", "w") as f:
            json.dump(objects_data, f, indent=2)

        # Save messages
        messages_data = {"messages": world.messages}
        with open(path / "messages.json", "w") as f:
            json.dump(messages_data, f, indent=2)

    def _serialize_room(self, room: Room) -> dict:
        """Serialize a room to JSON-compatible dict."""
        # Convert flags to names
        flags = []
        for name, value in self.ROOM_FLAGS.items():
            if room.flags & value:
                flags.append(name)

        # Serialize exits
        exits = []
        for exit in room.exits:
            exits.append(self._serialize_exit(exit))

        return {
            "name": room.name,
            "description_first": room.description_first,
            "description_short": room.description_short,
            "flags": flags,
            "exits": exits,
            "action": room.action,
            "value": room.value,
        }

    def _serialize_exit(self, exit: Exit) -> dict:
        """Serialize an exit to JSON-compatible dict."""
        # Find direction name
        dir_name = "north"
        for name, value in self.DIRECTIONS.items():
            if exit.direction == value and len(name) > 1:
                dir_name = name
                break

        # Find exit type name
        type_name = "normal"
        for name, value in self.EXIT_TYPES.items():
            if exit.exit_type == value:
                type_name = name
                break

        result: dict[str, Any] = {
            "direction": dir_name,
            "destination": exit.destination_id,
            "type": type_name,
        }

        if exit.door_id:
            result["door_object"] = exit.door_id
        if exit.condition:
            result["condition"] = exit.condition
        if exit.message:
            result["message"] = exit.message

        return result

    def _serialize_object(self, obj: Object) -> dict:
        """Serialize an object to JSON-compatible dict."""
        # Convert flags to names
        flags: list[str] = []
        for name, value in self.OBJECT_FLAGS1.items():
            if obj.flags1 & value:
                flags.append(name)
        for name, value in self.OBJECT_FLAGS2.items():
            if obj.flags2 & value:
                flags.append(name)

        result = {
            "name": obj.name,
            "adjectives": obj.adjectives,
            "synonyms": obj.synonyms,
            "description": obj.description,
            "examine": obj.examine,
            "read_text": obj.read_text,
            "flags": flags,
            "initial_room": obj.initial_room,
            "size": obj.size,
            "capacity": obj.capacity,
            "value": obj.value,
            "tval": obj.tval,
            "action": obj.action,
            "properties": obj.properties,
        }

        return result
