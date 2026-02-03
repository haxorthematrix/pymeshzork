# PyMeshZork

A modern Python implementation of the classic Zork text adventure game, featuring a GUI map editor and designed for future Meshtastic mesh network multiplayer support.

```
ZORK I: The Great Underground Empire
PyMeshZork Version 0.1.0

West of House
You are standing in an open field west of a white house, with a boarded front door.
There is a small mailbox here.

>
```

## Features

- **Complete Zork I Implementation** - 98 rooms, 57 objects, all classic puzzles
- **JSON-Based World Data** - Easily editable game content
- **GUI Map Editor** - Visual world building with drag-and-drop rooms
- **Player Accounts** - Persistent progress with save/load support
- **Team System** - Create teams with roles, invites, and shared progress
- **Extensible Architecture** - Add custom worlds and puzzles

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Quick Install

```bash
# Clone the repository
git clone https://github.com/haxorthematrix/pymeshzork.git
cd pymeshzork

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e .

# For GUI map editor support
pip install -e ".[editor]"
```

### Dependencies

Core dependencies are installed automatically:
- `rich` - Beautiful terminal formatting
- `prompt_toolkit` - Enhanced input handling
- `bcrypt` - Secure password hashing

Optional for GUI editor:
- `PyQt6` - Cross-platform GUI framework

## Usage

### Playing Zork

Start the game from the command line:

```bash
# Using the installed command
zork

# Or run directly with Python
python -m pymeshzork.cli
```

#### Basic Commands

| Command | Description |
|---------|-------------|
| `look` (or `l`) | Describe current room |
| `inventory` (or `i`) | Show carried items |
| `take <item>` | Pick up an item |
| `drop <item>` | Put down an item |
| `open <object>` | Open a container or door |
| `examine <object>` | Look closely at something |
| `go <direction>` | Move (n, s, e, w, up, down) |
| `save` | Save your game |
| `restore` | Load a saved game |
| `quit` | Exit the game |

#### Movement

Use compass directions or shortcuts:
- `north` / `n`
- `south` / `s`
- `east` / `e`
- `west` / `w`
- `up` / `u`
- `down` / `d`
- `northeast` / `ne`
- `northwest` / `nw`
- `southeast` / `se`
- `southwest` / `sw`

### GUI Map Editor

Launch the visual map editor:

```bash
# Using the installed command
zork-editor

# Or run directly with Python
python -m pymeshzork.editor.main
```

#### Editor Features

- **Visual Map Display** - Rooms as draggable nodes with connection lines
- **Room Editor Panel** - Edit names, descriptions, flags, and exits
- **Object Editor Panel** - Manage items, containers, and properties
- **Auto-Layout** - Automatically arrange rooms (Ctrl+L)
- **Connection Tool** - Click and drag to create exits between rooms
- **Validation** - Detect orphan rooms and missing exits

#### Editor Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New world |
| `Ctrl+O` | Open world |
| `Ctrl+S` | Save world |
| `Ctrl+L` | Auto-layout rooms |
| `C` | Start connection from selected room |
| `Escape` | Cancel / Deselect |
| `Ctrl+0` | Fit map to window |
| `Mouse wheel` | Zoom in/out |
| `Middle-click drag` | Pan the map |

### Player Accounts

Create and manage player accounts in-game:

```
> account create myname
> account login myname
> account info
> account list
```

### Teams

Form teams for collaborative play:

```
> team create "Grue Hunters"
> team invite playername
> team join "Grue Hunters"
> team info
```

### Multiplayer (MQTT)

PyMeshZork supports multiplayer via MQTT, allowing players to see each other in the game world, observe actions, and chat.

#### Configuration

Create a configuration file at `~/.pymeshzork/config.json`:

```json
{
  "mqtt": {
    "enabled": true,
    "broker": "your-mqtt-server.example.com",
    "port": 1883,
    "username": "your-username",
    "password": "your-password",
    "channel": "pymeshzork",
    "use_tls": false
  },
  "game": {
    "player_name": "YourName",
    "brief_mode": false,
    "auto_save": true
  }
}
```

Or use environment variables:

```bash
export PYMESHZORK_MQTT_ENABLED=true
export PYMESHZORK_MQTT_BROKER=your-mqtt-server.example.com
export PYMESHZORK_MQTT_PORT=1883
export PYMESHZORK_MQTT_USERNAME=your-username
export PYMESHZORK_MQTT_PASSWORD=your-password
export PYMESHZORK_MQTT_CHANNEL=pymeshzork
export PYMESHZORK_PLAYER_NAME=YourName
```

#### Command Line Options

```bash
# Enable multiplayer (if configured)
zork --multiplayer

# Disable multiplayer even if configured
zork --no-multiplayer

# Set player name for this session
zork --player-name "Adventurer"
```

#### Multiplayer Features

