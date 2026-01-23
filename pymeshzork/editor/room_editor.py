"""Room editor panel for editing room properties."""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QPushButton,
    QSpinBox,
)

from pymeshzork.editor.world_model import EditorRoom


class RoomEditorPanel(QWidget):
    """Panel for editing room properties."""

    room_changed = pyqtSignal()

    # Available room flags
    ROOM_FLAGS = [
        ("RLIGHT", "Naturally lit"),
        ("RLAND", "Land room"),
        ("RWATER", "Water room"),
        ("RAIR", "Air room (flying)"),
        ("RSACRD", "Sacred (no fighting)"),
        ("RHOUSE", "Part of house"),
        ("RMUNG", "Room destroyed"),
        ("RFILL", "Can be filled"),
        ("REND", "End game room"),
    ]

    DIRECTIONS = [
        "north", "south", "east", "west",
        "northeast", "northwest", "southeast", "southwest",
        "up", "down", "enter", "exit",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.room: Optional[EditorRoom] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        # Scroll area for the panel
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        # Basic info group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)

        self.id_label = QLabel()
        self.id_label.setStyleSheet("font-family: monospace;")
        basic_layout.addRow("ID:", self.id_label)

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        basic_layout.addRow("Name:", self.name_edit)

        layout.addWidget(basic_group)

        # Descriptions group
        desc_group = QGroupBox("Descriptions")
        desc_layout = QVBoxLayout(desc_group)

        desc_layout.addWidget(QLabel("First Visit:"))
        self.desc_first_edit = QTextEdit()
        self.desc_first_edit.setMaximumHeight(100)
        self.desc_first_edit.textChanged.connect(self._on_desc_changed)
        desc_layout.addWidget(self.desc_first_edit)

        desc_layout.addWidget(QLabel("Short (revisit):"))
        self.desc_short_edit = QLineEdit()
        self.desc_short_edit.textChanged.connect(self._on_desc_changed)
        desc_layout.addWidget(self.desc_short_edit)

        layout.addWidget(desc_group)

        # Flags group
        flags_group = QGroupBox("Flags")
        flags_layout = QVBoxLayout(flags_group)

        self.flag_checkboxes: dict[str, QCheckBox] = {}
        for flag, description in self.ROOM_FLAGS:
            cb = QCheckBox(f"{flag} - {description}")
            cb.stateChanged.connect(self._on_flags_changed)
            self.flag_checkboxes[flag] = cb
            flags_layout.addWidget(cb)

        layout.addWidget(flags_group)

        # Exits group
        exits_group = QGroupBox("Exits")
        exits_layout = QVBoxLayout(exits_group)

        self.exits_table = QTableWidget()
        self.exits_table.setColumnCount(4)
        self.exits_table.setHorizontalHeaderLabels(["Direction", "Destination", "Type", ""])
        self.exits_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.exits_table.setMaximumHeight(200)
        exits_layout.addWidget(self.exits_table)

        exits_buttons = QHBoxLayout()
        self.add_exit_btn = QPushButton("Add Exit")
        self.add_exit_btn.clicked.connect(self._add_exit)
        exits_buttons.addWidget(self.add_exit_btn)
        exits_buttons.addStretch()
        exits_layout.addLayout(exits_buttons)

        layout.addWidget(exits_group)

        # Properties group
        props_group = QGroupBox("Properties")
        props_layout = QFormLayout(props_group)

        self.value_spin = QSpinBox()
        self.value_spin.setRange(0, 9999)
        self.value_spin.valueChanged.connect(self._on_value_changed)
        props_layout.addRow("Value:", self.value_spin)

        self.action_edit = QLineEdit()
        self.action_edit.setPlaceholderText("Action handler name")
        self.action_edit.textChanged.connect(self._on_action_changed)
        props_layout.addRow("Action:", self.action_edit)

        layout.addWidget(props_group)

        # Spacer
        layout.addStretch()

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def set_room(self, room: Optional[EditorRoom]) -> None:
        """Set the room to edit."""
        self.room = room
        self._update_ui()

    def _update_ui(self) -> None:
        """Update UI from room data."""
        # Block signals during update
        self._block_signals(True)

        if self.room:
            self.setEnabled(True)
            self.id_label.setText(self.room.id)
            self.name_edit.setText(self.room.name)
            self.desc_first_edit.setPlainText(self.room.description_first)
            self.desc_short_edit.setText(self.room.description_short)

            # Flags
            for flag, cb in self.flag_checkboxes.items():
                cb.setChecked(flag in self.room.flags)

            # Exits
            self._update_exits_table()

            # Properties
            self.value_spin.setValue(self.room.value)
            self.action_edit.setText(self.room.action or "")
        else:
            self.setEnabled(False)
            self.id_label.setText("")
            self.name_edit.setText("")
            self.desc_first_edit.setPlainText("")
            self.desc_short_edit.setText("")
            for cb in self.flag_checkboxes.values():
                cb.setChecked(False)
            self.exits_table.setRowCount(0)
            self.value_spin.setValue(0)
            self.action_edit.setText("")

        self._block_signals(False)

    def _update_exits_table(self) -> None:
        """Update the exits table."""
        self.exits_table.setRowCount(len(self.room.exits) if self.room else 0)

        if not self.room:
            return

        for i, exit in enumerate(self.room.exits):
            # Direction
            dir_combo = QComboBox()
            dir_combo.addItems(self.DIRECTIONS)
            current_dir = exit.get("direction", "north")
            if current_dir in self.DIRECTIONS:
                dir_combo.setCurrentText(current_dir)
            dir_combo.currentTextChanged.connect(
                lambda text, idx=i: self._on_exit_direction_changed(idx, text)
            )
            self.exits_table.setCellWidget(i, 0, dir_combo)

            # Destination
            dest_item = QTableWidgetItem(exit.get("destination", ""))
            self.exits_table.setItem(i, 1, dest_item)

            # Type
            type_combo = QComboBox()
            type_combo.addItems(["normal", "no_exit", "door", "conditional"])
            type_combo.setCurrentText(exit.get("type", "normal"))
            type_combo.currentTextChanged.connect(
                lambda text, idx=i: self._on_exit_type_changed(idx, text)
            )
            self.exits_table.setCellWidget(i, 2, type_combo)

            # Delete button
            del_btn = QPushButton("X")
            del_btn.setMaximumWidth(30)
            del_btn.clicked.connect(lambda checked, idx=i: self._remove_exit(idx))
            self.exits_table.setCellWidget(i, 3, del_btn)

    def _block_signals(self, block: bool) -> None:
        """Block or unblock signals from widgets."""
        self.name_edit.blockSignals(block)
        self.desc_first_edit.blockSignals(block)
        self.desc_short_edit.blockSignals(block)
        self.value_spin.blockSignals(block)
        self.action_edit.blockSignals(block)
        for cb in self.flag_checkboxes.values():
            cb.blockSignals(block)

    def _on_name_changed(self, text: str) -> None:
        """Handle name change."""
        if self.room:
            self.room.name = text
            self.room_changed.emit()

    def _on_desc_changed(self) -> None:
        """Handle description change."""
        if self.room:
            self.room.description_first = self.desc_first_edit.toPlainText()
            self.room.description_short = self.desc_short_edit.text()
            self.room_changed.emit()

    def _on_flags_changed(self) -> None:
        """Handle flag change."""
        if self.room:
            self.room.flags = [
                flag for flag, cb in self.flag_checkboxes.items() if cb.isChecked()
            ]
            self.room_changed.emit()

    def _on_value_changed(self, value: int) -> None:
        """Handle value change."""
        if self.room:
            self.room.value = value
            self.room_changed.emit()

    def _on_action_changed(self, text: str) -> None:
        """Handle action change."""
        if self.room:
            self.room.action = text if text else None
            self.room_changed.emit()

    def _add_exit(self) -> None:
        """Add a new exit."""
        if self.room:
            self.room.exits.append({
                "direction": "north",
                "destination": "",
            })
            self._update_exits_table()
            self.room_changed.emit()

    def _remove_exit(self, index: int) -> None:
        """Remove an exit."""
        if self.room and 0 <= index < len(self.room.exits):
            del self.room.exits[index]
            self._update_exits_table()
            self.room_changed.emit()

    def _on_exit_direction_changed(self, index: int, direction: str) -> None:
        """Handle exit direction change."""
        if self.room and 0 <= index < len(self.room.exits):
            self.room.exits[index]["direction"] = direction
            self.room_changed.emit()

    def _on_exit_type_changed(self, index: int, exit_type: str) -> None:
        """Handle exit type change."""
        if self.room and 0 <= index < len(self.room.exits):
            if exit_type == "normal":
                self.room.exits[index].pop("type", None)
            else:
                self.room.exits[index]["type"] = exit_type
            self.room_changed.emit()
