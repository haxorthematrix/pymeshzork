"""Event/clock system for PyMeshZork - timed triggers and demons."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from pymeshzork.engine.models import EventID

if TYPE_CHECKING:
    from pymeshzork.engine.game import Game


@dataclass
class EventResult:
    """Result of an event firing."""

    message: str | None = None
    player_dies: bool = False
    score_change: int = 0


class EventManager:
    """Manages timed events and demons (recurring processes)."""

    def __init__(self, game: "Game") -> None:
        """Initialize event manager with game reference."""
        self.game = game

        # Event handlers mapped by event ID
        self.handlers: dict[str, Callable[[], EventResult]] = {
            EventID.LANTERN: self.handle_lantern,
            EventID.MATCH: self.handle_match,
            EventID.CANDLE: self.handle_candle,
            EventID.FUSE: self.handle_fuse,
            EventID.VILLAIN: self.handle_villain,
        }

        # Demon handlers (run every turn)
        self.demons: dict[str, Callable[[], EventResult | None]] = {
            "thief": self.demon_thief,
            "sword": self.demon_sword,
        }

    def tick(self) -> list[EventResult]:
        """Process one turn of events. Returns list of results."""
        results = []

        # Process timed events
        for event_id, event_state in self.game.state.event_states.items():
            if event_state.active and event_state.ticks > 0:
                event_state.ticks -= 1

                if event_state.ticks == 0:
                    # Event fires
                    handler = self.handlers.get(event_id)
                    if handler:
                        result = handler()
                        if result.message:
                            results.append(result)

        # Process demons
        for demon_name, demon_handler in self.demons.items():
            result = demon_handler()
            if result and result.message:
                results.append(result)

        return results

    def set_event(self, event_id: str, ticks: int, active: bool = True) -> None:
        """Set or update an event timer."""
        event_state = self.game.state.get_event_state(event_id)
        event_state.ticks = ticks
        event_state.active = active

    def cancel_event(self, event_id: str) -> None:
        """Cancel an event."""
        event_state = self.game.state.get_event_state(event_id)
        event_state.active = False
        event_state.ticks = 0

    def is_event_active(self, event_id: str) -> bool:
        """Check if an event is active."""
        event_state = self.game.state.get_event_state(event_id)
        return event_state.active

    # ============ Event Handlers ============

    def handle_lantern(self) -> EventResult:
        """Handle lantern timer - battery runs out."""
        lamp_state = self.game.state.get_object_state("lamp")

        # Get remaining light
        remaining = lamp_state.properties.get("light_remaining", 0)

        if remaining <= 0:
            # Lamp dies
            from pymeshzork.engine.models import ObjectFlag1
            lamp_state.flags1 &= ~ObjectFlag1.ONBT
            return EventResult(
                message="Your lamp has run out of power.",
            )
        elif remaining <= 30:
            # Lamp is flickering
            lamp_state.properties["light_remaining"] = remaining - 1
            self.set_event(EventID.LANTERN, 1)  # Check again next turn
            if remaining == 30:
                return EventResult(
                    message="Your lamp is getting dim.",
                )
            elif remaining == 10:
                return EventResult(
                    message="Your lamp is nearly dead.",
                )

        return EventResult()

    def handle_match(self) -> EventResult:
        """Handle match burning out."""
        return EventResult(
            message="The match has gone out.",
        )

    def handle_candle(self) -> EventResult:
        """Handle candles burning out."""
        return EventResult(
            message="The candles have burned out.",
        )

    def handle_fuse(self) -> EventResult:
        """Handle fuse burning - explosion!"""
        # Check where the brick is
        brick_state = self.game.state.get_object_state("brick")
        if brick_state.room_id:
            # Explosion in a room
            if brick_state.room_id == self.game.state.current_room:
                return EventResult(
                    message="BOOOOOM! The blast knocks you out cold!",
                    player_dies=True,
                )
            else:
                return EventResult(
                    message="You hear a muffled explosion in the distance.",
                )
        return EventResult()

    def handle_villain(self) -> EventResult:
        """Handle villain movement and attacks."""
        # Placeholder for villain AI
        return EventResult()

    # ============ Demon Handlers ============

    def demon_thief(self) -> EventResult | None:
        """Thief demon - controls thief behavior."""
        thief_state = self.game.state.thief_state

        if not thief_state.active:
            return None

        # Thief behavior will be expanded
        # For now, just track if thief is in player's room
        thief_obj_state = self.game.state.get_object_state("thief")
        if thief_obj_state.room_id == self.game.state.current_room:
            thief_state.thief_here = True
        else:
            thief_state.thief_here = False

        return None

    def demon_sword(self) -> EventResult | None:
        """Sword demon - controls sword glow."""
        thief_state = self.game.state.thief_state

        if not thief_state.sword_active:
            return None

        sword_state = self.game.state.get_object_state("sword")

        # Check if player has sword
        if not sword_state.is_held_by("player"):
            thief_state.sword_glow = 0
            return None

        # Check for nearby enemies
        room_id = self.game.state.current_room
        enemies_near = False

        for obj_id in self.game.state.objects_in_room(room_id):
            obj = self.game.world.get_object(obj_id)
            if obj and obj.is_villain():
                enemies_near = True
                break

        # Update sword glow
        old_glow = thief_state.sword_glow

        if enemies_near:
            thief_state.sword_glow = 2  # Bright glow
        else:
            # Check adjacent rooms
            thief_state.sword_glow = 0

        # Report changes
        if thief_state.sword_glow != old_glow:
            if thief_state.sword_glow == 2:
                return EventResult(
                    message="Your sword is glowing with a bright blue light!",
                )
            elif thief_state.sword_glow == 1:
                return EventResult(
                    message="Your sword is glowing with a faint blue glow.",
                )
            elif old_glow > 0:
                return EventResult(
                    message="Your sword is no longer glowing.",
                )

        return None


# Grue handling
def check_grue(game: "Game") -> str | None:
    """Check if player is eaten by a grue in darkness."""
    room = game.world.get_room(game.state.current_room)
    if not room:
        return None

    if not game.world.is_room_lit(game.state, room):
        # In darkness - high chance of grue attack
        import random
        if random.random() < 0.25:  # 25% chance per turn
            return (
                "Oh no! You have walked into the slavering fangs of a lurking grue!"
            )
    return None
