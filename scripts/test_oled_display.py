#!/usr/bin/env python3
"""Test script for OLED display on Radio Bonnet.

Run this on a Raspberry Pi with the Adafruit Radio Bonnet to test
the OLED display cycling through different screens.

Usage:
    python scripts/test_oled_display.py
"""

import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, '/home/pi/pymeshzork')

from pymeshzork.meshtastic.oled_display import OLEDDisplay, DisplayMode

def main():
    print("OLED Display Test")
    print("=" * 40)

    # Create display instance
    display = OLEDDisplay()

    # Disable auto-cycling so we control it manually
    display.AUTO_CYCLE_INTERVAL = 0

    if not display.initialize():
        print("ERROR: Failed to initialize OLED display!")
        print("Make sure you're running on a Raspberry Pi with the Radio Bonnet.")
        return 1

    print("Display initialized successfully!")
    print()

    # Set up test data
    display.update_player("Adventurer", "whous", "West of House")
    display.set_connected(True, "Native")
    display.update_mesh_info(3)
    display.update_signal(rssi=-85, snr=7.5)
    display.set_players_in_room(["Player2", "Explorer"])
    display.add_message("Player2: Hello!")
    display.add_message("Explorer: Found lamp")

    print("Cycling through display screens...")
    print("Press Ctrl+C to exit")
    print()

    modes = [
        (DisplayMode.STATUS, "STATUS - Player, room, connection"),
        (DisplayMode.PLAYERS, "PLAYERS - Other players in room"),
        (DisplayMode.MESSAGES, "MESSAGES - Recent chat"),
        (DisplayMode.MESH_INFO, "MESH INFO - Network stats"),
    ]

    try:
        cycle = 0
        while True:
            for mode, description in modes:
                cycle += 1
                print(f"[{cycle}] {description}")
                display.set_mode(mode)

                # Simulate some activity
                if cycle % 3 == 0:
                    display.show_tx()
                    print("    -> TX indicator")
                if cycle % 4 == 0:
                    display.show_rx()
                    print("    -> RX indicator")

                # Wait and let the display render
                time.sleep(3)

            print()
            print("--- Cycle complete, repeating... ---")
            print()

            # Update some data to show changes
            display.update_signal(rssi=-85 + (cycle % 20), snr=7.5 + (cycle % 5) * 0.5)

    except KeyboardInterrupt:
        print()
        print("Exiting...")

    finally:
        display.shutdown()
        print("Display shutdown complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
