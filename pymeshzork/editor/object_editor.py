"""Object editor panel for editing object properties."""

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QLabel,
    QComboBox,
    QSpinBox,
)

from pymeshzork.editor.world_model import EditorObject, EditorWorld


class ObjectEditorPanel(QWidget):
    """Panel for editing object properties."""

    object_changed = pyqtSignal()

    # Available object flags (from ObjectFlag1 and ObjectFlag2)
    OBJECT_FLAGS = [
        # Flag1
        ("VISIBT", "Visible"),
        ("READBT", "Readable"),
        ("TAKEBT", "Can be taken"),
        ("DOORBT", "Is a door"),
        ("TRANBT", "Transparent"),
        ("CONTBT", "Container"),
        ("LITEBT", "Light source"),
        ("FOODBT", "Edible"),
        ("DRNKBT", "Drinkable"),
        ("BURNBT", "Burnable"),
        ("FLAMBT", "Flaming"),
        ("TOOLBT", "Tool"),
        ("TURNBT", "Can be turned"),
        ("ONBT", "Is on"),
        ("VICTBT", "Treasure"),
        ("NDSCBT", "No description"),
        # Flag2
        ("WEAPBT", "Weapon"),
        ("VILLBT", "Villain"),
        ("ACTRBT", "Actor/NPC"),
        ("FITEBT", "Fighter"),
        ("OPENBT", "Open/openable"),
        ("TIEBT", "Tieable"),
        ("CLMBBT", "Climbable"),
        ("VEHBT", "Vehicle"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.obj: Optional[EditorObject] = None
        self.world: Optional[EditorWorld] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
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

        self.synonyms_edit = QLineEdit()
        self.synonyms_edit.setPlaceholderText("comma-separated")
        self.synonyms_edit.textChanged.connect(self._on_synonyms_changed)
        basic_layout.addRow("Synonyms:", self.synonyms_edit)

        self.adjectives_edit = QLineEdit()
        self.adjectives_edit.setPlaceholderText("comma-separated")
        self.adjectives_edit.textChanged.connect(self._on_adjectives_changed)
        basic_layout.addRow("Adjectives:", self.adjectives_edit)

        layout.addWidget(basic_group)

        # Descriptions group
        desc_group = QGroupBox("Descriptions")
        desc_layout = QVBoxLayout(desc_group)

        desc_layout.addWidget(QLabel("Room description (when visible):"))
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("e.g., There is a sword here.")
        self.desc_edit.textChanged.connect(self._on_desc_changed)
        desc_layout.addWidget(self.desc_edit)

        desc_layout.addWidget(QLabel("Examine text:"))
        self.examine_edit = QTextEdit()
        self.examine_edit.setMaximumHeight(80)
        self.examine_edit.textChanged.connect(self._on_examine_changed)
        desc_layout.addWidget(self.examine_edit)

        desc_layout.addWidget(QLabel("Read text (if readable):"))
        self.read_edit = QTextEdit()
        self.read_edit.setMaximumHeight(80)
        self.read_edit.textChanged.connect(self._on_read_changed)
        desc_layout.addWidget(self.read_edit)

        layout.addWidget(desc_group)

        # Location group
        location_group = QGroupBox("Location")
        location_layout = QFormLayout(location_group)

        self.room_combo = QComboBox()
        self.room_combo.setEditable(True)
        self.room_combo.currentTextChanged.connect(self._on_room_changed)
        location_layout.addRow("Initial Room:", self.room_combo)

        self.container_combo = QComboBox()
        self.container_combo.setEditable(True)
        self.container_combo.currentTextChanged.connect(self._on_container_changed)
        location_layout.addRow("In Container:", self.container_combo)

        layout.addWidget(location_group)

        # Flags group
        flags_group = QGroupBox("Flags")
        flags_layout = QVBoxLayout(flags_group)

        self.flag_checkboxes: dict[str, QCheckBox] = {}
        for flag, description in self.OBJECT_FLAGS:
            cb = QCheckBox(f"{flag} - {description}")
            cb.stateChanged.connect(self._on_flags_changed)
            self.flag_checkboxes[flag] = cb
            flags_layout.addWidget(cb)

        layout.addWidget(flags_group)

        # Properties group
        props_group = QGroupBox("Properties")
        props_layout = QFormLayout(props_group)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(0, 9999)
        self.size_spin.valueChanged.connect(self._on_size_changed)
        props_layout.addRow("Size/Weight:", self.size_spin)

        self.capacity_spin = QSpinBox()
        self.capacity_spin.setRange(0, 9999)
        self.capacity_spin.valueChanged.connect(self._on_capacity_changed)
        props_layout.addRow("Capacity:", self.capacity_spin)

        self.value_spin = QSpinBox()
        self.value_spin.setRange(0, 9999)
        self.value_spin.valueChanged.connect(self._on_value_changed)
        props_layout.addRow("Value:", self.value_spin)

        self.tval_spin = QSpinBox()
        self.tval_spin.setRange(0, 9999)
        self.tval_spin.valueChanged.connect(self._on_tval_changed)
        props_layout.addRow("Trophy Value:", self.tval_spin)

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

    def set_world(self, world: Optional[EditorWorld]) -> None:
        """Set the world for room/container lookups."""
        self.world = world
        self._update_location_combos()

    def set_object(self, obj: Optional[EditorObject]) -> None:
        """Set the object to edit."""
        self.obj = obj
        self._update_ui()

    def _update_location_combos(self) -> None:
        """Update room and container combo boxes."""
        self.room_combo.clear()
        self.container_combo.clear()

        self.room_combo.addItem("")  # Empty option
        self.container_combo.addItem("")

        if self.world:
            for room_id in sorted(self.world.rooms.keys()):
                self.room_combo.addItem(room_id)

            for obj_id, obj in sorted(self.world.objects.items()):
                if "CONTBT" in obj.flags:
                    self.container_combo.addItem(obj_id)

    def _update_ui(self) -> None:
        """Update UI from object data."""
        self._block_signals(True)

        if self.obj:
            self.setEnabled(True)
            self.id_label.setText(self.obj.id)
            self.name_edit.setText(self.obj.name)
            self.synonyms_edit.setText(", ".join(self.obj.synonyms))
            self.adjectives_edit.setText(", ".join(self.obj.adjectives))
            self.desc_edit.setText(self.obj.description)
            self.examine_edit.setPlainText(self.obj.examine)
            self.read_edit.setPlainText(self.obj.read_text)

            # Location
            self.room_combo.setCurrentText(self.obj.initial_room or "")
            self.container_combo.setCurrentText(self.obj.initial_container or "")

            # Flags
            for flag, cb in self.flag_checkboxes.items():
                cb.setChecked(flag in self.obj.flags)

            # Properties
            self.size_spin.setValue(self.obj.size)
            self.capacity_spin.setValue(self.obj.capacity)
            self.value_spin.setValue(self.obj.value)
            self.tval_spin.setValue(self.obj.tval)
            self.action_edit.setText(self.obj.action or "")
        else:
            self.setEnabled(False)
            self.id_label.setText("")
            self.name_edit.setText("")
            self.synonyms_edit.setText("")
            self.adjectives_edit.setText("")
            self.desc_edit.setText("")
            self.examine_edit.setPlainText("")
            self.read_edit.setPlainText("")
            self.room_combo.setCurrentText("")
            self.container_combo.setCurrentText("")
            for cb in self.flag_checkboxes.values():
                cb.setChecked(False)
            self.size_spin.setValue(0)
            self.capacity_spin.setValue(0)
            self.value_spin.setValue(0)
            self.tval_spin.setValue(0)
            self.action_edit.setText("")

        self._block_signals(False)

    def _block_signals(self, block: bool) -> None:
        """Block or unblock signals."""
        widgets = [
            self.name_edit, self.synonyms_edit, self.adjectives_edit,
            self.desc_edit, self.examine_edit, self.read_edit,
            self.room_combo, self.container_combo,
            self.size_spin, self.capacity_spin, self.value_spin,
            self.tval_spin, self.action_edit,
        ]
        for w in widgets:
            w.blockSignals(block)
        for cb in self.flag_checkboxes.values():
            cb.blockSignals(block)

    def _on_name_changed(self, text: str) -> None:
        if self.obj:
            self.obj.name = text
            self.object_changed.emit()

    def _on_synonyms_changed(self, text: str) -> None:
        if self.obj:
            self.obj.synonyms = [s.strip() for s in text.split(",") if s.strip()]
            self.object_changed.emit()

    def _on_adjectives_changed(self, text: str) -> None:
        if self.obj:
            self.obj.adjectives = [s.strip() for s in text.split(",") if s.strip()]
            self.object_changed.emit()

    def _on_desc_changed(self, text: str) -> None:
        if self.obj:
            self.obj.description = text
            self.object_changed.emit()

    def _on_examine_changed(self) -> None:
        if self.obj:
            self.obj.examine = self.examine_edit.toPlainText()
            self.object_changed.emit()

    def _on_read_changed(self) -> None:
        if self.obj:
            self.obj.read_text = self.read_edit.toPlainText()
            self.object_changed.emit()

    def _on_room_changed(self, text: str) -> None:
        if self.obj:
            self.obj.initial_room = text if text else None
            if text:
                self.obj.initial_container = None
                self.container_combo.setCurrentText("")
            self.object_changed.emit()

    def _on_container_changed(self, text: str) -> None:
        if self.obj:
            self.obj.initial_container = text if text else None
            if text:
                self.obj.initial_room = None
                self.room_combo.setCurrentText("")
            self.object_changed.emit()

    def _on_flags_changed(self) -> None:
        if self.obj:
            self.obj.flags = [
                flag for flag, cb in self.flag_checkboxes.items() if cb.isChecked()
            ]
            self.object_changed.emit()

    def _on_size_changed(self, value: int) -> None:
        if self.obj:
            self.obj.size = value
            self.object_changed.emit()

    def _on_capacity_changed(self, value: int) -> None:
        if self.obj:
            self.obj.capacity = value
            self.object_changed.emit()

    def _on_value_changed(self, value: int) -> None:
        if self.obj:
            self.obj.value = value
            self.object_changed.emit()

    def _on_tval_changed(self, value: int) -> None:
        if self.obj:
            self.obj.tval = value
            self.object_changed.emit()

    def _on_action_changed(self, text: str) -> None:
        if self.obj:
            self.obj.action = text if text else None
            self.object_changed.emit()
