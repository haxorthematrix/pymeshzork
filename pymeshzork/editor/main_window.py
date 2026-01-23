"""Main window for the PyMeshZork Map Editor."""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QCloseEvent
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QMenuBar,
    QMenu,
    QToolBar,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QLabel,
)

from pymeshzork.editor.map_canvas import MapCanvas
from pymeshzork.editor.room_editor import RoomEditorPanel
from pymeshzork.editor.object_editor import ObjectEditorPanel
from pymeshzork.editor.world_model import EditorWorld


class MainWindow(QMainWindow):
    """Main application window for the map editor."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyMeshZork Map Editor")
        self.setMinimumSize(1200, 800)

        # Editor state
        self.world: Optional[EditorWorld] = None
        self.current_file: Optional[Path] = None
        self.is_modified: bool = False

        # Settings
        self.settings = QSettings("PyMeshZork", "MapEditor")

        # Set up UI
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._restore_geometry()

        # Start with new world
        self._new_world()

    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        # Central widget with horizontal splitter
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main splitter: left panel | map canvas | right panel
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter)

        # Left panel - Object list/tree
        self.left_panel = self._create_left_panel()
        self.main_splitter.addWidget(self.left_panel)

        # Center - Map canvas
        self.map_canvas = MapCanvas()
        self.map_canvas.room_selected.connect(self._on_room_selected)
        self.map_canvas.room_moved.connect(self._on_room_moved)
        self.map_canvas.connection_created.connect(self._on_connection_created)
        self.main_splitter.addWidget(self.map_canvas)

        # Right panel - Properties editors
        self.right_panel = self._create_right_panel()
        self.main_splitter.addWidget(self.right_panel)

        # Set splitter sizes (left: 200, center: stretch, right: 350)
        self.main_splitter.setSizes([200, 650, 350])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

    def _create_left_panel(self) -> QWidget:
        """Create the left panel with world overview."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        # Tabs for Rooms and Objects lists
        tabs = QTabWidget()

        # Rooms list placeholder
        rooms_widget = QWidget()
        rooms_layout = QVBoxLayout(rooms_widget)
        self.rooms_list_label = QLabel("Rooms: 0")
        rooms_layout.addWidget(self.rooms_list_label)
        rooms_layout.addStretch()
        tabs.addTab(rooms_widget, "Rooms")

        # Objects list placeholder
        objects_widget = QWidget()
        objects_layout = QVBoxLayout(objects_widget)
        self.objects_list_label = QLabel("Objects: 0")
        objects_layout.addWidget(self.objects_list_label)
        objects_layout.addStretch()
        tabs.addTab(objects_widget, "Objects")

        layout.addWidget(tabs)
        return panel

    def _create_right_panel(self) -> QWidget:
        """Create the right panel with property editors."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        # Tabs for Room and Object editors
        self.editor_tabs = QTabWidget()

        # Room editor
        self.room_editor = RoomEditorPanel()
        self.room_editor.room_changed.connect(self._on_room_changed)
        self.editor_tabs.addTab(self.room_editor, "Room")

        # Object editor
        self.object_editor = ObjectEditorPanel()
        self.object_editor.object_changed.connect(self._on_object_changed)
        self.editor_tabs.addTab(self.object_editor, "Object")

        layout.addWidget(self.editor_tabs)
        return panel

    def _setup_menus(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()
        # Disable native menubar on macOS to avoid menu visibility issues
        menubar.setNativeMenuBar(False)

        # File menu
        file_menu = menubar.addMenu("&File")

        self.action_new = QAction("&New World", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self._new_world)
        file_menu.addAction(self.action_new)

        self.action_open = QAction("&Open...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self._open_file)
        file_menu.addAction(self.action_open)

        file_menu.addSeparator()

        self.action_save = QAction("&Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self._save_file)
        file_menu.addAction(self.action_save)

        self.action_save_as = QAction("Save &As...", self)
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_save_as.triggered.connect(self._save_file_as)
        file_menu.addAction(self.action_save_as)

        file_menu.addSeparator()

        self.action_quit = QAction("&Quit", self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(self.close)
        file_menu.addAction(self.action_quit)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self.action_undo = QAction("&Undo", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.setEnabled(False)
        edit_menu.addAction(self.action_undo)

        self.action_redo = QAction("&Redo", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.setEnabled(False)
        edit_menu.addAction(self.action_redo)

        edit_menu.addSeparator()

        self.action_add_room = QAction("Add &Room", self)
        self.action_add_room.setShortcut(QKeySequence("Ctrl+R"))
        self.action_add_room.triggered.connect(self._add_room)
        edit_menu.addAction(self.action_add_room)

        self.action_add_object = QAction("Add &Object", self)
        self.action_add_object.setShortcut(QKeySequence("Ctrl+O"))
        self.action_add_object.triggered.connect(self._add_object)
        edit_menu.addAction(self.action_add_object)

        self.action_delete = QAction("&Delete Selected", self)
        self.action_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self.action_delete.triggered.connect(self._delete_selected)
        edit_menu.addAction(self.action_delete)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.action_zoom_in = QAction("Zoom &In", self)
        self.action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.action_zoom_in.triggered.connect(self._zoom_in)
        view_menu.addAction(self.action_zoom_in)

        self.action_zoom_out = QAction("Zoom &Out", self)
        self.action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.action_zoom_out.triggered.connect(self._zoom_out)
        view_menu.addAction(self.action_zoom_out)

        self.action_zoom_fit = QAction("&Fit to Window", self)
        self.action_zoom_fit.setShortcut(QKeySequence("Ctrl+0"))
        self.action_zoom_fit.triggered.connect(self._zoom_fit)
        view_menu.addAction(self.action_zoom_fit)

        view_menu.addSeparator()

        self.action_auto_layout = QAction("&Auto Layout", self)
        self.action_auto_layout.setShortcut(QKeySequence("Ctrl+L"))
        self.action_auto_layout.triggered.connect(self._auto_layout)
        view_menu.addAction(self.action_auto_layout)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        self.action_validate = QAction("&Validate World", self)
        self.action_validate.setShortcut(QKeySequence("Ctrl+T"))
        self.action_validate.triggered.connect(self._validate_world)
        tools_menu.addAction(self.action_validate)

        self.action_find_orphans = QAction("Find &Orphan Rooms", self)
        self.action_find_orphans.triggered.connect(self._find_orphans)
        tools_menu.addAction(self.action_find_orphans)

        tools_menu.addSeparator()

        self.action_test_play = QAction("Test &Play", self)
        self.action_test_play.setShortcut(QKeySequence("F5"))
        self.action_test_play.triggered.connect(self._test_play)
        tools_menu.addAction(self.action_test_play)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        self.action_about = QAction("&About", self)
        self.action_about.triggered.connect(self._show_about)
        help_menu.addAction(self.action_about)

    def _setup_toolbar(self) -> None:
        """Set up the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(self.action_new)
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_save)
        toolbar.addSeparator()
        toolbar.addAction(self.action_add_room)
        toolbar.addAction(self.action_add_object)
        toolbar.addSeparator()
        toolbar.addAction(self.action_zoom_in)
        toolbar.addAction(self.action_zoom_out)
        toolbar.addAction(self.action_zoom_fit)
        toolbar.addAction(self.action_auto_layout)
        toolbar.addSeparator()
        toolbar.addAction(self.action_validate)
        toolbar.addAction(self.action_test_play)

    def _setup_statusbar(self) -> None:
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_rooms = QLabel("Rooms: 0")
        self.status_objects = QLabel("Objects: 0")
        self.status_zoom = QLabel("Zoom: 100%")

        self.statusbar.addPermanentWidget(self.status_rooms)
        self.statusbar.addPermanentWidget(self.status_objects)
        self.statusbar.addPermanentWidget(self.status_zoom)

        self.statusbar.showMessage("Ready")

    def _restore_geometry(self) -> None:
        """Restore window geometry from settings."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def _save_geometry(self) -> None:
        """Save window geometry to settings."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event."""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self._save_file():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        self._save_geometry()
        event.accept()

    def _update_title(self) -> None:
        """Update window title with current file."""
        title = "PyMeshZork Map Editor"
        if self.current_file:
            title = f"{self.current_file.name} - {title}"
        if self.is_modified:
            title = f"* {title}"
        self.setWindowTitle(title)

    def _mark_modified(self) -> None:
        """Mark the world as modified."""
        if not self.is_modified:
            self.is_modified = True
            self._update_title()

    def _update_status(self) -> None:
        """Update status bar counts."""
        if self.world:
            self.status_rooms.setText(f"Rooms: {len(self.world.rooms)}")
            self.status_objects.setText(f"Objects: {len(self.world.objects)}")
            self.rooms_list_label.setText(f"Rooms: {len(self.world.rooms)}")
            self.objects_list_label.setText(f"Objects: {len(self.world.objects)}")
        else:
            self.status_rooms.setText("Rooms: 0")
            self.status_objects.setText("Objects: 0")

    # === File Operations ===

    def _new_world(self) -> None:
        """Create a new empty world."""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Create a new world? Unsaved changes will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.world = EditorWorld.create_new()
        self.current_file = None
        self.is_modified = False
        self._update_title()
        self._update_status()
        self.map_canvas.set_world(self.world)
        self.room_editor.set_room(None)
        self.object_editor.set_object(None)
        self.statusbar.showMessage("Created new world")

    def _open_file(self) -> None:
        """Open a world file."""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Open another file? Unsaved changes will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Default to data/worlds directory relative to current working directory
        default_dir = Path.cwd() / "data" / "worlds"
        if not default_dir.exists():
            default_dir = Path.cwd()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open World File",
            str(default_dir),
            "JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            self._load_file(Path(file_path))

    def _load_file(self, path: Path) -> bool:
        """Load a world from file."""
        try:
            self.world = EditorWorld.load_from_file(path)
            self.current_file = path
            self.is_modified = False
            self._update_title()
            self._update_status()
            self.map_canvas.set_world(self.world)
            self.room_editor.set_room(None)
            self.object_editor.set_object(None)
            self.statusbar.showMessage(f"Loaded {path.name}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")
            return False

    def _save_file(self) -> bool:
        """Save the current world."""
        if not self.current_file:
            return self._save_file_as()

        return self._save_to_file(self.current_file)

    def _save_file_as(self) -> bool:
        """Save the world to a new file."""
        # Default to data/worlds directory or current file location
        if self.current_file:
            default_path = self.current_file
        else:
            default_dir = Path.cwd() / "data" / "worlds"
            if not default_dir.exists():
                default_dir = Path.cwd()
            default_path = default_dir / "world.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save World File",
            str(default_path),
            "JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            return self._save_to_file(Path(file_path))
        return False

    def _save_to_file(self, path: Path) -> bool:
        """Save the world to a specific file."""
        if not self.world:
            return False

        try:
            self.world.save_to_file(path)
            self.current_file = path
            self.is_modified = False
            self._update_title()
            self.statusbar.showMessage(f"Saved {path.name}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")
            return False

    # === Edit Operations ===

    def _add_room(self) -> None:
        """Add a new room."""
        if not self.world:
            return
        room = self.world.add_room()
        self._mark_modified()
        self._update_status()
        self.map_canvas.add_room_node(room)
        self.map_canvas.select_room(room.id)
        self.statusbar.showMessage(f"Added room: {room.id}")

    def _add_object(self) -> None:
        """Add a new object."""
        if not self.world:
            return
        obj = self.world.add_object()
        self._mark_modified()
        self._update_status()
        self.editor_tabs.setCurrentIndex(1)  # Switch to object tab
        self.object_editor.set_object(obj)
        self.statusbar.showMessage(f"Added object: {obj.id}")

    def _delete_selected(self) -> None:
        """Delete the selected item."""
        selected = self.map_canvas.selected_room_id
        if selected and self.world:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete room '{selected}' and all its connections?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.world.remove_room(selected)
                self._mark_modified()
                self._update_status()
                self.map_canvas.remove_room_node(selected)
                self.room_editor.set_room(None)
                self.statusbar.showMessage(f"Deleted room: {selected}")

    # === View Operations ===

    def _zoom_in(self) -> None:
        """Zoom in on the map."""
        self.map_canvas.zoom_in()
        self._update_zoom_status()

    def _zoom_out(self) -> None:
        """Zoom out on the map."""
        self.map_canvas.zoom_out()
        self._update_zoom_status()

    def _zoom_fit(self) -> None:
        """Fit the map to the window."""
        self.map_canvas.zoom_fit()
        self._update_zoom_status()

    def _update_zoom_status(self) -> None:
        """Update zoom level in status bar."""
        zoom = int(self.map_canvas.zoom_level * 100)
        self.status_zoom.setText(f"Zoom: {zoom}%")

    def _auto_layout(self) -> None:
        """Automatically arrange rooms using force-directed layout."""
        if self.world:
            room_count = len(self.world.rooms)
            self.statusbar.showMessage(f"Applying auto layout to {room_count} rooms...")
            self.setCursor(Qt.CursorShape.WaitCursor)

            # Run the layout algorithm
            self.map_canvas.auto_layout()

            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._mark_modified()
            self.statusbar.showMessage(f"Auto layout complete - {room_count} rooms arranged")

    # === Tools ===

    def _validate_world(self) -> None:
        """Validate the world for errors."""
        if not self.world:
            return

        errors = self.world.validate()
        if errors:
            msg = "Validation found issues:\n\n" + "\n".join(f"- {e}" for e in errors)
            QMessageBox.warning(self, "Validation Results", msg)
        else:
            QMessageBox.information(
                self, "Validation Results", "World validated successfully!"
            )

    def _find_orphans(self) -> None:
        """Find rooms that cannot be reached."""
        if not self.world:
            return

        orphans = self.world.find_orphan_rooms()
        if orphans:
            msg = "Orphan rooms (not reachable from start):\n\n" + "\n".join(
                f"- {r}" for r in orphans
            )
            QMessageBox.warning(self, "Orphan Rooms", msg)
        else:
            QMessageBox.information(
                self, "Orphan Rooms", "All rooms are reachable from the starting room."
            )

    def _test_play(self) -> None:
        """Launch test play mode."""
        QMessageBox.information(
            self,
            "Test Play",
            "Test play mode coming soon!\n\nThis will launch the game engine with the current world.",
        )

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About PyMeshZork Map Editor",
            "PyMeshZork Map Editor v0.1.0\n\n"
            "A visual editor for creating Zork-style text adventure worlds.\n\n"
            "Part of the PyMeshZork project.",
        )

    # === Event Handlers ===

    def _on_room_selected(self, room_id: str) -> None:
        """Handle room selection in the map canvas."""
        if self.world and room_id:
            room = self.world.get_room(room_id)
            self.room_editor.set_room(room)
            self.editor_tabs.setCurrentIndex(0)  # Switch to room tab

    def _on_room_moved(self, room_id: str, x: float, y: float) -> None:
        """Handle room being moved in the canvas."""
        if self.world:
            self.world.set_room_position(room_id, x, y)
            self._mark_modified()

    def _on_room_changed(self) -> None:
        """Handle room properties being changed."""
        self._mark_modified()
        self._update_status()
        self.map_canvas.update()

    def _on_object_changed(self) -> None:
        """Handle object properties being changed."""
        self._mark_modified()
        self._update_status()

    def _on_connection_created(
        self, from_room: str, to_room: str, direction: str, bidirectional: bool = True
    ) -> None:
        """Handle a new connection being created."""
        if self.world:
            self.world.add_exit(from_room, to_room, direction, bidirectional=bidirectional)
            self._mark_modified()
            self.map_canvas.update()
            conn_type = "↔" if bidirectional else "→"
            self.statusbar.showMessage(
                f"Connected {from_room} {conn_type} {to_room} ({direction})"
            )
