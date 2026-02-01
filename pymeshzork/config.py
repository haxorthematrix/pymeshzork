"""Configuration management for PyMeshZork.

Configuration is loaded from (in order of precedence):
1. Environment variables (PYMESHZORK_*)
2. User config file (~/.pymeshzork/config.json)
3. Default values

Environment variables:
    PYMESHZORK_MQTT_ENABLED - Enable multiplayer (true/false)
    PYMESHZORK_MQTT_BROKER - MQTT broker hostname
    PYMESHZORK_MQTT_PORT - MQTT broker port
    PYMESHZORK_MQTT_USERNAME - MQTT username
    PYMESHZORK_MQTT_PASSWORD - MQTT password
    PYMESHZORK_MQTT_CHANNEL - Game channel name
    PYMESHZORK_PLAYER_NAME - Default player name
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# Default config directory
CONFIG_DIR = Path.home() / ".pymeshzork"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class MQTTConfig:
    """MQTT multiplayer configuration."""

    enabled: bool = False
    broker: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    channel: str = "pymeshzork"
    use_tls: bool = False

    def is_configured(self) -> bool:
        """Check if MQTT is properly configured."""
        return bool(self.broker and self.enabled)


@dataclass
class LoRaConfig:
    """LoRa radio configuration for direct RF communication."""

    enabled: bool = False
    frequency: float = 915.0  # MHz (915.0 for US, 868.0 for EU)
    tx_power: int = 23  # dBm (5-23)
    spreading_factor: int = 7  # SF7-SF12
    bandwidth: int = 125000  # Hz

    def is_configured(self) -> bool:
        """Check if LoRa is enabled."""
        return self.enabled


@dataclass
class GameConfig:
    """Game configuration."""

    player_name: str = "Adventurer"
    brief_mode: bool = False
    auto_save: bool = True
    data_dir: str = ""


@dataclass
class Config:
    """Main configuration container."""

    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    lora: LoRaConfig = field(default_factory=LoRaConfig)
    game: GameConfig = field(default_factory=GameConfig)

    def to_dict(self) -> dict:
        """Convert to dictionary for saving."""
        return {
            "mqtt": asdict(self.mqtt),
            "lora": asdict(self.lora),
            "game": asdict(self.game),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create from dictionary."""
        config = cls()
        if "mqtt" in data:
            config.mqtt = MQTTConfig(**data["mqtt"])
        if "lora" in data:
            config.lora = LoRaConfig(**data["lora"])
        if "game" in data:
            config.game = GameConfig(**data["game"])
        return config


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable."""
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


def _get_env_int(key: str, default: int) -> int:
    """Get integer from environment variable."""
    value = os.environ.get(key, "")
    try:
        return int(value)
    except ValueError:
        return default


def load_config() -> Config:
    """Load configuration from environment and/or file.

    Environment variables take precedence over file config.
    """
    config = Config()

    # Try to load from file first
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                config = Config.from_dict(data)
        except (json.JSONDecodeError, OSError):
            pass  # Use defaults

    # Override with environment variables
    if "PYMESHZORK_MQTT_ENABLED" in os.environ:
        config.mqtt.enabled = _get_env_bool("PYMESHZORK_MQTT_ENABLED")
    if "PYMESHZORK_MQTT_BROKER" in os.environ:
        config.mqtt.broker = os.environ["PYMESHZORK_MQTT_BROKER"]
    if "PYMESHZORK_MQTT_PORT" in os.environ:
        config.mqtt.port = _get_env_int("PYMESHZORK_MQTT_PORT", 1883)
    if "PYMESHZORK_MQTT_USERNAME" in os.environ:
        config.mqtt.username = os.environ["PYMESHZORK_MQTT_USERNAME"]
    if "PYMESHZORK_MQTT_PASSWORD" in os.environ:
        config.mqtt.password = os.environ["PYMESHZORK_MQTT_PASSWORD"]
    if "PYMESHZORK_MQTT_CHANNEL" in os.environ:
        config.mqtt.channel = os.environ["PYMESHZORK_MQTT_CHANNEL"]
    if "PYMESHZORK_MQTT_TLS" in os.environ:
        config.mqtt.use_tls = _get_env_bool("PYMESHZORK_MQTT_TLS")
    if "PYMESHZORK_PLAYER_NAME" in os.environ:
        config.game.player_name = os.environ["PYMESHZORK_PLAYER_NAME"]

    # LoRa environment variables
    if "PYMESHZORK_LORA_ENABLED" in os.environ:
        config.lora.enabled = _get_env_bool("PYMESHZORK_LORA_ENABLED")
    if "PYMESHZORK_LORA_FREQUENCY" in os.environ:
        try:
            config.lora.frequency = float(os.environ["PYMESHZORK_LORA_FREQUENCY"])
        except ValueError:
            pass
    if "PYMESHZORK_LORA_TX_POWER" in os.environ:
        config.lora.tx_power = _get_env_int("PYMESHZORK_LORA_TX_POWER", 23)

    return config


def save_config(config: Config) -> None:
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config.to_dict(), f, indent=2)


def get_example_config() -> str:
    """Get example configuration file content."""
    return '''{
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
}'''


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    """Reload configuration from sources."""
    global _config
    _config = load_config()
    return _config
