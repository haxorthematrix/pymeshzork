"""Main game engine for PyMeshZork."""

from dataclasses import dataclass, field
from typing import Callable

from pymeshzork.engine.events import EventManager, check_grue
from pymeshzork.engine.models import ObjectFlag2
from pymeshzork.engine.parser import ParsedCommand, Parser
from pymeshzork.engine.state import GameState
from pymeshzork.engine.verbs import VerbHandler, VerbResult
from pymeshzork.engine.world import World


@dataclass
class GameResult:
    """Result of processing a turn."""

    messages: list[str] = field(default_factory=list)
    quit_requested: bool = False
    player_died: bool = False
    score_change: int = 0


class Game:
    """Main game engine - coordinates all systems."""

    def __init__(
        self,
        world: World | None = None,
        state: GameState | None = None,
    ) -> None:
        """Initialize game with world and state."""
        self.world = world or World()
        self.state = state or GameState()
        self.parser = Parser()
        self.verbs = VerbHandler(self)
        self.events = EventManager(self)

        # Hooks for extensibility
        self.pre_turn_hooks: list[Callable[[], str | None]] = []
        self.post_turn_hooks: list[Callable[[], str | None]] = []

    def start(self) -> str:
        """Start a new game. Returns opening text."""
        # Initialize object states from world definitions
        self.world.initialize_object_states(self.state)

        # Get starting room
        room = self.world.get_room(self.state.current_room)
        if not room:
            return "Error: Starting room not found!"

        # Mark starting room as visited
        room_state = self.state.get_room_state(room.id)
        room_state.mark_visited()

        # Build opening message
        lines = [
            "ZORK I: The Great Underground Empire",
            "PyMeshZork Version 0.1.0",
            "Copyright (c) 1981, 1982, 1983 Infocom, Inc.",
            "Python conversion for educational purposes.",
            "",
        ]

        # Add room description
        description = self.world.describe_room(self.state, room)
        lines.append(description)

        return "\n".join(lines)

    def process_input(self, input_text: str) -> GameResult:
        """Process player input and return result."""
        result = GameResult()

        # Run pre-turn hooks
        for hook in self.pre_turn_hooks:
            msg = hook()
            if msg:
                result.messages.append(msg)

        # Parse input
        command = self.parser.parse(input_text, self.world, self.state)

        # Execute command
        verb_result = self.verbs.execute(command)

        # Add verb result message
        if verb_result.message:
            if verb_result.message == "QUIT":
                result.quit_requested = True
                result.messages.append("Goodbye!")
            else:
                result.messages.append(verb_result.message)

        # Track score changes
        if verb_result.score_change:
            self.state.add_score(verb_result.score_change)
            result.score_change = verb_result.score_change

        # If action used a turn, process events
        if verb_result.end_turn:
            self.state.increment_moves()

            # Process timed events
            event_results = self.events.tick()
            for ev in event_results:
                if ev.message:
                    result.messages.append(ev.message)
                if ev.player_dies:
                    result.player_died = True
                if ev.score_change:
                    self.state.add_score(ev.score_change)
                    result.score_change += ev.score_change

            # Check for grue
            grue_msg = check_grue(self)
            if grue_msg:
                result.messages.append(grue_msg)
                result.player_died = True

        # Run post-turn hooks
        for hook in self.post_turn_hooks:
            msg = hook()
            if msg:
                result.messages.append(msg)

        # Handle death
        if result.player_died:
            result.messages.append(self._handle_death())

        return result

    def _handle_death(self) -> str:
        """Handle player death."""
        self.state.record_death()

        if self.state.deaths >= 3:
            return (
                "\n    ****  You have died  ****\n\n"
                "You have died three times. That's enough for today.\n"
                "Your score is {self.state.score}."
            )

        # Resurrect player
        self.state.current_room = "whous"  # Back to start

        # Drop all inventory
        for obj_id in list(self.state.objects_held_by("player")):
            # Items go to... somewhere appropriate
            self.state.move_object_to_room(obj_id, "whous")

        return (
            "\n    ****  You have died  ****\n\n"
            "As you take your last breath, you feel relieved of your "
            "worldly possessions. As your vision dims, you see a figure "
            "approaching. 'I'm afraid your adventure is over for now, but "
            "I'll give you another chance.'\n\n"
            "You wake up in a familiar place..."
        )

    def save_game(self) -> dict:
        """Save game state to dictionary."""
        return self.state.to_dict()

    def load_game(self, data: dict) -> bool:
        """Load game state from dictionary."""
        try:
            self.state = GameState.from_dict(data)
            return True
        except Exception:
            return False

    def get_current_room_description(self) -> str:
        """Get description of current room."""
        room = self.world.get_room(self.state.current_room)
        if not room:
            return "You are nowhere!"
        return self.world.describe_room(self.state, room)

    def get_prompt(self) -> str:
        """Get the input prompt."""
        return ">"


