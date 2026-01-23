"""Tests for PyMeshZork engine."""

import pytest

from pymeshzork.engine.game import Game, create_game
from pymeshzork.engine.models import (
    Direction,
    Exit,
    Object,
    ObjectFlag1,
    Room,
    RoomFlag,
)
from pymeshzork.engine.parser import Parser
from pymeshzork.engine.state import GameState
from pymeshzork.engine.world import World


class TestModels:
    """Tests for core data models."""

    def test_room_flags(self):
        """Test room flag operations."""
        room = Room(
            id="test",
            name="Test Room",
            description_first="A test room.",
            description_short="Test",
            flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
        )

        assert room.is_lit()
        assert room.is_land()
        assert not room.is_water()
        assert not room.is_visited()

    def test_object_flags(self):
        """Test object flag operations."""
        obj = Object(
            id="lamp",
            name="lamp",
            flags1=ObjectFlag1.VISIBT | ObjectFlag1.TAKEBT | ObjectFlag1.LITEBT,
        )

        assert obj.is_visible()
        assert obj.is_takeable()
        assert obj.is_light_source()
        assert not obj.is_on()


class TestParser:
    """Tests for command parser."""

    def test_simple_direction(self):
        """Test parsing simple direction commands."""
        parser = Parser()
        world = World()
        state = GameState()

        cmd = parser.parse("north", world, state)

        assert cmd.verb == "walk"
        assert cmd.direction == "north"
        assert cmd.error is None

    def test_verb_only(self):
        """Test parsing verb-only commands."""
        parser = Parser()
        world = World()
        state = GameState()

        cmd = parser.parse("look", world, state)

        assert cmd.verb == "look"
        assert cmd.direct_object is None

    def test_verb_noun(self):
        """Test parsing verb + noun commands."""
        parser = Parser()
        world = World()
        state = GameState()

        # Add a lamp to the world
        world.add_object(Object(
            id="lamp",
            name="brass lantern",
            synonyms=["lamp", "lantern"],
            flags1=ObjectFlag1.VISIBT | ObjectFlag1.TAKEBT,
            initial_room="whous",
        ))

        # Initialize state
        state.current_room = "whous"
        world.initialize_object_states(state)

        cmd = parser.parse("take lamp", world, state)

        assert cmd.verb == "take"
        assert cmd.direct_object == "lamp"

    def test_verb_noun_prep_noun(self):
        """Test parsing verb + noun + prep + noun commands."""
        parser = Parser()
        world = World()
        state = GameState()

        cmd = parser.parse("put book in case", world, state)

        assert cmd.verb == "put"
        assert cmd.preposition == "in"


class TestWorld:
    """Tests for world management."""

    def test_add_room(self):
        """Test adding rooms to world."""
        world = World()

        room = Room(
            id="test",
            name="Test Room",
            description_first="A test room.",
            description_short="Test",
        )

        world.add_room(room)
        assert world.get_room("test") == room

    def test_movement(self):
        """Test movement between rooms."""
        world = World()
        state = GameState()

        # Create two connected rooms
        room1 = Room(
            id="room1",
            name="Room 1",
            description_first="First room.",
            description_short="Room 1",
            flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
            exits=[Exit(Direction.NORTH, "room2")],
        )

        room2 = Room(
            id="room2",
            name="Room 2",
            description_first="Second room.",
            description_short="Room 2",
            flags=RoomFlag.RLIGHT | RoomFlag.RLAND,
            exits=[Exit(Direction.SOUTH, "room1")],
        )

        world.add_room(room1)
        world.add_room(room2)

        state.current_room = "room1"

        # Move north
        success, message = world.move_player(state, Direction.NORTH)

        assert success
        assert state.current_room == "room2"


class TestGameState:
    """Tests for game state management."""

    def test_object_movement(self):
        """Test moving objects between locations."""
        state = GameState()

        # Put object in room
        state.move_object_to_room("sword", "lroom")
        assert "sword" in state.objects_in_room("lroom")

        # Give to player
        state.move_object_to_actor("sword", "player")
        assert "sword" not in state.objects_in_room("lroom")
        assert "sword" in state.objects_held_by("player")

    def test_serialization(self):
        """Test save/load of game state."""
        state = GameState()
        state.current_room = "kitchen"
        state.score = 42
        state.moves = 100

        # Serialize
        data = state.to_dict()

        # Deserialize
        loaded = GameState.from_dict(data)

        assert loaded.current_room == "kitchen"
        assert loaded.score == 42
        assert loaded.moves == 100


class TestGame:
    """Tests for main game engine."""

    def test_create_game(self):
        """Test game creation."""
        game = create_game()

        assert game is not None
        assert game.world is not None
        assert game.state is not None
        assert game.state.current_room == "whous"

    def test_start(self):
        """Test game start produces output."""
        game = create_game()
        output = game.start()

        assert "ZORK" in output
        assert "West of House" in output

    def test_look_command(self):
        """Test look command."""
        game = create_game()
        game.start()

        result = game.process_input("look")

        assert result.messages
        assert "West of House" in result.messages[0]

    def test_movement_command(self):
        """Test movement command."""
        game = create_game()
        game.start()

        result = game.process_input("north")

        assert result.messages
        assert game.state.current_room == "nhous"

    def test_take_drop(self):
        """Test take and drop commands."""
        game = create_game()
        game.start()

        # Go to living room
        game.process_input("north")
        game.process_input("east")
        game.process_input("enter")  # Through window
        game.process_input("west")  # To living room

        # Take sword
        result = game.process_input("take sword")
        assert result.messages
        assert "sword" in game.state.objects_held_by("player")

        # Drop sword
        result = game.process_input("drop sword")
        assert "sword" in game.state.objects_in_room("lroom")

    def test_inventory(self):
        """Test inventory command."""
        game = create_game()
        game.start()

        result = game.process_input("inventory")

        assert result.messages
        assert "empty-handed" in result.messages[0]


class TestIntegration:
    """Integration tests for full gameplay."""

    def test_basic_exploration(self):
        """Test basic exploration loop."""
        game = create_game()
        game.start()

        # Walk around the house
        commands = ["n", "e", "s", "s", "w"]
        for cmd in commands:
            result = game.process_input(cmd)
            assert not result.player_died

        # Should be back near start
        assert game.state.moves == 5

    def test_quit_command(self):
        """Test quit command."""
        game = create_game()
        game.start()

        result = game.process_input("quit")

        assert result.quit_requested
