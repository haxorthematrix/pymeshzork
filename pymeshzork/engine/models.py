"""Core data models for PyMeshZork game entities."""

from dataclasses import dataclass, field
from enum import IntFlag, auto
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pymeshzork.engine.state import ObjectState


class RoomFlag(IntFlag):
    """Room property flags (from vars.h)."""

    NONE = 0
    REND = 16  # End game room
    RNWALL = 32  # No wall
    RHOUSE = 64  # Part of house
    RBUCK = 128  # Bucket room (for well)
    RMUNG = 256  # Room is destroyed/munged
    RFILL = 512  # Room can be filled with water
    RSACRD = 1024  # Sacred room (no fighting allowed)
    RAIR = 2048  # Air/flying room
    RWATER = 4096  # Water room
    RLAND = 8192  # Land room
    RLIGHT = 16384  # Room is naturally lit
    RSEEN = 32768  # Room has been visited


class ObjectFlag1(IntFlag):
    """Primary object flags (from vars.h oflag1)."""

    NONE = 0
    ONBT = 1  # Object is on (light source)
    TURNBT = 2  # Can be turned
    TOOLBT = 4  # Is a tool
    FLAMBT = 8  # Is flaming
    BURNBT = 16  # Can be burned
    VICTBT = 32  # Is a victim
    LITEBT = 64  # Is a light source
    CONTBT = 128  # Is a container
    DRNKBT = 256  # Is drinkable
    NDSCBT = 512  # No description (suppress in room)
    FOODBT = 1024  # Is food
    TRANBT = 2048  # Is transparent
    DOORBT = 4096  # Is a door
    TAKEBT = 8192  # Can be taken
    READBT = 16384  # Can be read
    VISIBT = 32768  # Is visible


class ObjectFlag2(IntFlag):
    """Secondary object flags (from vars.h oflag2)."""

    NONE = 0
    SCHBT = 1  # Is searchable
    VEHBT = 2  # Is a vehicle
    TCHBT = 4  # Has been touched
    OPENBT = 8  # Is openable
    NOCHBT = 16  # No choose (for FWIM)
    TRYBT = 32  # Try to take
    STAGBT = 64  # Is staggered
    VILLBT = 128  # Is a villain
    FITEBT = 256  # Is fighting
    WEAPBT = 512  # Is a weapon
    ACTRBT = 1024  # Is an actor
    CLMBBT = 2048  # Is climbable
    TIEBT = 4096  # Can be tied
    SCRDBT = 8192  # Is sacred
    SLEPBT = 16384  # Is sleeping
    FINDBT = 32768  # Has been found


class Direction(IntFlag):
    """Movement directions (from xsrch_ in vars.h)."""

    NORTH = 1024
    NE = 2048
    EAST = 3072
    SE = 4096
    SOUTH = 5120
    SW = 6144
    WEST = 7168
    NW = 8192
    UP = 9216
    DOWN = 10240
    LAUNCH = 11264
    LAND = 12288
    ENTER = 13312
    EXIT = 14336
    TRAVEL = 15360


class ExitType(IntFlag):
    """Exit types for room connections."""

    NORMAL = 1  # Normal unconditional exit
    NO_EXIT = 2  # No exit in this direction
    CONDITIONAL = 3  # Conditional exit (requires action)
    DOOR = 4  # Door exit (requires door to be open)


@dataclass
class Exit:
    """Represents a room exit/connection."""

    direction: Direction
    destination_id: str  # Room ID to go to
    exit_type: ExitType = ExitType.NORMAL
    door_id: str | None = None  # Object ID if door type
    condition: str | None = None  # Condition function name if conditional
    message: str | None = None  # Message if blocked


@dataclass
class Room:
    """Represents a room in the game world."""

    id: str
    name: str
    description_first: str  # Long description (first visit)
    description_short: str  # Short description (subsequent visits)
    flags: RoomFlag = RoomFlag.RLAND | RoomFlag.RLIGHT
    exits: list[Exit] = field(default_factory=list)
    action: str | None = None  # Special action handler name
    value: int = 0  # Room value (for scoring)

    # Runtime state (not persisted in world JSON)
    _action_handler: Callable | None = field(default=None, repr=False)

    def is_lit(self) -> bool:
        """Check if room is naturally lit."""
        return bool(self.flags & RoomFlag.RLIGHT)

    def is_visited(self) -> bool:
        """Check if room has been visited."""
        return bool(self.flags & RoomFlag.RSEEN)

    def is_land(self) -> bool:
        """Check if room is a land room."""
        return bool(self.flags & RoomFlag.RLAND)

    def is_water(self) -> bool:
        """Check if room is a water room."""
        return bool(self.flags & RoomFlag.RWATER)

    def is_sacred(self) -> bool:
        """Check if fighting is forbidden."""
        return bool(self.flags & RoomFlag.RSACRD)