- **Player Presence** - See other players in rooms ("Bob is here.")
- **Movement Notifications** - See when players enter/leave rooms
- **Action Broadcasting** - See what others are doing ("Alice takes the lamp.")
- **Chat Commands** - Send messages to other players

#### Multiplayer Commands

When connected to multiplayer (MQTT or LoRa), additional commands are available:

| Command | Description |
|---------|-------------|
| `chat <message>` | Broadcast a message to all players |
| `say <message>` | Say something to players in your current room |
| `yell <message>` | Shout a message to all players (shown with [YELLING]) |
| `who` | Show all online players and their locations |
| `help` | Shows multiplayer commands when connected |

**Examples:**

```
> chat Hello everyone!
You broadcast: "Hello everyone!"

> say Anyone found the lamp yet?
You say "Anyone found the lamp yet?"

> yell Watch out for grues!
You yell "Watch out for grues!"

> who
Players online (2):
  Alice (here)
  Bob (in lroom)
```

**Receiving Messages:**

Messages from other players appear when you enter your next command:

```
> look

Alice says: "Hello Bob!"

West of House
You are standing in an open field...
```

#### Setting Up Your Own MQTT Server

For private multiplayer, you can set up a Mosquitto MQTT broker:

```bash
# Ubuntu/Debian
sudo apt install mosquitto mosquitto-clients

# Create password file
sudo mosquitto_passwd -c /etc/mosquitto/passwd pymeshzork

# Configure /etc/mosquitto/mosquitto.conf:
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd

# Restart service
sudo systemctl restart mosquitto
```

### LoRa Radio (Raspberry Pi)

For off-grid multiplayer without internet, use a Raspberry Pi with the Adafruit Radio + OLED Bonnet.

#### Hardware Required

