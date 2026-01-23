"""Room-specific action handlers for PyMeshZork puzzles."""

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymeshzork.engine.game import Game
    from pymeshzork.engine.models import Direction


class RoomActionResult:
    """Result from a room action."""

    def __init__(
        self,
        message: str | None = None,
        block_action: bool = False,
        redirect_direction: "Direction | None" = None,
        score_change: int = 0,
    ):
        self.message = message
        self.block_action = block_action
        self.redirect_direction = redirect_direction
        self.score_change = score_change


class RoomActions:
    """Handles room-specific puzzle mechanics."""

    def __init__(self, game: "Game"):
        self.game = game

        # Room action handlers
        self.handlers = {
            "carou": self.action_carousel,
            "lld2": self.action_loud_room,
            "mmach": self.action_machine_room,
            "riddl": self.action_riddle_room,
            "reser": self.action_reservoir,
            "vlbot": self.action_balloon_bottom,
            "vlair": self.action_balloon_air,
        }

    def on_enter_room(self, room_id: str) -> RoomActionResult | None:
        """Called when player enters a room."""
        handler = self.handlers.get(room_id)
        if handler:
            return handler("enter")
        return None

    def on_move(self, room_id: str, direction: "Direction") -> RoomActionResult | None:
        """Called when player tries to move from a room."""
        handler = self.handlers.get(room_id)
        if handler:
            return handler("move", direction=direction)
        return None

    def on_action(self, room_id: str, verb: str, obj_id: str | None = None, **kwargs) -> RoomActionResult | None:
        """Called for special verb actions in a room."""
        handler = self.handlers.get(room_id)
        if handler:
            return handler("action", verb=verb, obj_id=obj_id, **kwargs)
        return None

    # ============ Carousel Room ============

    def action_carousel(self, event: str, **kwargs) -> RoomActionResult | None:
        """Carousel room - directions are randomized unless carousel is off."""
        from pymeshzork.engine.models import Direction

        if event == "enter":
            if not self.game.state.flags.caroff:
                return RoomActionResult(
                    message="You are dizzy from the spinning room.",
                )

        if event == "move":
            direction = kwargs.get("direction")
            if not self.game.state.flags.caroff and direction:
                # Carousel spinning - randomize direction
                directions = [
                    Direction.NORTH, Direction.SOUTH,
                    Direction.EAST, Direction.WEST,
                ]
                # 50% chance to go wrong direction
                if random.random() < 0.5:
                    new_dir = random.choice(directions)
                    if new_dir != direction:
                        return RoomActionResult(
                            message="The spinning room disorients you...",
                            redirect_direction=new_dir,
                        )
        return None

    # ============ Loud Room ============

    def action_loud_room(self, event: str, **kwargs) -> RoomActionResult | None:
        """Loud Room - echo puzzle. Say 'echo' to solve."""
        if event == "enter":
            if not self.game.state.flags.lldf:
                return RoomActionResult(
                    message="The room is deafeningly loud with an incessant roar.",
                )

        if event == "action":
            verb = kwargs.get("verb")
            obj_id = kwargs.get("obj_id")

            # Saying "echo" solves the puzzle
            if verb == "say" and obj_id and obj_id.lower() == "echo":
                if not self.game.state.flags.lldf:
                    self.game.state.flags.lldf = True
                    # Drop the platinum bar
                    bar_state = self.game.state.get_object_state("bar")
                    if bar_state:
                        bar_state.room_id = "lld2"
                    return RoomActionResult(
                        message="The acoustics of the room change subtly. Suddenly, a platinum bar falls from the ceiling and lands at your feet!",
                        score_change=5,
                    )
                else:
                    return RoomActionResult(
                        message="Your voice echoes back: 'echo... echo... echo...'",
                    )

            # Any other loud noise
            if verb in ["yell", "shout", "scream"]:
                return RoomActionResult(
                    message="Your voice is swallowed by the roar. Perhaps a specific word would help?",
                )

        return None

    # ============ Machine Room ============

    def action_machine_room(self, event: str, **kwargs) -> RoomActionResult | None:
        """Machine room - put coal in machine to make diamond."""
        if event == "action":
            verb = kwargs.get("verb")
            obj_id = kwargs.get("obj_id")
            target = kwargs.get("target")

            # Putting coal in machine
            if verb == "put" and obj_id == "coal":
                if target in ["machi", "machine", "receptacle", "recep"]:
                    return self._process_coal_machine()

        return None

    def _process_coal_machine(self) -> RoomActionResult:
        """Process coal in the machine."""
        coal_state = self.game.state.get_object_state("coal")

        if not coal_state.is_held_by("player"):
            return RoomActionResult(
                message="You're not carrying the coal.",
                block_action=True,
            )

        # Check if machine has been activated (need screwdriver)
        # For now, allow the transformation
        coal_state.room_id = None  # Remove coal

        # Create/reveal diamond
        diamond_state = self.game.state.get_object_state("diamo")
        diamond_state.room_id = "mmach"

        return RoomActionResult(
            message="The machine rumbles and shakes. After a moment, it quiets down. Inside the machine, where the coal was, now sits a huge diamond!",
            score_change=10,
        )

    # ============ Riddle Room ============

    def action_riddle_room(self, event: str, **kwargs) -> RoomActionResult | None:
        """Riddle room - answer the riddle to proceed east."""
        if event == "enter":
            if not self.game.state.flags.riddlf:
                return RoomActionResult(
                    message='The inscription reads:\n"What is it that walks on four legs in the morning, two at noon, and three in the evening?"',
                )

        if event == "action":
            verb = kwargs.get("verb")
            obj_id = kwargs.get("obj_id")

            if verb in ["say", "answer"]:
                answer = (obj_id or "").lower()
                if answer in ["man", "a man", "human", "person", "mankind"]:
                    if not self.game.state.flags.riddlf:
                        self.game.state.flags.riddlf = True
                        return RoomActionResult(
                            message="A voice booms: 'Correct!' A passage opens to the east.",
                            score_change=5,
                        )
                    else:
                        return RoomActionResult(
                            message="The passage to the east remains open.",
                        )
                else:
                    return RoomActionResult(
                        message="A voice booms: 'Wrong!' You feel a chill.",
                    )

        if event == "move":
            from pymeshzork.engine.models import Direction
            direction = kwargs.get("direction")
            if direction == Direction.EAST and not self.game.state.flags.riddlf:
                return RoomActionResult(
                    message="An invisible barrier blocks your way. Perhaps you should answer the riddle first.",
                    block_action=True,
                )

        return None

    # ============ Reservoir ============

    def action_reservoir(self, event: str, **kwargs) -> RoomActionResult | None:
        """Reservoir - water level controlled by dam."""
        if event == "enter":
            if self.game.state.flags.lwtidf:
                return RoomActionResult(
                    message="The reservoir is empty, its bottom now exposed.",
                )
            else:
                return RoomActionResult(
                    message="The reservoir stretches before you, dark and deep.",
                )

        if event == "move":
            from pymeshzork.engine.models import Direction
            direction = kwargs.get("direction")

            # Can only cross when water is low
            if direction in [Direction.NORTH, Direction.SOUTH]:
                if not self.game.state.flags.lwtidf:
                    return RoomActionResult(
                        message="The water is too deep to cross. Perhaps you could drain it somehow?",
                        block_action=True,
                    )

        return None

    # ============ Balloon Rooms ============

    def action_balloon_bottom(self, event: str, **kwargs) -> RoomActionResult | None:
        """Balloon at volcano bottom."""
        if event == "enter":
            balloon_state = self.game.state.get_object_state("ballo")
            if balloon_state.room_id == "vlbot":
                return RoomActionResult(
                    message="A hot air balloon is here, tethered to the ground.",
                )
        return None

    def action_balloon_air(self, event: str, **kwargs) -> RoomActionResult | None:
        """Balloon in the air."""
        if event == "enter":
            return RoomActionResult(
                message="You are floating high above the volcano in a hot air balloon.",
            )
        return None


