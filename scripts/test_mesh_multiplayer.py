#!/usr/bin/env python3
"""Test script for mesh multiplayer across all nodes.

Run this on each Pi to test cross-mesh communication.

Usage:
    python scripts/test_mesh_multiplayer.py --name Player1 --serial  # For USB devices
    python scripts/test_mesh_multiplayer.py --name Player1 --native  # For Radio Bonnet
"""

import argparse
import sys
import time

sys.path.insert(0, '/home/lpesce/pymeshzork')

def main():
    parser = argparse.ArgumentParser(description='Test mesh multiplayer')
    parser.add_argument('--name', required=True, help='Player name')
    parser.add_argument('--serial', action='store_true', help='Use serial mode')
    parser.add_argument('--native', action='store_true', help='Use native mode')
    parser.add_argument('--port', help='Serial port (optional)')
    parser.add_argument('--duration', type=int, default=45, help='Test duration in seconds')
    args = parser.parse_args()

    from pymeshzork.meshtastic.multiplayer import MultiplayerManager, MultiplayerBackend

    if args.native:
        backend = MultiplayerBackend.NATIVE
        mode_name = "Native"
    elif args.serial:
        backend = MultiplayerBackend.SERIAL
        mode_name = "Serial"
    else:
        print("ERROR: Must specify --serial or --native")
        return 1

    print(f"=== Mesh Multiplayer Test: {args.name} ({mode_name}) ===")
    print()

    # Create multiplayer manager
    mp = MultiplayerManager(player_name=args.name, backend=backend)

    # Track received messages
    received_messages = []

    def on_join(player):
        msg = f"[JOIN] {player.name} entered the game"
        print(msg)
        received_messages.append(msg)

    def on_leave(player):
        msg = f"[LEAVE] {player.name} left the game"
        print(msg)
        received_messages.append(msg)

    def on_chat(player, message, is_team):
        msg = f"[CHAT] {player.name}: {message}"
        print(msg)
        received_messages.append(msg)

    def on_move(player, from_room, to_room):
        msg = f"[MOVE] {player.name} moved from {from_room} to {to_room}"
        print(msg)
        received_messages.append(msg)

    # Register callbacks
    mp.on_player_join(on_join)
    mp.on_player_leave(on_leave)
    mp.on_chat(on_chat)
    mp.on_player_move(on_move)

    # Connect
    print(f"Connecting to mesh ({mode_name})...")
    if not mp.connect():
        print("ERROR: Failed to connect!")
        return 1

    print(f"Connected! Player ID: {mp.player_id}")
    print()

    # Send join
    print(f"Sending JOIN message...")
    mp.send_join("whous")
    time.sleep(2)

    # Send chat
    chat_msg = f"Hello from {args.name}!"
    print(f"Sending CHAT: {chat_msg}")
    mp.send_chat(chat_msg)
    time.sleep(2)

    # Send move
    print(f"Sending MOVE: whous -> nhous")
    mp.send_move("whous", "nhous")
    time.sleep(2)

    # Wait and listen for messages
    print()
    print(f"Listening for messages ({args.duration - 6} seconds)...")
    print("-" * 40)

    start_time = time.time()
    while time.time() - start_time < args.duration - 6:
        # Process any pending messages
        pending = mp.get_pending_messages()
        for msg in pending:
            print(f"PENDING: {msg}")
        time.sleep(1)

    print("-" * 40)
    print()

    # Send leave
    print(f"Sending LEAVE message...")
    mp.disconnect()

    # Summary
    print()
    print("=== Test Complete ===")
    print(f"Player: {args.name}")
    print(f"Mode: {mode_name}")
    print(f"Messages received: {len(received_messages)}")
    for msg in received_messages:
        print(f"  - {msg}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
