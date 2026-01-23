"""Main entry point for the PyMeshZork Map Editor."""

import sys


def main() -> int:
    """Launch the map editor application."""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("Error: PyQt6 is required for the map editor.")
        print("Install it with: pip install pymeshzork[gui]")
        return 1

    from pymeshzork.editor.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("PyMeshZork Map Editor")
    app.setOrganizationName("PyMeshZork")
    app.setApplicationVersion("0.1.0")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
