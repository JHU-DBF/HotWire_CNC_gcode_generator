#!/usr/bin/env python3
"""
Dialog classes for the Hot Wire CNC G-code Generator.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QGroupBox, QPushButton, QAbstractItemView, QSizePolicy, QComboBox, QLineEdit, QFormLayout, QDialogButtonBox, QRadioButton, QButtonGroup
from PySide6.QtCore import Qt

from canvases import MatplotlibCanvas, MatplotlibCanvas3D


class ProfileSelectorDialog(QDialog):
    """Dialog for selecting faces that define left and right profiles in 3D mode."""

    def __init__(self, parent, faces, face_centers, existing_left=None, existing_right=None):
        super().__init__(parent)
        self.faces = faces
        self.face_centers = face_centers

        # Identify the middle/symmetry plane
        self.symmetry_plane_y = np.mean([center[1] for center in face_centers])
        print(f"Identified symmetry plane at Y = {self.symmetry_plane_y:.2f}")

        # Restore existing selections or start empty
        self.selected_left_faces = existing_left.copy() if existing_left else []
        self.selected_right_faces = existing_right.copy() if existing_right else []

        # Debouncing for click events
        self.last_click_time = 0
        self.click_debounce_ms = 200  # 200ms debounce

        # Track last focused list for delete operations
        self.last_focused_list = None

        self.setWindowTitle("Profile Selector")
        self.setModal(True)
        self.resize(1200, 800)  # Made window bigger

        self.setup_ui()
        self.plot_faces()

    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel("Select faces that define the left and right profiles.\nClick on face numbers in the 3D plot to select them.\nFaces will be auto-assigned to left/right based on symmetry plane.")
        instructions.setMaximumHeight(60)  # Limit height
        layout.addWidget(instructions)

        # 3D plot
        self.canvas_3d = MatplotlibCanvas3D(self, width=12, height=10)  # Made plot bigger

        # Connect picker event for face selection
        self.canvas_3d.fig.canvas.mpl_connect("pick_event", self.on_3d_entity_click)

        # Make canvas take more space
        self.canvas_3d.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas_3d, stretch=1)  # Give canvas stretch priority

        # Lists for selected faces
        list_layout = QHBoxLayout()

        # Left profile list
        left_group = QGroupBox("Left Profile Faces")
        left_layout = QVBoxLayout(left_group)
        self.left_list = QListWidget()
        self.left_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Enable multi-select
        self.left_list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.left_list.setAcceptDrops(True)
        self.left_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        left_layout.addWidget(self.left_list)
        list_layout.addWidget(left_group)

        # Right profile list
        right_group = QGroupBox("Right Profile Faces")
        right_layout = QVBoxLayout(right_group)
        self.right_list = QListWidget()
        self.right_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Enable multi-select
        self.right_list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.right_list.setAcceptDrops(True)
        self.right_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        right_layout.addWidget(self.right_list)
        list_layout.addWidget(right_group)

        layout.addLayout(list_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_selections)
        button_layout.addWidget(self.clear_button)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Connect key press events for DEL key
        self.left_list.installEventFilter(self)
        self.right_list.installEventFilter(self)

        # Connect drop events for cross-list drag and drop
        self.left_list.dropEvent = self.left_list_drop_event
        self.right_list.dropEvent = self.right_list_drop_event

    def plot_faces(self):
        """Plot the 3D model with numbered faces and face geometry."""
        ax = self.canvas_3d.ax
        ax.clear()

        colors = plt.cm.tab20(np.linspace(0, 1, len(self.faces)))

        # Store face scatter points for picking
        self.face_points = []
        self.face_texts = []

        for i, (face, center) in enumerate(zip(self.faces, self.face_centers)):
            color = colors[i % len(colors)]

            # Plot face geometry
            vertices = []
            for vertex in face.Vertices():
                point = vertex.toTuple()
                vertices.append(point)

            if len(vertices) >= 3:
                vertices = np.array(vertices)
                # Create a simple wireframe representation
                ax.plot(vertices[:, 0], vertices[:, 1], vertices[:, 2], color=color, alpha=0.6, linewidth=1)

                # Plot face edges
                for edge in face.Edges():
                    try:
                        # Get edge curve
                        curve = edge._geomAdaptor()
                        # Sample points along the edge
                        edge_points = []
                        for u in np.linspace(0, 1, 10):
                            try:
                                # Get parameter range
                                u_min = curve.FirstParameter()
                                u_max = curve.LastParameter()
                                param = u_min + u * (u_max - u_min)
                                point = curve.Value(param)
                                edge_points.append([point.X(), point.Y(), point.Z()])
                            except Exception:
                                continue

                        if len(edge_points) > 1:
                            edge_points = np.array(edge_points)
                            ax.plot(edge_points[:, 0], edge_points[:, 1], edge_points[:, 2], color=color, alpha=0.8, linewidth=2)
                    except Exception:
                        continue

            # Add invisible scatter point for picking
            point = ax.scatter([center[0]], [center[1]], [center[2]], s=100, color="none", alpha=0, picker=True)
            self.face_points.append((point, i))

            # Add face number as text
            text_color = "blue" if i in self.selected_left_faces else ("red" if i in self.selected_right_faces else "black")
            text = ax.text(center[0], center[1], center[2], str(i), fontsize=12, color=text_color, weight="bold", ha="center", va="center", bbox=dict(facecolor="white", alpha=0.9, boxstyle="round,pad=0.3", edgecolor="black"))

            self.face_texts.append((text, i))

        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm)")
        ax.set_title("3D Model - Click Face Numbers to Select\n(Mouse: rotate, scroll: zoom)")

        # Allow automatic aspect ratio for full panel usage
        ax.set_box_aspect(None)

        # Enable mouse interaction
        ax.mouse_init()

        self.canvas_3d.draw()
        self.canvas_3d.setFocus()  # Ensure the canvas can receive mouse events

        # Restore existing selections in UI
        self.restore_selections()

    def restore_selections(self):
        """Restore existing selections in the UI."""
        # Populate lists
        for face_idx in self.selected_left_faces:
            self.left_list.addItem(f"Face {face_idx}")

        for face_idx in self.selected_right_faces:
            self.right_list.addItem(f"Face {face_idx}")

    def refresh_face_highlighting(self):
        """Refresh face highlighting in 3D plot after drag/drop operations."""
        if hasattr(self, "faces") and self.faces:
            self.plot_faces()

    def on_3d_entity_click(self, event):
        """Handle clicking on face numbers using matplotlib picker events."""
        current_time = time.time() * 1000  # Convert to milliseconds
        if current_time - self.last_click_time < self.click_debounce_ms:
            return

        self.last_click_time = current_time

        # This method handles the picker events from matplotlib
        if hasattr(event, "artist"):
            # Check if the clicked artist is one of our face points
            for point, face_idx in self.face_points:
                if event.artist == point:
                    self.select_face(face_idx)
                    return

            # Find which face was clicked
            for text, face_idx in self.face_texts:
                if event.artist == text:
                    self.select_face(face_idx)
                    return

        # Fallback to distance-based selection if picker doesn't work
        if hasattr(event, "mouseevent") and event.mouseevent.xdata is not None:
            self.handle_click_by_distance(event.mouseevent)

    def handle_click_by_distance(self, event):
        """Fallback method for face selection using distance calculation."""
        if not hasattr(event, "xdata") or event.xdata is None:
            return

        # Get the 3D coordinates of the click in data space
        # This is approximate since we don't have true 3D picking
        ax = self.canvas_3d.ax

        # Find the closest face center to the click point
        min_distance = float("inf")
        closest_face = None

        for i, center in enumerate(self.face_centers):
            # Transform 3D point to 2D screen coordinates for comparison
            try:
                x2d, y2d, _ = ax.projection.transform_point([center[0], center[1], center[2]])
                screen_distance = np.sqrt((event.x - x2d) ** 2 + (event.y - y2d) ** 2)

                if screen_distance < min_distance:
                    min_distance = screen_distance
                    closest_face = i
            except Exception:
                # If projection fails, use simple 2D distance
                distance = np.sqrt((event.xdata - center[0]) ** 2 + (event.ydata - center[1]) ** 2)
                if distance < min_distance:
                    min_distance = distance
                    closest_face = i

        # Use a reasonable threshold for selection (in pixels)
        if closest_face is not None and min_distance < 50:
            self.select_face(closest_face)

    def select_face(self, face_idx):
        """Select a face and assign it to left or right based on position relative to symmetry plane."""
        if face_idx in self.selected_left_faces or face_idx in self.selected_right_faces:
            return

        center_y = self.face_centers[face_idx][1]

        # Auto-assign based on position relative to symmetry plane
        if center_y < self.symmetry_plane_y:
            self.selected_left_faces.append(face_idx)
            self.left_list.addItem(f"Face {face_idx}")
            side = "left"
        else:
            self.selected_right_faces.append(face_idx)
            self.right_list.addItem(f"Face {face_idx}")
            side = "right"

        print(f"Selected face {face_idx} ({side} side, Y={center_y:.2f}, symmetry_plane={self.symmetry_plane_y:.2f})")

        # Update the plot to highlight selected face
        self.highlight_selected_face(face_idx, side)

    def highlight_selected_face(self, face_idx, side):
        """Highlight a selected face by changing its text color."""
        if face_idx < len(self.face_texts):
            text, _ = self.face_texts[face_idx]
            color = "blue" if side == "left" else "red"
            text.set_color(color)
            self.canvas_3d.draw()

    def delete_selected(self):
        """Delete selected items from the last focused list."""
        # Use last focused list, or fall back to current focus/selection logic
        target_list = self.last_focused_list
        if target_list is None:
            focused_widget = self.focusWidget()
            if focused_widget == self.left_list or (not focused_widget and self.left_list.selectedItems()):
                target_list = self.left_list
            elif focused_widget == self.right_list or (not focused_widget and self.right_list.selectedItems()):
                target_list = self.right_list

        if target_list == self.left_list:
            selected_items = self.left_list.selectedItems()
            for item in selected_items:
                text = item.text()
                face_idx = int(text.split()[1])
                if face_idx in self.selected_left_faces:
                    self.selected_left_faces.remove(face_idx)
                    # Reset text color
                    if face_idx < len(self.face_texts):
                        text_obj, _ = self.face_texts[face_idx]
                        text_obj.set_color("black")
                self.left_list.takeItem(self.left_list.row(item))

        elif target_list == self.right_list:
            selected_items = self.right_list.selectedItems()
            for item in selected_items:
                text = item.text()
                face_idx = int(text.split()[1])
                if face_idx in self.selected_right_faces:
                    self.selected_right_faces.remove(face_idx)
                    # Reset text color
                    if face_idx < len(self.face_texts):
                        text_obj, _ = self.face_texts[face_idx]
                        text_obj.set_color("black")
                self.right_list.takeItem(self.right_list.row(item))

        # Redraw to update colors
        self.canvas_3d.draw()
        self.canvas_3d.fig.canvas.flush_events()

    def clear_selections(self):
        """Clear all face selections."""
        self.selected_left_faces.clear()
        self.selected_right_faces.clear()
        self.left_list.clear()
        self.right_list.clear()

        # Reset all face text colors
        for text, _ in self.face_texts:
            text.set_color("black")

        # Redraw to update colors
        self.canvas_3d.draw()
        self.canvas_3d.fig.canvas.flush_events()

    def eventFilter(self, obj, event):
        """Handle key press events for DEL key and focus tracking."""
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key_Delete:
            self.delete_selected()
            return True
        elif event.type() == event.Type.FocusIn:
            if obj == self.left_list:
                self.last_focused_list = self.left_list
            elif obj == self.right_list:
                self.last_focused_list = self.right_list
        return super().eventFilter(obj, event)

    def left_list_drop_event(self, event):
        """Handle drop events on the left list."""
        self.handle_drop_event(event, self.left_list, self.right_list, self.selected_left_faces, self.selected_right_faces)

    def right_list_drop_event(self, event):
        """Handle drop events on the right list."""
        self.handle_drop_event(event, self.right_list, self.left_list, self.selected_right_faces, self.selected_left_faces)

    def handle_drop_event(self, event, target_list, source_list, target_faces, source_faces):
        """Handle drag and drop between left and right lists."""
        if event.source() == target_list:
            # Internal reorder - use default behavior
            super(type(target_list), target_list).dropEvent(event)
            return

        if event.source() == source_list:
            # Cross-list move
            selected_items = source_list.selectedItems()
            if not selected_items:
                return

            # Move items from source to target
            for item in selected_items:
                text = item.text()
                face_idx = int(text.split()[1])

                # Remove from source
                source_list.takeItem(source_list.row(item))
                if face_idx in source_faces:
                    source_faces.remove(face_idx)

                # Add to target
                target_list.addItem(text)
                if face_idx not in target_faces:
                    target_faces.append(face_idx)

                # Update text color
                if face_idx < len(self.face_texts):
                    text_obj, _ = self.face_texts[face_idx]
                    color = "blue" if target_list == self.left_list else "red"
                    text_obj.set_color(color)

            # Redraw to update colors
            self.canvas_3d.draw()
            self.canvas_3d.fig.canvas.flush_events()
        else:
            # External drop - ignore
            event.ignore()

    def get_selections(self):
        """Return the selected face lists."""
        return self.selected_left_faces, self.selected_right_faces


class LeadInOutDialog(QDialog):
    """Dialog for configuring lead-in/out parameters with notebook-style entry/exit system."""

    def __init__(self, parent, lead_type="Lead-in", current_distance=None):
        super().__init__(parent)
        self.lead_type = lead_type
        self.current_distance = current_distance or [10.0, 0.0]  # Default distance

        self.setWindowTitle(f"Configure {lead_type}")
        self.setModal(True)

        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QFormLayout(self)

        # Entry/Exit Type selection (for quick preset selection)
        self.entry_type_combo = QComboBox()
        if self.lead_type == "Lead-in":
            self.entry_type_combo.addItems(["Entry +X (10, 0)", "Entry -X (-10, 0)", "Entry -Y (0, -10)"])
        else:
            self.entry_type_combo.addItems(["Exit -X (-10, 0)", "Exit +X (10, 0)", "Exit +Y (0, 10)"])

        self.entry_type_combo.currentTextChanged.connect(self.on_preset_selected)
        layout.addRow(f"Preset {self.lead_type} Types:", self.entry_type_combo)

        # Distance input fields
        self.x_distance_edit = QLineEdit(str(self.current_distance[0]))
        self.y_distance_edit = QLineEdit(str(self.current_distance[1]))
        layout.addRow("X Distance (mm):", self.x_distance_edit)
        layout.addRow("Y Distance (mm):", self.y_distance_edit)

        # Info label
        info_label = QLabel("Select a preset above or enter custom X/Y distances.")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info_label)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def on_preset_selected(self, text):
        """Handle preset selection and update distance fields."""
        # Extract distance values from preset text
        if "(10, 0)" in text:
            self.x_distance_edit.setText("10.0")
            self.y_distance_edit.setText("0.0")
        elif "(-10, 0)" in text:
            self.x_distance_edit.setText("-10.0")
            self.y_distance_edit.setText("0.0")
        elif "(0, -10)" in text:
            self.x_distance_edit.setText("0.0")
            self.y_distance_edit.setText("-10.0")
        elif "(0, 10)" in text:
            self.x_distance_edit.setText("0.0")
            self.y_distance_edit.setText("10.0")

    def get_selected_distance(self):
        """Return the selected distance as [x, y] array."""
        try:
            x = float(self.x_distance_edit.text())
            y = float(self.y_distance_edit.text())
            return [x, y]
        except ValueError:
            # Return default if invalid input
            return [10.0, 0.0]


class WireLengthDialog(QDialog):
    """Dialog for displaying wire length analysis."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Wire Length Analysis")
        self.setModal(False)  # Non-modal
        self.resize(800, 600)

        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Canvas for wire length plot
        self.canvas = MatplotlibCanvas(self, width=10, height=6)
        layout.addWidget(self.canvas)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def plot_wire_lengths(self, wire_lengths):
        """Plot the wire length analysis."""
        ax = self.canvas.ax
        ax.clear()

        # Plot wire lengths
        ax.plot(wire_lengths, "b-", linewidth=2, label="Wire Length")

        # Add statistics lines
        max_length = np.max(wire_lengths)
        min_length = np.min(wire_lengths)
        avg_length = np.mean(wire_lengths)

        ax.axhline(y=max_length, color="r", linestyle="--", label=f"Max: {max_length:.2f}mm")
        ax.axhline(y=min_length, color="g", linestyle="--", label=f"Min: {min_length:.2f}mm")
        ax.axhline(y=avg_length, color="orange", linestyle="--", label=f"Avg: {avg_length:.2f}mm")

        ax.set_xlabel("Point Index")
        ax.set_ylabel("Wire Length (mm)")
        ax.set_title("Hot Wire Length Analysis")
        ax.legend()
        ax.grid(True, alpha=0.3)

        self.canvas.draw()


