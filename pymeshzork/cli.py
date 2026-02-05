"""Command-line interface for PyMeshZork."""

import json
import sys
from datetime import datetime
from pathlib import Path

from pymeshzork.config import get_config, save_config, CONFIG_DIR
from pymeshzork.engine.game import Game, create_game, load_game_from_json
from pymeshzork.meshtastic.multiplayer import MultiplayerManager, MultiplayerBackend


# Autosave directory
AUTOSAVE_DIR = CONFIG_DIR / "autosaves"


def get_autosave_path(player_name: str) -> Path:
    """Get the autosave file path for a player."""
    # Sanitize player name for filename
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in player_name)
    return AUTOSAVE_DIR / f"{safe_name}_autosave.json"


def save_autosave(game: Game, player_name: str) -> bool:
    """Save game state to autosave file."""
    try:
        AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
        autosave_path = get_autosave_path(player_name)

        save_data = game.save_game()
        save_data["player_name"] = player_name
        save_data["timestamp"] = datetime.now().isoformat()

        with open(autosave_path, "w") as f:
            json.dump(save_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Warning: Could not save autosave: {e}", file=sys.stderr)
        return False


def load_autosave(player_name: str) -> dict | None:
    """Load autosave file for a player if it exists."""
    autosave_path = get_autosave_path(player_name)
    if autosave_path.exists():
        try:
            with open(autosave_path) as f:
                return json.load(f)
        except Exception:
            return None
    return None


def prompt_for_player_name() -> str:
    """Prompt the user to enter a player name."""
    print("\n" + "=" * 60)
    print("Welcome to PyMeshZork!")
    print("=" * 60)
    print("\nBefore we begin, please choose a name for your adventurer.")
    print("This name will be visible to other players in multiplayer mode.")
    print()

    while True:
        try:
            name = input("Enter your adventurer name: ").strip()
            if not name:
                print("Please enter a name.")
                continue
            if len(name) > 20:
                print("Name must be 20 characters or less.")
                continue
            if not all(c.isalnum() or c in " -_" for c in name):
                print("Name can only contain letters, numbers, spaces, hyphens, and underscores.")
                continue

            # Confirm
            confirm = input(f"Your name will be '{name}'. Is this correct? (Y/n): ").strip().lower()
            if confirm in ("", "y", "yes"):
                return name
        except (KeyboardInterrupt, EOFError):
            print("\n\nUsing default name: Adventurer")
            return "Adventurer"


def get_player_name(args, config) -> str:
    """Get player name from args, config, or prompt user."""
    # 1. Command line takes priority
    if args.player_name:
        return args.player_name

    # 2. Check if config has a non-default name
    if config.game.player_name and config.game.player_name != "Adventurer":
        return config.game.player_name

    # 3. Prompt user for name
    name = prompt_for_player_name()

    # Save to config
    config.game.player_name = name
    try:
        save_config(config)
        print(f"\nYour name has been saved to {CONFIG_DIR / 'config.json'}")
        print("You can change it later by editing that file.\n")
    except Exception as e:
        print(f"\nNote: Could not save config: {e}")
        print("Your name will be used for this session only.\n")

    return name


def run_game(game: Game, player_name: str, autosave_enabled: bool = True) -> None:
    """Run the main game loop."""
    # Print opening
    print(game.start())
    print()

    # Main game loop
    try:
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

                # Autosave after each command
                if autosave_enabled:
                    save_autosave(game, player_name)

                # Handle quit
                if result.quit_requested:
                    if autosave_enabled:
                        print("Your progress has been saved.")
                    break

                # Handle death with multiple deaths
                if result.player_died and game.state.deaths >= 3:
                    break

            except KeyboardInterrupt:
                print("\n")
                if autosave_enabled:
                    save_autosave(game, player_name)
                    print("Your progress has been saved.")
                else:
                    print("Your game has not been saved.")
                break
            except EOFError:
                print("\n\nGoodbye!")
                if autosave_enabled:
                    save_autosave(game, player_name)
                break
    finally:
        # Disconnect multiplayer on exit
        if game.multiplayer:
            game.multiplayer.disconnect()


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

    parser.add_argument(
        "--multiplayer",
        action="store_true",
        help="Enable multiplayer (requires MQTT config)",
    )

    parser.add_argument(
        "--no-multiplayer",
        action="store_true",
        help="Disable multiplayer even if configured",
    )

    parser.add_argument(
        "--lora",
        action="store_true",
        help="Use LoRa radio for multiplayer (Adafruit Radio Bonnet)",
    )

    parser.add_argument(
        "--lora-freq",
        type=float,
        default=915.0,
        help="LoRa frequency in MHz (915.0 for US, 868.0 for EU)",
    )

    parser.add_argument(
        "--serial",
        action="store_true",
        help="Use USB serial connection to Meshtastic device (T-Beam, Heltec, etc.)",
    )

    parser.add_argument(
        "--serial-port",
        type=str,
        help="Serial port for Meshtastic device (e.g., /dev/ttyUSB0, COM3). Auto-detects if not specified.",
    )

    parser.add_argument(
        "--native",
        action="store_true",
        help="Use meshtasticd (Meshtastic Native) on Raspberry Pi with Radio Bonnet",
    )

    parser.add_argument(
        "--player-name",
        type=str,
        help="Player name for multiplayer",
    )

    parser.add_argument(
        "--reset-location",
        action="store_true",
        help="Start at the beginning (West of House) instead of saved location",
    )

    parser.add_argument(
        "--reset-inventory",
        action="store_true",
        help="Start with empty inventory instead of saved items",
    )

    parser.add_argument(
        "--reset-all",
        action="store_true",
        help="Fresh start: reset both location and inventory",
    )

    parser.add_argument(
        "--no-autosave",
        action="store_true",
        help="Disable automatic saving of game progress",
    )

    args = parser.parse_args()

    # Handle --reset-all
    if args.reset_all:
        args.reset_location = True
        args.reset_inventory = True

    # Get config
    config = get_config()

    # Get player name (may prompt user)
    player_name = get_player_name(args, config)

    # Initialize multiplayer if enabled
    multiplayer = None

    # Determine backend
    if args.native:
        backend = MultiplayerBackend.NATIVE
        use_multiplayer = not args.no_multiplayer
    elif args.serial:
        backend = MultiplayerBackend.SERIAL
        config.serial.enabled = True
        if args.serial_port:
            config.serial.port = args.serial_port
        use_multiplayer = not args.no_multiplayer
    elif args.lora:
        backend = MultiplayerBackend.LORA
        # Override config frequency if specified
        if args.lora_freq != 915.0:
            config.lora.frequency = args.lora_freq
        config.lora.enabled = True
        use_multiplayer = not args.no_multiplayer
    else:
        backend = MultiplayerBackend.MQTT
        use_multiplayer = (
            (args.multiplayer or config.mqtt.enabled)
            and not args.no_multiplayer
            and config.mqtt.is_configured()
        )

    if use_multiplayer:
        multiplayer = MultiplayerManager(player_name, backend=backend)

        if args.native:
            backend_name = "Meshtastic Native (meshtasticd)"
        elif args.serial:
            backend_name = "Meshtastic serial"
        elif args.lora:
            backend_name = "LoRa radio (legacy)"
        else:
            backend_name = "MQTT"
        print(f"Connecting to multiplayer ({backend_name}) as {player_name}...")
        if multiplayer.connect():
            print("Connected!")
        else:
            print(f"Failed to connect to {backend_name}. Playing offline.")
            multiplayer = None

    # Create game
    if args.world:
        # Load custom world from specified path
        try:
            game = load_game_from_json(str(args.world))
            game.multiplayer = multiplayer
            if multiplayer:
                multiplayer.set_game(game)
        except Exception as e:
            print(f"Error loading world: {e}", file=sys.stderr)
            return 1
    else:
        # Try to load from default JSON, fall back to demo world
        try:
            game = load_game_from_json()
        except Exception:
            game = create_game()

        game.multiplayer = multiplayer
        if multiplayer:
            multiplayer.set_game(game)

    # Load save if specified via --load
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
    else:
        # Try to load autosave unless reset flags are set
        autosave_data = load_autosave(player_name)
        if autosave_data and not (args.reset_location and args.reset_inventory):
            timestamp = autosave_data.get("timestamp", "unknown")
            current_room = autosave_data.get("current_room", "unknown")
            score = autosave_data.get("score", 0)
            moves = autosave_data.get("moves", 0)

            print(f"\nFound saved game for {player_name}:")
            print(f"  Last played: {timestamp}")
            print(f"  Location: {current_room}")
            print(f"  Score: {score}, Moves: {moves}")

            if args.reset_location or args.reset_inventory:
                # Partial reset - load the save then reset specific parts
                game.load_game(autosave_data)

                if args.reset_location:
                    game.state.current_room = "whous"  # West of House
                    print("  -> Location reset to West of House")

                if args.reset_inventory:
                    # Clear player inventory by moving items to limbo
                    for obj_id, obj_state in game.state.object_states.items():
                        if obj_state.location == "player":
                            obj_state.location = "limbo"
                    print("  -> Inventory cleared")
                print()
            else:
                # Ask to restore
                try:
                    restore = input("Restore saved game? (Y/n): ").strip().lower()
                    if restore in ("", "y", "yes"):
                        if game.load_game(autosave_data):
                            print("Game restored!\n")
                        else:
                            print("Could not restore save. Starting fresh.\n")
                    else:
                        print("Starting fresh game.\n")
                except (KeyboardInterrupt, EOFError):
                    print("\nStarting fresh game.\n")

    # Run game
    autosave_enabled = not args.no_autosave
    run_game(game, player_name, autosave_enabled)

    return 0


if __name__ == "__main__":
    sys.exit(main())
