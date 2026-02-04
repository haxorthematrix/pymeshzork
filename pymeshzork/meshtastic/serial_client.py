"""Serial client for Meshtastic devices via USB.

Connects to Meshtastic nodes (T-Beam, Heltec, RAK, etc.) via USB serial
for multiplayer communication. Uses the official Meshtastic Python library.

Supported devices:
  - T-Beam (CP2102, /dev/ttyUSB0)
  - Heltec LoRa 32 V3 (CP2102, /dev/ttyUSB0)
  - RAK4631 (native USB, /dev/ttyACM0)
  - Station G2 (CP2102, /dev/ttyUSB0)

macOS device paths: /dev/cu.usbserial-* or /dev/cu.SLAB_USBtoUART
Windows device paths: COM3, COM4, etc.
"""

import logging
import threading
import time
from typing import Any

from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.protocol import (
    GameMessage,
    MessageType,
    encode_message,
    decode_message,
    PROTOCOL_VERSION,
)

logger = logging.getLogger(__name__)

# Meshtastic port number for private app data
# Using PRIVATE_APP (256) to avoid conflicts with standard Meshtastic ports
PRIVATE_APP_PORT = 256


class SerialClient(MeshtasticClient):
    """Meshtastic client using USB serial connection.

    Connects to a Meshtastic device via USB and uses its LoRa radio
    for mesh network communication. The device handles all radio
    operations; this client just sends/receives data.

    Example usage:
        client = SerialClient(
            player_name="adventurer",
            port="/dev/ttyUSB0",  # Auto-detect if None
        )
        client.on_message(handle_message)
        if client.connect():
            client.send_join("whous")
    """

    def __init__(
        self,
        player_name: str,
        port: str | None = None,
        channel: str = "pymeshzork",
    ):
        """Initialize serial client.

        Args:
            player_name: Display name for this player.
            port: Serial port path (e.g., /dev/ttyUSB0, COM3).
                  If None, auto-detects first available Meshtastic device.
            channel: Game channel name.
        """
        super().__init__(player_name, channel)

        self.port = port
        self._interface: Any = None  # meshtastic.serial_interface.SerialInterface
        self._pubsub: Any = None  # pubsub subscription

    def _ensure_meshtastic(self) -> bool:
        """Ensure meshtastic library is available."""
        try:
            import meshtastic
            import meshtastic.serial_interface
            return True
        except ImportError:
            logger.error(
                "meshtastic library not installed. Install with: pip install meshtastic"
            )
            return False

    def _find_device(self) -> str | None:
        """Auto-detect Meshtastic device port.

        Returns:
            Device path if found, None otherwise.
        """
        import serial.tools.list_ports

        # Known Meshtastic USB device identifiers
        known_devices = [
            # (VID, PID, description pattern)
            (0x10C4, 0xEA60, "CP210"),  # Silicon Labs CP2102/CP2104
            (0x1A86, 0x55D4, "CH9102"),  # WCH CH9102
            (0x303A, 0x1001, "ESP32"),  # ESP32-S3 native USB
        ]

        ports = list(serial.tools.list_ports.comports())

        for port in ports:
            # Check by VID/PID
            for vid, pid, desc in known_devices:
                if port.vid == vid and port.pid == pid:
                    logger.info(f"Found Meshtastic device at {port.device} ({desc})")
                    return port.device

            # Check by description
            if port.description:
                desc_lower = port.description.lower()
                if any(x in desc_lower for x in ["cp210", "ch910", "meshtastic", "esp32"]):
                    logger.info(f"Found Meshtastic device at {port.device} ({port.description})")
                    return port.device

        # Check common paths on Linux/macOS
        import os
        common_paths = [
            "/dev/ttyUSB0",
            "/dev/ttyUSB1",
            "/dev/ttyACM0",
            "/dev/ttyACM1",
        ]

        for path in common_paths:
            if os.path.exists(path):
                logger.info(f"Found serial device at {path}")
                return path

        return None

    def connect(self) -> bool:
        """Connect to the Meshtastic device via serial.

        Returns:
            True if connection successful, False otherwise.
        """
        if not self._ensure_meshtastic():
            self._set_state(ConnectionState.ERROR)
            return False

        if self._state == ConnectionState.CONNECTED:
            return True

        self._set_state(ConnectionState.CONNECTING)

        try:
            import meshtastic
            import meshtastic.serial_interface
            from pubsub import pub

            # Auto-detect port if not specified
            port = self.port
            if port is None:
                port = self._find_device()
                if port is None:
                    logger.error("No Meshtastic device found. Specify port with --serial-port")
                    self._set_state(ConnectionState.ERROR)
                    return False

            logger.info(f"Connecting to Meshtastic device at {port}")

            # Connect to device
            self._interface = meshtastic.serial_interface.SerialInterface(
                devPath=port,
                noProto=False,  # Use full protocol mode
            )

            # Wait for node info to be ready
            time.sleep(2)

            # Get our node info
            node_info = self._interface.getMyNodeInfo()
            if node_info:
                node_id = node_info.get("num", 0)
                logger.info(f"Connected to node {node_id:08x}")

            # Subscribe to received messages
            pub.subscribe(self._on_receive, "meshtastic.receive")
            self._pubsub = pub

            self._set_state(ConnectionState.CONNECTED)

            # Start heartbeat
            self._start_heartbeat()

            logger.info(f"Meshtastic serial client connected on {port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Meshtastic device: {e}")
            self._set_state(ConnectionState.ERROR)
            return False

    def disconnect(self) -> None:
        """Disconnect from the Meshtastic device."""
        self._stop_heartbeat_thread()

        if self._pubsub:
            try:
                from pubsub import pub
                pub.unsubscribe(self._on_receive, "meshtastic.receive")
            except Exception:
                pass
            self._pubsub = None

        if self._interface:
            try:
                # Send leave message before disconnecting
                self.send_leave()
                time.sleep(0.2)
                self._interface.close()
            except Exception as e:
                logger.debug(f"Error during disconnect: {e}")
            self._interface = None

        self._set_state(ConnectionState.DISCONNECTED)
        logger.info("Meshtastic serial client disconnected")

    def _send_raw(self, data: str) -> None:
        """Send raw data via Meshtastic mesh.

        Args:
            data: JSON-encoded message string.

        Raises:
            RuntimeError: If not connected or send fails.
        """
        if not self._interface or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("Not connected to Meshtastic device")

        try:
            from meshtastic import portnums_pb2

            # Convert string to bytes
            data_bytes = data.encode("utf-8")

            # Send as private app data to all nodes (broadcast)
            self._interface.sendData(
                data=data_bytes,
                portNum=portnums_pb2.PortNum.PRIVATE_APP,
                wantAck=False,  # Don't wait for ack for faster gameplay
                wantResponse=False,
            )

            logger.debug(f"Sent {len(data_bytes)} bytes via Meshtastic mesh")

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    def _on_receive(self, packet: dict, interface: Any = None) -> None:
        """Handle received Meshtastic packet.

        Args:
            packet: The received packet dictionary.
            interface: The interface that received the packet.
        """
        try:
            from meshtastic import portnums_pb2

            # Only process private app messages (our game data)
            port_num = packet.get("decoded", {}).get("portnum")
            if port_num != portnums_pb2.PortNum.PRIVATE_APP:
                return

            # Get the payload
            payload = packet.get("decoded", {}).get("payload")
            if not payload:
                return

            # Decode bytes to string
            if isinstance(payload, bytes):
                json_str = payload.decode("utf-8")
            else:
                json_str = str(payload)

            # Parse and handle the game message
            self._handle_incoming(json_str)

            # Log reception
            from_id = packet.get("fromId", "unknown")
            logger.debug(f"Received game message from {from_id}")

        except Exception as e:
            logger.debug(f"Failed to process received packet: {e}")

    def get_node_info(self) -> dict | None:
        """Get information about the connected Meshtastic node.

        Returns:
            Node info dictionary or None if not connected.
        """
        if self._interface:
            return self._interface.getMyNodeInfo()
        return None

    def get_mesh_nodes(self) -> dict:
        """Get information about all nodes in the mesh.

        Returns:
            Dictionary of node_id -> node_info.
        """
        if self._interface:
            return self._interface.nodes or {}
        return {}


def create_serial_client(
    player_name: str,
    port: str | None = None,
) -> SerialClient:
    """Create a serial client for Meshtastic devices.

    Args:
        player_name: Display name for the player.
        port: Serial port path. Auto-detects if None.

    Returns:
        Configured SerialClient instance.
    """
    return SerialClient(
        player_name=player_name,
        port=port,
    )


def list_serial_devices() -> list[dict]:
    """List available serial devices that might be Meshtastic nodes.

    Returns:
        List of device info dictionaries.
    """
    try:
        import serial.tools.list_ports
    except ImportError:
        return []

    devices = []
    for port in serial.tools.list_ports.comports():
        devices.append({
            "device": port.device,
            "description": port.description,
            "hwid": port.hwid,
            "vid": port.vid,
            "pid": port.pid,
        })

    return devices
