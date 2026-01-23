"""Game state management for PyMeshZork."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pymeshzork.engine.models import (
    Actor,
    ActorFlag,
    Event,
    Object,
    ObjectFlag1,
    ObjectFlag2,
    Room,
    RoomFlag,
)

if TYPE_CHECKING:
    from pymeshzork.engine.world import World


@dataclass
class RoomState:
    """Runtime state for a room."""

    room_id: str
    flags: RoomFlag = RoomFlag.NONE

    def mark_visited(self) -> None:
        """Mark the room as visited."""
        self.flags |= RoomFlag.RSEEN

    def is_visited(self) -> bool:
        """Check if room has been visited."""
        return bool(self.flags & RoomFlag.RSEEN)


@dataclass
class ObjectState:
    """Runtime state for an object."""

    object_id: str
    room_id: str | None = None  # Current room (None if not in a room)
    actor_id: str | None = None  # Actor holding it (None if not held)
    container_id: str | None = None  # Container it's in (None if not contained)
    flags1: ObjectFlag1 = ObjectFlag1.NONE
    flags2: ObjectFlag2 = ObjectFlag2.NONE
    properties: dict = field(default_factory=dict)  # Dynamic properties

    def is_in_room(self, room_id: str) -> bool:
        """Check if object is in a specific room."""
        return self.room_id == room_id and self.actor_id is None and self.container_id is None

    def is_held_by(self, actor_id: str) -> bool:
        """Check if object is held by a specific actor."""
        return self.actor_id == actor_id

    def is_in_container(self, container_id: str) -> bool:
        """Check if object is in a specific container."""
        return self.container_id == container_id


@dataclass
class ActorState:
    """Runtime state for an actor."""

    actor_id: str
    room_id: str
    score: int = 0
    strength: int = 0
    vehicle_id: str | None = None
    flags: ActorFlag = ActorFlag.NONE


@dataclass
class EventState:
    """Runtime state for a timed event."""

    event_id: str
    ticks: int = 0
    active: bool = False


@dataclass
class GameFlags:
    """Game-wide flags matching findex_ from vars.h."""

    # Logical flags (46 total in original)
    trollf: bool = False  # Troll killed
    cagesf: bool = False  # Cage
    bucktf: bool = False  # Bucket
    caroff: bool = False  # Carousel off
    carone: bool = False  # Carousel spun once
    lwtidf: bool = False  # Low tide
    domef: bool = False  # Dome visited
    glacrf: bool = False  # Glacier
    echof: bool = False  # Echo room
    riddlf: bool = False  # Riddle solved
    lldf: bool = False  # Loud room
    cyclof: bool = False  # Cyclops gone
    magicf: bool = False  # Magic boat inflated
    litldf: bool = False  # Little door
    safef: bool = False  # Safe open
    gnomef: bool = False  # Gnome appeared
    gnodrf: bool = False  # Gnome door
    mirrmf: bool = False  # Mirror
    egyptf: bool = False  # Egypt room
    onpolf: bool = False  # On pole
    blabf: bool = False  # Blab
    brieff: bool = False  # Brief mode
    superf: bool = False  # Super brief mode
    buoyf: bool = False  # Buoy opened
    grunlf: bool = False  # Grue
    gatef: bool = False  # Gate
    rainbf: bool = False  # Rainbow solid
    cagetf: bool = False  # Cage tied
    empthf: bool = False  # Empty hands
    deflaf: bool = False  # Deflated
    glacmf: bool = False  # Glacier moved
    frobzf: bool = False  # Frobozz
    endgmf: bool = False  # End game started
    badlkf: bool = False  # Bad luck
    thfenf: bool = False  # Thief engaged
    singsf: bool = False  # Singing
    mrpshf: bool = False  # Mirror pushed

    # Puzzle state flags for conditional exits
    rug_moved: bool = False  # Rug moved revealing trap door
    grate_open: bool = False  # Grating unlocked/opened
    rope_tied: bool = False  # Rope tied to railing in dome
    gates_open: bool = False  # Gates of Hades opened
    mropnf: bool = False  # Mirror open
    wdopnf: bool = False  # Wooden door open
    mr1f: bool = False  # Mirror room 1
    mr2f: bool = False  # Mirror room 2
    inqstf: bool = False  # Inquisition
    follwf: bool = False  # Following
    spellf: bool = False  # Spell active
    cpoutf: bool = False  # CP out
    cpushf: bool = False  # CP pushed

    # Integer switches (22 in original)
    btief: int = 0  # Boat tied
    binff: int = 0  # Boat inflated
    rvmnt: int = 0  # Reservoir mount
    rvclr: int = 0  # Reservoir clear
    rvcyc: int = 0  # Reservoir cycle
    rvsnd: int = 0  # Reservoir sound
    rvgua: int = 0  # Reservoir guard
    orrug: int = 0  # Oriental rug
    orcand: int = 0  # Oriental candle
    ormtch: int = 0  # Oriental match
    orlamp: int = 0  # Oriental lamp
    mdir: int = 0  # Mirror direction
    mloc: int = 0  # Mirror location
    poleuf: int = 0  # Pole up
    quesno: int = 0  # Question number
    nqatt: int = 0  # Number of question attempts
    corrct: int = 0  # Correct answers
    lcell: int = 0  # Last cell
    pnumb: int = 0  # Puzzle number
    acession: int = 0  # Access
    dcession: int = 0  # DC
    cession: int = 0  # Current sphere position


@dataclass
class VillainState:
    """State for villain combat system."""

    villains: list[str] = field(default_factory=list)  # Active villain IDs
    probabilities: dict[str, int] = field(default_factory=dict)  # Hit probabilities
    opponents: dict[str, str] = field(default_factory=dict)  # Who they're fighting
    best_weapons: dict[str, str] = field(default_factory=dict)  # Best weapon vs each
    in_melee: dict[str, bool] = field(default_factory=dict)  # Currently in combat


@dataclass
class ThiefState:
    """State for the thief demon."""

    position: int = 0  # Thief's current room index
    active: bool = False  # Thief demon active
    thief_here: bool = False  # Thief in player's room
    sword_active: bool = False  # Sword demon active
    sword_glow: int = 0  # Sword glow level (0-2)


@dataclass
class PuzzleState:
    """State for sliding puzzle and other puzzles."""

    # 8x8 puzzle grid
    cpvec: list[int] = field(default_factory=lambda: [
        1, 1, 1, 1, 1, 1, 1, 1,
        1, 0, -1, 0, 0, -1, 0, 1,
        1, -1, 0, 1, 0, -2, 0, 1,
        1, 0, 0, 0, 0, 1, 0, 1,
        1, -3, 0, 0, -1, -1, 0, 1,
        1, 0, 0, -1, 0, 0, 0, 1,
        1, 1, 1, 0, 0, 0, 1, 1,
        1, 1, 1, 1, 1, 1, 1, 1,
    ])


@dataclass
class GameState:
    """Complete game state for a session."""

    # Core state
    current_room: str = "whous"  # West of House
    winner: str = "player"  # Current acting entity
    moves: int = 0
    deaths: int = 0
    score: int = 0
    max_score: int = 350  # Maximum possible score
    max_load: int = 100  # Maximum carrying capacity

    # Room states
    room_states: dict[str, RoomState] = field(default_factory=dict)

    # Object states (location, flags, properties)
    object_states: dict[str, ObjectState] = field(default_factory=dict)

    # Actor states
    actor_states: dict[str, ActorState] = field(default_factory=dict)

    # Event states
    event_states: dict[str, EventState] = field(default_factory=dict)

    # Game flags
    flags: GameFlags = field(default_factory=GameFlags)

    # Combat state
    villain_state: VillainState = field(default_factory=VillainState)

    # Thief/demon state
    thief_state: ThiefState = field(default_factory=ThiefState)

    # Puzzle state
    puzzle_state: PuzzleState = field(default_factory=PuzzleState)

    # Parser state
    last_it: str | None = None  # Last object referred to as "it"
    tell_flag: bool = False  # Something was told to player this turn

    # Light state
    light_shift: int = 0
    block_value: int = 0
    munged_room: str | None = None

    # End game state
    end_game_score: int = 0
    end_game_max: int = 100

    # Combat/health state
    player_wounds: int = 0  # Accumulated damage (death at 10)
    player_health: int = 10  # Maximum health

    def get_room_state(self, room_id: str) -> RoomState:
        """Get or create state for a room."""
        if room_id not in self.room_states:
            self.room_states[room_id] = RoomState(room_id=room_id)
        return self.room_states[room_id]

    def get_object_state(self, object_id: str) -> ObjectState:
        """Get or create state for an object."""
        if object_id not in self.object_states:
            self.object_states[object_id] = ObjectState(object_id=object_id)
        return self.object_states[object_id]

    def get_actor_state(self, actor_id: str) -> ActorState:
        """Get or create state for an actor."""
        if actor_id not in self.actor_states:
            self.actor_states[actor_id] = ActorState(
                actor_id=actor_id,
                room_id=self.current_room,
            )
        return self.actor_states[actor_id]

    def get_event_state(self, event_id: str) -> EventState:
        """Get or create state for an event."""
        if event_id not in self.event_states:
            self.event_states[event_id] = EventState(event_id=event_id)
        return self.event_states[event_id]

    def is_room_lit(self, room: Room) -> bool:
        """Check if a room is currently lit (natural or by light source)."""
        if room.is_lit():
            return True
        # Check for light sources in player's inventory or room
        # This will be implemented when we have the full object system
        return False

    def add_score(self, points: int) -> None:
        """Add points to the score."""
        self.score += points

    def increment_moves(self) -> None:
        """Increment the move counter."""
        self.moves += 1

    def record_death(self) -> None:
        """Record a player death."""
        self.deaths += 1

    def objects_in_room(self, room_id: str) -> list[str]:
        """Get all objects visible in a room."""
        return [
            obj_id for obj_id, state in self.object_states.items()
            if state.is_in_room(room_id)
        ]

    def objects_held_by(self, actor_id: str) -> list[str]:
        """Get all objects held by an actor."""
        return [
            obj_id for obj_id, state in self.object_states.items()
            if state.is_held_by(actor_id)
        ]

    def objects_in_container(self, container_id: str) -> list[str]:
        """Get all objects in a container."""
        return [
            obj_id for obj_id, state in self.object_states.items()
            if state.is_in_container(container_id)
        ]

    def move_object_to_room(self, object_id: str, room_id: str) -> None:
        """Move an object to a room."""
        state = self.get_object_state(object_id)
        state.room_id = room_id
        state.actor_id = None
        state.container_id = None

    def move_object_to_actor(self, object_id: str, actor_id: str) -> None:
        """Give an object to an actor."""
        state = self.get_object_state(object_id)
        state.room_id = None
        state.actor_id = actor_id
        state.container_id = None

    def move_object_to_container(self, object_id: str, container_id: str) -> None:
        """Put an object in a container."""
        state = self.get_object_state(object_id)
        state.room_id = None
        state.actor_id = None
        state.container_id = container_id

    def to_dict(self) -> dict:
        """Serialize game state to a dictionary for saving."""
        return {
            "current_room": self.current_room,
            "winner": self.winner,
            "moves": self.moves,
            "deaths": self.deaths,
            "score": self.score,
            "max_score": self.max_score,
            "max_load": self.max_load,
            "room_states": {
                k: {"room_id": v.room_id, "flags": int(v.flags)}
                for k, v in self.room_states.items()
            },
            "object_states": {
                k: {
                    "object_id": v.object_id,
                    "room_id": v.room_id,
                    "actor_id": v.actor_id,
                    "container_id": v.container_id,
                    "flags1": int(v.flags1),
                    "flags2": int(v.flags2),
                    "properties": v.properties,
                }
                for k, v in self.object_states.items()
            },
            "actor_states": {
                k: {
                    "actor_id": v.actor_id,
                    "room_id": v.room_id,
                    "score": v.score,
                    "strength": v.strength,
                    "vehicle_id": v.vehicle_id,
                    "flags": int(v.flags),
                }
                for k, v in self.actor_states.items()
            },
            "event_states": {
                k: {"event_id": v.event_id, "ticks": v.ticks, "active": v.active}
                for k, v in self.event_states.items()
            },
            "flags": {
                k: v for k, v in self.flags.__dict__.items()
            },
            "last_it": self.last_it,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        """Deserialize game state from a dictionary."""
        state = cls()
        state.current_room = data.get("current_room", "whous")
        state.winner = data.get("winner", "player")
        state.moves = data.get("moves", 0)
        state.deaths = data.get("deaths", 0)
        state.score = data.get("score", 0)
        state.max_score = data.get("max_score", 350)
        state.max_load = data.get("max_load", 100)
        state.last_it = data.get("last_it")

        # Restore room states
        for k, v in data.get("room_states", {}).items():
            state.room_states[k] = RoomState(
                room_id=v["room_id"],
                flags=RoomFlag(v.get("flags", 0)),
            )

        # Restore object states
        for k, v in data.get("object_states", {}).items():
            state.object_states[k] = ObjectState(
                object_id=v["object_id"],
                room_id=v.get("room_id"),
                actor_id=v.get("actor_id"),
                container_id=v.get("container_id"),
                flags1=ObjectFlag1(v.get("flags1", 0)),
                flags2=ObjectFlag2(v.get("flags2", 0)),
                properties=v.get("properties", {}),
            )

        # Restore actor states
        for k, v in data.get("actor_states", {}).items():
            state.actor_states[k] = ActorState(
                actor_id=v["actor_id"],
                room_id=v["room_id"],
                score=v.get("score", 0),
                strength=v.get("strength", 0),
                vehicle_id=v.get("vehicle_id"),
                flags=ActorFlag(v.get("flags", 0)),
            )

        # Restore event states
        for k, v in data.get("event_states", {}).items():
            state.event_states[k] = EventState(
                event_id=v["event_id"],
                ticks=v.get("ticks", 0),
                active=v.get("active", False),
            )

        # Restore flags
        if "flags" in data:
            for k, v in data["flags"].items():
                if hasattr(state.flags, k):
                    setattr(state.flags, k, v)

        return state