@dataclass
class Object:
    """Represents an object/item in the game."""

    id: str
    name: str
    adjectives: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    description: str = ""  # Description when in room
    examine: str = ""  # Description when examined
    read_text: str = ""  # Text when read
    flags1: ObjectFlag1 = ObjectFlag1.VISIBT
    flags2: ObjectFlag2 = ObjectFlag2.NONE
    initial_room: str | None = None  # Starting room ID
    size: int = 0  # Size (weight)
    capacity: int = 0  # Container capacity
    value: int = 0  # Treasure value
    tval: int = 0  # Trophy case value
    action: str | None = None  # Special action handler name

    # Dynamic properties (runtime state)
    properties: dict = field(default_factory=dict)

    # Runtime handler (not persisted)
    _action_handler: Callable | None = field(default=None, repr=False)

    def is_visible(self) -> bool:
        """Check if object is visible."""
        return bool(self.flags1 & ObjectFlag1.VISIBT)

    def is_takeable(self) -> bool:
        """Check if object can be taken."""
        return bool(self.flags1 & ObjectFlag1.TAKEBT)

    def is_container(self) -> bool:
        """Check if object is a container."""
        return bool(self.flags1 & ObjectFlag1.CONTBT)

    def is_open(self, state: "ObjectState | None" = None) -> bool:
        """Check if object is currently open.

        Args:
            state: Optional ObjectState to check dynamic state.
                   If None, checks the object's default flags.
        """
        if state is not None:
            return bool(state.flags2 & ObjectFlag2.OPENBT)
        return bool(self.flags2 & ObjectFlag2.OPENBT)

    def is_transparent(self) -> bool:
        """Check if object is transparent (can see contents when closed)."""
        return bool(self.flags1 & ObjectFlag1.TRANBT)

    def is_light_source(self) -> bool:
        """Check if object provides light."""
        return bool(self.flags1 & ObjectFlag1.LITEBT)

    def is_on(self, state: "ObjectState | None" = None) -> bool:
        """Check if light source is on.

        Args:
            state: Optional ObjectState to check dynamic state.
                   If None, checks the object's default flags.
        """
        if state is not None:
            return bool(state.flags1 & ObjectFlag1.ONBT)
        return bool(self.flags1 & ObjectFlag1.ONBT)

    def is_weapon(self) -> bool:
        """Check if object is a weapon."""
        return bool(self.flags2 & ObjectFlag2.WEAPBT)

    def is_villain(self) -> bool:
        """Check if object is a villain."""
        return bool(self.flags2 & ObjectFlag2.VILLBT)

    def is_actor(self) -> bool:
        """Check if object is an actor/NPC."""
        return bool(self.flags2 & ObjectFlag2.ACTRBT)

    def is_door(self) -> bool:
        """Check if object is a door."""
        return bool(self.flags1 & ObjectFlag1.DOORBT)

    def is_readable(self) -> bool:
        """Check if object can be read."""
        return bool(self.flags1 & ObjectFlag1.READBT)

    def is_food(self) -> bool:
        """Check if object is edible."""
        return bool(self.flags1 & ObjectFlag1.FOODBT)


class ActorFlag(IntFlag):
    """Actor-specific flags."""

    NONE = 0
    ASTAG = 32768  # Actor is staggered


@dataclass
class Actor:
    """Represents a player or NPC actor."""

    id: str
    name: str
    room_id: str  # Current room
    score: int = 0
    strength: int = 0
    vehicle_id: str | None = None  # Currently in vehicle
    object_id: str | None = None  # Associated object (for NPCs)
    action: str | None = None  # Action handler name
    flags: ActorFlag = ActorFlag.NONE

    # Runtime handler (not persisted)
    _action_handler: Callable | None = field(default=None, repr=False)


@dataclass
class Event:
    """Represents a timed event/clock."""

    id: str
    name: str
    ticks: int  # Turns until event fires (0 = inactive)
    action: str  # Action handler name
    active: bool = False
    repeating: bool = False

    # Runtime handler (not persisted)
    _action_handler: Callable | None = field(default=None, repr=False)


