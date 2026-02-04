"""Native client for meshtasticd on Raspberry Pi.

Connects to meshtasticd (Meshtastic Native) running on the same machine
via TCP interface. This allows PyMeshZork to use the Radio Bonnet with
full Meshtastic protocol compatibility.

meshtasticd provides:
  - Full Meshtastic mesh protocol
  - Interoperability with all Meshtastic devices (Heltec, T-Beam, etc.)
  - TCP API on port 4403 (configurable)

Requires meshtasticd to be running and configured for the Radio Bonnet.
"""

import logging
import socket
import threading
import time
from typing import Any

from pymeshzork.meshtastic.client import MeshtasticClient, ConnectionState
from pymeshzork.meshtastic.protocol import (
    GameMessage,
    encode_message,
    decode_message,
    PROTOCOL_VERSION,
)

logger = logging.getLogger(__name__)

# Default meshtasticd TCP port
DEFAULT_TCP_PORT = 4403


class NativeClient(MeshtasticClient):
    """Meshtastic client using meshtasticd TCP interface.

    Connects to meshtasticd running on the local machine, which handles
    the LoRa radio communication via the Radio Bonnet.

    Example usage:
        client = NativeClient(
            player_name="adventurer",
            host="localhost",
            port=4403,
        )
        client.on_message(handle_message)
        if client.connect():
            client.send_join("whous")
    """

    def __init__(
        self,
        player_name: str,
        host: str = "localhost",
        port: int = DEFAULT_TCP_PORT,
        channel: str = "pymeshzork",
    ):
        """Initialize native client.

        Args:
            player_name: Display name for this player.
            host: meshtasticd hostname (default: localhost).
            port: meshtasticd TCP port (default: 4403).
            channel: Game channel name.
        """
        super().__init__(player_name, channel)

        self.host = host
        self.port = port
        self._interface: Any = None  # meshtastic.tcp_interface.TCPInterface

    def _ensure_meshtastic(self) -> bool:
        """Ensure meshtastic library is available."""
        try:
            import meshtastic
            import meshtastic.tcp_interface
            return True
        except ImportError:
            logger.error(
                "meshtastic library not installed. Install with: pip install meshtastic"
            )
            return False

    def _check_meshtasticd(self) -> bool:
        """Check if meshtasticd is running and accessible."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def connect(self) -> bool:
        """Connect to meshtasticd via TCP.

        Returns:
            True if connection successful, False otherwise.
        """
        if not self._ensure_meshtastic():
            self._set_state(ConnectionState.ERROR)
            return False

        if self._state == ConnectionState.CONNECTED:
            return True

        self._set_state(ConnectionState.CONNECTING)

        # Check if meshtasticd is running
        if not self._check_meshtasticd():
            logger.error(
                f"meshtasticd not running at {self.host}:{self.port}. "
                "Start it with: sudo systemctl start meshtasticd"
            )
            self._set_state(ConnectionState.ERROR)
            return False

        try:
            import meshtastic.tcp_interface
            from pubsub import pub

            logger.info(f"Connecting to meshtasticd at {self.host}:{self.port}")

            # Connect via TCP interface
            self._interface = meshtastic.tcp_interface.TCPInterface(
                hostname=self.host,
                portNumber=self.port,
            )

            # Wait for connection to establish
            time.sleep(2)

            # Get node info
            node_info = self._interface.getMyNodeInfo()
            if node_info:
                node_id = node_info.get("num", 0)
                logger.info(f"Connected to meshtasticd node {node_id:08x}")

            # Subscribe to received messages
            pub.subscribe(self._on_receive, "meshtastic.receive")

            self._set_state(ConnectionState.CONNECTED)

            # Start heartbeat
            self._start_heartbeat()

            logger.info(f"Native client connected to meshtasticd")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to meshtasticd: {e}")
            self._set_state(ConnectionState.ERROR)
            return False

    def disconnect(self) -> None:
        """Disconnect from meshtasticd."""
        self._stop_heartbeat_thread()

        try:
            from pubsub import pub
            pub.unsubscribe(self._on_receive, "meshtastic.receive")
        except Exception:
            pass

        if self._interface:
            try:
                self.send_leave()
                time.sleep(0.2)
                self._interface.close()
            except Exception as e:
                logger.debug(f"Error during disconnect: {e}")
            self._interface = None

        self._set_state(ConnectionState.DISCONNECTED)
        logger.info("Native client disconnected")

    def _send_raw(self, data: str) -> None:
        """Send raw data via meshtasticd.

        Args:
            data: JSON-encoded message string.

        Raises:
            RuntimeError: If not connected or send fails.
        """
        if not self._interface or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("Not connected to meshtasticd")

        try:
            from meshtastic import portnums_pb2

            # Convert string to bytes
            data_bytes = data.encode("utf-8")

            # Send as private app data to all nodes (broadcast)
            self._interface.sendData(
                data=data_bytes,
                portNum=portnums_pb2.PortNum.PRIVATE_APP,
                wantAck=False,
                wantResponse=False,
            )

            logger.debug(f"Sent {len(data_bytes)} bytes via meshtasticd")

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

            from_id = packet.get("fromId", "unknown")
            logger.debug(f"Received game message from {from_id}")

        except Exception as e:
            logger.debug(f"Failed to process received packet: {e}")

    def get_node_info(self) -> dict | None:
        """Get information about the meshtasticd node.

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


def create_native_client(
    player_name: str,
    host: str = "localhost",
    port: int = DEFAULT_TCP_PORT,
) -> NativeClient:
    """Create a native client for meshtasticd.

    Args:
        player_name: Display name for the player.
        host: meshtasticd hostname.
        port: meshtasticd TCP port.

    Returns:
        Configured NativeClient instance.
    """
    return NativeClient(
        player_name=player_name,
        host=host,
        port=port,
    )


def check_meshtasticd_running(
    host: str = "localhost",
    port: int = DEFAULT_TCP_PORT,
) -> bool:
    """Check if meshtasticd is running and accessible.

    Args:
        host: meshtasticd hostname.
        port: meshtasticd TCP port.

    Returns:
        True if meshtasticd is accessible.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False