def create_demo_world() -> World:
    """Create a minimal demo world for testing."""
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

    world = World()

    # West of House
    world.add_room(Room(
        id="whous",
        name="West of House",
        description_first=(
            "You are standing in an open field west of a white house, "
            "with a boarded front door.\n"
            "There is a small mailbox here."
        ),
        description_short="West of House",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
        exits=[
            Exit(Direction.NORTH, "nhous"),
            Exit(Direction.SOUTH, "shous"),
            Exit(Direction.WEST, "forest"),
            Exit(Direction.EAST, "whous", ExitType.NO_EXIT,
                 message="The door is boarded and you can't remove the boards."),
        ],
    ))

    # North of House
    world.add_room(Room(
        id="nhous",
        name="North of House",
        description_first=(
            "You are facing the north side of a white house. There is no door here, "
            "and all the windows are boarded up. To the north a narrow path winds "
            "through the trees."
        ),
        description_short="North of House",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
        exits=[
            Exit(Direction.SOUTH, "whous"),
            Exit(Direction.WEST, "forest"),
            Exit(Direction.EAST, "ehous"),
            Exit(Direction.NORTH, "forest"),
        ],
    ))

    # South of House
    world.add_room(Room(
        id="shous",
        name="South of House",
        description_first=(
            "You are facing the south side of a white house. There is no door here, "
            "and all the windows are boarded."
        ),
        description_short="South of House",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
        exits=[
            Exit(Direction.NORTH, "whous"),
            Exit(Direction.WEST, "forest"),
            Exit(Direction.EAST, "ehous"),
        ],
    ))

    # Behind House
    world.add_room(Room(
        id="ehous",
        name="Behind House",
        description_first=(
            "You are behind the white house. A path leads into the forest to the east. "
            "In one corner of the house there is a small window which is slightly ajar."
        ),
        description_short="Behind House",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
        exits=[
            Exit(Direction.NORTH, "nhous"),
            Exit(Direction.SOUTH, "shous"),
            Exit(Direction.EAST, "forest"),
            Exit(Direction.WEST, "kitchen", ExitType.DOOR, door_id="window"),
            Exit(Direction.ENTER, "kitchen", ExitType.DOOR, door_id="window"),
        ],
    ))

    # Kitchen
    world.add_room(Room(
        id="kitchen",
        name="Kitchen",
        description_first=(
            "You are in the kitchen of the white house. A table seems to have been "
            "used recently for the preparation of food. A passage leads to the west "
            "and a dark staircase can be seen leading upward. A dark chimney leads "
            "down and to the east is a small window which is open."
        ),
        description_short="Kitchen",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND | RoomFlag.RHOUSE,
        exits=[
            Exit(Direction.EAST, "ehous", ExitType.DOOR, door_id="window"),
            Exit(Direction.WEST, "lroom"),
            Exit(Direction.UP, "attic"),
            Exit(Direction.DOWN, "cella"),
        ],
    ))

    # Living Room
    world.add_room(Room(
        id="lroom",
        name="Living Room",
        description_first=(
            "You are in the living room. There is a doorway to the east, a wooden "
            "door with strange gothic lettering to the west, which appears to be "
            "nailed shut, a trophy case, and a large oriental rug in the center of "
            "the room.\nAbove the trophy case hangs an elvish sword of great antiquity."
        ),
        description_short="Living Room",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND | RoomFlag.RHOUSE,
        exits=[
            Exit(Direction.EAST, "kitchen"),
            Exit(Direction.WEST, "lroom", ExitType.NO_EXIT,
                 message="The door is nailed shut."),
        ],
    ))

    # Forest (generic)
    world.add_room(Room(
        id="forest",
        name="Forest",
        description_first=(
            "This is a forest, with trees in all directions. To the east, there "
            "appears to be sunlight."
        ),
        description_short="Forest",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
        exits=[
            Exit(Direction.EAST, "whous"),
            Exit(Direction.NORTH, "forest"),
            Exit(Direction.SOUTH, "forest"),
            Exit(Direction.WEST, "forest"),
        ],
    ))

    # Attic
    world.add_room(Room(
        id="attic",
        name="Attic",
        description_first=(
            "This is the attic. The only exit is a stairway leading down. A large "
            "coil of rope is lying in the corner. On a table is a nasty-looking knife."
        ),
        description_short="Attic",
        flags=RoomFlag.RLIGHT | RoomFlag.RLAND | RoomFlag.RHOUSE,
        exits=[
            Exit(Direction.DOWN, "kitchen"),
        ],
    ))

    # Cellar
    world.add_room(Room(
        id="cella",
        name="Cellar",
        description_first=(
            "You are in a dark and damp cellar with a narrow passageway leading "
            "north, and a crawlway to the south. On the west is the bottom of a "
            "steep metal ramp which is unclimbable."
        ),
        description_short="Cellar",
        flags=RoomFlag.RLAND,  # No light!
        exits=[
            Exit(Direction.UP, "kitchen"),
            Exit(Direction.NORTH, "mtrol"),
        ],
    ))

    # Troll Room
    world.add_room(Room(
        id="mtrol",
        name="Troll Room",
        description_first=(
            "This is a small room with passages to the east and south and a "
            "forbidding hole leading west. Bloodstains and deep scratches (perhaps "
            "made by straining fingers) mar the walls."
        ),
        description_short="Troll Room",
        flags=RoomFlag.RLAND,
        exits=[
            Exit(Direction.SOUTH, "cella"),
        ],
    ))

    # ============ Objects ============

    # Mailbox
    world.add_object(Object(
        id="mailbox",
        name="small mailbox",
        synonyms=["mailbox", "box"],
        adjectives=["small"],
        description="There is a small mailbox here.",
        examine="The mailbox is a small mailbox.",
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.CONTBT,
        flags2=ObjectFlag2.OPENBT,
        initial_room="whous",
        capacity=10,
    ))

    # Leaflet
    world.add_object(Object(
        id="leaflet",
        name="leaflet",
        synonyms=["paper", "flyer"],
        description="",
        examine="The leaflet says 'WELCOME TO ZORK!'",
        read_text=(
            "WELCOME TO ZORK!\n\n"
            "ZORK is a game of adventure, danger, and low cunning. In it you will "
            "explore some of the most amazing territory ever seen by mortals. No "
            "computer should be without one!"
        ),
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.TAKEBT | ObjectFlag1.READBT,
        initial_room=None,  # Starts in mailbox
    ))

    # Sword
    world.add_object(Object(
        id="sword",
        name="elvish sword",
        synonyms=["sword", "blade"],
        adjectives=["elvish", "antique"],
        description="Above the trophy case hangs an elvish sword of great antiquity.",
        examine=(
            "The sword is of exquisite craftsmanship. It is inscribed with "
            "ancient elvish runes."
        ),
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.TAKEBT,
        flags2=ObjectFlag2.WEAPBT,
        initial_room="lroom",
        size=30,
    ))

    # Lamp
    world.add_object(Object(
        id="lamp",
        name="brass lantern",
        synonyms=["lamp", "lantern", "light"],
        adjectives=["brass"],
        description="There is a brass lantern (battery-powered) here.",
        examine="The lamp is a battery-powered brass lantern.",
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.TAKEBT | ObjectFlag1.LITEBT,
        initial_room="lroom",
        size=15,
        properties={"light_remaining": 350},
    ))

    # Trophy Case
    world.add_object(Object(
        id="tcase",
        name="trophy case",
        synonyms=["case"],
        adjectives=["trophy"],
        description="",
        examine="The trophy case is empty.",
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.CONTBT | ObjectFlag1.TRANBT,
        flags2=ObjectFlag2.OPENBT,
        initial_room="lroom",
        capacity=100,
    ))

    # Rug
    world.add_object(Object(
        id="rug",
        name="oriental rug",
        synonyms=["rug", "carpet"],
        adjectives=["oriental", "large"],
        description="",
        examine="The rug is a beautiful oriental carpet.",
        flags1=ObjectFlag1.VISIBT,
        initial_room="lroom",
    ))

    # Window
    world.add_object(Object(
        id="window",
        name="small window",
        synonyms=["window"],
        adjectives=["small"],
        description="",
        examine="The window is slightly ajar.",
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.DOORBT,
        flags2=ObjectFlag2.OPENBT,
        initial_room="ehous",
    ))

    # Rope
    world.add_object(Object(
        id="rope",
        name="coil of rope",
        synonyms=["rope", "coil"],
        description="A large coil of rope is lying in the corner.",
        examine="The rope is strong and about 50 feet long.",
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.TAKEBT,
        initial_room="attic",
        size=10,
    ))

    # Knife
    world.add_object(Object(
        id="knife",
        name="nasty knife",
        synonyms=["knife", "blade"],
        adjectives=["nasty"],
        description="On a table is a nasty-looking knife.",
        examine="The knife looks very sharp and unpleasant.",
        flags1=ObjectFlag1.VISIBT | ObjectFlag1.TAKEBT,
        flags2=ObjectFlag2.WEAPBT,
        initial_room="attic",
        size=20,
    ))

    # Set leaflet in mailbox
    world.objects["leaflet"].initial_room = None

    return world


def create_game() -> Game:
    """Create a new game with demo world."""
    world = create_demo_world()
    state = GameState()

    # Put leaflet in mailbox
    state.move_object_to_container("leaflet", "mailbox")

    # Open the window for kitchen access
    window_state = state.get_object_state("window")
    window_state.flags2 |= ObjectFlag2.OPENBT

    return Game(world=world, state=state)