# Pre-defined event IDs matching cindex_ from vars.h
class EventID:
    """Standard event identifiers."""

    CURRENT = "cevcur"  # Current/immediate event
    MOUNTAIN = "cevmnt"  # Mountain entry
    LANTERN = "cevlnt"  # Lantern timer
    MATCH = "cevmat"  # Match burning
    CANDLE = "cevcnd"  # Candle timer
    BALLOON = "cevbal"  # Balloon events
    BURNING = "cevbrn"  # Something burning
    FUSE = "cevfus"  # Fuse burning
    LED = "cevled"  # LED
    SAFE = "cevsaf"  # Safe events
    VILLAIN = "cevvlg"  # Villain events
    GNOME = "cevgno"  # Gnome events
    BUCKET = "cevbuc"  # Bucket events
    SPHERE = "cevsph"  # Sphere events
    ENDGAME_HINT = "cevegh"  # End game hint
    FOREST = "cevfor"  # Forest events
    SCROLL = "cevscl"  # Scroll events
    ZIGGY_IN = "cevzgi"  # Ziggy events in
    ZIGGY_OUT = "cevzgo"  # Ziggy events out
    STEAM = "cevste"  # Steam events
    MIRROR = "cevmrs"  # Mirror events
    PINE = "cevpin"  # Pine events
    INQUISITION = "cevinq"  # Inquisition events
    FOLLOW = "cevfol"  # Follow events


# Pre-defined room IDs matching rindex_ from vars.h
class RoomID:
    """Standard room identifiers from original Zork."""

    WEST_OF_HOUSE = "whous"
    LIVING_ROOM = "lroom"
    CELLAR = "cella"
    TROLL_ROOM = "mtrol"
    MAZE_1 = "maze1"
    GRATING = "mgrat"
    MAZE_15 = "maz15"
    FOREST_1 = "fore1"
    FOREST_3 = "fore3"
    CLEARING = "clear"
    RESERVOIR = "reser"
    STREAM = "strea"
    EGYPT = "egypt"
    ECHO_ROOM = "echor"
    TOP_OF_SHAFT = "tshaf"
    BOTTOM_OF_SHAFT = "bshaf"
    MACHINE_ROOM = "mmach"
    DOME = "dome"
    TORCH_ROOM = "mtorc"
    CAROUSEL = "carou"
    RIDDLE_ROOM = "riddl"
    LOUD_ROOM = "lld2"
    TEMPLE = "temp1"
    TEMPLE_2 = "temp2"
    MAINTENANCE = "maint"
    BLUE_ROOM = "blroo"
    TREASURE_ROOM = "treas"
    RIVER_1 = "rivr1"
    RIVER_2 = "rivr2"
    RIVER_3 = "rivr3"
    CYCLOPS_ROOM = "mcycl"


# Pre-defined object IDs matching oindex_ from vars.h
class ObjectID:
    """Standard object identifiers from original Zork."""

    GARLIC = "garli"
    FOOD = "food"
    GUNK = "gunk"
    COAL = "coal"
    MACHINE = "machi"
    DIAMOND = "diamo"
    TROPHY_CASE = "tcase"
    BOTTLE = "bottl"
    WATER = "water"
    ROPE = "rope"
    KNIFE = "knife"
    SWORD = "sword"
    LAMP = "lamp"
    BROKEN_LAMP = "blamp"
    RUG = "rug"
    LEAVES = "leave"
    TROLL = "troll"
    AXE = "axe"
    RUSTY_KNIFE = "rknif"
    KEYS = "keys"
    ICE = "ice"
    BAR = "bar"
    COFFIN = "coffi"
    TORCH = "torch"
    TRUNK_BASKET = "tbask"
    FALLEN_BASKET = "fbask"
    IRON_BOX = "irbox"
    GHOST = "ghost"
    TRUNK = "trunk"
    BELL = "bell"
    BOOK = "book"
    CANDLES = "candl"
    MATCHES = "match"
    TUBE = "tube"
    PUTTY = "putty"
    WRENCH = "wrenc"
    SCREWDRIVER = "screw"
    CYCLOPS = "cyclo"
    CHALICE = "chali"
    THIEF = "thief"
    STILETTO = "still"
    WINDOW = "windo"
    GRATE = "grate"
    DOOR = "door"
