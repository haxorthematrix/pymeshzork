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
            "fight": self.do_attack,

            # Physical actions
            "push": self.do_push,
            "pull": self.do_pull,
            "turn": self.do_turn,
            "move": self.do_move,
            "lift": self.do_move,
            "raise": self.do_move,

            # Light
            "light": self.do_light,
            "extinguish": self.do_extinguish,
            "burn": self.do_burn,

            # Food/drink
            "eat": self.do_eat,
            "drink": self.do_drink,
            "fill": self.do_fill,
            "empty": self.do_empty,
            "pour": self.do_empty,

            # Communication
            "hello": self.do_hello,
            "yell": self.do_yell,
            "say": self.do_say,
            "shout": self.do_yell,

            # Special object interactions
            "tie": self.do_tie,
            "untie": self.do_untie,
            "inflate": self.do_inflate,
            "deflate": self.do_deflate,
            "wind": self.do_wind,
            "ring": self.do_ring,
            "wave": self.do_wave,
            "rub": self.do_rub,
            "touch": self.do_touch,
            "knock": self.do_knock,

            # Lock/unlock
            "lock": self.do_lock,
            "unlock": self.do_unlock,

            # Special
            "climb": self.do_climb,
            "jump": self.do_jump,
            "swim": self.do_swim,
            "dig": self.do_dig,
            "pray": self.do_pray,
            "curse": self.do_curse,
            "odysseus": self.do_odysseus,
            "ulysses": self.do_odysseus,
            "echo": self.do_echo,
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

        # Check if this is something that can be opened (container or door)
        if not obj.is_container() and not obj.is_door():
            return VerbResult(
                success=False,
                message=f"You can't open the {obj.name}.",
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

        # Check if this is something that can be closed (container or door)
        if not obj.is_container() and not obj.is_door():
            return VerbResult(
                success=False,
                message=f"You can't close the {obj.name}.",
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
        import random

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

        # Check if target is in the room
        obj_state = self.game.state.get_object_state(obj.id)
        if obj_state.room_id != self.game.state.current_room:
            return VerbResult(
                success=False,
                message=f"The {obj.name} isn't here.",
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

        # Engage in combat
        messages = [f"You swing the {weapon.name} at the {obj.name}!"]

        # Calculate hit chance (base 50% + weapon bonus)
        weapon_bonus = weapon.value if weapon.value else 0
        hit_chance = min(50 + weapon_bonus, 85)

        if random.randint(1, 100) <= hit_chance:
            # Hit! Calculate damage
            damage = random.randint(1, 5) + (weapon_bonus // 10)

            # Track damage on villain
            villain_wounds = obj_state.properties.get("wounds", 0) + damage
            obj_state.properties["wounds"] = villain_wounds

            # Check if villain is defeated
            villain_health = obj_state.properties.get("health", 5)
            if villain_wounds >= villain_health:
                messages.append(f"Your blow strikes true! The {obj.name} falls dead!")
                # Remove villain
                self.game.events.kill_villain(obj.id)
                # Set puzzle flags for specific villains
                if obj.id == "troll":
                    self.game.state.flags.trollf = True
                elif obj.id == "thief":
                    self.game.state.flags.thfenf = True
                elif obj.id in ["cyclo", "cyclops"]:
                    self.game.state.flags.cyclof = True
                return VerbResult(
                    success=True,
                    message="\n".join(messages),
                    score_change=10,
                )
            else:
                hit_msgs = [
                    f"You wound the {obj.name}!",
                    f"Your blow connects with the {obj.name}!",
                    f"The {obj.name} staggers from your attack!",
                ]
                messages.append(random.choice(hit_msgs))
        else:
            miss_msgs = [
                f"You miss the {obj.name}!",
                f"The {obj.name} parries your attack!",
                f"Your swing goes wide!",
            ]
            messages.append(random.choice(miss_msgs))

        # Activate villain for counterattack
        self.game.events.activate_villain(obj.id)

        return VerbResult(
            success=True,
            message="\n".join(messages),
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
        from pymeshzork.engine.models import EventID

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

        # Start appropriate timer based on light source
        if obj.id in ["lamp", "lante", "lantern"]:
            # Lantern has battery life
            remaining = obj_state.properties.get("light_remaining", 350)
            if remaining > 0:
                self.game.events.set_event(EventID.LANTERN, 1)
            else:
                obj_state.flags1 &= ~ObjectFlag1.ONBT
                return VerbResult(
                    success=False,
                    message="The lamp's batteries are dead.",
                    end_turn=False,
                )
        elif obj.id in ["match", "matches"]:
            # Match burns out quickly
            self.game.events.set_event(EventID.MATCH, 2)
        elif obj.id in ["candl", "candle", "candles"]:
            # Candles last longer
            self.game.events.set_event(EventID.CANDLE, 50)

        return VerbResult(
            success=True,
            message=f"The {obj.name} is now on.",
        )

    def do_extinguish(self, cmd: ParsedCommand) -> VerbResult:
        """Handle EXTINGUISH command."""
        from pymeshzork.engine.models import EventID

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

        # Cancel timers when turning off
        if obj.id in ["lamp", "lante", "lantern"]:
            self.game.events.cancel_event(EventID.LANTERN)
        elif obj.id in ["match", "matches"]:
            self.game.events.cancel_event(EventID.MATCH)
        elif obj.id in ["candl", "candle", "candles"]:
            self.game.events.cancel_event(EventID.CANDLE)

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

    # ============ Move/Lift ============

    def do_move(self, cmd: ParsedCommand) -> VerbResult:
        """Handle MOVE/LIFT/RAISE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to move?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        # Special case: rug reveals trap door
        if obj.id == "rug":
            room = self.game.world.get_room(self.game.state.current_room)
            if room and room.id == "lroom":
                # Check if already moved
                obj_state = self.game.state.get_object_state(obj.id)
                if obj_state.flags2 & ObjectFlag2.TCHBT:
                    return VerbResult(
                        success=True,
                        message="Having moved the carpet once, you find it impossible to move it again.",
                        end_turn=False,
                    )
                obj_state.flags2 |= ObjectFlag2.TCHBT
                # Set puzzle flag to enable trap door exit
                self.game.state.flags.rug_moved = True
                return VerbResult(
                    success=True,
                    message="With great effort, the rug is moved to one side of the room, revealing the dusty cover of a closed trap door.",
                    score_change=2,
                )

        # Special case: leaves might reveal grating
        if obj.id == "leave":
            room = self.game.world.get_room(self.game.state.current_room)
            if room and room.id == "mgrat":
                return VerbResult(
                    success=True,
                    message="A grating appears beneath the pile of leaves!",
                )

        # Default behavior
        if obj.is_takeable():
            return VerbResult(
                success=True,
                message=f"Moving the {obj.name} reveals nothing.",
                end_turn=False,
            )
        else:
            return VerbResult(
                success=False,
                message=f"You can't move the {obj.name}.",
                end_turn=False,
            )

    # ============ Tie/Untie ============

    def do_tie(self, cmd: ParsedCommand) -> VerbResult:
        """Handle TIE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to tie?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"You don't have any {cmd.direct_object}.",
                end_turn=False,
            )

        # Check if it can be tied (rope)
        if obj.id != "rope":
            return VerbResult(
                success=False,
                message=f"You can't tie the {obj.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're not carrying the rope.",
                end_turn=False,
            )

        # Check if we're in the dome room
        room = self.game.world.get_room(self.game.state.current_room)
        if not room or room.id != "dome":
            return VerbResult(
                success=False,
                message="There's nothing here to tie the rope to.",
                end_turn=False,
            )

        # Tie rope to railing
        if cmd.indirect_object and cmd.indirect_object not in ["railing", "rail"]:
            return VerbResult(
                success=False,
                message=f"You can't tie the rope to that.",
                end_turn=False,
            )

        # Mark rope as tied
        obj_state.flags2 |= ObjectFlag2.TIEBT
        # Move rope to room
        self.game.state.move_object_to_room(obj.id, room.id)
        # Set puzzle flag to enable dome-torch room passage
        self.game.state.flags.rope_tied = True

        return VerbResult(
            success=True,
            message="The rope is now tied to the railing and dangles down into the darkness below.",
            score_change=2,
        )

    def do_untie(self, cmd: ParsedCommand) -> VerbResult:
        """Handle UNTIE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to untie?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not (obj_state.flags2 & ObjectFlag2.TIEBT):
            return VerbResult(
                success=False,
                message=f"The {obj.name} isn't tied to anything.",
                end_turn=False,
            )

        obj_state.flags2 &= ~ObjectFlag2.TIEBT
        self.game.state.move_object_to_actor(obj.id, "player")
        # Clear puzzle flag - rope no longer tied
        if obj.id == "rope":
            self.game.state.flags.rope_tied = False

        return VerbResult(
            success=True,
            message=f"The {obj.name} is now untied.",
        )

    # ============ Inflate/Deflate ============

    def do_inflate(self, cmd: ParsedCommand) -> VerbResult:
        """Handle INFLATE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to inflate?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        # Only the boat can be inflated
        if obj.id not in ["iboat", "boat"]:
            return VerbResult(
                success=False,
                message=f"You can't inflate the {obj.name}.",
                end_turn=False,
            )

        # Need a pump
        pump = self.game.world.get_object("pump")
        pump_state = self.game.state.get_object_state("pump") if pump else None

        if not pump_state or not pump_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You don't have anything to inflate it with.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if obj_state.flags2 & ObjectFlag2.VEHBT:
            return VerbResult(
                success=False,
                message="The boat is already inflated.",
                end_turn=False,
            )

        # Inflate the boat
        obj_state.flags2 |= ObjectFlag2.VEHBT

        return VerbResult(
            success=True,
            message="The boat inflates and is now ready to board.",
        )

    def do_deflate(self, cmd: ParsedCommand) -> VerbResult:
        """Handle DEFLATE command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to deflate?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if obj.id not in ["iboat", "boat", "rboat"]:
            return VerbResult(
                success=False,
                message=f"You can't deflate the {obj.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not (obj_state.flags2 & ObjectFlag2.VEHBT):
            return VerbResult(
                success=False,
                message="The boat is already deflated.",
                end_turn=False,
            )

        obj_state.flags2 &= ~ObjectFlag2.VEHBT

        return VerbResult(
            success=True,
            message="The boat deflates into a pile of plastic.",
        )

    # ============ Wind ============

    def do_wind(self, cmd: ParsedCommand) -> VerbResult:
        """Handle WIND command (for the clockwork canary)."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to wind?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        # Only the canary can be wound
        if obj.id not in ["canar", "canary"]:
            return VerbResult(
                success=False,
                message=f"You can't wind the {obj.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're not carrying the canary.",
                end_turn=False,
            )

        # The canary sings
        room = self.game.world.get_room(self.game.state.current_room)

        # Special case: in the forest near the tree, the bird's song attracts the songbird
        if room and room.id in ["fore3", "uptree"]:
            return VerbResult(
                success=True,
                message="The canary begins to sing. From somewhere nearby, an answering song is heard. A songbird flies down and lands on the branch beside you!",
                score_change=2,
            )

        return VerbResult(
            success=True,
            message="The canary begins to sing a beautiful melody.",
        )

    # ============ Ring ============

    def do_ring(self, cmd: ParsedCommand) -> VerbResult:
        """Handle RING command (for the bell)."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to ring?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if obj.id != "bell":
            return VerbResult(
                success=False,
                message=f"You can't ring the {obj.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're not carrying the bell.",
                end_turn=False,
            )

        room = self.game.world.get_room(self.game.state.current_room)

        # Special case: in Hades entrance, ringing the bell is part of the exorcism
        if room and room.id == "entrc":
            # Check if holding candles and book too
            candles = self.game.world.get_object("candl")
            book = self.game.world.get_object("book")
            candles_state = self.game.state.get_object_state("candl") if candles else None
            book_state = self.game.state.get_object_state("book") if book else None

            if candles_state and candles_state.is_held_by("player"):
                if book_state and book_state.is_held_by("player"):
                    # Successful exorcism - open gates of Hades
                    self.game.state.flags.gates_open = True
                    return VerbResult(
                        success=True,
                        message="The bell rings with a pure tone that echoes through the chamber. The spirits begin to stir...\n\nThe candles flicker with an eerie light. With a great creaking, the gates of Hades swing open!",
                        score_change=5,
                    )
                return VerbResult(
                    success=True,
                    message="The bell rings but nothing happens. Perhaps you need something else?",
                )

        return VerbResult(
            success=True,
            message="The bell rings clearly.",
        )

    # ============ Wave ============

    def do_wave(self, cmd: ParsedCommand) -> VerbResult:
        """Handle WAVE command (for the scepter)."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to wave?",
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

        room = self.game.world.get_room(self.game.state.current_room)

        # Special case: waving scepter at rainbow
        if obj.id in ["scept", "scepter", "sceptre"]:
            if room and room.id == "mrain":
                return VerbResult(
                    success=True,
                    message="The scepter glows brightly and a shimmering path appears across the rainbow! You may now cross safely.",
                    score_change=5,
                )

        return VerbResult(
            success=True,
            message=f"You wave the {obj.name}. Nothing happens.",
            end_turn=False,
        )

    # ============ Touch/Rub ============

    def do_touch(self, cmd: ParsedCommand) -> VerbResult:
        """Handle TOUCH command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to touch?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        # Special case: mirror in mirror room
        if obj.id == "mirro" or "mirror" in obj.id:
            return VerbResult(
                success=True,
                message="There is a faint tingling sensation as you touch the mirror.",
            )

        return VerbResult(
            success=True,
            message=f"Touching the {obj.name} doesn't seem to do anything.",
            end_turn=False,
        )

    def do_rub(self, cmd: ParsedCommand) -> VerbResult:
        """Handle RUB command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to rub?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        return VerbResult(
            success=True,
            message=f"Rubbing the {obj.name} doesn't seem to do anything.",
            end_turn=False,
        )

    def do_knock(self, cmd: ParsedCommand) -> VerbResult:
        """Handle KNOCK command."""
        if not cmd.direct_object:
            return VerbResult(
                success=True,
                message="Knock knock. Who's there?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if obj and obj.is_door():
            return VerbResult(
                success=True,
                message="Nobody's home.",
                end_turn=False,
            )

        return VerbResult(
            success=True,
            message="Why would you want to knock on that?",
            end_turn=False,
        )

    # ============ Lock/Unlock ============

    def do_unlock(self, cmd: ParsedCommand) -> VerbResult:
        """Handle UNLOCK command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to unlock?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        # Check for key in inventory
        keys = self.game.world.get_object("keys")
        keys_state = self.game.state.get_object_state("keys") if keys else None

        if not keys_state or not keys_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You don't have anything to unlock it with.",
                end_turn=False,
            )

        # Special case: grating
        if obj.id in ["grate", "grati", "grating"]:
            obj_state = self.game.state.get_object_state(obj.id)
            if obj_state.flags2 & ObjectFlag2.OPENBT:
                return VerbResult(
                    success=False,
                    message="The grating is already unlocked.",
                    end_turn=False,
                )
            obj_state.flags2 |= ObjectFlag2.OPENBT
            # Set puzzle flag to enable grating passage
            self.game.state.flags.grate_open = True
            return VerbResult(
                success=True,
                message="The grating is now unlocked.",
            )

        if not obj.is_door():
            return VerbResult(
                success=False,
                message=f"You can't unlock the {obj.name}.",
                end_turn=False,
            )

        return VerbResult(
            success=True,
            message=f"The {obj.name} is now unlocked.",
        )

    def do_lock(self, cmd: ParsedCommand) -> VerbResult:
        """Handle LOCK command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to lock?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_door():
            return VerbResult(
                success=False,
                message=f"You can't lock the {obj.name}.",
                end_turn=False,
            )

        return VerbResult(
            success=True,
            message=f"The {obj.name} is now locked.",
        )

    # ============ Burn ============

    def do_burn(self, cmd: ParsedCommand) -> VerbResult:
        """Handle BURN command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to burn?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        # Check if we have something to burn with (match or torch)
        has_fire = False
        for item_id in self.game.state.objects_held_by("player"):
            item = self.game.world.get_object(item_id)
            if item and item.id in ["match", "torch"]:
                item_state = self.game.state.get_object_state(item.id)
                if item_state.flags1 & ObjectFlag1.ONBT:
                    has_fire = True
                    break

        if not has_fire:
            return VerbResult(
                success=False,
                message="You don't have anything to burn it with.",
                end_turn=False,
            )

        # Check if burnable
        if not (obj.flags1 & ObjectFlag1.BURNBT):
            return VerbResult(
                success=False,
                message=f"The {obj.name} won't burn.",
                end_turn=False,
            )

        # Burn the object (remove it)
        obj_state = self.game.state.get_object_state(obj.id)
        obj_state.room_id = None
        obj_state.actor_id = None
        obj_state.container_id = None

        return VerbResult(
            success=True,
            message=f"The {obj.name} burns up in a puff of smoke.",
        )

    # ============ Fill/Empty ============

    def do_fill(self, cmd: ParsedCommand) -> VerbResult:
        """Handle FILL command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to fill?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        # Only bottle can be filled
        if obj.id != "bottl":
            return VerbResult(
                success=False,
                message=f"You can't fill the {obj.name}.",
                end_turn=False,
            )

        obj_state = self.game.state.get_object_state(obj.id)
        if not obj_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You're not carrying the bottle.",
                end_turn=False,
            )

        # Check if near water
        room = self.game.world.get_room(self.game.state.current_room)

        if not room or not room.is_water():
            return VerbResult(
                success=False,
                message="There's no water here.",
                end_turn=False,
            )

        # Add water to bottle
        water = self.game.world.get_object("water")
        if water:
            self.game.state.move_object_to_container("water", "bottl")

        return VerbResult(
            success=True,
            message="The bottle is now full of water.",
        )

    def do_empty(self, cmd: ParsedCommand) -> VerbResult:
        """Handle EMPTY/POUR command."""
        if not cmd.direct_object:
            return VerbResult(
                success=False,
                message="What do you want to empty?",
                end_turn=False,
            )

        obj = self.game.world.get_object(cmd.direct_object)
        if not obj:
            return VerbResult(
                success=False,
                message=f"I don't see any {cmd.direct_object} here.",
                end_turn=False,
            )

        if not obj.is_container():
            return VerbResult(
                success=False,
                message=f"You can't empty the {obj.name}.",
                end_turn=False,
            )

        # Empty contents to current room
        contents = list(self.game.state.objects_in_container(obj.id))
        if not contents:
            return VerbResult(
                success=True,
                message=f"The {obj.name} is already empty.",
                end_turn=False,
            )

        for item_id in contents:
            self.game.state.move_object_to_room(item_id, self.game.state.current_room)

        return VerbResult(
            success=True,
            message=f"The {obj.name} is now empty.",
        )

    # ============ Special verbs ============

    def do_swim(self, cmd: ParsedCommand) -> VerbResult:
        """Handle SWIM command."""
        room = self.game.world.get_room(self.game.state.current_room)

        if room and room.is_water():
            return VerbResult(
                success=True,
                message="You paddle around for a bit.",
            )

        return VerbResult(
            success=False,
            message="There's no water here to swim in.",
            end_turn=False,
        )

    def do_dig(self, cmd: ParsedCommand) -> VerbResult:
        """Handle DIG command."""
        # Check for shovel
        shovel = self.game.world.get_object("shove")
        shovel_state = self.game.state.get_object_state("shove") if shovel else None

        if not shovel_state or not shovel_state.is_held_by("player"):
            return VerbResult(
                success=False,
                message="You have nothing to dig with.",
                end_turn=False,
            )

        room = self.game.world.get_room(self.game.state.current_room)

        # Special case: sandy beach reveals scarab
        if room and room.id == "sbeac":
            scarab = self.game.world.get_object("scara")
            if scarab:
                scarab_state = self.game.state.get_object_state("scara")
                if not scarab_state.room_id:
                    self.game.state.move_object_to_room("scara", room.id)
                    return VerbResult(
                        success=True,
                        message="You uncover a beautiful jeweled scarab!",
                        score_change=5,
                    )

        return VerbResult(
            success=True,
            message="You dig for a while but find nothing.",
        )

    def do_pray(self, cmd: ParsedCommand) -> VerbResult:
        """Handle PRAY command."""
        room = self.game.world.get_room(self.game.state.current_room)

        # Special case: in temple
        if room and room.id in ["temp1", "temp2"]:
            return VerbResult(
                success=True,
                message="Your prayer is answered by a faint humming sound.",
            )

        return VerbResult(
            success=True,
            message="If you pray enough, your prayers may be answered.",
            end_turn=False,
        )

    def do_curse(self, cmd: ParsedCommand) -> VerbResult:
        """Handle CURSE command."""
        return VerbResult(
            success=True,
            message="Such language in a family adventure!",
            end_turn=False,
        )

    def do_odysseus(self, cmd: ParsedCommand) -> VerbResult:
        """Handle ODYSSEUS/ULYSSES command (defeats cyclops)."""
        room = self.game.world.get_room(self.game.state.current_room)

        if not room or room.id != "mcycl":
            return VerbResult(
                success=False,
                message="Nothing happens.",
                end_turn=False,
            )

        cyclops = self.game.world.get_object("cyclo")
        if not cyclops:
            return VerbResult(
                success=False,
                message="Nothing happens.",
                end_turn=False,
            )

        cyclops_state = self.game.state.get_object_state("cyclo")
        if not cyclops_state.room_id:
            return VerbResult(
                success=False,
                message="The cyclops isn't here.",
                end_turn=False,
            )

        # Defeat the cyclops!
        cyclops_state.room_id = None  # Remove cyclops
        # Set puzzle flag - cyclops is gone
        self.game.state.flags.cyclof = True

        return VerbResult(
            success=True,
            message='The cyclops cowers in terror! "No, not again! NOBODY will get me this time!" The cyclops flees through a door which appears in the west wall, slamming it behind him.',
            score_change=10,
        )

    def do_echo(self, cmd: ParsedCommand) -> VerbResult:
        """Handle ECHO command (for echo room)."""
        room = self.game.world.get_room(self.game.state.current_room)

        if room and room.id == "echor":
            return VerbResult(
                success=True,
                message="echo ... echo ... echo ...",
            )

        return VerbResult(
            success=True,
            message="Echo!",
            end_turn=False,
        )

    def do_say(self, cmd: ParsedCommand) -> VerbResult:
        """Handle SAY command."""
        if not cmd.direct_object:
            return VerbResult(
                success=True,
                message="You mutter to yourself.",
                end_turn=False,
            )

        # Check for magic words
        word = cmd.direct_object.lower()

        if word in ["odysseus", "ulysses"]:
            return self.do_odysseus(cmd)

        if word == "echo":
            return self.do_echo(cmd)

        if word in ["xyzzy", "plugh", "plover"]:
            return VerbResult(
                success=True,
                message="A hollow voice says 'Fool.'",
            )

        return VerbResult(
            success=True,
            message=f'You say "{cmd.direct_object}" but nothing happens.',
            end_turn=False,
        )
