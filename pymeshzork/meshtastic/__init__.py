"""Meshtastic multiplayer support for PyMeshZork."""

from pymeshzork.meshtastic.protocol import (
    MessageType,
    GameMessage,
    encode_message,
    decode_message,
    ROOM_IDS,
    OBJECT_IDS,
)
from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.mqtt_client import MQTTClient
from pymeshzork.meshtastic.presence import PresenceManager, PlayerInfo
from pymeshzork.meshtastic.multiplayer import (
    MultiplayerManager,
    get_multiplayer,
    init_multiplayer,
)

# LoRa client is optional (requires hardware)
try:
    from pymeshzork.meshtastic.lora_client import LoRaClient, create_lora_client
    LORA_AVAILABLE = True
except ImportError:
    LoRaClient = None  # type: ignore
    create_lora_client = None  # type: ignore
    LORA_AVAILABLE = False

__all__ = [
    # Protocol
    "MessageType",
    "GameMessage",
    "encode_message",
    "decode_message",
    "ROOM_IDS",
    "OBJECT_IDS",
    # Client
    "MeshtasticClient",
    "ConnectionState",
    "MQTTClient",
    # LoRa Client
    "LoRaClient",
    "create_lora_client",
    "LORA_AVAILABLE",
    # Presence
    "PresenceManager",
    "PlayerInfo",
    # Multiplayer integration
    "MultiplayerManager",
    "get_multiplayer",
    "init_multiplayer",
]
