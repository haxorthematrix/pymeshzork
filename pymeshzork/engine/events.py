"""Event/clock system for PyMeshZork - timed triggers and demons."""

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from pymeshzork.engine.models import EventID, ObjectFlag1, ObjectFlag2

if TYPE_CHECKING:
    from pymeshzork.engine.game import Game


@dataclass
class EventResult:
    """Result of an event firing."""

    message: str | None = None
    player_dies: bool = False
    score_change: int = 0


# Thief movement configuration
THIEF_ROOMS = [
    "treas", "lroom", "kitch", "attic", "cella", "mtrol", "maze1", "maze2",
    "maze3", "mtorc", "dome", "entra", "egypt", "temp1", "bank", "safty",
]

# Villain definitions
VILLAINS = {
    "thief": {
        "name": "thief",
        "strength": 5,
        "rooms": THIEF_ROOMS,
        "roams": True,
        "steals": True,
    },
    "troll": {
        "name": "troll",
        "strength": 3,
        "rooms": ["mtrol"],
        "roams": False,
        "blocks_exit": True,
    },
    "cyclo": {
        "name": "cyclops",
        "strength": 10000,  # Essentially invincible in combat
        "rooms": ["mcycl"],
        "roams": False,
        "special_defeat": "odysseus",
    },
}


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
            EventID.BALLOON: self.handle_balloon,
            EventID.FOREST: self.handle_forest,
            EventID.BUCKET: self.handle_bucket,
        }

        # Demon handlers (run every turn)
        self.demons: dict[str, Callable[[], EventResult | None]] = {
            "thief": self.demon_thief,
            "sword": self.demon_sword,
            "troll": self.demon_troll,
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
        """Handle villain combat turn."""
        results = []
        player_room = self.game.state.current_room

        for villain_id in list(self.game.state.villain_state.villains):
            villain_state = self.game.state.get_object_state(villain_id)
            if villain_state.room_id != player_room:
                continue

            # Villain attacks player
            villain_info = VILLAINS.get(villain_id, {})
            strength = villain_info.get("strength", 3)

            # Roll for hit (based on strength and player weapon)
            hit_chance = min(50 + strength * 5, 90)
            if random.randint(1, 100) <= hit_chance:
                damage = random.randint(1, strength)
                if damage >= 3:
                    results.append(f"The {villain_info.get('name', villain_id)} wounds you badly!")
                elif damage >= 1:
                    results.append(f"The {villain_info.get('name', villain_id)} hits you!")
                # Track damage (could lead to death)
                self.game.state.player_wounds = getattr(
                    self.game.state, "player_wounds", 0
                ) + damage
                if self.game.state.player_wounds >= 10:
                    return EventResult(
                        message="\n".join(results) + "\nYou have died.",
                        player_dies=True,
                    )
            else:
                results.append(f"The {villain_info.get('name', villain_id)} misses!")

        if results:
            return EventResult(message="\n".join(results))
        return EventResult()

    def handle_balloon(self) -> EventResult:
        """Handle balloon movement events."""
        # Balloon moves between volcano rooms when launched
        balloon_state = self.game.state.get_object_state("ballo")
        if not balloon_state.room_id:
            return EventResult()

        balloon_rooms = ["vlbot", "vlair", "vleft", "vledg"]
        current_idx = balloon_rooms.index(balloon_state.room_id) if balloon_state.room_id in balloon_rooms else 0

        # Move to next room
        next_idx = (current_idx + 1) % len(balloon_rooms)
        balloon_state.room_id = balloon_rooms[next_idx]

        # If player is in balloon, move them too
        if self.game.state.current_room in balloon_rooms:
            self.game.state.current_room = balloon_rooms[next_idx]
            room = self.game.world.get_room(balloon_rooms[next_idx])
            if room:
                return EventResult(
                    message=f"The balloon drifts...\n\n{room.name}\n{room.description_first}",
                )

        return EventResult()

    def handle_forest(self) -> EventResult:
        """Handle getting lost in the forest."""
        # Random chance to get disoriented in forest rooms
        if self.game.state.current_room.startswith("fore"):
            if random.random() < 0.3:
                return EventResult(
                    message="You hear in the distance the chirping of a song bird.",
                )
        return EventResult()

    def handle_bucket(self) -> EventResult:
        """Handle bucket filling/emptying at well."""
        bucket_state = self.game.state.get_object_state("bucke")
        if bucket_state.room_id == "well":
            # Bucket fills with water at well
            water = self.game.world.get_object("water")
            if water:
                self.game.state.move_object_to_container("water", "bucke")
                return EventResult(
                    message="The bucket fills with water from the well.",
                )
        return EventResult()

    # ============ Demon Handlers ============

    def demon_thief(self) -> EventResult | None:
        """Thief demon - controls thief movement and stealing behavior."""
        thief_state = self.game.state.thief_state

        if not thief_state.active:
            return None

        thief_obj_state = self.game.state.get_object_state("thief")
        player_room = self.game.state.current_room
        thief_room = thief_obj_state.room_id

        # Update thief_here flag
        thief_state.thief_here = (thief_room == player_room)

        # Thief behavior depends on whether player is present
        if thief_state.thief_here:
            return self._thief_in_room()
        else:
            return self._thief_wander()

    def _thief_in_room(self) -> EventResult | None:
        """Handle thief behavior when in same room as player."""
        messages = []

        # 30% chance thief tries to steal something
        if random.random() < 0.30:
            stolen = self._thief_steal()
            if stolen:
                messages.append(
                    f"The thief, who is extremely dexterous, steals the {stolen} from you!"
                )

        # 20% chance thief attacks
        if random.random() < 0.20:
            # Add thief to active villains for combat
            if "thief" not in self.game.state.villain_state.villains:
                self.game.state.villain_state.villains.append("thief")
            messages.append("The thief lunges at you with his stiletto!")

        # 40% chance thief taunts/comments
        elif random.random() < 0.40:
            taunts = [
                "The thief grins menacingly at you.",
                "\"I'll get you yet,\" mutters the thief.",
                "The thief eyes your possessions greedily.",
                "The thief seems unimpressed by your adventuring skills.",
            ]
            messages.append(random.choice(taunts))

        if messages:
            return EventResult(message="\n".join(messages))
        return None

    def _thief_steal(self) -> str | None:
        """Thief attempts to steal a valuable item from player."""
        # Find valuable items in player inventory
        valuable_items = []
        for obj_id in self.game.state.objects_held_by("player"):
            obj = self.game.world.get_object(obj_id)
            if obj and obj.value > 0 and obj_id not in ["sword", "lamp", "knife"]:
                valuable_items.append((obj_id, obj.name, obj.value))

        if not valuable_items:
            return None

        # Prefer higher value items
        valuable_items.sort(key=lambda x: x[2], reverse=True)

        # 70% chance to steal most valuable, 30% random
        if random.random() < 0.70:
            target = valuable_items[0]
        else:
            target = random.choice(valuable_items)

        obj_id, obj_name, _ = target

        # Move item to thief's stash (treasure room)
        self.game.state.move_object_to_room(obj_id, "treas")

        return obj_name

    def _thief_wander(self) -> EventResult | None:
        """Thief wanders between rooms."""
        thief_obj_state = self.game.state.get_object_state("thief")

        # 25% chance to move each turn
        if random.random() > 0.25:
            return None

        current_room = thief_obj_state.room_id or "treas"

        # Get adjacent rooms
        room = self.game.world.get_room(current_room)
        if not room:
            return None

        # Find valid destinations (underground rooms only, generally)
        valid_rooms = []
        for exit in room.exits:
            if exit.destination_id in THIEF_ROOMS:
                valid_rooms.append(exit.destination_id)

        # Also allow random teleport to any thief room (10% chance)
        if random.random() < 0.10:
            valid_rooms = THIEF_ROOMS

        if valid_rooms:
            new_room = random.choice(valid_rooms)
            thief_obj_state.room_id = new_room

            # If thief enters player's room, announce
            if new_room == self.game.state.current_room:
                self.game.state.thief_state.thief_here = True
                entrances = [
                    "A seedy-looking individual with a large bag enters from the shadows.",
                    "The thief appears from nowhere, looking dangerous.",
                    "You hear a noise and turn to find the thief behind you!",
                ]
                return EventResult(message=random.choice(entrances))

        return None

    def demon_troll(self) -> EventResult | None:
        """Troll demon - controls troll behavior."""
        troll_state = self.game.state.get_object_state("troll")

        if not troll_state.room_id:
            return None  # Troll is dead/gone

        player_room = self.game.state.current_room

        if troll_state.room_id != player_room:
            return None  # Troll not in same room

        # Troll blocks passage and may attack
        if "troll" not in self.game.state.villain_state.villains:
            self.game.state.villain_state.villains.append("troll")

        # Troll growls or attacks
        if random.random() < 0.30:
            growls = [
                "The troll growls menacingly.",
                "The troll swings his axe through the air.",
                "The troll blocks your path, looking hungry.",
            ]
            return EventResult(message=random.choice(growls))

        return None

    def demon_sword(self) -> EventResult | None:
        """Sword demon - controls sword glow when enemies are near."""
        thief_state = self.game.state.thief_state

        if not thief_state.sword_active:
            return None

        sword_state = self.game.state.get_object_state("sword")

        # Check if player has sword
        if not sword_state.is_held_by("player"):
            thief_state.sword_glow = 0
            return None

        # Check for enemies in current room
        room_id = self.game.state.current_room
        enemies_in_room = self._check_enemies_in_room(room_id)

        # Check for enemies in adjacent rooms
        enemies_adjacent = self._check_enemies_adjacent(room_id)

        # Update sword glow
        old_glow = thief_state.sword_glow

        if enemies_in_room:
            thief_state.sword_glow = 2  # Bright glow
        elif enemies_adjacent:
            thief_state.sword_glow = 1  # Faint glow
        else:
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

    def _check_enemies_in_room(self, room_id: str) -> bool:
        """Check if there are enemies in the specified room."""
        for obj_id in self.game.state.objects_in_room(room_id):
            obj = self.game.world.get_object(obj_id)
            if obj and (obj.is_villain() or obj_id in VILLAINS):
                return True
        return False

    def _check_enemies_adjacent(self, room_id: str) -> bool:
        """Check if there are enemies in adjacent rooms."""
        room = self.game.world.get_room(room_id)
        if not room:
            return False

        for exit in room.exits:
            if exit.destination_id:
                if self._check_enemies_in_room(exit.destination_id):
                    return True
        return False

    # ============ Utility Methods ============

    def activate_thief(self) -> None:
        """Activate the thief demon (called when entering underground)."""
        self.game.state.thief_state.active = True
        self.game.state.thief_state.sword_active = True

    def activate_villain(self, villain_id: str) -> None:
        """Add a villain to active combat."""
        if villain_id not in self.game.state.villain_state.villains:
            self.game.state.villain_state.villains.append(villain_id)

    def deactivate_villain(self, villain_id: str) -> None:
        """Remove a villain from combat (defeated/fled)."""
        if villain_id in self.game.state.villain_state.villains:
            self.game.state.villain_state.villains.remove(villain_id)

    def kill_villain(self, villain_id: str) -> None:
        """Permanently remove a villain."""
        self.deactivate_villain(villain_id)
        villain_state = self.game.state.get_object_state(villain_id)
        villain_state.room_id = None  # Remove from world


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