- Raspberry Pi 4 (recommended), 3B+, or Zero 2W
- [Adafruit LoRa Radio Bonnet with OLED](https://www.adafruit.com/product/4074) (RFM95W @ 915MHz)
- Antenna (required - **never transmit without antenna!**)

#### Quick Setup (Automated)

```bash
# On your Raspberry Pi:
curl -sSL https://raw.githubusercontent.com/haxorthematrix/pymeshzork/master/scripts/setup_pi_lora.sh | sudo bash
```

The script will:
1. Install all required system packages
2. Enable I2C and SPI interfaces
3. Apply Pi 4 SPI fixes (if needed)
4. Clone and install PyMeshZork with LoRa support
5. Create a config file template
6. Prompt to reboot

After reboot, run:
```bash
cd ~/pymeshzork
./run_zork_lora.sh
```

#### Manual Installation

```bash
# 1. Install system dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev git i2c-tools libgpiod2 fonts-dejavu

# 2. Enable I2C and SPI
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0

# 3. Add user to required groups
sudo usermod -a -G gpio,i2c,spi $USER

# 4. Apply Pi 4 SPI fixes (REQUIRED for Pi 4)
# Edit /boot/firmware/config.txt:
sudo nano /boot/firmware/config.txt

# Add this line:
dtoverlay=spi0-0cs

# Comment out this line (if present):
#dtoverlay=vc4-kms-v3d

# 5. Reboot for changes to take effect
sudo reboot

# 6. After reboot, clone the repository
git clone https://github.com/haxorthematrix/pymeshzork.git
cd pymeshzork

# 7. Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[lora]"

# 8. Install MQTT support (optional, for internet multiplayer)
pip install paho-mqtt

# 9. Run with LoRa
zork --lora --player-name "YourName"
```

#### Configuration

Create `~/.pymeshzork/config.json`:

```json
{
  "lora": {
    "enabled": true,
    "frequency": 915.0,
    "tx_power": 23
  },
  "mqtt": {
    "enabled": false,
    "broker": "your-mqtt-server.example.com",
    "port": 1883,
    "username": "",
    "password": "",
    "channel": "pymeshzork"
  },
  "game": {
    "player_name": "Adventurer",
    "brief_mode": false,
    "auto_save": true
  }
}
```

| Setting | Description |
|---------|-------------|
| `lora.frequency` | 915.0 MHz (US) or 868.0 MHz (EU) |
| `lora.tx_power` | Transmit power 5-23 dBm |
| `game.player_name` | Your name shown to other players |

#### Command Line Options

```bash
# Use LoRa radio
zork --lora

# Specify frequency (EU)
zork --lora --lora-freq 868.0

# Set player name for this session
zork --lora --player-name "Explorer"
```

#### OLED Display

The bonnet's OLED display shows:
- Player name and current room
- TX/RX activity indicators
- Signal strength (RSSI) of received messages
- Recent chat messages

#### Hardware Notes

- **Always attach antenna before powering on** - transmitting without an antenna can damage the radio
- Range: ~1km line-of-sight, less in buildings/forests
- Multiple Pi nodes can play together within radio range
- Works completely offline - no WiFi or internet needed

#### Pi 4 Specific Configuration

On Raspberry Pi 4, the GPU overlay `vc4-kms-v3d` interferes with SPI timing, causing unreliable radio communication. The fix requires two changes to `/boot/firmware/config.txt`:

```bash
# Add this line to enable software chip-select:
dtoverlay=spi0-0cs

# Comment out or remove this line:
#dtoverlay=vc4-kms-v3d
```

The automated setup script applies these fixes automatically.

#### Troubleshooting

**"No module named 'board'" error:**
```bash
pip install -e ".[lora]"
```

**Radio not responding / SPI errors:**
1. Check that antenna is attached
2. Verify SPI is enabled: `ls /dev/spi*` should show devices
3. On Pi 4, ensure `dtoverlay=spi0-0cs` is in config.txt
4. On Pi 4, ensure `vc4-kms-v3d` is commented out
5. Reboot after config changes

**"Permission denied" on /dev/spidev:**
```bash
sudo usermod -a -G spi,gpio $USER
# Log out and back in
```

**Messages not being received:**
- Check both radios are on the same frequency (915.0 MHz default)
- Ensure antennas are attached on both devices
- Try moving devices closer together for testing
- Check OLED display for TX/RX indicators

**OLED display blank:**
1. Verify I2C is enabled: `ls /dev/i2c*` should show devices
2. Check I2C address: `i2cdetect -y 1` should show device at 0x3C
3. Ensure user is in i2c group: `groups` should include "i2c"

## Project Structure

```
pymeshzork/
├── pymeshzork/
│   ├── engine/          # Core game engine
│   │   ├── game.py      # Main game loop
│   │   ├── parser.py    # Natural language parser
│   │   ├── verbs.py     # Command handlers
│   │   ├── world.py     # Room/map management
│   │   ├── events.py    # Timed events and demons
│   │   └── room_actions.py  # Puzzle mechanics
│   ├── editor/          # GUI map editor
│   │   ├── main_window.py
│   │   ├── map_canvas.py
│   │   └── room_editor.py
│   ├── meshtastic/      # Multiplayer support
│   │   ├── protocol.py  # Message encoding/decoding
│   │   ├── client.py    # Base client interface
│   │   ├── mqtt_client.py  # MQTT implementation
│   │   ├── lora_client.py  # LoRa radio implementation
│   │   ├── presence.py  # Player presence tracking
│   │   └── multiplayer.py  # Game integration
│   ├── accounts/        # Player account system
│   ├── data/            # JSON loaders
│   ├── config.py        # Configuration management
│   └── cli.py           # Command-line interface
├── data/
│   └── worlds/
│       └── classic_zork/  # Zork I game data
├── tests/               # Test suite
└── SPECIFICATION.md     # Technical specification
```

## Creating Custom Worlds

Create your own adventures by editing the JSON world files:

### Room Format

```json
{
  "rooms": {
    "my_room": {
      "name": "My Custom Room",
      "description_first": "A detailed description for first visit...",
      "description_short": "My Custom Room",
      "flags": ["RLIGHT", "RLAND"],
      "exits": [
        {"direction": "north", "destination": "other_room"},
        {"direction": "east", "destination": "locked_room", "type": "door", "door_object": "my_door"}
      ]
    }
  }
}
```

### Object Format

```json
{
  "objects": {
    "my_item": {
      "name": "shiny key",
      "description": "There is a shiny key here.",
      "examine": "A small brass key with intricate engravings.",
      "flags": ["TAKEBT", "VISIBT"],
      "initial_room": "my_room",
      "synonyms": ["key", "brass key"]
    }
  }
}
```

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_engine.py
```

## Roadmap

- [x] Phase 1: Python Core Engine
- [x] Phase 2: JSON Data Externalization
- [x] Phase 3: GUI Map Editor
- [x] Phase 4: Player Account System
- [x] Phase 5: Meshtastic Multiplayer (MQTT + LoRa complete)

See [SPECIFICATION.md](SPECIFICATION.md) for detailed technical documentation.

## Historical Note

This project is a modern reimplementation based on the classic Zork/Dungeon game. The original Dungeon was created at MIT by Tim Anderson, Marc Blank, Bruce Daniels, and Dave Lebling, inspired by Crowther and Woods' Adventure game and Gygax and Arneson's Dungeons & Dragons.

The original source code went through several transformations:
- MDL (1977-1979) - Original implementation
- FORTRAN (1980) - DEC translation
- f77 (1981) - Unix port
- C (1991) - f2c translation by Ian Lance Taylor
- **Python (2026)** - This implementation with JSON externalization

## License

This project contains reimplemented game logic for educational purposes. The original Zork is a trademark of Infocom, Inc. (now Activision).

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