# ============ Verb Extensions for Puzzles ============

def handle_push_button(game: "Game", obj_id: str) -> str | None:
    """Handle pushing buttons/switches for dam control."""
    if obj_id in ["butto", "button", "buton"]:
        room = game.world.get_room(game.state.current_room)
        if room and room.id in ["dam", "maint", "dambas"]:
            # Toggle dam gates
            if game.state.flags.lwtidf:
                game.state.flags.lwtidf = False
                return "You hear a loud rumbling as the dam gates close. Water begins to fill the reservoir."
            else:
                game.state.flags.lwtidf = True
                return "You hear a loud rumbling as the dam gates open. Water drains from the reservoir."

    if obj_id in ["bolt", "wrench"]:
        room = game.world.get_room(game.state.current_room)
        if room and room.id in ["dam", "maint"]:
            return "The bolt turns with a grinding noise."

    return None


def handle_turn_dial(game: "Game", obj_id: str) -> str | None:
    """Handle turning dials/controls."""
    if obj_id in ["dial", "wheel", "control"]:
        room = game.world.get_room(game.state.current_room)
        if room and room.id == "carou":
            # Toggle carousel
            if game.state.flags.caroff:
                game.state.flags.caroff = False
                return "The carousel begins to spin again."
            else:
                game.state.flags.caroff = True
                game.state.flags.carone = True
                return "The carousel slows to a stop. The room is now still."
    return None


def handle_launch_balloon(game: "Game") -> str | None:
    """Handle launching the balloon."""
    balloon_state = game.state.get_object_state("ballo")

    if game.state.current_room != balloon_state.room_id:
        return "You're not in the balloon."

    # Check for fuel/heat source
    brazier_state = game.state.get_object_state("brazi")
    if not brazier_state or not brazier_state.room_id:
        return "The balloon needs a heat source to rise."

    # Launch!
    if balloon_state.room_id == "vlbot":
        balloon_state.room_id = "vlair"
        game.state.current_room = "vlair"
        return "The balloon rises majestically into the air!"

    return "The balloon is already airborne."


def handle_land_balloon(game: "Game") -> str | None:
    """Handle landing the balloon."""
    balloon_state = game.state.get_object_state("ballo")

    if game.state.current_room != balloon_state.room_id:
        return "You're not in the balloon."

    if balloon_state.room_id in ["vlair", "vair1", "vair2"]:
        balloon_state.room_id = "vlbot"
        game.state.current_room = "vlbot"
        return "The balloon descends and lands gently at the bottom of the volcano."

    return "The balloon is already on the ground."