class DirectionCustomizationDialog(QDialog):
    """Dialog for customizing cutting direction for sequence items."""

    def __init__(self, parent, item_text, current_direction=0):
        super().__init__(parent)
        self.setWindowTitle("Customize Cutting Direction")
        self.setModal(True)
        self.resize(400, 300)

        self.current_direction = current_direction
        self.item_text = item_text

        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Item info
        info_label = QLabel(f"Customize direction for: {self.item_text}")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Direction options
        direction_group = QGroupBox("Cutting Direction")
        direction_layout = QVBoxLayout(direction_group)

        self.direction_group = QButtonGroup(self)

        # Create mapping from button IDs to direction values
        self.id_to_direction = {
            0: 0,  # Auto
            1: 1,  # Left to right
            2: -1,  # Right to left
            3: 2,  # Increasing Z
            4: -2,  # Decreasing Z
        }

        # Reverse mapping for setting current selection
        self.direction_to_id = {v: k for k, v in self.id_to_direction.items()}

        # Auto direction
        self.auto_radio = QRadioButton("Auto (minimize travel distance)")
        self.auto_radio.setToolTip("Automatically choose direction to minimize travel distance")
        self.direction_group.addButton(self.auto_radio, 0)
        direction_layout.addWidget(self.auto_radio)

        # Left to right
        self.left_to_right_radio = QRadioButton("Left to Right → (increasing X)")
        self.left_to_right_radio.setToolTip("Force path to go from left to right (increasing X)")
        self.direction_group.addButton(self.left_to_right_radio, 1)
        direction_layout.addWidget(self.left_to_right_radio)

        # Right to left
        self.right_to_left_radio = QRadioButton("Right to Left ← (decreasing X)")
        self.right_to_left_radio.setToolTip("Force path to go from right to left (decreasing X)")
        self.direction_group.addButton(self.right_to_left_radio, 2)
        direction_layout.addWidget(self.right_to_left_radio)

        # Increasing Z
        self.increasing_z_radio = QRadioButton("Increasing Z ↑ (bottom to top)")
        self.increasing_z_radio.setToolTip("Force path to go from bottom to top (increasing Z)")
        self.direction_group.addButton(self.increasing_z_radio, 3)
        direction_layout.addWidget(self.increasing_z_radio)

        # Decreasing Z
        self.decreasing_z_radio = QRadioButton("Decreasing Z ↓ (top to bottom)")
        self.decreasing_z_radio.setToolTip("Force path to go from top to bottom (decreasing Z)")
        self.direction_group.addButton(self.decreasing_z_radio, 4)
        direction_layout.addWidget(self.decreasing_z_radio)

        # Set current selection
        button_id = self.direction_to_id.get(self.current_direction, 0)
        button = self.direction_group.button(button_id)
        if button:
            button.setChecked(True)
        else:
            self.auto_radio.setChecked(True)

        layout.addWidget(direction_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_direction(self):
        """Get the selected direction value."""
        button_id = self.direction_group.checkedId()
        return self.id_to_direction.get(button_id, 0)  # Default to auto if not found

    def get_direction_text(self):
        """Get the text description of the selected direction."""
        direction = self.get_direction()
        direction_names = {0: "Auto", 1: "L→R", -1: "R→L", 2: "↑Z", -2: "↓Z"}
        return direction_names.get(direction, "Auto")
