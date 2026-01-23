"""Command-line interface for PyMeshZork."""

import json
import sys
from pathlib import Path

from pymeshzork.engine.game import Game, create_game, load_game_from_json


def run_game(game: Game) -> None:
    """Run the main game loop."""
    # Print opening
    print(game.start())
    print()

    # Main game loop
    while True:
        try:
            # Get input
            user_input = input(game.get_prompt() + " ").strip()

            if not user_input:
                continue

            # Process input
            result = game.process_input(user_input)

            # Print messages
            for message in result.messages:
                print(message)
                print()

            # Handle quit
            if result.quit_requested:
                break

            # Handle death with multiple deaths
            if result.player_died and game.state.deaths >= 3:
                break

        except KeyboardInterrupt:
            print("\n\nInterrupted. Your game has not been saved.")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="PyMeshZork - Python Zork with Meshtastic Multiplayer",
        prog="zork",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="PyMeshZork 0.1.0",
    )

    parser.add_argument(
        "--world",
        type=Path,
        help="Path to world JSON file",
    )

    parser.add_argument(
        "--load",
        type=Path,
        help="Path to save file to load",
    )

    parser.add_argument(
        "--save-dir",
        type=Path,
        default=Path.home() / ".pymeshzork" / "saves",
        help="Directory for save files",
    )

    args = parser.parse_args()

    # Create game
    if args.world:
        # Load custom world from specified path
        try:
            game = load_game_from_json(str(args.world))
        except Exception as e:
            print(f"Error loading world: {e}", file=sys.stderr)
            return 1
    else:
        # Try to load from default JSON, fall back to demo world
        try:
            game = load_game_from_json()
        except Exception:
            game = create_game()

    # Load save if specified
    if args.load:
        try:
            with open(args.load) as f:
                save_data = json.load(f)
            if not game.load_game(save_data):
                print("Error loading save file.", file=sys.stderr)
                return 1
            print(f"Game loaded from {args.load}")
        except Exception as e:
            print(f"Error loading save: {e}", file=sys.stderr)
            return 1

    # Run game
    run_game(game)

    return 0


if __name__ == "__main__":
    sys.exit(main())
