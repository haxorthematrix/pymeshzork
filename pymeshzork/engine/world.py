"""World management for PyMeshZork - rooms, navigation, and map."""

from dataclasses import dataclass, field

from pymeshzork.engine.models import (
    Direction,
    Exit,
    ExitType,
    Object,
    Room,
    RoomFlag,
)
from pymeshzork.engine.state import GameState, ObjectState


@dataclass
class World:
    """Manages the game world - rooms, objects, and navigation."""

    rooms: dict[str, Room] = field(default_factory=dict)
    objects: dict[str, Object] = field(default_factory=dict)
    messages: dict[str, str] = field(default_factory=dict)

    # Direction name mappings
    DIRECTION_NAMES: dict[str, Direction] = field(default_factory=lambda: {
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
        "leave": Direction.EXIT,
    })

    DIRECTION_DISPLAY: dict[Direction, str] = field(default_factory=lambda: {
        Direction.NORTH: "north",
        Direction.SOUTH: "south",
        Direction.EAST: "east",
        Direction.WEST: "west",
        Direction.NE: "northeast",
        Direction.NW: "northwest",
        Direction.SE: "southeast",
        Direction.SW: "southwest",
        Direction.UP: "up",
        Direction.DOWN: "down",
        Direction.ENTER: "in",
        Direction.EXIT: "out",
    })

    def add_room(self, room: Room) -> None:
        """Add a room to the world."""
        self.rooms[room.id] = room

    def add_object(self, obj: Object) -> None:
        """Add an object to the world."""
        self.objects[obj.id] = obj

    def get_room(self, room_id: str) -> Room | None:
        """Get a room by ID."""
        return self.rooms.get(room_id)

    def get_object(self, object_id: str) -> Object | None:
        """Get an object by ID."""
        return self.objects.get(object_id)

    def get_message(self, message_id: str) -> str:
        """Get a message by ID."""
        return self.messages.get(message_id, f"[Message {message_id} not found]")

    def parse_direction(self, direction_str: str) -> Direction | None:
        """Parse a direction string to a Direction enum."""
        return self.DIRECTION_NAMES.get(direction_str.lower())

    def direction_name(self, direction: Direction) -> str:
        """Get display name for a direction."""
        return self.DIRECTION_DISPLAY.get(direction, "unknown")

    def find_exit(self, room: Room, direction: Direction) -> Exit | None:
        """Find an exit from a room in a given direction."""
        for exit in room.exits:
            if exit.direction == direction:
                return exit
        return None

    def get_available_exits(self, room: Room) -> list[Exit]:
        """Get all available exits from a room."""
        return [e for e in room.exits if e.exit_type != ExitType.NO_EXIT]

    def can_move(
        self,
        state: GameState,
        from_room: Room,
        direction: Direction,
    ) -> tuple[bool, str | None, str | None]:
        """
        Check if movement is possible.

        Returns:
            (can_move, destination_room_id, error_message)
        """
        exit = self.find_exit(from_room, direction)

        if exit is None:
            return False, None, "You can't go that way."

        if exit.exit_type == ExitType.NO_EXIT:
            return False, None, exit.message or "You can't go that way."

        if exit.exit_type == ExitType.DOOR:
            # Check if door is open
            if exit.door_id:
                door_state = state.get_object_state(exit.door_id)
                door = self.get_object(exit.door_id)
                if door and not (door_state.flags2 & 8):  # OPENBT
                    return False, None, "The door is closed."

        if exit.exit_type == ExitType.CONDITIONAL:
            # Conditional exits need special handling
            # This will be expanded with the action system
            if exit.condition:
                # For now, block conditional exits without handlers
                return False, None, exit.message or "You can't go that way."

        return True, exit.destination_id, None

    def move_player(
        self,
        state: GameState,
        direction: Direction,
    ) -> tuple[bool, str]:
        """
        Attempt to move the player in a direction.

        Returns:
            (success, message)
        """
        current_room = self.get_room(state.current_room)
        if not current_room:
            return False, "You are nowhere!"

        can_go, destination_id, error = self.can_move(state, current_room, direction)

        if not can_go:
            return False, error or "You can't go that way."

        if not destination_id:
            return False, "There's nothing in that direction."

        destination = self.get_room(destination_id)
        if not destination:
            return False, f"The path leads nowhere. (Missing room: {destination_id})"

        # Update state
        state.current_room = destination_id

        # Mark room as visited
        room_state = state.get_room_state(destination_id)
        first_visit = not room_state.is_visited()
        room_state.mark_visited()

        # Return appropriate description
        if first_visit or not state.flags.brieff:
            return True, destination.description_first
        else:
            return True, destination.description_short

    def describe_room(
        self,
        state: GameState,
        room: Room,
        force_long: bool = False,
    ) -> str:
        """Get the description of a room."""
        room_state = state.get_room_state(room.id)

        # Check if room is lit
        if not self.is_room_lit(state, room):
            return "It is pitch black. You are likely to be eaten by a grue."

        # Build description
        parts = [room.name]

        # Description
        if force_long or not room_state.is_visited() or not state.flags.brieff:
            parts.append(room.description_first)
        else:
            parts.append(room.description_short)

        # List objects in room
        objects_here = self.get_visible_objects_in_room(state, room.id)
        if objects_here:
            for obj in objects_here:
                if obj.description:
                    parts.append(obj.description)

        return "\n".join(parts)

    def is_room_lit(self, state: GameState, room: Room) -> bool:
        """Check if a room is currently lit."""
        # Room has natural light
        if room.flags & RoomFlag.RLIGHT:
            return True

        # Check for light sources in player's inventory
        for obj_id in state.objects_held_by("player"):
            obj = self.get_object(obj_id)
            if obj and obj.is_light_source():
                obj_state = state.get_object_state(obj_id)
                if obj.is_on(obj_state):
                    return True

        # Check for light sources in room
        for obj_id in state.objects_in_room(room.id):
            obj = self.get_object(obj_id)
            if obj and obj.is_light_source():
                obj_state = state.get_object_state(obj_id)
                if obj.is_on(obj_state):
                    return True

        return False

    def get_visible_objects_in_room(
        self,
        state: GameState,
        room_id: str,
    ) -> list[Object]:
        """Get all visible objects in a room."""
        result = []
        for obj_id in state.objects_in_room(room_id):
            obj = self.get_object(obj_id)
            if obj and obj.is_visible():
                result.append(obj)
        return result

    def get_inventory(self, state: GameState, actor_id: str = "player") -> list[Object]:
        """Get objects held by an actor."""
        result = []
        for obj_id in state.objects_held_by(actor_id):
            obj = self.get_object(obj_id)
            if obj:
                result.append(obj)
        return result

    def find_object_by_name(
        self,
        name: str,
        state: GameState,
        search_inventory: bool = True,
        search_room: bool = True,
        search_containers: bool = True,
    ) -> list[Object]:
        """Find objects matching a name (with synonyms and adjectives)."""
        name_lower = name.lower()
        matches = []

        # Determine which objects to search
        candidate_ids = set()
        if search_inventory:
            candidate_ids.update(state.objects_held_by("player"))
        if search_room:
            candidate_ids.update(state.objects_in_room(state.current_room))

        # Also search inside open containers in the room and inventory
        if search_containers:
            container_ids = list(candidate_ids)  # Copy current candidates
            for container_id in container_ids:
                container = self.get_object(container_id)
                if container and container.is_container():
                    container_state = state.get_object_state(container_id)
                    # Check if container is open (or transparent)
                    if container.is_open(container_state) or container.is_transparent():
                        # Add objects inside this container
                        candidate_ids.update(state.objects_in_container(container_id))

        for obj_id in candidate_ids:
            obj = self.get_object(obj_id)
            if not obj or not obj.is_visible():
                continue

            # Check main name
            if name_lower in obj.name.lower():
                matches.append(obj)
                continue

            # Check synonyms
            for syn in obj.synonyms:
                if name_lower in syn.lower():
                    matches.append(obj)
                    break

        return matches

    def initialize_object_states(self, state: GameState) -> None:
        """Initialize object states from world definitions."""
        for obj_id, obj in self.objects.items():
            obj_state = state.get_object_state(obj_id)
            obj_state.flags1 = obj.flags1
            obj_state.flags2 = obj.flags2
            obj_state.properties = dict(obj.properties)
            if obj.initial_room:
                obj_state.room_id = obj.initial_room
