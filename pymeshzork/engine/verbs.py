"""Verb handlers for PyMeshZork - command execution."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from pymeshzork.engine.models import Direction, ObjectFlag1, ObjectFlag2
from pymeshzork.engine.parser import ParsedCommand

if TYPE_CHECKING:
    from pymeshzork.engine.game import Game


@dataclass
class VerbResult:
    """Result of executing a verb."""

    success: bool
    message: str
    score_change: int = 0
    end_turn: bool = True  # Whether this action uses a turn


class VerbHandler:
    """Handles verb execution for the game."""

    def __init__(self, game: "Game") -> None:
        """Initialize verb handler with game reference."""
        self.game = game

        # Map verbs to handler methods
        self.handlers: dict[str, Callable[[ParsedCommand], VerbResult]] = {
            # Movement
            "walk": self.do_walk,

            # Looking
            "look": self.do_look,
            "examine": self.do_examine,
            "read": self.do_read,

            # Object manipulation
            "take": self.do_take,
            "drop": self.do_drop,
            "put": self.do_put,
            "throw": self.do_throw,
            "give": self.do_give,

            # Container operations
            "open": self.do_open,
            "close": self.do_close,

            # Inventory
            "inventory": self.do_inventory,

            # Meta commands
            "wait": self.do_wait,
            "score": self.do_score,
            "quit": self.do_quit,
            "brief": self.do_brief,
            "verbose": self.do_verbose,
            "superbrief": self.do_superbrief,
            "version": self.do_version,
            "help": self.do_help,
            "diagnose": self.do_diagnose,

            # Combat
            "attack": self.do_attack,
            "kill": self.do_attack,

            # Physical actions
            "push": self.do_push,
            "pull": self.do_pull,
            "turn": self.do_turn,

            # Light
            "light": self.do_light,
            "extinguish": self.do_extinguish,

            # Food/drink
            "eat": self.do_eat,
            "drink": self.do_drink,

            # Communication
            "hello": self.do_hello,
            "yell": self.do_yell,

            # Special
            "climb": self.do_climb,
            "jump": self.do_jump,
        }

    def execute(self, command: ParsedCommand) -> VerbResult:
        """Execute a parsed command."""
        if command.error:
            return VerbResult(success=False, message=command.error, end_turn=False)

        if not command.verb:
            return VerbResult(
                success=False,
                message="I don't understand that.",
                end_turn=False,
            )

        handler = self.handlers.get(command.verb)
        if handler:
            return handler(command)
        else:
            return VerbResult(
                success=False,
                message=f"I don't know how to {command.verb}.",
                end_turn=False,
            )

    # ============ Movement ============

    def do_walk(self, cmd: ParsedCommand) -> VerbResult:
        """Handle movement commands."""
        if not cmd.direction:
            return VerbResult(
                success=False,
                message="Which direction do you want to go?",
                end_turn=False,
            )

        direction = self.game.world.parse_direction(cmd.direction)
        if not direction:
            return VerbResult(
                success=False,
                message=f"I don't know the direction '{cmd.direction}'.",
                end_turn=False,
            )

        success, message = self.game.world.move_player(self.game.state, direction)
        return VerbResult(success=success, message=message)

    # ============ Looking ============

    def do_look(self, cmd: ParsedCommand) -> VerbResult:
        """Handle LOOK command."""
        room = self.game.world.get_room(self.game.state.current_room)
        if not room:
            return VerbResult(success=False, message="You are nowhere!")

        description = self.game.world.describe_room(
            self.game.state, room, force_long=True
        )
        return VerbResult(success=True, message=description, end_turn=False)

    def do_examine(self, cmd: ParsedCommand) -> VerbResult:
        """Handle EXAMINE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to examine?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if obj.examine:
            return VerbResult(success=True, message=obj.examine, end_turn=False)
        elif obj.description:
            return VerbResult(success=True, message=obj.description, end_turn=False)
        else:
            return VerbResult(
                success=True,
                message=f"There's nothing special about the {obj.name}.",
                end_turn=False,
            )

    def do_read(self, cmd: ParsedCommand) -> VerbResult:
        """Handle READ command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to read?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_readable():
            return VerbResult(
                success=False,
                message=f"There's nothing to read on the {obj.name}.",
                end_turn=False,
            )

        if obj.read_text:
            return VerbResult(success=True, message=obj.read_text, end_turn=False)
        else:
            return VerbResult(
                success=True,
                message=f"The {obj.name} has nothing written on it.",
                end_turn=False,
            )

    # ============ Object Manipulation ============

    def do_take(self, cmd: ParsedCommand) -> VerbResult:
        """Handle TAKE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to take?",
                end_turn=False,
            )

        if cmd.direct_object == "all":
            return self._take_all()

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)

        # Check if already carrying
        if obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're already carrying that.",
                end_turn=False,
            )

        # Check if takeable
        if not obj.is_takeable():
            return VerbResult(
                success=False,
                message=f"You can't take the {obj.name}.",
                end_turn=False,
            )

        # Check weight limit
        inventory = self.game.world.get_inventory(self.game.state)
        total_weight = sum(o.size for o in inventory)
        if total_weight + obj.size > self.game.state.max_load:
            return VerbResult(
                success=False,
                message="Your load is too heavy.",
                end_turn=False,
            )

        # Take the object
        self.game.state.move_object_to_actor(obj.id, "player")
        self.game.state.last_it = obj.id

        return VerbResult(success=True, message="Taken.")

    def _take_all(self) -> VerbResult:
        """Take all visible takeable objects in room."""
        taken = []
        room_id = self.game.state.current_room

        for obj_id in self.game.state.objects_in_room(room_id):
            obj = self.game.world.get_object(obj_id)
            if obj and obj.is_takeable() and obj.is_visible():
                inventory = self.game.world.get_inventory(self.game.state)
                total_weight = sum(o.size for o in inventory)
                if total_weight + obj.size <= self.game.state.max_load:
                    self.game.state.move_object_to_actor(obj.id, "player")
                    taken.append(obj.name)

        if taken:
            return VerbResult(
                success=True,
                message=f"Taken: {', '.join(taken)}",
            )
        else:
            return VerbResult(
                success=False,
                message="There's nothing here to take.",
                end_turn=False,
            )

    def do_drop(self, cmd: ParsedCommand) -> VerbResult:
        """Handle DROP command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to drop?",
                end_turn=False,
            )

        if cmd.direct_object == "all":
            return self._drop_all()

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"You don't have any {cmd.direct_object}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)

        if not obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're not carrying that.",
                end_turn=False,
            )

        self.game.state.move_object_to_room(obj.id, self.game.state.current_room)
        return VerbResult(success=True, message="Dropped.")

    def _drop_all(self) -> VerbResult:
        """Drop all carried objects."""
        dropped = []

        for obj_id in list(self.game.state.objects_held_by("player")):
            obj = self.game.world.get_object(obj_id)
            if obj:
                self.game.state.move_object_to_room(
                    obj.id, self.game.state.current_room
                )
                dropped.append(obj.name)

        if dropped:
            return VerbResult(
                success=True,
                message=f"Dropped: {', '.join(dropped)}",
            )
        else:
            return VerbResult(
                success=False,
                message="You're not carrying anything.",
                end_turn=False,
            )

    def do_put(self, cmd: ParsedCommand) -> VerbResult:
        """Handle PUT command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to put?",
                end_turn=False,
            )

        if not cmd.indirect_object:
            return VerbResult(
                success=False,
                message="Where do you want to put it?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        container = self.game.world.get_object(cmd.indirect_object)

        if not obj:
            return VerbResult(
                success=False,
                message=f"You don't have any {cmd.direct_object}.",
                end_turn=False,
            )

        if not container:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.indirect_object} here.",
                end_turn=False,
            )

        if not container.is_container():
            return VerbResult(
                success=False,
                message=f"You can't put things in the {container.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're not carrying that.",
                end_turn=False,
            )

        # Check container capacity
        contents = self.game.state.objects_in_container(container.id)
        total_size = sum(
            self.game.world.get_object(oid).size
            for oid in contents
            if self.game.world.get_object(oid)
        )

        if container.capacity > 0 and total_size + obj.size > container.capacity:
            return VerbResult(
                success=False,
                message=f"The {container.name} is full.",
                end_turn=False,
            )

        self.game.state.move_object_to_container(obj.id, container.id)
        return VerbResult(success=True, message="Done.")

    def do_throw(self, cmd: ParsedCommand) -> VerbResult:
        """Handle THROW command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to throw?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"You don't have any {cmd.direct_object}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're not carrying that.",
                end_turn=False,
            )

        self.game.state.move_object_to_room(obj.id, self.game.state.current_room)
        return VerbResult(
            success=True,
            message=f"The {obj.name} hits the ground and lies there.",
        )

    def do_give(self, cmd: ParsedCommand) -> VerbResult:
        """Handle GIVE command."""
        if not cmd.direct_object or not cmd.indirect_object:
            return VerbResult(
                success=False,
                message="Give what to whom?",
                end_turn=False,
            )

        return VerbResult(
            success=False,
            message="There's no one here to give things to.",
            end_turn=False,
        )

    # ============ Container Operations ============

    def do_open(self, cmd: ParsedCommand) -> VerbResult:
        """Handle OPEN command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to open?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_open():
            return VerbResult(
                success=False,
                message=f"The {obj.name} cannot be opened.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)

        # Check if already open
        if obj_state.flags2 & ObjectFlag2.OPENBT:
            return VerbResult(
                success=False,
                message=f"The {obj.name} is already open.",
                end_turn=False,
            )

        obj_state.flags2 |= ObjectFlag2.OPENBT
        self.game.state.last_it = obj.id

        # Describe contents if container
        if obj.is_container():
            contents = self.game.state.objects_in_container(obj.id)
            if contents:
                items = []
                for item_id in contents:
                    item = self.game.world.get_object(item_id)
                    if item:
                        items.append(item.name)
                return VerbResult(
                    success=True,
                    message=f"Opening the {obj.name} reveals: {', '.join(items)}.",
                )

        return VerbResult(success=True, message="Opened.")

    def do_close(self, cmd: ParsedCommand) -> VerbResult:
        """Handle CLOSE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to close?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_open():
            return VerbResult(
                success=False,
                message=f"The {obj.name} cannot be closed.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)

        if not (obj_state.flags2 & ObjectFlag2.OPENBT):
            return VerbResult(
                success=False,
                message=f"The {obj.name} is already closed.",
                end_turn=False,
            )

        obj_state.flags2 &= ~ObjectFlag2.OPENBT
        return VerbResult(success=True, message="Closed.")

    # ============ Inventory ============

    def do_inventory(self, cmd: ParsedCommand) -> VerbResult:
        """Handle INVENTORY command."""
        inventory = self.game.world.get_inventory(self.game.state)

        if not inventory:
            return VerbResult(
                success=True,
                message="You are empty-handed.",
                end_turn=False,
            )

        items = [obj.name for obj in inventory]
        return VerbResult(
            success=True,
            message=f"You are carrying:\n  " + "\n  ".join(items),
            end_turn=False,
        )

    # ============ Meta Commands ============

    def do_wait(self, cmd: ParsedCommand) -> VerbResult:
        """Handle WAIT command."""
        return VerbResult(success=True, message="Time passes...")

    def do_score(self, cmd: ParsedCommand) -> VerbResult:
        """Handle SCORE command."""
        state = self.game.state
        return VerbResult(
            success=True,
            message=(
                f"Your score is {state.score} (out of {state.max_score}), "
                f"in {state.moves} move{'s' if state.moves != 1 else ''}."
            ),
            end_turn=False,
        )

    def do_quit(self, cmd: ParsedCommand) -> VerbResult:
        """Handle QUIT command."""
        return VerbResult(
            success=True,
            message="QUIT",  # Special marker for game loop
            end_turn=False,
        )

    def do_brief(self, cmd: ParsedCommand) -> VerbResult:
        """Handle BRIEF command."""
        self.game.state.flags.brieff = True
        self.game.state.flags.superf = False
        return VerbResult(
            success=True,
            message="Brief mode enabled. Room descriptions shown once.",
            end_turn=False,
        )

    def do_verbose(self, cmd: ParsedCommand) -> VerbResult:
        """Handle VERBOSE command."""
        self.game.state.flags.brieff = False
        self.game.state.flags.superf = False
        return VerbResult(
            success=True,
            message="Verbose mode enabled. Full descriptions always shown.",
            end_turn=False,
        )

    def do_superbrief(self, cmd: ParsedCommand) -> VerbResult:
        """Handle SUPERBRIEF command."""
        self.game.state.flags.brieff = True
        self.game.state.flags.superf = True
        return VerbResult(
            success=True,
            message="Superbrief mode enabled. Minimal descriptions.",
            end_turn=False,
        )

    def do_version(self, cmd: ParsedCommand) -> VerbResult:
        """Handle VERSION command."""
        return VerbResult(
            success=True,
            message="PyMeshZork 0.1.0 - Python Zork with Meshtastic Multiplayer",
            end_turn=False,
        )

    def do_help(self, cmd: ParsedCommand) -> VerbResult:
        """Handle HELP command."""
        return VerbResult(
            success=True,
            message=self.game.parser.format_help(),
            end_turn=False,
        )

    def do_diagnose(self, cmd: ParsedCommand) -> VerbResult:
        """Handle DIAGNOSE command."""
        state = self.game.state
        return VerbResult(
            success=True,
            message=(
                f"You have died {state.deaths} time{'s' if state.deaths != 1 else ''}.\n"
                f"You are in perfect health."
            ),
            end_turn=False,
        )

    # ============ Combat ============

    def do_attack(self, cmd: ParsedCommand) -> VerbResult:
        """Handle ATTACK/KILL command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to attack?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_villain() and not obj.is_actor():
            return VerbResult(
                success=False,
                message=f"Attacking the {obj.name} would be pointless.",
                end_turn=False,
            )

        # Check for weapon
        weapon = None
        if cmd.indirect_object:
            weapon = self.game.world.get_object(cmd.indirect_object)
        else:
            # Find weapon in inventory
            for obj_id in self.game.state.objects_held_by("player"):
                w = self.game.world.get_object(obj_id)
                if w and w.is_weapon():
                    weapon = w
                    break

        if not weapon:
            return VerbResult(
                success=False,
                message="Strangle him with your bare hands?",
                end_turn=False,
            )

        # Basic combat placeholder - will be expanded
        return VerbResult(
            success=True,
            message=f"You swing the {weapon.name} at the {obj.name}!",
        )

    # ============ Physical Actions ============

    def do_push(self, cmd: ParsedCommand) -> VerbResult:
        """Handle PUSH command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to push?",
                end_turn=False,
            )

        return VerbResult(
            success=True,
            message="Nothing happens.",
            end_turn=False,
        )

    def do_pull(self, cmd: ParsedCommand) -> VerbResult:
        """Handle PULL command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to pull?",
                end_turn=False,
            )

        return VerbResult(
            success=True,
            message="Nothing happens.",
            end_turn=False,
        )

    def do_turn(self, cmd: ParsedCommand) -> VerbResult:
        """Handle TURN command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to turn?",
                end_turn=False,
            )

        return VerbResult(
            success=True,
            message="Nothing happens.",
            end_turn=False,
        )

    # ============ Light ============

    def do_light(self, cmd: ParsedCommand) -> VerbResult:
        """Handle LIGHT command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to light?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_light_source():
            return VerbResult(
                success=False,
                message=f"You can't light the {obj.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if obj_state.flags1 & ObjectFlag1.ONBT:
            return VerbResult(
                success=False,
                message=f"The {obj.name} is already lit.",
                end_turn=False,
            )

        obj_state.flags1 |= ObjectFlag1.ONBT
        return VerbResult(
            success=True,
            message=f"The {obj.name} is now on.",
        )

    def do_extinguish(self, cmd: ParsedCommand) -> VerbResult:
        """Handle EXTINGUISH command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to turn off?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_light_source():
            return VerbResult(
                success=False,
                message=f"You can't turn off the {obj.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not (obj_state.flags1 & ObjectFlag1.ONBT):
            return VerbResult(
                success=False,
                message=f"The {obj.name} is already off.",
                end_turn=False,
            )

        obj_state.flags1 &= ~ObjectFlag1.ONBT
        return VerbResult(
            success=True,
            message=f"The {obj.name} is now off.",
        )

    # ============ Food/Drink ============

    def do_eat(self, cmd: ParsedCommand) -> VerbResult:
        """Handle EAT command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to eat?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_food():
            return VerbResult(
                success=False,
                message=f"I don't think the {obj.name} would agree with you.",
                end_turn=False,
            )

        # Remove the food
        obj_state = self.game.state.get_object_state(obj.id)
        obj_state.room_id = None
        obj_state.actor_id = None
        obj_state.container_id = None

        return VerbResult(success=True, message="Thank you. It hit the spot.")

    def do_drink(self, cmd: ParsedCommand) -> VerbResult:
        """Handle DRINK command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to drink?",
                end_turn=False,
            )

        return VerbResult(
            success=False,
            message="You can't drink that.",
            end_turn=False,
        )

    # ============ Communication ============

    def do_hello(self, cmd: ParsedCommand) -> VerbResult:
        """Handle HELLO command."""
        return VerbResult(
            success=True,
            message="Hello yourself.",
            end_turn=False,
        )

    def do_yell(self, cmd: ParsedCommand) -> VerbResult:
        """Handle YELL command."""
        return VerbResult(
            success=True,
            message="Aaaarrrrgggghhhh!",
            end_turn=False,
        )

    # ============ Special Actions ============

    def do_climb(self, cmd: ParsedCommand) -> VerbResult:
        """Handle CLIMB command."""
        return VerbResult(
            success=False,
            message="There's nothing here to climb.",
            end_turn=False,
        )

    def do_jump(self, cmd: ParsedCommand) -> VerbResult:
        """Handle JUMP command."""
        return VerbResult(
            success=True,
            message="Wheeee!",
            end_turn=False,
        )
