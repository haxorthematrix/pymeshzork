"""Map canvas for visualizing and editing the room graph."""

import math
from typing import Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QFont,
    QPainterPath,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
)
from PyQt6.QtWidgets import (
    QWidget,
    QMenu,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QPushButton,
    QDialogButtonBox,
)

from pymeshzork.editor.world_model import EditorWorld, EditorRoom


class DirectionPickerDialog(QDialog):
    """Dialog for picking a direction when connecting rooms."""

    DIRECTIONS = [
        ("north", "North"),
        ("south", "South"),
        ("east", "East"),
        ("west", "West"),
        ("northeast", "Northeast"),
        ("northwest", "Northwest"),
        ("southeast", "Southeast"),
        ("southwest", "Southwest"),
        ("up", "Up"),
        ("down", "Down"),
        ("enter", "Enter"),
        ("exit", "Exit"),
    ]

    def __init__(
        self,
        from_room: str,
        to_room: str,
        suggested_direction: str = "north",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect Rooms")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Info label
        info = QLabel(f"Connect <b>{from_room}</b> to <b>{to_room}</b>")
        layout.addWidget(info)

        # Direction picker
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Direction:"))
        self.direction_combo = QComboBox()
        for value, label in self.DIRECTIONS:
            self.direction_combo.addItem(label, value)
        # Set suggested direction
        for i, (value, _) in enumerate(self.DIRECTIONS):
            if value == suggested_direction:
                self.direction_combo.setCurrentIndex(i)
                break
        dir_layout.addWidget(self.direction_combo)
        layout.addLayout(dir_layout)

        # Bidirectional checkbox
        self.bidirectional_check = QCheckBox("Create bidirectional connection (two-way)")
        self.bidirectional_check.setChecked(True)
        layout.addWidget(self.bidirectional_check)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_direction(self) -> str:
        """Get the selected direction."""
        return self.direction_combo.currentData()

    def is_bidirectional(self) -> bool:
        """Check if bidirectional connection is selected."""
        return self.bidirectional_check.isChecked()


class MapCanvas(QWidget):
    """Canvas widget for displaying and editing the room map."""

    # Signals
    room_selected = pyqtSignal(str)  # room_id
    room_moved = pyqtSignal(str, float, float)  # room_id, x, y
    connection_created = pyqtSignal(str, str, str, bool)  # from_room, to_room, direction, bidirectional

    # Constants
    ROOM_WIDTH = 120
    ROOM_HEIGHT = 60
    ROOM_RADIUS = 8
    GRID_SIZE = 20

    # Colors
    COLOR_BACKGROUND = QColor(40, 44, 52)
    COLOR_GRID = QColor(60, 64, 72)
    COLOR_ROOM_FILL = QColor(70, 130, 180)
    COLOR_ROOM_BORDER = QColor(100, 160, 210)
    COLOR_ROOM_SELECTED = QColor(255, 200, 100)
    COLOR_ROOM_START = QColor(100, 200, 100)
    COLOR_ROOM_DARK = QColor(100, 80, 120)
    COLOR_TEXT = QColor(255, 255, 255)
    COLOR_CONNECTION = QColor(150, 150, 150)
    COLOR_CONNECTION_ONEWAY = QColor(200, 100, 100)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # World data
        self.world: Optional[EditorWorld] = None

        # View state
        self.zoom_level: float = 1.0
        self.pan_offset: QPointF = QPointF(0, 0)
        self.min_zoom: float = 0.1
        self.max_zoom: float = 3.0

        # Interaction state
        self.selected_room_id: Optional[str] = None
        self.hovered_room_id: Optional[str] = None
        self.dragging: bool = False
        self.drag_start: QPointF = QPointF()
        self.drag_room_start: QPointF = QPointF()
        self.panning: bool = False
        self.pan_start: QPointF = QPointF()

        # Connection creation mode
        self.connecting: bool = False
        self.connect_from_room: Optional[str] = None
        self.connect_mouse_pos: QPointF = QPointF()

    def set_world(self, world: Optional[EditorWorld]) -> None:
        """Set the world to display."""
        self.world = world
        self.selected_room_id = None
        self.hovered_room_id = None
        self.update()

    def select_room(self, room_id: Optional[str]) -> None:
        """Select a room by ID."""
        self.selected_room_id = room_id
        if room_id:
            self.room_selected.emit(room_id)
        self.update()

    def add_room_node(self, room: EditorRoom) -> None:
        """Add a room node to the display."""
        self.update()

    def remove_room_node(self, room_id: str) -> None:
        """Remove a room node from the display."""
        if self.selected_room_id == room_id:
            self.selected_room_id = None
        self.update()

    # === Zoom and Pan ===

    def zoom_in(self) -> None:
        """Zoom in."""
        self.zoom_level = min(self.max_zoom, self.zoom_level * 1.2)
        self.update()

    def zoom_out(self) -> None:
        """Zoom out."""
        self.zoom_level = max(self.min_zoom, self.zoom_level / 1.2)
        self.update()

    def zoom_fit(self) -> None:
        """Fit all rooms in view."""
        if not self.world or not self.world.rooms:
            self.zoom_level = 1.0
            self.pan_offset = QPointF(0, 0)
            self.update()
            return

        # Find bounding box of all rooms
        min_x = min(r.x for r in self.world.rooms.values())
        max_x = max(r.x + self.ROOM_WIDTH for r in self.world.rooms.values())
        min_y = min(r.y for r in self.world.rooms.values())
        max_y = max(r.y + self.ROOM_HEIGHT for r in self.world.rooms.values())

        # Add padding
        padding = 50
        min_x -= padding
        min_y -= padding
        max_x += padding
        max_y += padding

        # Calculate zoom to fit
        width = max_x - min_x
        height = max_y - min_y
        zoom_x = self.width() / width if width > 0 else 1.0
        zoom_y = self.height() / height if height > 0 else 1.0
        self.zoom_level = min(zoom_x, zoom_y, 1.0)

        # Center the view
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        self.pan_offset = QPointF(
            self.width() / 2 - center_x * self.zoom_level,
            self.height() / 2 - center_y * self.zoom_level,
        )

        self.update()

    def auto_layout(self) -> None:
        """Automatically arrange rooms in a grid-like layout."""
        if not self.world or not self.world.rooms:
            return

        # Simple grid layout
        cols = max(3, int(math.sqrt(len(self.world.rooms))))
        spacing_x = self.ROOM_WIDTH + 80
        spacing_y = self.ROOM_HEIGHT + 60

        for i, (room_id, room) in enumerate(self.world.rooms.items()):
            col = i % cols
            row = i // cols
            room.x = 100 + col * spacing_x
            room.y = 100 + row * spacing_y

        self.update()

    # === Coordinate Conversion ===

    def world_to_screen(self, world_pos: QPointF) -> QPointF:
        """Convert world coordinates to screen coordinates."""
        return QPointF(
            world_pos.x() * self.zoom_level + self.pan_offset.x(),
            world_pos.y() * self.zoom_level + self.pan_offset.y(),
        )

    def screen_to_world(self, screen_pos: QPointF) -> QPointF:
        """Convert screen coordinates to world coordinates."""
        return QPointF(
            (screen_pos.x() - self.pan_offset.x()) / self.zoom_level,
            (screen_pos.y() - self.pan_offset.y()) / self.zoom_level,
        )

    def room_at_pos(self, world_pos: QPointF) -> Optional[str]:
        """Find room at world position."""
        if not self.world:
            return None

        for room_id, room in self.world.rooms.items():
            rect = QRectF(room.x, room.y, self.ROOM_WIDTH, self.ROOM_HEIGHT)
            if rect.contains(world_pos):
                return room_id
        return None

    # === Painting ===

    def paintEvent(self, event) -> None:
        """Paint the canvas."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self.COLOR_BACKGROUND)

        # Grid
        self._draw_grid(painter)

        if not self.world:
            return

        # Transform for zoom and pan
        painter.translate(self.pan_offset)
        painter.scale(self.zoom_level, self.zoom_level)

        # Draw connections first (behind rooms)
        self._draw_connections(painter)

        # Draw connection in progress
        if self.connecting and self.connect_from_room:
            self._draw_connection_preview(painter)

        # Draw rooms
        for room_id, room in self.world.rooms.items():
            self._draw_room(painter, room, room_id)

    def _draw_grid(self, painter: QPainter) -> None:
        """Draw the background grid."""
        pen = QPen(self.COLOR_GRID, 1)
        painter.setPen(pen)

        grid_size = self.GRID_SIZE * self.zoom_level

        # Vertical lines
        start_x = self.pan_offset.x() % grid_size
        x = start_x
        while x < self.width():
            painter.drawLine(int(x), 0, int(x), self.height())
            x += grid_size

        # Horizontal lines
        start_y = self.pan_offset.y() % grid_size
        y = start_y
        while y < self.height():
            painter.drawLine(0, int(y), self.width(), int(y))
            y += grid_size

    def _draw_room(self, painter: QPainter, room: EditorRoom, room_id: str) -> None:
        """Draw a single room node."""
        rect = QRectF(room.x, room.y, self.ROOM_WIDTH, self.ROOM_HEIGHT)

        # Determine room color
        fill_color = self.COLOR_ROOM_FILL
        border_color = self.COLOR_ROOM_BORDER

        # Check if this is the starting room
        if self.world and self.world.meta.get("starting_room") == room_id:
            fill_color = self.COLOR_ROOM_START

        # Check if room is dark
        if "RLIGHT" not in room.flags:
            fill_color = self.COLOR_ROOM_DARK

        # Check selection/hover state
        if room_id == self.selected_room_id:
            border_color = self.COLOR_ROOM_SELECTED
        elif room_id == self.hovered_room_id:
            border_color = QColor(200, 200, 200)

        # Draw room rectangle with rounded corners
        painter.setPen(QPen(border_color, 2))
        painter.setBrush(QBrush(fill_color))
        painter.drawRoundedRect(rect, self.ROOM_RADIUS, self.ROOM_RADIUS)

        # Draw room name
        painter.setPen(self.COLOR_TEXT)
        font = QFont("Sans", 9)
        font.setBold(room_id == self.selected_room_id)
        painter.setFont(font)

        # Truncate name if too long
        name = room.name
        if len(name) > 15:
            name = name[:14] + "..."

        text_rect = QRectF(room.x + 4, room.y + 4, self.ROOM_WIDTH - 8, 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, name)

        # Draw room ID below name
        painter.setPen(QColor(180, 180, 180))
        font.setBold(False)
        font.setPointSize(7)
        painter.setFont(font)
        id_rect = QRectF(room.x + 4, room.y + 22, self.ROOM_WIDTH - 8, 16)
        painter.drawText(id_rect, Qt.AlignmentFlag.AlignCenter, f"[{room_id}]")

        # Draw exit indicators
        self._draw_exit_indicators(painter, room)

    def _draw_exit_indicators(self, painter: QPainter, room: EditorRoom) -> None:
        """Draw small indicators showing which directions have exits."""
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.setBrush(QBrush(QColor(200, 200, 200)))

        cx = room.x + self.ROOM_WIDTH / 2
        cy = room.y + self.ROOM_HEIGHT / 2
        size = 4

        for exit in room.exits:
            direction = exit.get("direction", "").lower()
            dx, dy = self._direction_to_offset(direction)
            if dx != 0 or dy != 0:
                ex = cx + dx * (self.ROOM_WIDTH / 2 - 4)
                ey = cy + dy * (self.ROOM_HEIGHT / 2 - 4)
                painter.drawEllipse(QPointF(ex, ey), size, size)

    def _draw_connections(self, painter: QPainter) -> None:
        """Draw connection lines between rooms."""
        if not self.world:
            return

        drawn = set()  # Track drawn connections to avoid duplicates

        for room_id, room in self.world.rooms.items():
            for exit in room.exits:
                dest_id = exit.get("destination")
                if not dest_id or dest_id not in self.world.rooms:
                    continue

                # Create connection key to avoid duplicates
                conn_key = tuple(sorted([room_id, dest_id]))
                if conn_key in drawn:
                    continue
                drawn.add(conn_key)

                dest_room = self.world.rooms[dest_id]

                # Calculate line endpoints (center of rooms)
                start = QPointF(
                    room.x + self.ROOM_WIDTH / 2,
                    room.y + self.ROOM_HEIGHT / 2,
                )
                end = QPointF(
                    dest_room.x + self.ROOM_WIDTH / 2,
                    dest_room.y + self.ROOM_HEIGHT / 2,
                )

                # Check if one-way connection
                is_bidirectional = any(
                    e.get("destination") == room_id for e in dest_room.exits
                )

                # Draw line
                color = self.COLOR_CONNECTION if is_bidirectional else self.COLOR_CONNECTION_ONEWAY
                painter.setPen(QPen(color, 2))
                painter.drawLine(start, end)

                # Draw arrow for one-way connections
                if not is_bidirectional:
                    self._draw_arrow(painter, start, end, color)

    def _draw_arrow(
        self, painter: QPainter, start: QPointF, end: QPointF, color: QColor
    ) -> None:
        """Draw an arrow head at the end of a line."""
        # Calculate direction
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return

        # Normalize
        dx /= length
        dy /= length

        # Arrow size
        arrow_size = 12

        # Calculate arrow points
        mid = QPointF(
            (start.x() + end.x()) / 2,
            (start.y() + end.y()) / 2,
        )

        # Arrow tip at midpoint
        tip = mid
        base1 = QPointF(
            tip.x() - arrow_size * dx + arrow_size * 0.5 * dy,
            tip.y() - arrow_size * dy - arrow_size * 0.5 * dx,
        )
        base2 = QPointF(
            tip.x() - arrow_size * dx - arrow_size * 0.5 * dy,
            tip.y() - arrow_size * dy + arrow_size * 0.5 * dx,
        )

        # Draw arrow
        path = QPainterPath()
        path.moveTo(tip)
        path.lineTo(base1)
        path.lineTo(base2)
        path.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(path)

    def _draw_connection_preview(self, painter: QPainter) -> None:
        """Draw connection being created."""
        if not self.world or not self.connect_from_room:
            return

        from_room = self.world.get_room(self.connect_from_room)
        if not from_room:
            return

        start = QPointF(
            from_room.x + self.ROOM_WIDTH / 2,
            from_room.y + self.ROOM_HEIGHT / 2,
        )
        end = self.screen_to_world(self.connect_mouse_pos)

        painter.setPen(QPen(QColor(100, 200, 100), 2, Qt.PenStyle.DashLine))
        painter.drawLine(start, end)

    def _direction_to_offset(self, direction: str) -> tuple[float, float]:
        """Convert direction to x, y offset."""
        offsets = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
            "northeast": (0.7, -0.7),
            "northwest": (-0.7, -0.7),
            "southeast": (0.7, 0.7),
            "southwest": (-0.7, 0.7),
            "up": (0, -0.8),
            "down": (0, 0.8),
        }
        return offsets.get(direction, (0, 0))

    # === Mouse Events ===

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press."""
        world_pos = self.screen_to_world(QPointF(event.position()))
        room_id = self.room_at_pos(world_pos)

        if event.button() == Qt.MouseButton.LeftButton:
            if room_id:
                # Select room
                self.select_room(room_id)
                # Start dragging room
                self.dragging = True
                self.drag_start = event.position()
                room = self.world.get_room(room_id) if self.world else None
                if room:
                    self.drag_room_start = QPointF(room.x, room.y)
            else:
                # Click on empty space - deselect and start panning
                self.select_room(None)
                self.panning = True
                self.pan_start = event.position()

        elif event.button() == Qt.MouseButton.RightButton:
            if room_id:
                self._show_room_context_menu(event.position(), room_id)
            else:
                self._show_canvas_context_menu(event.position())

        elif event.button() == Qt.MouseButton.MiddleButton:
            # Start panning with middle button
            self.panning = True
            self.pan_start = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move."""
        world_pos = self.screen_to_world(QPointF(event.position()))

        # Update hovered room
        new_hover = self.room_at_pos(world_pos)
        if new_hover != self.hovered_room_id:
            self.hovered_room_id = new_hover
            self.update()

        # Handle dragging
        if self.dragging and self.selected_room_id and self.world:
            delta = event.position() - self.drag_start
            new_x = self.drag_room_start.x() + delta.x() / self.zoom_level
            new_y = self.drag_room_start.y() + delta.y() / self.zoom_level

            # Snap to grid
            new_x = round(new_x / self.GRID_SIZE) * self.GRID_SIZE
            new_y = round(new_y / self.GRID_SIZE) * self.GRID_SIZE

            room = self.world.get_room(self.selected_room_id)
            if room:
                room.x = new_x
                room.y = new_y
                self.update()

        # Handle panning
        elif self.panning:
            delta = event.position() - self.pan_start
            self.pan_offset += QPointF(delta.x(), delta.y())
            self.pan_start = event.position()
            self.update()

        # Handle connection creation
        elif self.connecting:
            self.connect_mouse_pos = QPointF(event.position())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging and self.selected_room_id and self.world:
                room = self.world.get_room(self.selected_room_id)
                if room:
                    self.room_moved.emit(self.selected_room_id, room.x, room.y)
            self.dragging = False
            self.panning = False

            if self.connecting:
                world_pos = self.screen_to_world(QPointF(event.position()))
                target_room = self.room_at_pos(world_pos)
                if target_room and target_room != self.connect_from_room:
                    self._complete_connection(target_room)
                self.connecting = False
                self.connect_from_room = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.update()

        elif event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double click."""
        world_pos = self.screen_to_world(QPointF(event.position()))
        room_id = self.room_at_pos(world_pos)

        if not room_id and event.button() == Qt.MouseButton.LeftButton:
            # Create new room at click position
            if self.world:
                room = self.world.add_room()
                room.x = round(world_pos.x() / self.GRID_SIZE) * self.GRID_SIZE
                room.y = round(world_pos.y() / self.GRID_SIZE) * self.GRID_SIZE
                self.select_room(room.id)
                self.room_moved.emit(room.id, room.x, room.y)
                self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        # Get mouse position in world coordinates before zoom
        mouse_pos = QPointF(event.position())
        world_pos_before = self.screen_to_world(mouse_pos)

        # Zoom
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_level = min(self.max_zoom, self.zoom_level * 1.1)
        else:
            self.zoom_level = max(self.min_zoom, self.zoom_level / 1.1)

        # Adjust pan to keep mouse position stable
        world_pos_after = self.screen_to_world(mouse_pos)
        self.pan_offset += QPointF(
            (world_pos_after.x() - world_pos_before.x()) * self.zoom_level,
            (world_pos_after.y() - world_pos_before.y()) * self.zoom_level,
        )

        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press."""
        if event.key() == Qt.Key.Key_Delete:
            if self.selected_room_id:
                # Signal to delete room (handled by main window)
                pass
        elif event.key() == Qt.Key.Key_Escape:
            if self.connecting:
                self.connecting = False
                self.connect_from_room = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.update()
            else:
                self.select_room(None)
        elif event.key() == Qt.Key.Key_C:
            # Start connection mode from selected room
            if self.selected_room_id and not self.connecting:
                self._start_connection(self.selected_room_id)
        else:
            super().keyPressEvent(event)

    # === Context Menus ===

    def _show_room_context_menu(self, pos: QPointF, room_id: str) -> None:
        """Show context menu for a room."""
        menu = QMenu(self)

        action_edit = menu.addAction("Edit Room")
        action_edit.triggered.connect(lambda: self.select_room(room_id))

        menu.addSeparator()

        action_connect = menu.addAction("Connect to Another Room... (C)")
        action_connect.triggered.connect(lambda: self._start_connection(room_id))

        # Show hint about how to use
        hint = menu.addAction("  → Click target room or press Esc to cancel")
        hint.setEnabled(False)

        menu.addSeparator()

        action_delete = menu.addAction("Delete Room")
        action_delete.triggered.connect(lambda: self._request_delete_room(room_id))

        menu.exec(self.mapToGlobal(pos.toPoint()))

    def _show_canvas_context_menu(self, pos: QPointF) -> None:
        """Show context menu for empty canvas area."""
        menu = QMenu(self)

        action_add = menu.addAction("Add Room Here")
        action_add.triggered.connect(lambda: self._add_room_at(pos))

        menu.addSeparator()

        action_fit = menu.addAction("Fit to View")
        action_fit.triggered.connect(self.zoom_fit)

        action_layout = menu.addAction("Auto Layout")
        action_layout.triggered.connect(self.auto_layout)

        menu.exec(self.mapToGlobal(pos.toPoint()))

    def _start_connection(self, room_id: str) -> None:
        """Start creating a connection from a room."""
        self.connecting = True
        self.connect_from_room = room_id
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def _complete_connection(self, to_room: str) -> None:
        """Complete a connection to target room."""
        if not self.connect_from_room or not self.world:
            return

        from_room_obj = self.world.get_room(self.connect_from_room)
        to_room_obj = self.world.get_room(to_room)

        if not from_room_obj or not to_room_obj:
            return

        # Guess direction based on relative positions
        suggested = self._guess_direction(from_room_obj, to_room_obj)

        # Show direction picker dialog
        dialog = DirectionPickerDialog(
            from_room_obj.name,
            to_room_obj.name,
            suggested,
            self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            direction = dialog.get_direction()
            bidirectional = dialog.is_bidirectional()
            self.connection_created.emit(
                self.connect_from_room, to_room, direction, bidirectional
            )

    def _guess_direction(self, from_room: EditorRoom, to_room: EditorRoom) -> str:
        """Guess the direction based on relative room positions."""
        dx = to_room.x - from_room.x
        dy = to_room.y - from_room.y

        # Determine primary direction based on angle
        if abs(dx) < 30 and abs(dy) < 30:
            return "north"  # Default for overlapping

        angle = math.atan2(-dy, dx)  # Negative dy because screen Y is inverted
        # Convert to degrees and normalize to 0-360
        degrees = (math.degrees(angle) + 360) % 360

        # Map angle to direction (0° = east, 90° = north, etc.)
        if 337.5 <= degrees or degrees < 22.5:
            return "east"
        elif 22.5 <= degrees < 67.5:
            return "northeast"
        elif 67.5 <= degrees < 112.5:
            return "north"
        elif 112.5 <= degrees < 157.5:
            return "northwest"
        elif 157.5 <= degrees < 202.5:
            return "west"
        elif 202.5 <= degrees < 247.5:
            return "southwest"
        elif 247.5 <= degrees < 292.5:
            return "south"
        else:  # 292.5 <= degrees < 337.5
            return "southeast"

    def _add_room_at(self, screen_pos: QPointF) -> None:
        """Add a new room at screen position."""
        if self.world:
            world_pos = self.screen_to_world(screen_pos)
            room = self.world.add_room()
            room.x = round(world_pos.x() / self.GRID_SIZE) * self.GRID_SIZE
            room.y = round(world_pos.y() / self.GRID_SIZE) * self.GRID_SIZE
            self.select_room(room.id)
            self.room_moved.emit(room.id, room.x, room.y)
            self.update()

    def _request_delete_room(self, room_id: str) -> None:
        """Request deletion of a room (emits signal for main window to handle)."""
        # This would emit a signal for the main window to handle deletion
        pass
