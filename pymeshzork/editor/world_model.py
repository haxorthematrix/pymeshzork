"""Editor world model - handles world data with visual layout information."""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EditorRoom:
    """Room with editor metadata (position, etc.)."""

    id: str
    name: str
    description_first: str = ""
    description_short: str = ""
    flags: list[str] = field(default_factory=lambda: ["RLIGHT", "RLAND"])
    exits: list[dict] = field(default_factory=list)
    action: Optional[str] = None
    value: int = 0

    # Editor-specific
    x: float = 0.0
    y: float = 0.0


@dataclass
class EditorObject:
    """Object with editor metadata."""

    id: str
    name: str
    synonyms: list[str] = field(default_factory=list)
    adjectives: list[str] = field(default_factory=list)
    description: str = ""
    examine: str = ""
    read_text: str = ""
    flags: list[str] = field(default_factory=lambda: ["VISIBT"])
    initial_room: Optional[str] = None
    initial_container: Optional[str] = None
    size: int = 0
    capacity: int = 0
    value: int = 0
    tval: int = 0
    action: Optional[str] = None
    properties: dict = field(default_factory=dict)


@dataclass
class EditorWorld:
    """World data with editor metadata."""

    meta: dict = field(default_factory=dict)
    rooms: dict[str, EditorRoom] = field(default_factory=dict)
    objects: dict[str, EditorObject] = field(default_factory=dict)
    messages: dict[str, str] = field(default_factory=dict)

    # Editor metadata
    editor_meta: dict = field(default_factory=dict)

    @classmethod
    def create_new(cls) -> "EditorWorld":
        """Create a new empty world with a starting room."""
        world = cls()
        world.meta = {
            "id": "new_world",
            "name": "New World",
            "version": "1.0.0",
            "author": "",
            "description": "A new adventure world",
            "max_score": 0,
            "starting_room": "start",
        }

        # Create starting room
        start_room = EditorRoom(
            id="start",
            name="Starting Room",
            description_first="You are in the starting room of a new adventure.",
            description_short="Starting Room",
            x=400.0,
            y=300.0,
        )
        world.rooms["start"] = start_room

        return world

    @classmethod
    def load_from_file(cls, path: Path) -> "EditorWorld":
        """Load a world from a JSON file."""
        with open(path) as f:
            data = json.load(f)

        world = cls()

        # Load meta
        world.meta = data.get("meta", {})

        # Load editor metadata (positions, etc.)
        world.editor_meta = data.get("_editor", {})
        room_positions = world.editor_meta.get("room_positions", {})

        # Load rooms
        for room_id, room_data in data.get("rooms", {}).items():
            pos = room_positions.get(room_id, {})
            room = EditorRoom(
                id=room_id,
                name=room_data.get("name", room_id),
                description_first=room_data.get("description_first", ""),
                description_short=room_data.get("description_short", ""),
                flags=room_data.get("flags", ["RLIGHT", "RLAND"]),
                exits=room_data.get("exits", []),
                action=room_data.get("action"),
                value=room_data.get("value", 0),
                x=pos.get("x", 100.0 + len(world.rooms) * 150),
                y=pos.get("y", 100.0 + (len(world.rooms) % 5) * 120),
            )
            world.rooms[room_id] = room

        # Load objects
        for obj_id, obj_data in data.get("objects", {}).items():
            obj = EditorObject(
                id=obj_id,
                name=obj_data.get("name", obj_id),
                synonyms=obj_data.get("synonyms", []),
                adjectives=obj_data.get("adjectives", []),
                description=obj_data.get("description", ""),
                examine=obj_data.get("examine", ""),
                read_text=obj_data.get("read_text", ""),
                flags=obj_data.get("flags", ["VISIBT"]),
                initial_room=obj_data.get("initial_room"),
                initial_container=obj_data.get("initial_container"),
                size=obj_data.get("size", 0),
                capacity=obj_data.get("capacity", 0),
                value=obj_data.get("value", 0),
                tval=obj_data.get("tval", 0),
                action=obj_data.get("action"),
                properties=obj_data.get("properties", {}),
            )
            world.objects[obj_id] = obj

        # Load messages
        world.messages = data.get("messages", {})

        return world

    def save_to_file(self, path: Path) -> None:
        """Save the world to a JSON file."""
        # Build room positions for editor metadata
        room_positions = {}
        for room_id, room in self.rooms.items():
            room_positions[room_id] = {"x": room.x, "y": room.y}

        # Build output data
        data = {
            "meta": self.meta,
            "rooms": {},
            "objects": {},
            "messages": self.messages,
            "_editor": {"room_positions": room_positions},
        }

        # Serialize rooms
        for room_id, room in self.rooms.items():
            data["rooms"][room_id] = {
                "name": room.name,
                "description_first": room.description_first,
                "description_short": room.description_short,
                "flags": room.flags,
                "exits": room.exits,
            }
            if room.action:
                data["rooms"][room_id]["action"] = room.action
            if room.value:
                data["rooms"][room_id]["value"] = room.value

        # Serialize objects
        for obj_id, obj in self.objects.items():
            obj_data = {
                "name": obj.name,
                "synonyms": obj.synonyms,
                "adjectives": obj.adjectives,
                "description": obj.description,
                "examine": obj.examine,
                "flags": obj.flags,
            }
            if obj.read_text:
                obj_data["read_text"] = obj.read_text
            if obj.initial_room:
                obj_data["initial_room"] = obj.initial_room
            if obj.initial_container:
                obj_data["initial_container"] = obj.initial_container
            if obj.size:
                obj_data["size"] = obj.size
            if obj.capacity:
                obj_data["capacity"] = obj.capacity
            if obj.value:
                obj_data["value"] = obj.value
            if obj.tval:
                obj_data["tval"] = obj.tval
            if obj.action:
                obj_data["action"] = obj.action
            if obj.properties:
                obj_data["properties"] = obj.properties

            data["objects"][obj_id] = obj_data

        # Write file
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_room(self, room_id: str) -> Optional[EditorRoom]:
        """Get a room by ID."""
        return self.rooms.get(room_id)

    def get_object(self, obj_id: str) -> Optional[EditorObject]:
        """Get an object by ID."""
        return self.objects.get(obj_id)

    def add_room(self, room_id: Optional[str] = None) -> EditorRoom:
        """Add a new room."""
        if room_id is None:
            room_id = f"room_{uuid.uuid4().hex[:8]}"

        # Position new room offset from existing rooms
        x = 100.0 + (len(self.rooms) % 6) * 150
        y = 100.0 + (len(self.rooms) // 6) * 120

        room = EditorRoom(
            id=room_id,
            name=f"New Room {len(self.rooms) + 1}",
            description_first="A new room.",
            description_short="New Room",
            x=x,
            y=y,
        )
        self.rooms[room_id] = room
        return room

    def remove_room(self, room_id: str) -> None:
        """Remove a room and all connections to it."""
        if room_id in self.rooms:
            del self.rooms[room_id]

            # Remove exits pointing to this room
            for room in self.rooms.values():
                room.exits = [e for e in room.exits if e.get("destination") != room_id]

            # Update objects that were in this room
            for obj in self.objects.values():
                if obj.initial_room == room_id:
                    obj.initial_room = None

    def add_object(self, obj_id: Optional[str] = None) -> EditorObject:
        """Add a new object."""
        if obj_id is None:
            obj_id = f"obj_{uuid.uuid4().hex[:8]}"

        obj = EditorObject(
            id=obj_id,
            name=f"New Object {len(self.objects) + 1}",
        )
        self.objects[obj_id] = obj
        return obj

    def remove_object(self, obj_id: str) -> None:
        """Remove an object."""
        if obj_id in self.objects:
            del self.objects[obj_id]

            # Update objects that were in this container
            for obj in self.objects.values():
                if obj.initial_container == obj_id:
                    obj.initial_container = None

    def set_room_position(self, room_id: str, x: float, y: float) -> None:
        """Set the visual position of a room."""
        if room_id in self.rooms:
            self.rooms[room_id].x = x
            self.rooms[room_id].y = y

    def add_exit(
        self,
        from_room: str,
        to_room: str,
        direction: str,
        exit_type: str = "normal",
        bidirectional: bool = True,
    ) -> None:
        """Add an exit between rooms."""
        if from_room not in self.rooms or to_room not in self.rooms:
            return

        # Add forward exit
        exit_data = {
            "direction": direction,
            "destination": to_room,
        }
        if exit_type != "normal":
            exit_data["type"] = exit_type

        self.rooms[from_room].exits.append(exit_data)

        # Add reverse exit if bidirectional
        if bidirectional:
            reverse_dir = self._get_reverse_direction(direction)
            if reverse_dir:
                reverse_exit = {
                    "direction": reverse_dir,
                    "destination": from_room,
                }
                if exit_type != "normal":
                    reverse_exit["type"] = exit_type
                self.rooms[to_room].exits.append(reverse_exit)

    def remove_exit(self, from_room: str, direction: str) -> None:
        """Remove an exit from a room."""
        if from_room in self.rooms:
            self.rooms[from_room].exits = [
                e for e in self.rooms[from_room].exits if e.get("direction") != direction
            ]

    def _get_reverse_direction(self, direction: str) -> Optional[str]:
        """Get the opposite direction."""
        opposites = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east",
            "northeast": "southwest",
            "northwest": "southeast",
            "southeast": "northwest",
            "southwest": "northeast",
            "up": "down",
            "down": "up",
            "enter": "exit",
            "exit": "enter",
        }
        return opposites.get(direction.lower())

    def validate(self) -> list[str]:
        """Validate the world for common errors."""
        errors = []

        # Check for starting room
        starting_room = self.meta.get("starting_room")
        if not starting_room:
            errors.append("No starting room defined in meta")
        elif starting_room not in self.rooms:
            errors.append(f"Starting room '{starting_room}' does not exist")

        # Check for invalid exit destinations
        for room_id, room in self.rooms.items():
            for exit in room.exits:
                dest = exit.get("destination")
                if dest and dest not in self.rooms:
                    errors.append(
                        f"Room '{room_id}' has exit to non-existent room '{dest}'"
                    )

        # Check for objects in non-existent rooms
        for obj_id, obj in self.objects.items():
            if obj.initial_room and obj.initial_room not in self.rooms:
                errors.append(
                    f"Object '{obj_id}' placed in non-existent room '{obj.initial_room}'"
                )
            if obj.initial_container and obj.initial_container not in self.objects:
                errors.append(
                    f"Object '{obj_id}' placed in non-existent container '{obj.initial_container}'"
                )

        # Check for rooms with no exits (potential dead ends)
        for room_id, room in self.rooms.items():
            if not room.exits and room_id != starting_room:
                errors.append(f"Room '{room_id}' has no exits (dead end)")

        return errors

    def find_orphan_rooms(self) -> list[str]:
        """Find rooms that cannot be reached from the starting room."""
        starting_room = self.meta.get("starting_room")
        if not starting_room or starting_room not in self.rooms:
            return list(self.rooms.keys())

        # BFS to find reachable rooms
        reachable = set()
        queue = [starting_room]

        while queue:
            room_id = queue.pop(0)
            if room_id in reachable:
                continue
            reachable.add(room_id)

            room = self.rooms.get(room_id)
            if room:
                for exit in room.exits:
                    dest = exit.get("destination")
                    if dest and dest not in reachable:
                        queue.append(dest)

        # Return rooms not in reachable set
        return [r for r in self.rooms.keys() if r not in reachable]
