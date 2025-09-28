#!/usr/bin/env python3
"""
3D-specific functionality for the Hot Wire CNC G-code Generator.
"""

import numpy as np
import matplotlib.patches as patches
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QListWidget, QRadioButton, QLineEdit, QPushButton, QAbstractItemView, QDialog, QMessageBox, QFileDialog, QApplication
from PySide6.QtCore import Qt

from dialogs import ProfileSelectorDialog, LeadInOutDialog, WireLengthDialog, DirectionCustomizationDialog


class App3DMixin:
    """Mixin class with 3D-specific functionality."""

    def __init__(self):
        # 3D mode data storage
        self.is_3d_mode = False
        self.faces = []  # STEP file faces
        self.face_centers = []  # Face centers for selection
        self.selected_left_faces = []  # Selected left face indices
        self.selected_right_faces = []  # Selected right face indices
        self.left_profile_entities = []  # Left profile edge entities
        self.right_profile_entities = []  # Right profile edge entities
        self.left_sequence_order = []  # Left cutting sequence
        self.right_sequence_order = []  # Right cutting sequence
        self.gantry_gap = 924.0  # Default gantry gap in mm
        self.y_offset = 0.0  # Y offset for centering

        # 3D Animation state
        self.current_cutting_paths = []
        self.animation_segments = []
        self.current_frame = 0
        self.cutting_animation = None

        # 3D Animation state variables
        self.animation_frame_positions_3d = []
        self.animation_total_frames_3d = 0
        self.animation_paused = False
        self.animation_frame = 0  # Track current frame for pause/resume
        self.show_gcode_points = True
        self.unit_to_mm_3d = 1.0  # Default to mm

        # Track last focused sequence list for delete operations
        self.last_focused_sequence_list = None
        self.custom_arc_points = {}  # Store custom points per arc for entities

        # Direction control system (similar to 2D point customization)
        self.custom_directions = {}  # Store custom directions per sequence item

        # Animation state for QTimer-based approach (like 2D app)
        self.animation_timer_3d = None
        self.animation_timer_2d = None
        self.animation_paused = False
        self.animate_frame_3d = 0
        self.animate_frame_2d = 0
        self.total_frames_3d = 0
        self.total_frames_2d = 0
        self.animation_3d_params = {}  # Store animation parameters
        self.animation_2d_params = {}  # Store 2D animation parameters
        self.cumulative_distances_3d = None
        self.cumulative_distances_2d = None

        # Unit conversion tracking
        self.current_units_3d = "mm"  # Track current units to prevent recursive conversion

    def create_3d_control_panel(self):
        """Create the 3D mode control panel."""
        panel_3d = QWidget()
        control_layout = QVBoxLayout(panel_3d)
        control_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins

        # File & Parameters Group
        params_group = QGroupBox("3D Parameters")
        params_layout = QVBoxLayout(params_group)

        # Gantry Gap
        gantry_layout = QHBoxLayout()
        self.gantry_gap_label = QLabel("Gantry Gap (mm):")
        gantry_layout.addWidget(self.gantry_gap_label)
        self.gantry_gap_edit = QLineEdit("924")
        gantry_layout.addWidget(self.gantry_gap_edit)
        params_layout.addLayout(gantry_layout)

        # Y-Offset
        y_offset_layout = QHBoxLayout()
        self.y_offset_3d_label = QLabel("Y-Offset (mm):")
        y_offset_layout.addWidget(self.y_offset_3d_label)
        self.y_offset_3d_edit = QLineEdit("0")
        y_offset_layout.addWidget(self.y_offset_3d_edit)
        params_layout.addLayout(y_offset_layout)

        # Display Units
        display_units_group = QGroupBox("Display Units")
        display_units_layout = QHBoxLayout(display_units_group)
        self.display_mm_radio_3d = QRadioButton("mm")
        self.display_inch_radio_3d = QRadioButton("inch")
        self.display_mm_radio_3d.setChecked(True)
        display_units_layout.addWidget(self.display_mm_radio_3d)
        display_units_layout.addWidget(self.display_inch_radio_3d)
        params_layout.addWidget(display_units_group)

        control_layout.addWidget(params_group)

        # Cutting Sequence Group
        sequence_group = QGroupBox("Cutting Sequence")
        sequence_layout = QVBoxLayout(sequence_group)

        # Instructions
        instruction_label = QLabel("Select profiles first, then click edges to sequence cutting.\nLead-in/out entries are added to both sequences simultaneously.")
        instruction_label.setWordWrap(True)
        sequence_layout.addWidget(instruction_label)

        # Profile selection button
        self.select_profiles_button = QPushButton("Select Left/Right Profiles")
        self.select_profiles_button.clicked.connect(self.select_profiles)
        sequence_layout.addWidget(self.select_profiles_button)

        # Left and Right sequence lists side by side
        lists_layout = QHBoxLayout()

        # Left Profile Sequence - match face selection styling
        left_group = QGroupBox("Left Profile Sequence")
        left_layout = QVBoxLayout(left_group)
        self.left_sequence_list = QListWidget()
        self.left_sequence_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.left_sequence_list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.left_sequence_list.setAcceptDrops(True)
        self.left_sequence_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        # Match face selection panel height and styling
        self.left_sequence_list.setMinimumHeight(150)
        self.left_sequence_list.setMaximumHeight(200)
        self.left_sequence_list.model().rowsMoved.connect(self.on_3d_sequence_changed)
        left_layout.addWidget(self.left_sequence_list)
        lists_layout.addWidget(left_group)

        # Right Profile Sequence - match face selection styling
        right_group = QGroupBox("Right Profile Sequence")
        right_layout = QVBoxLayout(right_group)
        self.right_sequence_list = QListWidget()
        self.right_sequence_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.right_sequence_list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.right_sequence_list.setAcceptDrops(True)
        self.right_sequence_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        # Match face selection panel height and styling
        self.right_sequence_list.setMinimumHeight(150)
        self.right_sequence_list.setMaximumHeight(200)
        self.right_sequence_list.model().rowsMoved.connect(self.on_3d_sequence_changed)
        right_layout.addWidget(self.right_sequence_list)
        lists_layout.addWidget(right_group)

        sequence_layout.addLayout(lists_layout)

        # Lead-in/out buttons
        lead_layout = QHBoxLayout()
        self.add_leadin_button = QPushButton("Add Lead-in")
        self.add_leadout_button = QPushButton("Add Lead-out")
        self.add_leadin_button.clicked.connect(lambda: self.add_leadinout("Lead-in"))
        self.add_leadout_button.clicked.connect(lambda: self.add_leadinout("Lead-out"))
        lead_layout.addWidget(self.add_leadin_button)
        lead_layout.addWidget(self.add_leadout_button)
        sequence_layout.addLayout(lead_layout)

        # Delete selected button
        self.delete_selected_button = QPushButton("Delete Selected")
        self.delete_selected_button.clicked.connect(self.delete_selected_from_both_sequences)
        sequence_layout.addWidget(self.delete_selected_button)

        # Direction customization instructions
        direction_instruction = QLabel("Double-click sequence items to customize cutting direction.")
        direction_instruction.setStyleSheet("font-style: italic; color: #666;")
        sequence_layout.addWidget(direction_instruction)

        control_layout.addWidget(sequence_group)

        # Actions Group
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)

        # Animation Speed for Animation (moved here to match 2D layout)
        speed_layout = QHBoxLayout()
        self.animation_speed_label = QLabel("Animation Speed (mm/s):")
        speed_layout.addWidget(self.animation_speed_label)
        self.animation_speed_edit = QLineEdit("50.0")
        speed_layout.addWidget(self.animation_speed_edit)
        action_layout.addLayout(speed_layout)

        # Arc Points Control
        arc_points_layout = QHBoxLayout()
        arc_points_layout.addWidget(QLabel("Points per Arc:"))
        self.arc_points_edit = QLineEdit("10")
        arc_points_layout.addWidget(self.arc_points_edit)
        action_layout.addLayout(arc_points_layout)

        # First row - Generate and View Tool Path (2/3) + Show Wire Length (1/3)
        first_row_layout = QHBoxLayout()
        self.animate_3d_button = QPushButton("Generate and View Tool Path")
        self.animate_3d_button.clicked.connect(self.animate_path_3d)
        first_row_layout.addWidget(self.animate_3d_button, 2)  # 2/3 width

        self.wire_length_button = QPushButton("Show Wire Length")
        self.wire_length_button.clicked.connect(self.show_wire_length_plot)
        first_row_layout.addWidget(self.wire_length_button, 1)  # 1/3 width

        action_layout.addLayout(first_row_layout)

        # Second row - Pause, Hide G-Code Points, Save G-Code
        second_row_layout = QHBoxLayout()
        self.pause_3d_button = QPushButton("Pause")
        self.pause_3d_button.clicked.connect(self.toggle_3d_animation_pause)
        self.pause_3d_button.setEnabled(False)
        second_row_layout.addWidget(self.pause_3d_button)

        self.show_gcode_points_button = QPushButton("Hide G-Code Points")
        self.show_gcode_points_button.clicked.connect(self.toggle_gcode_points_3d)
        second_row_layout.addWidget(self.show_gcode_points_button)

        self.generate_3d_button = QPushButton("Save G-Code")
        self.generate_3d_button.clicked.connect(self.generate_and_save_gcode_3d)
        second_row_layout.addWidget(self.generate_3d_button)

        action_layout.addLayout(second_row_layout)

        # View toggle radio buttons
        view_group = QGroupBox("Animation View")
        view_layout = QHBoxLayout(view_group)
        self.view_2d_radio = QRadioButton("2D Animation")
        self.view_3d_radio = QRadioButton("3D Animation")
        self.view_2d_radio.setChecked(True)
        self.view_2d_radio.toggled.connect(self.toggle_animation_view)
        self.view_3d_radio.toggled.connect(self.toggle_animation_view)
        view_layout.addWidget(self.view_2d_radio)
        view_layout.addWidget(self.view_3d_radio)
        action_layout.addWidget(view_group)

        # Set initial button state - G-code points enabled for 2D (default)
        self.show_gcode_points_button.setEnabled(True)
        self.show_gcode_points_button.setStyleSheet("")

        control_layout.addWidget(action_group)

        # Add stretch to push everything to top
        control_layout.addStretch()

        # Connect event filters for DEL key and drop events for sequence lists
        self.left_sequence_list.installEventFilter(self)
        self.right_sequence_list.installEventFilter(self)
        self.left_sequence_list.dropEvent = self.left_sequence_drop_event
        self.right_sequence_list.dropEvent = self.right_sequence_drop_event

        # Connect double-click for editing lead-in/out entries and direction customization
        self.left_sequence_list.itemDoubleClicked.connect(self.customize_sequence_item)
        self.right_sequence_list.itemDoubleClicked.connect(self.customize_sequence_item)

        # Connect display units radio buttons
        self.display_inch_radio_3d.toggled.connect(self.on_display_units_changed_3d)

        # Connect arc points input
        self.arc_points_edit.textChanged.connect(self.on_arc_points_changed)

        return panel_3d

    def switch_to_3d_mode(self):
        """Switch UI to 3D mode."""
        self.is_3d_mode = True
        self.selection_label.setText("3D Model Profile Selection")
        self.selection_stack.setCurrentIndex(1)  # Show 3D selection canvas
        if hasattr(self, "control_stack"):
            self.control_stack.setCurrentIndex(1)  # Show 3D control panel
        print("Switched to 3D mode")

    def load_step_file_internal(self, file_path):
        """Internal method to load STEP file."""
        from base_app import BaseHotWireApp

        faces, face_centers, units_to_mm = BaseHotWireApp.load_step_file_internal(self, file_path)

        self.faces = faces
        self.face_centers = face_centers
        self.units_to_mm_3d = units_to_mm

        # Reset 3D mode data
        self.left_profile_entities = []
        self.right_profile_entities = []
        self.left_sequence_order = []
        self.right_sequence_order = []

        # Clear sequence lists if they exist
        if hasattr(self, "left_sequence_list"):
            self.left_sequence_list.clear()
        if hasattr(self, "right_sequence_list"):
            self.right_sequence_list.clear()

        print(f"Loaded STEP file with {len(self.faces)} faces")

        # Auto-open profile selector for first-time STEP loading
        if len(self.faces) > 0:
            self.select_profiles()

    def select_profiles(self):
        """Open dialog to select left and right profiles from 3D faces."""
        if not self.faces:
            QMessageBox.warning(self, "No Faces", "No faces loaded. Please load a STEP file first.")
            return

        dialog = ProfileSelectorDialog(self, self.faces, self.face_centers, self.selected_left_faces.copy(), self.selected_right_faces.copy())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            left_faces, right_faces = dialog.get_selections()
            self.selected_left_faces = left_faces
            self.selected_right_faces = right_faces
            self.update_profiles_from_faces(left_faces, right_faces)

    def update_profiles_from_faces(self, left_face_indices, right_face_indices):
        """Update profile entities from selected faces."""
        # Extract edges from selected faces
        self.left_profile_entities = []
        self.right_profile_entities = []

        for face_idx in left_face_indices:
            if face_idx < len(self.faces):
                edges = self.extract_face_edges(self.faces[face_idx])
                self.left_profile_entities.extend(edges)

        for face_idx in right_face_indices:
            if face_idx < len(self.faces):
                edges = self.extract_face_edges(self.faces[face_idx])
                self.right_profile_entities.extend(edges)

        print(f"Extracted {len(self.left_profile_entities)} left edges and {len(self.right_profile_entities)} right edges")

        # Plot the 3D profiles
        self.plot_3d_profiles()

    def extract_face_edges(self, face):
        """Extract the edges from a face with geometry-aware sampling"""
        edges = []
        points_flat = []

        # Get all the edges of the face
        for edge in face.Edges():
            points = []

            try:
                # Determine edge type
                edge_type = edge.geomType()

                if edge_type == "LINE":
                    # For lines, we only need start and end points
                    start_point = edge.startPoint()
                    end_point = edge.endPoint()
                    points.append((start_point.x, start_point.y, start_point.z))
                    points.append((end_point.x, end_point.y, end_point.z))

                elif edge_type == "ARC":
                    # For arcs, sample based on arc angle and radius
                    try:
                        # Use CadQuery's specific methods for arcs
                        radius = edge.radius()
                        start_point = edge.startPoint()
                        end_point = edge.endPoint()

                        # Sample the arc - 1 point per degree of arc with a minimum of 10
                        num_points = max(10, int(abs(edge.arcAngle())))

                        # Sample the arc
                        for i in range(num_points):
                            t = i / (num_points - 1)
                            try:
                                point = edge.positionAt(t)
                                points.append((point.x, point.y, point.z))
                            except Exception:
                                continue
                    except Exception as e:
                        print(f"Error processing arc: {str(e)}")
                        # Fallback to uniform sampling
                        num_points = 20
                        for i in range(num_points):
                            t = i / (num_points - 1)
                            try:
                                point = edge.positionAt(t)
                                points.append((point.x, point.y, point.z))
                            except Exception:
                                continue

                elif edge_type == "CIRCLE":
                    # For circles, sample based on radius
                    radius = edge.radius()
                    # Calculate points based on circumference
                    circumference = 2 * np.pi * radius
                    # Use approximately 1 point per mm for circles
                    num_points = max(20, int(circumference / 1.0))

                    for i in range(num_points):
                        t = i / (num_points - 1)
                        try:
                            point = edge.positionAt(t)
                            points.append((point.x, point.y, point.z))
                        except Exception:
                            continue

                elif edge_type == "ELLIPSE":
                    # For ellipses, sample more densely
                    try:
                        # Get approximate size using BoundingBox() method
                        bbox = edge.BoundingBox()
                        size = max(bbox.xlen, bbox.ylen)
                        num_points = max(30, int(size * 2))

                        for i in range(num_points):
                            t = i / (num_points - 1)
                            try:
                                point = edge.positionAt(t)
                                points.append((point.x, point.y, point.z))
                            except Exception:
                                continue
                    except Exception:
                        # Fallback if BoundingBox not available
                        num_points = 40
                        for i in range(num_points):
                            t = i / (num_points - 1)
                            try:
                                point = edge.positionAt(t)
                                points.append((point.x, point.y, point.z))
                            except Exception:
                                continue

                elif edge_type == "BSPLINE":
                    # For B-splines in CadQuery, we'll use a different approach

                    # Approach 1: Use length-based sampling
                    try:
                        # Calculate points based on edge length
                        edge_length = edge.Length()

                        # Use more points for longer edges
                        base_density = 1.0  # points per unit length
                        num_points = max(20, int(edge_length * base_density))
                        num_points = min(num_points, 200)  # Cap at 200 points

                    except Exception:
                        # If Length() method fails, use a fixed number of points
                        num_points = 50

                    # Initial uniform sampling
                    sample_points = []
                    for i in range(num_points):
                        t = i / (num_points - 1)
                        try:
                            point = edge.positionAt(t)
                            sample_points.append((point.x, point.y, point.z))
                        except Exception:
                            continue

                    # Check if we need adaptive sampling based on curvature
                    if len(sample_points) >= 3:
                        # Calculate curvature estimation and add extra points where needed
                        refined_points = [sample_points[0]]  # Start with first point

                        for i in range(1, len(sample_points) - 1):
                            prev_point = sample_points[i - 1]
                            curr_point = sample_points[i]
                            next_point = sample_points[i + 1]

                            # Add current point
                            refined_points.append(curr_point)

                            # Calculate vectors and estimate curvature
                            v1 = [curr_point[j] - prev_point[j] for j in range(3)]
                            v2 = [next_point[j] - curr_point[j] for j in range(3)]

                            # Calculate lengths
                            len_v1 = sum(v**2 for v in v1) ** 0.5
                            len_v2 = sum(v**2 for v in v2) ** 0.5

                            if len_v1 > 1e-6 and len_v2 > 1e-6:
                                # Normalize vectors
                                v1_norm = [v / len_v1 for v in v1]
                                v2_norm = [v / len_v2 for v in v2]

                                # Calculate dot product
                                dot_product = sum(v1_norm[j] * v2_norm[j] for j in range(3))

                                # Estimate curvature (1-dot gives a measure of the angle)
                                curvature = 1 - max(-1, min(1, dot_product))  # Clamp to [-1, 1]

                                # Add extra points where curvature is high
                                if curvature > 0.1:  # Threshold for adding points
                                    # Add more points between curr and next
                                    extra_points = int(curvature * 10) + 1  # More points for higher curvature

                                    for j in range(1, extra_points):
                                        t_extra = i + j / (extra_points + 1)
                                        t_normalized = t_extra / (num_points - 1)
                                        try:
                                            point = edge.positionAt(t_normalized)
                                            refined_points.append((point.x, point.y, point.z))
                                        except Exception:
                                            continue

                        # Add last point
                        refined_points.append(sample_points[-1])
                        points = refined_points
                    else:
                        # If adaptive sampling failed, use the uniform sampling
                        points = sample_points

                else:
                    # For other curve types (or types we didn't explicitly handle)
                    # Use default uniform sampling
                    num_points = 40
                    for i in range(num_points):
                        t = i / (num_points - 1)
                        try:
                            point = edge.positionAt(t)
                            points.append((point.x, point.y, point.z))
                        except Exception:
                            continue

            except Exception as e:
                print(f"Error extracting edge of type {edge.geomType()}: {str(e)}")
                # Fallback to basic sampling
                num_points = 30
                for i in range(num_points):
                    t = i / (num_points - 1)
                    try:
                        point = edge.positionAt(t)
                        points.append((point.x, point.y, point.z))
                    except Exception:
                        continue

            # Add the edge points if we have any
            if points:
                edges.append(points)
                points_flat.extend(points)

        return edges

    def plot_3d_profiles(self):
        """Plot the extracted 3D profile edges exactly like the notebook."""
        ax = self.selection_canvas_3d.ax
        ax.clear()

        # Store edge labels for picking
        self.edge_labels = []

        # Determine units and conversion factor
        is_inches = hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()
        unit_conversion = 1 / 25.4 if is_inches else 1.0
        unit_label = "inch" if is_inches else "mm"

        # Plot left profile entities in blue (following notebook's visualize_entities_3d)
        for i, entity in enumerate(self.left_profile_entities):
            if len(entity) > 1:
                points = np.array(entity) * unit_conversion
                ax.plot(points[:, 0], points[:, 1], points[:, 2], color="blue", linewidth=2, alpha=0.8)

                # Add markers for start and end points (like notebook)
                ax.scatter(points[0, 0], points[0, 1], points[0, 2], color="blue", marker="o", s=30)
                ax.scatter(points[-1, 0], points[-1, 1], points[-1, 2], color="blue", marker="x", s=30)

                # Add clickable label at center
                center = np.mean(points, axis=0)
                text = ax.text(center[0], center[1], center[2], f"L{i}", fontsize=10, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"), zorder=10, picker=True)
                self.edge_labels.append((text, "left", i))

        # Plot right profile entities in red (following notebook's visualize_entities_3d)
        for i, entity in enumerate(self.right_profile_entities):
            if len(entity) > 1:
                points = np.array(entity) * unit_conversion
                ax.plot(points[:, 0], points[:, 1], points[:, 2], color="red", linewidth=2, alpha=0.8)

                # Add markers for start and end points (like notebook)
                ax.scatter(points[0, 0], points[0, 1], points[0, 2], color="red", marker="o", s=30)
                ax.scatter(points[-1, 0], points[-1, 1], points[-1, 2], color="red", marker="x", s=30)

                # Add clickable label at center
                center = np.mean(points, axis=0)
                text = ax.text(center[0], center[1], center[2], f"R{i}", fontsize=10, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"), zorder=10, picker=True)
                self.edge_labels.append((text, "right", i))

        ax.set_xlabel(f"X ({unit_label})")
        ax.set_ylabel(f"Y ({unit_label})")
        ax.set_zlabel(f"Z ({unit_label})")
        ax.set_title(f"{self.loaded_filename} - Profile Edges (L=Left, R=Right)")

        # Set axis limits and aspect ratio to fill the space better
        all_points = []
        for entity in self.left_profile_entities + self.right_profile_entities:
            all_points.extend(entity)

        if all_points:
            all_points = np.array(all_points) * unit_conversion
            x_min, x_max = all_points[:, 0].min(), all_points[:, 0].max()
            y_min, y_max = all_points[:, 1].min(), all_points[:, 1].max()
            z_min, z_max = all_points[:, 2].min(), all_points[:, 2].max()

            # Add padding
            x_pad = (x_max - x_min) * 0.1
            y_pad = (y_max - y_min) * 0.1
            z_pad = (z_max - z_min) * 0.1

            ax.set_xlim(x_min - x_pad, x_max + x_pad)
            ax.set_ylim(y_min - y_pad, y_max + y_pad)
            ax.set_zlim(z_min - z_pad, z_max + z_pad)

            # Allow automatic aspect ratio for best fit
            ax.set_box_aspect(None)
        else:
            ax.set_box_aspect(None)

        # Connect pick event for edge label clicking
        self.selection_canvas_3d.fig.canvas.mpl_connect("pick_event", self.on_3d_edge_click)

        self.selection_canvas_3d.draw()

    def on_3d_edge_click(self, event):
        """Handle clicking on 3D profile edge labels for sequencing."""
        if hasattr(event, "artist"):
            # Find which edge was clicked
            for text, side, edge_idx in self.edge_labels:
                if event.artist == text:
                    self.add_edge_to_sequence(side, edge_idx)
                    return

    def add_edge_to_sequence(self, side, edge_idx):
        """Add an edge to the appropriate sequence list."""
        if side == "left":
            if edge_idx not in self.left_sequence_order:
                self.left_sequence_order.append(edge_idx)
                self.left_sequence_list.addItem(f"L{edge_idx}")
                print(f"Added left edge {edge_idx} to sequence")
        elif side == "right":
            if edge_idx not in self.right_sequence_order:
                self.right_sequence_order.append(edge_idx)
                self.right_sequence_list.addItem(f"R{edge_idx}")
                print(f"Added right edge {edge_idx} to sequence")

    def get_active_sequence_list(self):
        """Return the currently focused sequence list."""
        return self.last_focused_sequence_list or self.left_sequence_list

    def get_active_sequence_order(self):
        """Return the sequence order for the active list."""
        active_list = self.get_active_sequence_list()
        return self.left_sequence_order if active_list == self.left_sequence_list else self.right_sequence_order

    def add_leadinout(self, lead_type):
        """Add lead-in or lead-out to both left and right sequences simultaneously."""
        dialog = LeadInOutDialog(self, lead_type)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get distance from dialog
            distance = dialog.get_selected_distance()

            # Create lead-in/out item
            leadinout_item = {
                "type": lead_type.lower().replace("-", ""),  # "Lead-in" -> "leadin"
                "distance": distance,
            }

            # Create display text
            display_text = f"{lead_type} X{distance[0]} Y{distance[1]}"

            # Add to both sequences
            if lead_type == "Lead-in":
                # Insert at beginning for lead-in
                self.left_sequence_order.insert(0, leadinout_item.copy())
                self.right_sequence_order.insert(0, leadinout_item.copy())
                self.left_sequence_list.insertItem(0, display_text)
                self.right_sequence_list.insertItem(0, display_text)
            else:  # Lead-out
                # Append at end for lead-out
                self.left_sequence_order.append(leadinout_item.copy())
                self.right_sequence_order.append(leadinout_item.copy())
                self.left_sequence_list.addItem(display_text)
                self.right_sequence_list.addItem(display_text)

            print(f"Added {lead_type} with distance {distance} to both left and right sequences")

    def on_3d_sequence_changed(self):
        """Handle when 3D cutting sequence is changed by drag/drop."""
        # Update internal sequence orders based on list contents
        self.left_sequence_order = []
        self.right_sequence_order = []

        for i in range(self.left_sequence_list.count()):
            item = self.left_sequence_list.item(i)
            self.parse_sequence_item(item.text(), self.left_sequence_order)

        for i in range(self.right_sequence_list.count()):
            item = self.right_sequence_list.item(i)
            self.parse_sequence_item(item.text(), self.right_sequence_order)

        print(f"3D sequence updated: Left={len(self.left_sequence_order)}, Right={len(self.right_sequence_order)}")

    def parse_sequence_item(self, text, sequence_order):
        """Parse a sequence item text and add to sequence order."""
        if text.startswith("L"):
            # Left edge
            try:
                edge_idx = int(text[1:].split()[0])
                sequence_order.append(edge_idx)
            except (ValueError, IndexError):
                pass
        elif text.startswith("R"):
            # Right edge
            try:
                edge_idx = int(text[1:].split()[0])
                sequence_order.append(edge_idx)
            except (ValueError, IndexError):
                pass
        elif "Lead-in" in text or "Lead-out" in text:
            # Parse: "Lead-in X10.0 Y0.0" -> {"type": "leadin", "distance": [10.0, 0.0]}
            parts = text.split()
            lead_type = parts[0].lower().replace("-", "")  # "Lead-in" -> "leadin"

            # Extract X and Y values
            try:
                x_val = float(parts[1][1:])  # "X10.0" -> 10.0
                y_val = float(parts[2][1:])  # "Y0.0" -> 0.0

                leadinout_item = {"type": lead_type, "distance": [x_val, y_val]}
                sequence_order.append(leadinout_item)
            except (IndexError, ValueError) as e:
                print(f"Error parsing lead-in/out item '{text}': {e}")

    def eventFilter(self, obj, event):
        """Handle key press events for DEL key and focus tracking on sequence lists."""
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key_Delete:
            self.delete_selected_from_both_sequences()
            return True
        elif event.type() == event.Type.FocusIn:
            if obj == self.left_sequence_list:
                self.last_focused_sequence_list = self.left_sequence_list
            elif obj == self.right_sequence_list:
                self.last_focused_sequence_list = self.right_sequence_list
        return super().eventFilter(obj, event)

    def delete_selected_from_sequence(self, sequence_list, sequence_order):
        """Delete selected items from a sequence list."""
        selected_items = sequence_list.selectedItems()
        if not selected_items:
            return

        # Get selected rows in reverse order to avoid index shifting
        selected_rows = sorted([sequence_list.row(item) for item in selected_items], reverse=True)

        # Remove from list widget and sequence order
        for row in selected_rows:
            sequence_list.takeItem(row)
            if row < len(sequence_order):
                sequence_order.pop(row)

    def delete_selected_from_both_sequences(self):
        """Delete selected items from the last focused sequence list."""
        # Use last focused list, or fall back to current selection logic
        target_list = self.last_focused_sequence_list
        if target_list is None:
            selected_left = self.left_sequence_list.selectedItems()
            selected_right = self.right_sequence_list.selectedItems()
            if selected_left:
                target_list = self.left_sequence_list
            elif selected_right:
                target_list = self.right_sequence_list

        if target_list is None:
            return

        # Get selected items and check if any are lead-in/out items
        selected_items = target_list.selectedItems()
        if not selected_items:
            return

        # Get selected rows and check for lead-in/out items
        selected_rows = [target_list.row(item) for item in selected_items]
        selected_rows.sort(reverse=True)  # Reverse order to avoid index shifting

        leadinout_rows = []
        for row in selected_rows:
            item = target_list.item(row)
            if item and ("Lead-in" in item.text() or "Lead-out" in item.text()):
                leadinout_rows.append(row)

        # For lead-in/out items, delete from both sequences
        for row in leadinout_rows:
            # Remove from both UI lists
            self.left_sequence_list.takeItem(row)
            self.right_sequence_list.takeItem(row)

            # Remove from both sequence orders
            if row < len(self.left_sequence_order):
                self.left_sequence_order.pop(row)
            if row < len(self.right_sequence_order):
                self.right_sequence_order.pop(row)

        # For regular items, use the standard delete method
        remaining_selected = [item for item in selected_items if not ("Lead-in" in item.text() or "Lead-out" in item.text())]

        if remaining_selected:
            if target_list == self.left_sequence_list:
                self.delete_selected_from_sequence(self.left_sequence_list, self.left_sequence_order)
            elif target_list == self.right_sequence_list:
                self.delete_selected_from_sequence(self.right_sequence_list, self.right_sequence_order)

        if leadinout_rows:
            print(f"Deleted {len(leadinout_rows)} lead-in/out items from both sequences")

        # Update sequence tracking
        self.on_3d_sequence_changed()

    def customize_sequence_item(self, item):
        """Customize a sequence item - either edit lead-in/out or set cutting direction."""
        item_text = item.text()

        # Check if this is a lead-in/out entry
        if "Lead-in" in item_text or "Lead-out" in item_text:
            self.edit_leadinout_item(item)
        else:
            # This is a regular cutting sequence item - customize direction
            self.customize_cutting_direction(item)

    def edit_leadinout_item(self, item):
        """Edit a lead-in/out sequence item in both sequences."""
        # Determine which list this item is from
        sequence_list = item.listWidget()
        if sequence_list == self.left_sequence_list:
            sequence_order = self.left_sequence_order
            other_list = self.right_sequence_list
            other_order = self.right_sequence_order
        elif sequence_list == self.right_sequence_list:
            sequence_order = self.right_sequence_order
            other_list = self.left_sequence_list
            other_order = self.left_sequence_order
        else:
            return

        # Find the corresponding entry in sequence_order
        row = sequence_list.row(item)
        if row < len(sequence_order):
            leadinout_data = sequence_order[row]

            # Check if this is a lead-in/out item
            if isinstance(leadinout_data, dict) and leadinout_data.get("type") in ["leadin", "leadout"]:
                # Open dialog with current values
                lead_type = "Lead-in" if leadinout_data["type"] == "leadin" else "Lead-out"
                current_distance = leadinout_data["distance"]

                dialog = LeadInOutDialog(self, lead_type, current_distance=current_distance)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    # Update stored data in both sequences
                    new_distance = dialog.get_selected_distance()
                    leadinout_data["distance"] = new_distance

                    # Update the corresponding item in the other sequence
                    if row < len(other_order):
                        other_data = other_order[row]
                        if isinstance(other_data, dict) and other_data.get("type") == leadinout_data["type"]:
                            other_data["distance"] = new_distance

                    # Update UI display in both lists
                    display_text = f"{lead_type} X{new_distance[0]} Y{new_distance[1]}"
                    item.setText(display_text)

                    # Update corresponding item in other list
                    if row < other_list.count():
                        other_item = other_list.item(row)
                        if other_item:
                            other_item.setText(display_text)

                    print(f"Updated {lead_type} to distance {new_distance} in both sequences")

    def customize_cutting_direction(self, item):
        """Customize cutting direction for a sequence item."""
        item_text = item.text()

        # Determine which list this item is from and get the item key
        sequence_list = item.listWidget()
        row = sequence_list.row(item)

        if sequence_list == self.left_sequence_list:
            item_key = f"left_{row}"
            side_name = "Left"
        elif sequence_list == self.right_sequence_list:
            item_key = f"right_{row}"
            side_name = "Right"
        else:
            return

        # Get current direction setting
        current_direction = self.custom_directions.get(item_key, 0)  # Default to auto

        # Extract the base item text (without direction info)
        base_text = item_text
        if " [" in base_text:
            base_text = base_text.split(" [")[0]

        # Open direction customization dialog
        dialog = DirectionCustomizationDialog(self, f"{side_name} - {base_text}", current_direction)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_direction = dialog.get_direction()
            direction_text = dialog.get_direction_text()

            # Store the custom direction
            if new_direction == 0:  # Auto - remove custom setting
                self.custom_directions.pop(item_key, None)
                new_item_text = base_text
            else:
                self.custom_directions[item_key] = new_direction
                new_item_text = f"{base_text} [{direction_text}]"

            # Update the item text
            item.setText(new_item_text)

            print(f"Set direction for {side_name} sequence row {row}: {direction_text} ({new_direction})")

    def left_sequence_drop_event(self, event):
        """Handle drop events on the left sequence list."""
        self.handle_sequence_drop_event(event, self.left_sequence_list, self.right_sequence_list, self.left_sequence_order, self.right_sequence_order)

    def right_sequence_drop_event(self, event):
        """Handle drop events on the right sequence list."""
        self.handle_sequence_drop_event(event, self.right_sequence_list, self.left_sequence_list, self.right_sequence_order, self.left_sequence_order)

    def handle_sequence_drop_event(self, event, target_list, source_list, target_order, source_order):
        """Handle drag and drop between left and right sequence lists."""
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

                # Remove from source
                row = source_list.row(item)
                source_list.takeItem(row)
                if row < len(source_order):
                    moved_item = source_order.pop(row)
                    target_order.append(moved_item)

                # Add to target
                target_list.addItem(text)
        else:
            # External drop - ignore
            event.ignore()

    def toggle_animation_view(self):
        """Toggle between 2D and 3D animation view and start animation."""
        if self.view_2d_radio.isChecked():
            self.animation_stack.setCurrentIndex(0)  # Show 2D animation canvas
            # Enable G-code points button for 2D view
            self.show_gcode_points_button.setEnabled(True)
            self.show_gcode_points_button.setStyleSheet("")
        else:
            self.animation_stack.setCurrentIndex(1)  # Show 3D animation canvas
            # Disable and grey out G-code points button for 3D view
            self.show_gcode_points_button.setEnabled(False)
            self.show_gcode_points_button.setStyleSheet("color: gray;")

        # Start animation when view is toggled
        self.animate_path_3d()

    def animate_path_3d(self):
        """Animate the 3D cutting path."""
        # Check if sequences are configured
        if not self.left_sequence_order or not self.right_sequence_order:
            QMessageBox.warning(self, "No Sequence", "No cutting sequence configured. Please select profiles and add entities to the cutting sequence.")
            return

        cutting_paths = self.generate_cutting_path_3d()
        if not cutting_paths:
            QMessageBox.warning(self, "No Path", "No 3D cutting path to animate. Please configure the cutting sequence.")
            return

        # Reset animation state when starting new animation
        self.animation_paused = False
        self.pause_3d_button.setText("Pause")
        self.animate_frame_3d = 0
        self.animate_frame_2d = 0

        # Clear cumulative distances to force recalculation with new units
        self.cumulative_distances_2d = None
        self.cumulative_distances_3d = None

        # Stop any existing animation timers
        if hasattr(self, "animation_timer_3d") and self.animation_timer_3d is not None:
            self.animation_timer_3d.stop()
            self.animation_timer_3d = None
        if hasattr(self, "animation_timer_2d") and self.animation_timer_2d is not None:
            self.animation_timer_2d.stop()
            self.animation_timer_2d = None

        # Determine which canvas to use based on the radio button selection
        if hasattr(self, "view_3d_radio") and self.view_3d_radio.isChecked():
            ax = self.animation_canvas_3d.ax
            self.animation_stack.setCurrentIndex(1)  # Show 3D animation canvas
            self.plot_3d_animation(cutting_paths, ax)
        else:
            ax = self.animation_canvas.ax
            self.animation_stack.setCurrentIndex(0)  # Show 2D animation canvas
            self.plot_2d_projection_animation(cutting_paths, ax)

        # Process events to ensure canvas is updated
        QApplication.processEvents()

    def plot_3d_animation(self, cutting_paths, ax):
        """Create and start the 3D animation identical to the notebook's animate_dual_gantry_path_3d."""
        # Stop any existing animation
        try:
            if hasattr(self, "cutting_animation") and self.cutting_animation is not None and hasattr(self.cutting_animation, "event_source") and self.cutting_animation.event_source is not None:
                self.cutting_animation.event_source.stop()
        except Exception:
            pass
        self.cutting_animation = None

        # Start the 3D dual gantry animation
        self.animate_dual_gantry_path_3d(cutting_paths, ax)

    def animate_dual_gantry_path_2d(self, cutting_paths, ax, tool_size=5.0, interval=30, speed_multiplier=1.0):
        """Create a 2D animation showing both XY and AZ gantry movements identical to the notebook."""

        # Stop any existing animation
        if hasattr(self, "cutting_animation") and self.cutting_animation is not None and hasattr(self.cutting_animation, "event_source"):
            self.cutting_animation.event_source.stop()

        # Get speed from GUI
        try:
            speed = float(self.animation_speed_edit.text()) * speed_multiplier
        except (ValueError, AttributeError):
            speed = 50.0

        # Clear axis and setup
        ax.clear()

        # Flatten all paths into a single array for calculating bounds
        if not cutting_paths or all(len(path) == 0 for path in cutting_paths):
            return

        all_points = np.vstack([path for path in cutting_paths if len(path) > 0])

        # Apply unit conversion if needed
        unit_conversion = 1 / 25.4 if (hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()) else 1.0
        all_points_display = all_points * unit_conversion

        # Extract XY and AZ components
        xy_points = all_points_display[:, :2]  # X and Y (left gantry)
        az_points = all_points_display[:, 2:]  # A and Z (right gantry)

        # Calculate limits to fit both paths with margin
        all_coords = np.vstack([xy_points, az_points])
        tool_size_display = tool_size * unit_conversion
        x_min, y_min = all_coords.min(axis=0) - tool_size_display * 2
        x_max, y_max = all_coords.max(axis=0) + tool_size_display * 2

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_aspect("equal")

        # Store cutting paths for G-code point redrawing
        self.current_cutting_paths = cutting_paths

        # Store G-code point plots for visibility control
        self.gcode_point_plots_2d = []

        # Always plot complete paths in light gray (like 2D app)
        for i, path in enumerate(cutting_paths):
            if len(path) > 0:
                path_array = np.array(path) * unit_conversion

                # Plot gray path lines for XY and AZ paths
                xy_path_points = path_array[:, :2]  # X and Y (left gantry)
                az_path_points = path_array[:, 2:]  # A and Z (right gantry)

                ax.plot(xy_path_points[:, 0], xy_path_points[:, 1], color="lightgray", linewidth=1, alpha=0.7, zorder=3)
                ax.plot(az_path_points[:, 0], az_path_points[:, 1], color="lightgray", linewidth=1, alpha=0.7, zorder=3)

                # Plot G-code points if enabled
                if self.show_gcode_points:
                    (line1,) = ax.plot(xy_path_points[:, 0], xy_path_points[:, 1], "b.", markersize=2, alpha=0.6, zorder=4)
                    (line2,) = ax.plot(az_path_points[:, 0], az_path_points[:, 1], "r.", markersize=2, alpha=0.6, zorder=4)
                    self.gcode_point_plots_2d.extend([line1, line2])

        # No legends needed for 3D app animations

        # Initialize the gantry markers
        if len(xy_points) > 0:
            # Apply unit conversion to tool size
            tool_size_display = tool_size * unit_conversion
            self.xy_tool = patches.Circle((xy_points[0][0], xy_points[0][1]), tool_size_display, color="blue", alpha=0.7, zorder=10)
            self.az_tool = patches.Circle((az_points[0][0], az_points[0][1]), tool_size_display, color="green", alpha=0.7, zorder=10)
            ax.add_patch(self.xy_tool)
            ax.add_patch(self.az_tool)

            # Line connecting the two gantry positions (hot wire)
            (self.wire_line,) = ax.plot([xy_points[0][0], az_points[0][0]], [xy_points[0][1], az_points[0][1]], "g-", linewidth=2)

        # Lines for the traveled paths
        (self.xy_traveled,) = ax.plot([], [], "b-", linewidth=2)
        (self.az_traveled,) = ax.plot([], [], "r-", linewidth=2)

        # Progress text
        # No progress text needed for 3D app animations

        ax.set_title("Hot Wire Cutting Animation - XY and AZ Gantry Paths")
        ax.grid(True, linestyle="--", alpha=0.6)
        unit_label = "inch" if (hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()) else "mm"
        ax.set_xlabel(f"X/A ({unit_label})")
        ax.set_ylabel(f"Y/Z ({unit_label})")

        # Process cutting paths to ensure consistent motion
        self.animation_segments = []
        total_xy_length = 0
        total_az_length = 0

        # Process each path to create segments
        for path in cutting_paths:
            if len(path) < 2:
                continue

            # For paths with only two points (straight lines)
            if len(path) == 2:
                start_point = path[0]
                end_point = path[1]

                # Calculate distances for the straight line
                xy_dist = np.linalg.norm(end_point[:2] - start_point[:2])
                az_dist = np.linalg.norm(end_point[2:] - start_point[2:])
                avg_dist = (xy_dist + az_dist) / 2

                # Add segment with start and end points
                self.animation_segments.append((start_point, end_point, xy_dist, az_dist, avg_dist))

                # Accumulate total distance
                total_xy_length += xy_dist
                total_az_length += az_dist
            else:
                # For paths with more than two points, process segment by segment
                for i in range(1, len(path)):
                    xy_dist = np.linalg.norm(path[i][:2] - path[i - 1][:2])
                    az_dist = np.linalg.norm(path[i][2:] - path[i - 1][2:])
                    avg_dist = (xy_dist + az_dist) / 2
                    self.animation_segments.append((path[i - 1], path[i], xy_dist, az_dist, avg_dist))
                    total_xy_length += xy_dist
                    total_az_length += az_dist

        # Calculate total number of frames based on total path length
        avg_total_length = (total_xy_length + total_az_length) / 2
        self.animation_total_frames = max(int(avg_total_length / speed) + 10, 100)  # Ensure enough frames to reach 100%

        # Pre-compute positions for all frames for smoother animation
        self.animation_frame_positions = []

        # Initialize tracking variables
        dist_so_far = 0

        if self.animation_segments:
            # Add initial position with segment_idx = 0
            self.animation_frame_positions.append((self.animation_segments[0][0][:2], self.animation_segments[0][0][2:], 0, 0))

            # Compute distance intervals for frames
            dist_per_frame = avg_total_length / self.animation_total_frames

            current_segment_idx = 0
            current_segment = self.animation_segments[0]
            segment_start_dist = 0

            for frame in range(1, self.animation_total_frames + 1):
                target_dist = frame * dist_per_frame

                # Find the correct segment where this distance falls
                while dist_so_far + current_segment[4] < target_dist and current_segment_idx < len(self.animation_segments) - 1:
                    dist_so_far += current_segment[4]
                    current_segment_idx += 1
                    current_segment = self.animation_segments[current_segment_idx]
                    segment_start_dist = dist_so_far

                # Calculate position within current segment
                segment_progress = 0
                if current_segment[4] > 0:  # Avoid division by zero
                    segment_progress = min(1.0, (target_dist - segment_start_dist) / current_segment[4])

                # Interpolate the position along this segment
                xy_pos = current_segment[0][:2] + segment_progress * (current_segment[1][:2] - current_segment[0][:2])
                az_pos = current_segment[0][2:] + segment_progress * (current_segment[1][2:] - current_segment[0][2:])

                # Calculate overall progress
                overall_progress = target_dist / avg_total_length

                # Add to position list
                self.animation_frame_positions.append((xy_pos, az_pos, overall_progress, current_segment_idx))

        # Initialize frame counter
        self.current_frame = 0

        # Store animation parameters for QTimer-based animation
        self.animation_2d_params = {"cutting_paths": cutting_paths, "ax": ax, "speed": speed, "xy_points": xy_points, "az_points": az_points}

        # Calculate total frames for looping
        total_path_length = sum(len(path) for path in cutting_paths if len(path) > 0)
        fps = 30
        total_time = total_path_length / speed if speed > 0 else 1
        self.total_frames_2d = max(int(total_time * fps), 100)

        # Reset frame counter and completion flag
        self.animate_frame_2d = 0
        self.animation_completed_2d = False

        # Start QTimer-based animation
        self.animation_timer_2d = ax.figure.canvas.new_timer(interval=int(1000 / fps))
        self.animation_timer_2d.add_callback(self.update_2d_animation_qtimer)
        self.animation_timer_2d.start()

        # Enable controls
        self.pause_3d_button.setEnabled(True)

        # Force redraw
        ax.figure.canvas.draw()

    def update_2d_animation_qtimer(self):
        """Update 2D animation using QTimer approach like 2D app."""
        if not hasattr(self, "animation_2d_params") or not self.animation_2d_params:
            return

        # Check if animation completed - restart if so
        # Use distance-based completion instead of frame-based
        if hasattr(self, "animation_completed_2d") and self.animation_completed_2d:
            self.animate_frame_2d = 0  # Restart animation
            self.animation_completed_2d = False

        cutting_paths = self.animation_2d_params["cutting_paths"]
        ax = self.animation_2d_params["ax"]
        speed = self.animation_2d_params["speed"]

        if not cutting_paths:
            return

        # Flatten all paths into single array
        all_points = np.vstack([path for path in cutting_paths if len(path) > 0])
        if len(all_points) == 0:
            return

        # Calculate current position based on frame
        fps = 30
        time = self.animate_frame_2d / fps
        distance = time * speed

        # Calculate cumulative distances if not done yet
        if not hasattr(self, "cumulative_distances_2d") or self.cumulative_distances_2d is None:
            segment_vectors = all_points[1:] - all_points[:-1]
            segment_lengths = np.linalg.norm(segment_vectors, axis=1)
            self.cumulative_distances_2d = np.cumsum(np.insert(segment_lengths, 0, 0))

        total_length = self.cumulative_distances_2d[-1]
        if total_length <= 0:
            return

        # Check if animation completed
        if distance >= total_length:
            self.animation_completed_2d = True
            distance = total_length - 0.001  # Set to just before the end
        else:
            self.animation_completed_2d = False

        # Find current position
        segment_idx = np.searchsorted(self.cumulative_distances_2d, distance, side="right") - 1
        segment_idx = max(0, min(segment_idx, len(all_points) - 2))

        # Calculate position within segment
        segment_start_dist = self.cumulative_distances_2d[segment_idx]
        segment_length = self.cumulative_distances_2d[segment_idx + 1] - segment_start_dist

        if segment_length > 0:
            segment_progress = (distance - segment_start_dist) / segment_length
        else:
            segment_progress = 0

        # Interpolate current position
        current_point = all_points[segment_idx] + segment_progress * (all_points[segment_idx + 1] - all_points[segment_idx])

        # Apply unit conversion if needed
        unit_conversion = 1 / 25.4 if (hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()) else 1.0
        current_point_display = current_point * unit_conversion

        # Extract XY and AZ positions for 2D display
        xy_pos = current_point_display[:2]
        az_pos = current_point_display[2:]

        # Update tool positions
        if hasattr(self, "xy_tool"):
            self.xy_tool.center = (xy_pos[0], xy_pos[1])
        if hasattr(self, "az_tool"):
            self.az_tool.center = (az_pos[0], az_pos[1])

        # Update hot wire line
        if hasattr(self, "wire_line"):
            self.wire_line.set_data([xy_pos[0], az_pos[0]], [xy_pos[1], az_pos[1]])

        # Update traveled paths
        if hasattr(self, "xy_traveled") and hasattr(self, "az_traveled"):
            # Get all points up to current position
            traveled_points = all_points[: segment_idx + 1] * unit_conversion
            if len(traveled_points) > 0:
                # Add current interpolated point
                traveled_points = np.vstack([traveled_points, current_point_display])

                # Update XY traveled
                self.xy_traveled.set_data(traveled_points[:, 0], traveled_points[:, 1])
                # Update AZ traveled
                self.az_traveled.set_data(traveled_points[:, 2], traveled_points[:, 3])

        self.animate_frame_2d += 1
        ax.figure.canvas.draw()

        # Update tool positions
        self.xy_tool.center = (xy_pos[0], xy_pos[1])
        self.az_tool.center = (az_pos[0], az_pos[1])

        # Update hot wire (RED color as requested)
        self.wire_line.set_data([xy_pos[0], az_pos[0]], [xy_pos[1], az_pos[1]])

        # Collect all points up to the current position for the traveled path
        # Use all points up to current segment + interpolated position
        traveled_points = all_points[: segment_idx + 1].copy() * unit_conversion
        if len(traveled_points) > 0:
            # Add current interpolated position
            traveled_points = np.vstack([traveled_points, current_point_display])

            # Split into XY and AZ components
            xy_path_points = traveled_points[:, :2]
            az_path_points = traveled_points[:, 2:]

            # Update the traveled paths
            self.xy_traveled.set_data(xy_path_points[:, 0], xy_path_points[:, 1])
            self.az_traveled.set_data(az_path_points[:, 0], az_path_points[:, 1])

        # No progress text to update

        return []

    def animate_dual_gantry_path_3d(self, cutting_paths, ax, gantry_gap=None, tool_size=5.0, speed=None, interval=30, y_offset=0):
        """Create a 3D animation showing both XY and AZ gantry movements identical to notebook."""
        # Get parameters from GUI if not provided
        if gantry_gap is None:
            try:
                gantry_gap = float(self.gantry_gap_edit.text())
            except (ValueError, AttributeError):
                gantry_gap = 924.0

        if speed is None:
            try:
                speed = float(self.animation_speed_edit.text())
            except (ValueError, AttributeError):
                speed = 3.0

        if y_offset == 0:
            try:
                y_offset = float(self.y_offset_3d_edit.text())
            except (ValueError, AttributeError):
                y_offset = 0.0

        # Clear axis and setup
        ax.clear()

        # Define colors for different elements
        colors = {"left_entities": "lightblue", "right_entities": "lightgreen", "left_path": "blue", "right_path": "green", "hot_wire": "red", "completed_left": "blue", "completed_right": "green"}

        # Calculate gantry positions in display units
        # gantry_gap from UI is already in display units, don't convert again
        left_plane_y = -gantry_gap / 2
        right_plane_y = gantry_gap / 2

        # Plot the left and right profile entities (always visible as wireframe)
        unit_conversion = 1 / 25.4 if (hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()) else 1.0

        for i, entity in enumerate(self.left_profile_entities):
            if len(entity) > 1:
                points = np.array(entity)
                # Apply y-offset to center entities and unit conversion
                points_offset = points.copy()
                points_offset[:, 1] -= y_offset
                points_offset = points_offset * unit_conversion
                ax.plot(points_offset[:, 0], points_offset[:, 1], points_offset[:, 2], color=colors["left_entities"], linewidth=1.5, alpha=0.6, zorder=5)

        for i, entity in enumerate(self.right_profile_entities):
            if len(entity) > 1:
                points = np.array(entity)
                # Apply y-offset to center entities and unit conversion
                points_offset = points.copy()
                points_offset[:, 1] -= y_offset
                points_offset = points_offset * unit_conversion
                ax.plot(points_offset[:, 0], points_offset[:, 1], points_offset[:, 2], color=colors["right_entities"], linewidth=1.5, alpha=0.6, zorder=5)

        # Flatten all paths into a single array for calculating bounds
        if not cutting_paths or all(len(path) == 0 for path in cutting_paths):
            return

        all_points = np.vstack([path for path in cutting_paths if len(path) > 0])

        # Apply unit conversion if needed
        unit_conversion = 1 / 25.4 if (hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()) else 1.0
        all_points_display = all_points * unit_conversion

        # Calculate overall limits from all paths and entities
        x_min, x_max = float("inf"), float("-inf")
        z_min, z_max = float("inf"), float("-inf")

        # Consider cutting paths for limits
        if len(all_points_display) > 0:
            x_min = min(x_min, np.min(all_points_display[:, [0, 2]]))
            x_max = max(x_max, np.max(all_points_display[:, [0, 2]]))
            z_min = min(z_min, np.min(all_points_display[:, [1, 3]]))
            z_max = max(z_max, np.max(all_points_display[:, [1, 3]]))

        # Consider entities for limits
        for entity in self.left_profile_entities + self.right_profile_entities:
            if len(entity) > 0:
                points = np.array(entity) * unit_conversion
                points[:, 1] -= y_offset * unit_conversion  # Apply y-offset
                x_min = min(x_min, np.min(points[:, 0]))
                x_max = max(x_max, np.max(points[:, 0]))
                z_min = min(z_min, np.min(points[:, 2]))
                z_max = max(z_max, np.max(points[:, 2]))

        # Add padding to limits
        padding = 0.1
        x_range = max(0.001, x_max - x_min)
        z_range = max(0.001, z_max - z_min)

        x_min -= padding * x_range
        x_max += padding * x_range
        z_min -= padding * z_range
        z_max += padding * z_range

        # Set limits with padding
        ax.set_xlim(x_min, x_max)
        # Gantry positions are already in display units, don't apply conversion again
        ax.set_ylim(left_plane_y - 0.2 * gantry_gap, right_plane_y + 0.2 * gantry_gap)
        ax.set_zlim(z_min, z_max)

        # Initialize the gantry markers and hot wire
        # Don't scale tool size - it's already in display units (points)
        self.left_gantry_3d = ax.scatter([], [], [], color=colors["left_path"], s=tool_size**2, marker="o", zorder=10)
        self.right_gantry_3d = ax.scatter([], [], [], color=colors["right_path"], s=tool_size**2, marker="o", zorder=10)

        # Hot wire connecting the gantries (GREEN color as requested)
        (self.hot_wire_3d,) = ax.plot([], [], [], color=colors["hot_wire"], linewidth=2, zorder=9)

        # Lines for the traveled paths
        (self.left_traveled_3d,) = ax.plot([], [], [], color=colors["completed_left"], linewidth=2, zorder=8)
        (self.right_traveled_3d,) = ax.plot([], [], [], color=colors["completed_right"], linewidth=2, zorder=8)

        # Progress text
        # No progress text needed for 3D app animations

        # Set labels and title with proper units
        unit_label = "inch" if (hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()) else "mm"
        ax.set_xlabel(f"X ({unit_label})")
        ax.set_ylabel(f"Y ({unit_label})")
        ax.set_zlabel(f"Z ({unit_label})")
        ax.set_title("Hot Wire Cutting Animation - 3D View")

        # No legend needed for 3D app animations

        # Calculate total path length and frames needed
        total_xy_length = 0
        total_az_length = 0
        self.animation_segments_3d = []

        for path in cutting_paths:
            if len(path) < 2:
                continue

            for i in range(1, len(path)):
                xy_dist = np.linalg.norm(path[i][:2] - path[i - 1][:2])
                az_dist = np.linalg.norm(path[i][2:] - path[i - 1][2:])
                avg_dist = (xy_dist + az_dist) / 2
                self.animation_segments_3d.append((path[i - 1], path[i], xy_dist, az_dist, avg_dist))
                total_xy_length += xy_dist
                total_az_length += az_dist

        # Calculate total number of frames based on total path length
        avg_total_length = (total_xy_length + total_az_length) / 2
        self.animation_total_frames_3d = max(int(avg_total_length / speed) + 10, 100)  # Ensure enough frames to reach 100%

        # Pre-compute positions for all frames
        self.animation_frame_positions_3d = []

        # Initialize tracking variables
        dist_so_far = 0

        if self.animation_segments_3d:
            # Add initial position with segment_idx = 0
            self.animation_frame_positions_3d.append((self.animation_segments_3d[0][0][:2], self.animation_segments_3d[0][0][2:], 0, 0))

            # Compute distance intervals for frames
            dist_per_frame = avg_total_length / self.animation_total_frames_3d

            current_segment_idx = 0
            current_segment = self.animation_segments_3d[0]
            segment_start_dist = 0

            for frame in range(1, self.animation_total_frames_3d + 1):
                target_dist = frame * dist_per_frame

                # Find the correct segment where this distance falls
                while dist_so_far + current_segment[4] < target_dist and current_segment_idx < len(self.animation_segments_3d) - 1:
                    dist_so_far += current_segment[4]
                    current_segment_idx += 1
                    current_segment = self.animation_segments_3d[current_segment_idx]
                    segment_start_dist = dist_so_far

                # Calculate position within current segment
                segment_progress = 0
                if current_segment[4] > 0:  # Avoid division by zero
                    segment_progress = min(1.0, (target_dist - segment_start_dist) / current_segment[4])

                # Interpolate the position along this segment
                xy_pos = current_segment[0][:2] + segment_progress * (current_segment[1][:2] - current_segment[0][:2])
                az_pos = current_segment[0][2:] + segment_progress * (current_segment[1][2:] - current_segment[0][2:])

                # Calculate overall progress
                overall_progress = target_dist / avg_total_length

                # Add to position list
                self.animation_frame_positions_3d.append((xy_pos, az_pos, overall_progress, current_segment_idx))

        # Store cutting paths for reference
        self.current_cutting_paths = cutting_paths

        # Store animation parameters for QTimer-based animation
        self.animation_3d_params = {"cutting_paths": cutting_paths, "ax": ax, "gantry_gap": gantry_gap, "speed": speed, "y_offset": y_offset, "left_plane_y": left_plane_y, "right_plane_y": right_plane_y}

        # Initialize frame counter and completion flag
        self.animate_frame_3d = 0
        self.animation_completed_3d = False

        # Calculate total frames for looping
        total_path_length = sum(len(path) for path in cutting_paths if len(path) > 0)
        fps = 30
        total_time = total_path_length / speed if speed > 0 else 1
        self.total_frames_3d = max(int(total_time * fps), 100)

        # Start QTimer-based animation
        self.animation_timer_3d = ax.figure.canvas.new_timer(interval=int(1000 / fps))
        self.animation_timer_3d.add_callback(self.update_3d_animation_qtimer)
        self.animation_timer_3d.start()

        # Set a good default view angle
        ax.view_init(elev=20, azim=-35)

        # Add gray path lines for complete cutting paths (like 2D app)
        for path in cutting_paths:
            if len(path) > 0:
                path_array = np.array(path) * unit_conversion

                # Plot left gantry path (XY) in light gray
                ax.plot(path_array[:, 0], [left_plane_y * unit_conversion] * len(path_array), path_array[:, 1], color="lightgray", linewidth=1.5, alpha=0.6, zorder=7)
                # Plot right gantry path (AZ) in light gray
                ax.plot(path_array[:, 2], [right_plane_y * unit_conversion] * len(path_array), path_array[:, 3], color="lightgray", linewidth=1.5, alpha=0.6, zorder=7)

        # Optimize 3D plot to use full width - calculate aspect ratios
        # Set equal aspect ratio for proper 3D visualization
        ax.set_box_aspect([1, 1, 1])

        # Enable controls
        self.pause_3d_button.setEnabled(True)

        # Force redraw
        ax.figure.canvas.draw()

    def toggle_3d_animation_pause(self):
        """Toggle pause/resume for both 2D and 3D animations."""
        # Check which timer is currently active
        active_timer = None
        if hasattr(self, "animation_timer_3d") and self.animation_timer_3d is not None:
            active_timer = self.animation_timer_3d
        elif hasattr(self, "animation_timer_2d") and self.animation_timer_2d is not None:
            active_timer = self.animation_timer_2d

        if active_timer is None:
            return

        if self.animation_paused:
            active_timer.start()
            self.pause_3d_button.setText("Pause")
            self.animation_paused = False
        else:
            active_timer.stop()
            self.pause_3d_button.setText("Resume")
            self.animation_paused = True

    def toggle_gcode_points_3d(self):
        """Toggle showing/hiding G-code points for 3D mode."""
        self.show_gcode_points = not self.show_gcode_points

        if self.show_gcode_points:
            self.show_gcode_points_button.setText("Hide G-Code Points")
        else:
            self.show_gcode_points_button.setText("Show G-Code Points")

        # Update the current display without restarting animation
        self.update_gcode_points_display()

    def stop_animation(self):
        """Stop the current animation."""
        if hasattr(self, "cutting_animation") and self.cutting_animation is not None and hasattr(self.cutting_animation, "event_source"):
            self.cutting_animation.event_source.stop()
            self.cutting_animation = None

        # Reset pause state and frame tracking
        self.animation_paused = False
        self.animation_frame = 0
        self.pause_3d_button.setText("Pause")
        self.pause_3d_button.setEnabled(False)

        # Re-enable animate button
        self.animate_3d_button.setEnabled(True)

    def set_custom_arc_points(self, entity_id, points):
        """Set custom number of points for an arc entity."""
        self.custom_arc_points[entity_id] = points

        # Update both left and right entities with same ID to maintain symmetry
        # This ensures the same number of points for corresponding entities
        if entity_id < len(self.left_profile_entities) and entity_id < len(self.right_profile_entities):
            # Re-extract points for both entities with new point count
            try:
                # This would need to be implemented in the entity extraction logic
                # For now, store the setting and apply during next path generation
                pass
            except Exception as e:
                print(f"Error updating arc points for entity {entity_id}: {e}")

    def on_display_units_changed_3d(self):
        """Handle display units change for 3D mode."""
        is_inches = self.display_inch_radio_3d.isChecked()
        new_units = "inch" if is_inches else "mm"

        # Check if units actually changed to prevent recursive conversion
        if new_units == self.current_units_3d:
            return

        # Update input field values with unit conversion
        try:
            current_gantry = float(self.gantry_gap_edit.text())
            current_y_offset = float(self.y_offset_3d_edit.text())

            if is_inches and self.current_units_3d == "mm":
                # Converting from mm to inches
                self.gantry_gap_edit.setText(f"{current_gantry / 25.4:.3f}")
                self.y_offset_3d_edit.setText(f"{current_y_offset / 25.4:.3f}")
            elif not is_inches and self.current_units_3d == "inch":
                # Converting from inches to mm
                self.gantry_gap_edit.setText(f"{current_gantry * 25.4:.3f}")
                self.y_offset_3d_edit.setText(f"{current_y_offset * 25.4:.3f}")
        except (ValueError, AttributeError):
            # If conversion fails, set default values
            if is_inches:
                self.gantry_gap_edit.setText("36.378")
                self.y_offset_3d_edit.setText("0.000")
            else:
                self.gantry_gap_edit.setText("924.000")
                self.y_offset_3d_edit.setText("0.000")

        # Update current units tracking
        self.current_units_3d = new_units

        # Update unit labels
        unit_text = "inch" if is_inches else "mm"
        if hasattr(self, "gantry_gap_label"):
            self.gantry_gap_label.setText(f"Gantry Gap ({unit_text}):")
        if hasattr(self, "y_offset_3d_label"):
            self.y_offset_3d_label.setText(f"Y-Offset ({unit_text}):")

        # Update the plot with new units
        if hasattr(self, "left_profile_entities") and self.left_profile_entities:
            self.plot_3d_profiles()

        # Restart animation with new units if animation is active
        if hasattr(self, "current_cutting_paths") and self.current_cutting_paths:
            # Stop current animation
            if hasattr(self, "animation_timer_2d") and self.animation_timer_2d is not None:
                self.animation_timer_2d.stop()
                self.animation_timer_2d = None
            if hasattr(self, "animation_timer_3d") and self.animation_timer_3d is not None:
                self.animation_timer_3d.stop()
                self.animation_timer_3d = None

            # Restart animation with new units
            self.animate_path_3d()

    def on_arc_points_changed(self):
        """Handle arc points input change."""
        try:
            points = int(self.arc_points_edit.text())
            if points < 2:
                points = 2
            elif points > 100:
                points = 100

            # Apply to all entities - this ensures symmetry
            for i in range(max(len(self.left_profile_entities), len(self.right_profile_entities))):
                self.set_custom_arc_points(i, points)

        except ValueError:
            # Invalid input, ignore
            pass

    def update_3d_animation_qtimer(self):
        """Update 3D animation using QTimer approach like 2D app."""
        if not hasattr(self, "animation_3d_params") or not self.animation_3d_params:
            return

        # Check if animation completed - restart if so
        # Use distance-based completion instead of frame-based
        if hasattr(self, "animation_completed_3d") and self.animation_completed_3d:
            self.animate_frame_3d = 0  # Restart animation
            self.animation_completed_3d = False

        cutting_paths = self.animation_3d_params["cutting_paths"]
        ax = self.animation_3d_params["ax"]
        speed = self.animation_3d_params["speed"]
        left_plane_y = self.animation_3d_params["left_plane_y"]
        right_plane_y = self.animation_3d_params["right_plane_y"]

        if not cutting_paths:
            return

        # Flatten all paths into single array
        all_points = np.vstack([path for path in cutting_paths if len(path) > 0])
        if len(all_points) == 0:
            return

        # Calculate current position based on frame
        fps = 30
        time = self.animate_frame_3d / fps
        distance = time * speed

        # Calculate cumulative distances if not done yet
        if not hasattr(self, "cumulative_distances_3d") or self.cumulative_distances_3d is None:
            segment_vectors = all_points[1:] - all_points[:-1]
            segment_lengths = np.linalg.norm(segment_vectors, axis=1)
            self.cumulative_distances_3d = np.cumsum(np.insert(segment_lengths, 0, 0))

        total_length = self.cumulative_distances_3d[-1]
        if total_length <= 0:
            return

        # Check if animation completed
        if distance >= total_length:
            self.animation_completed_3d = True
            distance = total_length - 0.001  # Set to just before the end
        else:
            self.animation_completed_3d = False

        # Find current position
        segment_idx = np.searchsorted(self.cumulative_distances_3d, distance, side="right") - 1
        segment_idx = max(0, min(segment_idx, len(all_points) - 2))

        # Calculate position within segment
        segment_start_dist = self.cumulative_distances_3d[segment_idx]
        segment_length = self.cumulative_distances_3d[segment_idx + 1] - segment_start_dist

        if segment_length > 0:
            segment_progress = (distance - segment_start_dist) / segment_length
        else:
            segment_progress = 0

        # Interpolate current position
        current_point = all_points[segment_idx] + segment_progress * (all_points[segment_idx + 1] - all_points[segment_idx])

        # Apply unit conversion if needed
        unit_conversion = 1 / 25.4 if (hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()) else 1.0
        current_point_display = current_point * unit_conversion

        # Extract XY and AZ positions
        xy_pos = current_point_display[:2]
        az_pos = current_point_display[2:]

        # Apply unit conversion to plane positions as well
        left_plane_y_display = left_plane_y  # * unit_conversion
        right_plane_y_display = right_plane_y  # * unit_conversion

        # Update gantry positions
        if hasattr(self, "left_gantry_3d") and hasattr(self, "right_gantry_3d"):
            self.left_gantry_3d._offsets3d = ([xy_pos[0]], [left_plane_y_display], [xy_pos[1]])
            self.right_gantry_3d._offsets3d = ([az_pos[0]], [right_plane_y_display], [az_pos[1]])

        # Update hot wire
        if hasattr(self, "hot_wire_3d"):
            self.hot_wire_3d.set_data([xy_pos[0], az_pos[0]], [left_plane_y_display, right_plane_y_display])
            self.hot_wire_3d.set_3d_properties([xy_pos[1], az_pos[1]])

        # Update traveled paths
        if hasattr(self, "left_traveled_3d") and hasattr(self, "right_traveled_3d"):
            # Get all points up to current position
            traveled_points = all_points[: segment_idx + 1] * unit_conversion
            if len(traveled_points) > 0:
                # Add current interpolated point
                traveled_points = np.vstack([traveled_points, current_point_display])

                # Update left path
                left_x = traveled_points[:, 0]
                left_y = [left_plane_y_display] * len(traveled_points)
                left_z = traveled_points[:, 1]
                self.left_traveled_3d.set_data(left_x, left_y)
                self.left_traveled_3d.set_3d_properties(left_z)

                # Update right path
                right_x = traveled_points[:, 2]
                right_y = [right_plane_y_display] * len(traveled_points)
                right_z = traveled_points[:, 3]
                self.right_traveled_3d.set_data(right_x, right_y)
                self.right_traveled_3d.set_3d_properties(right_z)

        self.animate_frame_3d += 1
        ax.figure.canvas.draw()

        # Update gantry positions (3D scatter)
        self.left_gantry_3d._offsets3d = ([xy_pos[0]], [left_plane_y], [xy_pos[1]])
        self.right_gantry_3d._offsets3d = ([az_pos[0]], [right_plane_y], [az_pos[1]])

        # Update hot wire position (3D line) - RED color as requested
        self.hot_wire_3d.set_data([xy_pos[0], az_pos[0]], [left_plane_y, right_plane_y])
        self.hot_wire_3d.set_3d_properties([xy_pos[1], az_pos[1]])

        # Collect all points up to the current position for the traveled path
        # Use all points up to current segment + interpolated position
        traveled_points = all_points[: segment_idx + 1].copy() * unit_conversion
        if len(traveled_points) > 0:
            # Add current interpolated position
            traveled_points = np.vstack([traveled_points, current_point_display])

            # Split into left and right gantry positions
            left_x_points = traveled_points[:, 0]
            left_y_points = np.full(len(traveled_points), left_plane_y)
            left_z_points = traveled_points[:, 1]

            right_x_points = traveled_points[:, 2]
            right_y_points = np.full(len(traveled_points), right_plane_y)
            right_z_points = traveled_points[:, 3]

            # Update the traveled paths
            self.left_traveled_3d.set_data(left_x_points, left_y_points)
            self.left_traveled_3d.set_3d_properties(left_z_points)

            self.right_traveled_3d.set_data(right_x_points, right_y_points)
            self.right_traveled_3d.set_3d_properties(right_z_points)

        # No progress text to update

        return []

    def init_3d_animation_elements(self, ax, cutting_paths, colors, gantry_gap, tool_size):
        """Initialize 3D animation elements."""
        # Plot static profile entities
        for i, entity in enumerate(self.left_profile_entities):
            if len(entity) > 1:
                points = np.array(entity)
                ax.plot(points[:, 0], points[:, 1], points[:, 2], color=colors["left_entities"], alpha=0.3, linewidth=1)

        for i, entity in enumerate(self.right_profile_entities):
            if len(entity) > 1:
                points = np.array(entity)
                ax.plot(points[:, 0], points[:, 1], points[:, 2], color=colors["right_entities"], alpha=0.3, linewidth=1)

        # Initialize moving elements
        (self.xy_gantry,) = ax.plot([], [], [], "o", color=colors["left_path"], markersize=tool_size, label="XY Gantry")
        (self.az_gantry,) = ax.plot([], [], [], "o", color=colors["right_path"], markersize=tool_size, label="AZ Gantry")
        (self.hot_wire_line,) = ax.plot([], [], [], color=colors["hot_wire"], linewidth=3, label="Hot Wire")
        (self.completed_path_left,) = ax.plot([], [], [], color=colors["completed_left"], linewidth=2, alpha=0.7)
        (self.completed_path_right,) = ax.plot([], [], [], color=colors["completed_right"], linewidth=2, alpha=0.7)

        # Set up the plot
        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
        ax.set_zlabel("Z (mm)")
        ax.set_title("3D Hot Wire Cutting Animation")
        ax.legend()

        # Force initial redraw
        ax.figure.canvas.draw()
        ax.figure.canvas.flush_events()

        # Store paths for animation
        self.current_cutting_paths = cutting_paths
        self.current_frame = 0

    def plot_2d_projection_animation(self, cutting_paths, ax):
        """Create 2D animation identical to the notebook's animate_dual_gantry_path."""
        # Stop any existing animation
        try:
            if hasattr(self, "cutting_animation") and self.cutting_animation is not None and hasattr(self.cutting_animation, "event_source") and self.cutting_animation.event_source is not None:
                self.cutting_animation.event_source.stop()
        except Exception:
            pass
        self.cutting_animation = None

        # Start the 2D dual gantry animation
        self.animate_dual_gantry_path_2d(cutting_paths, ax)

    def show_wire_length_plot(self):
        """Show wire length analysis dialog."""
        cutting_paths = self.generate_cutting_path_3d()
        if not cutting_paths:
            QMessageBox.warning(self, "No Path", "No 3D cutting path available for analysis.")
            return

        wire_lengths = self.calculate_hotwire_lengths(cutting_paths)
        if wire_lengths is None or len(wire_lengths) == 0:
            QMessageBox.warning(self, "No Data", "No wire length data available.")
            return

        # Create and show wire length dialog
        dialog = WireLengthDialog(self)
        dialog.plot_wire_lengths(wire_lengths)
        dialog.show()

    def generate_cutting_path_3d(self):
        """Generate 3D cutting paths from the sequence."""
        if not self.left_profile_entities or not self.right_profile_entities:
            return []

        # Check if entity counts match
        if len(self.left_sequence_order) != len(self.right_sequence_order):
            QMessageBox.warning(self, "Entity Count Mismatch", f"Entity count mismatch: Left {len(self.left_sequence_order)}, Right {len(self.right_sequence_order)}\n\nThe number of entities in left and right sequences must be the same.")
            return []

        try:
            gantry_gap = float(self.gantry_gap_edit.text())
            y_offset_input = float(self.y_offset_3d_edit.text())
            # Convert gantry gap and y-offset from display units to millimeters for consistent calculations
            is_inches = hasattr(self, "display_inch_radio_3d") and self.display_inch_radio_3d.isChecked()
            if is_inches:
                gantry_gap = gantry_gap * 25.4  # Convert inches to mm
                y_offset_input = y_offset_input * 25.4  # Convert inches to mm
        except (ValueError, AttributeError):
            gantry_gap = 924.0
            y_offset_input = 0.0

        # Calculate y_offset like in notebook (center the entities)
        all_points = []
        for entity in self.left_profile_entities + self.right_profile_entities:
            all_points.extend(entity)

        if all_points:
            all_points = np.array(all_points)
            y_offset = (np.max(all_points[:, 1]) + np.min(all_points[:, 1])) / 2
        else:
            y_offset = y_offset_input

        # Create combined entities list like in notebook
        entities = self.left_profile_entities + self.right_profile_entities

        # Adjust indices for the combined list
        adjusted_left_indices = []
        adjusted_right_indices = []

        for left_idx in self.left_sequence_order:
            if isinstance(left_idx, int) and left_idx < len(self.left_profile_entities):
                adjusted_left_indices.append(left_idx)  # Left entities start at index 0
            else:
                adjusted_left_indices.append(left_idx)  # Keep lead-in/out entries as-is

        for right_idx in self.right_sequence_order:
            if isinstance(right_idx, int) and right_idx < len(self.right_profile_entities):
                adjusted_right_indices.append(right_idx + len(self.left_profile_entities))  # Right entities offset by left count
            else:
                adjusted_right_indices.append(right_idx)  # Keep lead-in/out entries as-is

        # Generate paths from sequences
        cutting_paths = self.generate_hotcutting_paths(entities, adjusted_left_indices, adjusted_right_indices, gantry_gap, y_offset)

        return cutting_paths

    def get_directions_for_sequences(self, left_entity_indices, right_entity_indices):
        """Get direction array based on stored custom directions.

        Returns:
            list: Direction values for each entity pair:
                  0 = auto (minimize travel distance)
                  1 = increasing x (left to right)
                  -1 = decreasing x (right to left)
                  2 = increasing z (bottom to top)
                  -2 = decreasing z (top to bottom)
        """
        directions = [0] * len(left_entity_indices)  # Default to auto for all paths

        # Apply custom directions based on stored settings
        for i in range(len(directions)):
            # Check both left and right sequence lists for custom directions
            left_key = f"left_{i}"
            right_key = f"right_{i}"

            # Use custom direction if set, otherwise keep default (0 = auto)
            if left_key in self.custom_directions:
                directions[i] = self.custom_directions[left_key]
            elif right_key in self.custom_directions:
                directions[i] = self.custom_directions[right_key]

        print(f"Direction settings: {directions}")
        return directions

    def generate_hotcutting_paths(self, entities, left_entity_indices, right_entity_indices, gantry_gap, y_offset=0):
        """
        Generate hot wire cutting paths for the gantry based on left and right entities.
        Exactly matching the notebook implementation.
        """
        if len(left_entity_indices) != len(right_entity_indices):
            raise ValueError(f"Entity count mismatch: Left {len(left_entity_indices)}, Right {len(right_entity_indices)}")

        cutting_paths = []
        last_end_positions = None

        # Get direction settings from UI

        # Get direction settings from UI
        directions = self.get_directions_for_sequences(left_entity_indices, right_entity_indices)

        for i, (left_entity_id, right_entity_id) in enumerate(zip(left_entity_indices, right_entity_indices)):
            # Handle lead-in/out entries which are dicts with type and distance
            if isinstance(left_entity_id, dict) and left_entity_id.get("type") in ["leadin", "leadout"]:
                # Add placeholder for lead-in/out entries - will be processed in entry/exit section
                cutting_paths.append(np.array([[0, 0, 0, 0]]))
                continue

            # Handle numeric entity IDs
            if not isinstance(left_entity_id, int) or not isinstance(right_entity_id, int):
                continue

            # Skip empty entities
            left_entity = entities[left_entity_id]
            right_entity = entities[right_entity_id]
            if not left_entity or not right_entity:
                raise ValueError(f"Empty entity found: Left {left_entity_id}, Right {right_entity_id}")

            # Center y coordinates
            left_points = np.array(left_entity)
            right_points = np.array(right_entity)

            left_points[:, 1] -= y_offset
            right_points[:, 1] -= y_offset

            # Resample to ensure both entities have the same number of points
            resampled_left, resampled_right = self.resample_entities_notebook(left_points, right_points)

            # Determine cutting direction
            if directions[i] == 1:
                # increasing x
                if resampled_left[0][0] > resampled_left[-1][0]:
                    resampled_left = resampled_left[::-1]
                if resampled_right[0][0] > resampled_right[-1][0]:
                    resampled_right = resampled_right[::-1]
            elif directions[i] == -1:
                # decreasing x
                if resampled_left[0][0] < resampled_left[-1][0]:
                    resampled_left = resampled_left[::-1]
                if resampled_right[0][0] < resampled_right[-1][0]:
                    resampled_right = resampled_right[::-1]
            elif directions[i] == 2:
                # increasing z
                if resampled_left[0][2] > resampled_left[-1][2]:
                    resampled_left = resampled_left[::-1]
                if resampled_right[0][2] > resampled_right[-1][2]:
                    resampled_right = resampled_right[::-1]
            elif directions[i] == -2:
                # decreasing z
                if resampled_left[0][2] < resampled_left[-1][2]:
                    resampled_left = resampled_left[::-1]
                if resampled_right[0][2] < resampled_right[-1][2]:
                    resampled_right = resampled_right[::-1]
            elif directions[i] == 0:
                # choose direction that minimizes travel distance
                if last_end_positions is not None:
                    last_left, last_right = last_end_positions[0], last_end_positions[1]
                    # Calculate distances to both potential starting points
                    start_dist = np.linalg.norm(last_left - resampled_left[0]) + np.linalg.norm(last_right - resampled_right[0])
                    end_dist = np.linalg.norm(last_left - resampled_left[-1]) + np.linalg.norm(last_right - resampled_right[-1])

                    if end_dist < start_dist:
                        # Reverse direction if the end is closer
                        resampled_left = resampled_left[::-1]
                        resampled_right = resampled_right[::-1]

            # Calculate gantry positions for this entity pair
            gantry_positions = self.calculate_gantry_positions_notebook(resampled_left, resampled_right, gantry_gap)

            cutting_paths.append(gantry_positions)

            last_end_positions = [resampled_left[-1], resampled_right[-1]]

        # Process entry and exit points for lead-in/out entries
        for i, (left_entity_id, right_entity_id) in enumerate(zip(left_entity_indices, right_entity_indices)):
            # Check if both sides are lead-in/out entries with same type
            if isinstance(left_entity_id, dict) and isinstance(right_entity_id, dict) and left_entity_id.get("type") == right_entity_id.get("type") and left_entity_id.get("type") in ["leadin", "leadout"]:
                lead_type = left_entity_id["type"]
                left_distance = left_entity_id["distance"]
                right_distance = right_entity_id["distance"]

                if lead_type == "leadin":
                    # Entry point - create path from offset position to next cutting point
                    if i + 1 < len(cutting_paths) and len(cutting_paths[i + 1]) > 0:
                        next_point = cutting_paths[i + 1][0]
                        # Use custom distances from the lead-in entries
                        entry_point = np.array([next_point[0] - left_distance[0], next_point[1] - left_distance[1], next_point[2] - right_distance[0], next_point[3] - right_distance[1]])
                        cutting_paths[i] = np.array([entry_point, next_point])
                        print(f"Added entry point with distances Left:{left_distance}, Right:{right_distance}")

                elif lead_type == "leadout":
                    # Exit point - create path from previous cutting point to offset position
                    if i - 1 >= 0 and len(cutting_paths[i - 1]) > 0:
                        prev_point = cutting_paths[i - 1][-1]
                        # Use custom distances from the lead-out entries
                        exit_point = np.array([prev_point[0] + left_distance[0], prev_point[1] + left_distance[1], prev_point[2] + right_distance[0], prev_point[3] + right_distance[1]])
                        cutting_paths[i] = np.array([prev_point, exit_point])
                        print(f"Added exit point with distances Left:{left_distance}, Right:{right_distance}")

        return cutting_paths

    def resample_entities_notebook(self, left_points, right_points):
        """Resample entities to have the same number of points"""
        # Choose the higher point count for better accuracy
        target_points = max(len(left_points), len(right_points))

        # Resample both entities to the target point count
        resampled_left = self.resample_curve_notebook(left_points, target_points)
        resampled_right = self.resample_curve_notebook(right_points, target_points)

        return resampled_left, resampled_right

    def resample_curve_notebook(self, points, num_points):
        """Resample a curve to have a specific number of points"""
        # If we already have the correct number, return as is
        if len(points) == num_points:
            return points

        # Calculate cumulative distances along the curve
        dists = np.zeros(len(points))
        for i in range(1, len(points)):
            segment = points[i] - points[i - 1]
            dists[i] = dists[i - 1] + np.linalg.norm(segment)

        # Create new parameterization
        new_dists = np.linspace(0, dists[-1], num_points)

        # Interpolate points along the curve
        resampled_points = np.zeros((num_points, points.shape[1]))

        for i in range(points.shape[1]):  # For each dimension (x, y, z)
            resampled_points[:, i] = np.interp(new_dists, dists, points[:, i])

        return resampled_points

    def calculate_gantry_positions_notebook(self, left_points, right_points, gantry_gap):
        """
        Calculate XY and AZ gantry positions where the wire intersects the gantry planes.
        Exactly matching the notebook implementation.
        """
        gantry_positions = []

        # Define the y-coordinates of the gantry planes
        left_plane_y = -gantry_gap / 2
        right_plane_y = gantry_gap / 2

        for left_pt, right_pt in zip(left_points, right_points):
            # Calculate the 3D line equation passing through both points
            # Line equation: P = P0 + t * (P1 - P0)
            direction = right_pt - left_pt

            # Check if the line is parallel to the gantry planes
            if abs(direction[1]) < 1e-6:  # Near-zero y component
                # If parallel, use the original points' x and z coordinates
                xy_pos = (left_pt[0], left_plane_y, left_pt[2])
                az_pos = (right_pt[0], right_plane_y, right_pt[2])
            else:
                # Calculate t for the left gantry plane intersection
                t_left = (left_plane_y - left_pt[1]) / direction[1]
                # Calculate the intersection point
                xy_pos = left_pt + t_left * direction

                # Calculate t for the right gantry plane intersection
                t_right = (right_plane_y - left_pt[1]) / direction[1]
                # Calculate the intersection point
                az_pos = left_pt + t_right * direction

            # Format as XYAZ coordinates (X, Y from XY gantry, A, Z from AZ gantry)
            xyaz = np.array([xy_pos[0], xy_pos[2], az_pos[0], az_pos[2]])
            gantry_positions.append(xyaz)

        gantry_positions = np.array(gantry_positions)
        return gantry_positions

    def calculate_hotwire_lengths(self, cutting_paths):
        """Calculate the wire length at each step of the cutting path. Exact notebook implementation."""
        lengths = []

        # Get gantry gap from UI
        try:
            gantry_gap = float(self.gantry_gap_edit.text())
        except (ValueError, AttributeError):
            gantry_gap = 924.0

        for path in cutting_paths:
            for step in path:
                # Calculate the distance between the left and right points
                left_point = np.array([step[0], -gantry_gap / 2, step[1]])
                right_point = np.array([step[2], gantry_gap / 2, step[3]])

                # Calculate Euclidean distance (wire length)
                wire_length = np.linalg.norm(right_point - left_point)
                lengths.append(wire_length)

        return np.array(lengths)

    def generate_and_save_gcode_3d(self):
        """Generate and save 3D G-code."""
        cutting_paths = self.generate_cutting_path_3d()
        if not cutting_paths:
            QMessageBox.warning(self, "No Path", "No 3D cutting path to generate. Please configure the cutting sequence.")
            return

        try:
            feed_rate = 200.0  # Default feed rate for 3D
            wire_current = 1000  # Default wire current
        except (ValueError, AttributeError):
            feed_rate = 200.0
            wire_current = 1000

        # Generate 3D G-code
        gcode = self.generate_gcode_3d(cutting_paths, feed_rate, wire_current)

        # Save to file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save G-code", f"{self.loaded_filename.rsplit('.', 1)[0]}_3d.ngc", "G-code Files (*.ngc *.gcode);;All Files (*)")

        if file_path:
            try:
                with open(file_path, "w") as f:
                    f.write(gcode)
                total_points = sum(len(path) for path in cutting_paths)
                QMessageBox.information(self, "G-code Saved", f"3D G-code saved successfully to {file_path}\n\nTotal paths: {len(cutting_paths)}\nTotal points: {total_points}")
            except Exception as e:
                QMessageBox.critical(self, "Error Saving G-code", f"Failed to save G-code: {str(e)}")

    def generate_gcode_3d(self, cutting_paths, feed_rate=200.0, wire_current=1000):
        """Generate G-code from a list of points. Exact notebook implementation."""
        cutting_paths_flat = np.concatenate(cutting_paths, axis=0)

        gcode = []

        # Header
        gcode.append("; Generated G-code for 4-axis hot wire cutter")
        gcode.append("; 2D profile cutting mode - left and right sides move together")
        gcode.append("")
        gcode.append("G17 ; XY plane")
        gcode.append("G21 ; Set units to millimeters")
        gcode.append("G90 ; Use absolute positioning")
        gcode.append("G40 ; Cutter compensation off")
        gcode.append("G49 ; Tool length offset compensation off")
        gcode.append("G64 ; Path Control Mode - Continuous mode")
        gcode.append("G94 ; Set feed rate")
        gcode.append(f"G{feed_rate} ; mm/min")
        gcode.append(f"M3 S{wire_current} ; Set wire current")
        gcode.append("G4 P2 ; Wait 2 seconds for wire to heat up")
        gcode.append("")

        # Move to the first point (rapid positioning)
        first_point = cutting_paths_flat[0]
        gcode.append(f"G0 X{first_point[0]:.3f} Y{first_point[1]:.3f} A{first_point[2]:.3f} Z{first_point[3]:.3f}; Rapid move to start position")

        # Add points for cutting (linear interpolation)
        for point in cutting_paths_flat[1:]:
            gcode.append(f"G1 X{point[0]:.3f} Y{point[1]:.3f} A{point[2]:.3f} Z{point[3]:.3f}")

        # Footer
        gcode.append("")
        gcode.append("M5 ; Turn off wire heater")
        gcode.append("M2 ; End program")

        return "\n".join(gcode)

    def write_gcode_file(self, gcode, output_file):
        """Write G-code to file. Exact notebook implementation."""
        try:
            with open(output_file, "w") as f:
                for line in gcode.split("\n"):
                    f.write(line + "\n")
            print(f"G-code successfully written to: {output_file}")
            return True
        except Exception as e:
            print(f"Error writing G-code file: {e}")
            return False

    def update_gcode_points_display(self):
        """Update G-code points visibility without restarting animation."""
        # Update for 3D animation
        if hasattr(self, "gcode_point_plots_3d"):
            for plot in self.gcode_point_plots_3d:
                if hasattr(plot, "set_visible"):
                    plot.set_visible(self.show_gcode_points)

        # Update for 2D animation
        if hasattr(self, "gcode_point_plots_2d"):
            for plot in self.gcode_point_plots_2d:
                if hasattr(plot, "set_visible"):
                    plot.set_visible(self.show_gcode_points)

        # Redraw the appropriate canvas
        if hasattr(self, "view_3d_radio") and self.view_3d_radio.isChecked():
            if hasattr(self, "animation_canvas_3d"):
                self.animation_canvas_3d.draw()
        else:
            if hasattr(self, "animation_canvas"):
                self.animation_canvas.draw()
