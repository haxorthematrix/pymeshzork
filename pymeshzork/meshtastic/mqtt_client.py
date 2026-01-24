"""MQTT client for Meshtastic multiplayer (Scenario A).

Connects to Meshtastic network via MQTT broker (local Mosquitto or public).
"""

import json
import logging
import threading
import time
from typing import Any

from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.protocol import PROTOCOL_VERSION

logger = logging.getLogger(__name__)


class MQTTClient(MeshtasticClient):
    """MQTT-based Meshtastic client.

    Connects to either:
    - Local Mosquitto broker (recommended for private games)
    - Public Meshtastic MQTT at mqtt.meshtastic.org

    Example usage:
        client = MQTTClient(
            player_name="adventurer",
            broker="localhost",
            port=1883,
        )
        client.on_message(handle_message)
        client.connect()
        client.send_join("whous")
    """

    # Default topics for PyMeshZork multiplayer
    TOPIC_PREFIX = "msh/pymeshzork"
    TOPIC_GAME = f"{TOPIC_PREFIX}/game"
    TOPIC_PRESENCE = f"{TOPIC_PREFIX}/presence"
    TOPIC_CHAT = f"{TOPIC_PREFIX}/chat"

    def __init__(
        self,
        player_name: str,
        broker: str = "localhost",
        port: int = 1883,
        channel: str = "pymeshzork",
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
    ):
        """Initialize MQTT client.

        Args:
            player_name: Display name for this player.
            broker: MQTT broker hostname (default: localhost).
            port: MQTT broker port (default: 1883, or 8883 for TLS).
            channel: Game channel name (default: pymeshzork).
            username: Optional MQTT username.
            password: Optional MQTT password.
            use_tls: Whether to use TLS encryption.
        """
        super().__init__(player_name, channel)

        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

        # paho-mqtt client (lazy import)
        self._mqtt_client: Any = None
        self._mqtt_connected = threading.Event()

    def _ensure_paho(self) -> bool:
        """Ensure paho-mqtt is available."""
        try:
            import paho.mqtt.client as mqtt
            return True
        except ImportError:
            logger.error(
                "paho-mqtt not installed. Install with: pip install paho-mqtt"
            )
            return False

    def _get_topics(self) -> list[str]:
        """Get list of topics to subscribe to."""
        return [
            f"{self.TOPIC_PREFIX}/{self.channel}/+",  # All message types
            f"{self.TOPIC_PRESENCE}/{self.channel}",
            f"{self.TOPIC_CHAT}/{self.channel}",
        ]

    def connect(self) -> bool:
        """Connect to the MQTT broker."""
        if not self._ensure_paho():
            self._set_state(ConnectionState.ERROR)
            return False

        import paho.mqtt.client as mqtt

        self._set_state(ConnectionState.CONNECTING)

        try:
            # Create client with callback API version 2
            self._mqtt_client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"pymeshzork_{self.player_id}",
            )

            # Set up callbacks
            self._mqtt_client.on_connect = self._on_connect
            self._mqtt_client.on_disconnect = self._on_disconnect
            self._mqtt_client.on_message = self._on_message

            # Authentication
            if self.username and self.password:
                self._mqtt_client.username_pw_set(self.username, self.password)

            # TLS
            if self.use_tls:
                self._mqtt_client.tls_set()

            # Connect
            logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}")
            self._mqtt_client.connect(self.broker, self.port, keepalive=60)

            # Start network loop in background
            self._mqtt_client.loop_start()

            # Wait for connection with timeout
            if not self._mqtt_connected.wait(timeout=10):
                logger.error("Connection timeout")
                self._set_state(ConnectionState.ERROR)
                return False

            # Start heartbeat
            self._start_heartbeat()

            # Flush any queued messages
            self._flush_queue()

            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._set_state(ConnectionState.ERROR)
            return False

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        self._stop_heartbeat_thread()

        if self._mqtt_client:
            try:
                # Send leave message before disconnecting
                self.send_leave()
                time.sleep(0.1)  # Brief delay to send message

                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception as e:
                logger.debug(f"Error during disconnect: {e}")

        self._mqtt_connected.clear()
        self._set_state(ConnectionState.DISCONNECTED)

    def _send_raw(self, data: str) -> None:
        """Send raw data via MQTT."""
        if not self._mqtt_client or self.state != ConnectionState.CONNECTED:
            raise ConnectionError("Not connected")

        topic = f"{self.TOPIC_PREFIX}/{self.channel}/game"
        result = self._mqtt_client.publish(topic, data, qos=1)

        if result.rc != 0:
            raise ConnectionError(f"Publish failed with code {result.rc}")

    def _on_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        """Handle MQTT connection."""
        if reason_code == 0:
            logger.info("Connected to MQTT broker")
            self._set_state(ConnectionState.CONNECTED)
            self._mqtt_connected.set()

            # Subscribe to game topics
            for topic in self._get_topics():
                client.subscribe(topic, qos=1)
                logger.debug(f"Subscribed to {topic}")

            # Flush queued messages
            self._flush_queue()
        else:
            logger.error(f"Connection failed with code: {reason_code}")
            self._set_state(ConnectionState.ERROR)

    def _on_disconnect(
        self,
        client: Any,
        userdata: Any,
        flags: Any = None,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        """Handle MQTT disconnection."""
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")
        self._mqtt_connected.clear()

        if self.state != ConnectionState.DISCONNECTED:
            self._set_state(ConnectionState.RECONNECTING)
            # paho-mqtt will auto-reconnect by default

    def _on_message(
        self,
        client: Any,
        userdata: Any,
        message: Any,
    ) -> None:
        """Handle incoming MQTT message."""
        try:
            payload = message.payload.decode("utf-8")
            self._handle_incoming(payload)
        except Exception as e:
            logger.debug(f"Failed to process message: {e}")

    def send_chat(self, message: str, is_team: bool = False) -> bool:
        """Send a chat message with dedicated topic."""
        result = super().send_chat(message, is_team)

        # Also publish to dedicated chat topic for chat-only subscribers
        if self._mqtt_client and self.state == ConnectionState.CONNECTED:
            chat_data = {
                "v": PROTOCOL_VERSION,
                "p": self.player_id,
                "n": self.player_name[:16],
                "m": message[:128],
                "t": "team" if is_team else "room",
            }
            topic = f"{self.TOPIC_CHAT}/{self.channel}"
            self._mqtt_client.publish(topic, json.dumps(chat_data), qos=1)

        return result

    def publish_presence(self, online: bool = True) -> None:
        """Publish presence to dedicated presence topic."""
        if self._mqtt_client and self.state == ConnectionState.CONNECTED:
            presence_data = {
                "v": PROTOCOL_VERSION,
                "p": self.player_id,
                "n": self.player_name[:16],
                "r": self._current_room,
                "online": online,
                "ts": int(time.time()),
            }
            topic = f"{self.TOPIC_PRESENCE}/{self.channel}"
            self._mqtt_client.publish(
                topic,
                json.dumps(presence_data),
                qos=1,
                retain=True,  # Retain last presence
            )
