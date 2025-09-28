#!/usr/bin/env python3
"""
Main entry point for the Hot Wire CNC G-code Generator application.
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget, QVBoxLayout, QGroupBox, QPushButton

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base_app import BaseHotWireApp
from app_2d import App2DMixin
from app_3d import App3DMixin


class HotWireGCodeApp(BaseHotWireApp, App2DMixin, App3DMixin):
    """
    Main application class combining all functionality through multiple inheritance.

    This class inherits from:
    - BaseHotWireApp: Common UI setup, file loading, canvas management
    - App2DMixin: All 2D-specific functionality (DXF processing, 2D animation)
    - App3DMixin: All 3D-specific functionality (STEP processing, 3D animation)
    """

    def __init__(self):
        # Initialize all parent classes
        BaseHotWireApp.__init__(self)
        App2DMixin.__init__(self)
        App3DMixin.__init__(self)

        # Set up the complete UI
        self.setup_ui()
        self.setup_event_connections()

        print("Hot Wire G-code Generator initialized successfully")

    def setup_ui(self):
        """Set up the complete user interface."""
        # Initialize base UI from BaseHotWireApp
        BaseHotWireApp.setup_base_ui(self)

        # Set initial mode to 2D
        self.switch_to_2d_mode()

    def create_control_panel(self):
        """Override to create the control panel with stacked panels for 2D and 3D modes."""
        control_widget = QWidget()
        control_widget.setMaximumWidth(400)
        control_layout = QVBoxLayout(control_widget)

        # File Operations (unified for both modes)
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout(file_group)

        self.load_button = QPushButton("Load DXF or STEP File")
        self.load_button.clicked.connect(self.load_file)
        file_layout.addWidget(self.load_button)

        control_layout.addWidget(file_group)

        # Create control panels for both modes
        panel_2d = self.create_2d_control_panel()
        panel_3d = self.create_3d_control_panel()

        # Set up stacked widget for switching between control panels
        self.control_stack = QStackedWidget()
        self.control_stack.addWidget(panel_2d)  # Index 0 for 2D
        self.control_stack.addWidget(panel_3d)  # Index 1 for 3D

        control_layout.addWidget(self.control_stack)

        return control_widget

    def setup_event_connections(self):
        """Set up event connections between UI elements."""
        # Connect canvas click events - canvas handles its own click events
        # self.selection_canvas.mpl_connect("button_press_event", self.on_entity_click)
        self.selection_canvas_3d.mpl_connect("pick_event", self.on_3d_edge_click)

        # Connect mode switching if buttons exist
        if hasattr(self, "mode_2d_button"):
            self.mode_2d_button.clicked.connect(self.switch_to_2d_mode)
        if hasattr(self, "mode_3d_button"):
            self.mode_3d_button.clicked.connect(self.switch_to_3d_mode)

    def load_dxf_file_internal(self, file_path):
        """Override to handle DXF loading for 2D mode."""
        # Switch to 2D mode when DXF is loaded
        self.switch_to_2d_mode()

        # Call the App2DMixin method (which calls BaseHotWireApp and plots)
        return App2DMixin.load_dxf_file_internal(self, file_path)

    def load_step_file_internal(self, file_path):
        """Override to handle STEP loading for 3D mode."""
        # Switch to 3D mode when STEP is loaded
        self.switch_to_3d_mode()

        # Call the 3D mixin's load method
        return App3DMixin.load_step_file_internal(self, file_path)

    def closeEvent(self, event):
        """Handle application close event."""
        # Stop any running animations
        if hasattr(self, "stop_animation"):
            self.stop_animation()

        # Accept the close event
        event.accept()
        print("Application closed")


def main():
    """Main application entry point."""
    # Create QApplication instance
    app = QApplication(sys.argv)
    
    # Set application style to match original
    app.setStyle("Fusion")
    
    app.setApplicationName("Hot Wire CNC G-code Generator")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Hot Wire CNC")

    # Create and show main window
    window = HotWireGCodeApp()
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
