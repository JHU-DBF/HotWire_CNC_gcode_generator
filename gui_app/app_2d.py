#!/usr/bin/env python3
"""
App2DMixin - 2D-specific functionality for the Hot Wire CNC G-code Generator.

This module contains all 2D-related functionality including:
- DXF file processing and entity handling
- 2D visualization and entity selection
- 2D animation and path generation
- G-code generation for 2D profiles
"""

import math
import numpy as np
import matplotlib.pyplot as plt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QListWidget, QRadioButton, QAbstractItemView, QMessageBox, QFileDialog, QDialog, QFormLayout, QSpinBox, QDialogButtonBox
from PySide6.QtCore import QTimer

from constants import DEFAULT_ANIMATION_SPEED, DEFAULT_MAX_SEGMENT_LENGTH, DEFAULT_SCALE_FACTOR, DEFAULT_OFFSET, STATIC_DOTS_SIZE, STATIC_DOTS_ALPHA
import ezdxf


class App2DMixin:
    """Mixin class with 2D-specific functionality."""

    def __init__(self):
        # 2D mode data storage
        self.entities = []
        self.cutting_order = []
        self.entity_colors = {}
        self.entity_centers = {}  # Store entity center points for selection
        self.points = None
        self.animation = None
        self.custom_entity_params = {}  # Store custom parameters for entities
        self.static_colorbar = None  # Track colorbar for static plots
        self.animation_zoom_controls = None  # Track animation zoom controls
        self.show_static_dots = True  # Track if static dots are shown on animation
        self.static_dots_plot = None  # Track static dots plot object

        # Direction control system (from notebook)
        self.directions = []  # Will be set based on sequence

        # 2D Animation state
        self.animation_timer = None
        self.animation_paused = False
        self.animate_frame = 0
        self.total_frames = 0
        self.cumulative_distances = None
        self.tool = None
        self.traveled_line = None

    def create_2d_control_panel(self):
        """Create the 2D mode control panel."""
        panel_2d = QWidget()
        control_layout = QVBoxLayout(panel_2d)
        control_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins

        # Cutting Order
        order_group = QGroupBox("Cutting Sequence")
        order_layout = QVBoxLayout(order_group)

        order_layout.addWidget(QLabel("Click entities on the plot to add them."))

        self.cutting_list = QListWidget()
        self.cutting_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.cutting_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Enable multi-select
        self.cutting_list.setMinimumHeight(200)  # Minimum height
        self.cutting_list.setMaximumHeight(400)  # Maximum height to allow scrolling
        self.cutting_list.itemDoubleClicked.connect(self.customize_entity_parameters)
        self.cutting_list.model().rowsMoved.connect(self.on_cutting_order_changed)  # Track drag/drop changes
        order_layout.addWidget(self.cutting_list)

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self.remove_selected_entity)
        order_layout.addWidget(self.remove_button)

        # First path direction controls
        direction_group = QGroupBox("First Path Direction")
        direction_layout = QHBoxLayout(direction_group)
        self.right_to_left_radio = QRadioButton("Right to Left ←")
        self.left_to_right_radio = QRadioButton("Left to Right →")
        self.left_to_right_radio.setChecked(True)  # Default to left-to-right
        direction_layout.addWidget(self.left_to_right_radio)
        direction_layout.addWidget(self.right_to_left_radio)
        order_layout.addWidget(direction_group)

        control_layout.addWidget(order_group)

        # Geometry & Transformation Parameters
        geo_group = QGroupBox("Geometry & Transformation")
        geo_layout = QVBoxLayout(geo_group)

        # Display Units
        display_units_group = QGroupBox("Display Units")
        display_units_layout = QHBoxLayout(display_units_group)
        self.display_mm_radio = QRadioButton("mm")
        self.display_inch_radio = QRadioButton("inch")
        self.display_mm_radio.setChecked(True)
        display_units_layout.addWidget(self.display_mm_radio)
        display_units_layout.addWidget(self.display_inch_radio)
        geo_layout.addWidget(display_units_group)

        # Scale Factor
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale Factor:"))
        self.scale_factor_edit = QLineEdit()
        scale_layout.addWidget(self.scale_factor_edit)
        geo_layout.addLayout(scale_layout)

        # X Offset
        x_offset_layout = QHBoxLayout()
        x_offset_layout.addWidget(QLabel("X Offset:"))
        self.x_offset_edit = QLineEdit()
        x_offset_layout.addWidget(self.x_offset_edit)
        geo_layout.addLayout(x_offset_layout)

        # Y Offset
        y_offset_layout = QHBoxLayout()
        y_offset_layout.addWidget(QLabel("Y Offset:"))
        self.y_offset_edit = QLineEdit()
        y_offset_layout.addWidget(self.y_offset_edit)
        geo_layout.addLayout(y_offset_layout)

        # Max Segment Length
        segment_layout = QHBoxLayout()
        segment_layout.addWidget(QLabel("Max Segment Length:"))
        self.max_segment_length_edit = QLineEdit()
        segment_layout.addWidget(self.max_segment_length_edit)
        geo_layout.addLayout(segment_layout)

        control_layout.addWidget(geo_group)

        # G-Code Parameters
        gcode_group = QGroupBox("G-Code Parameters")
        gcode_layout = QVBoxLayout(gcode_group)

        # Feed Rate
        feed_layout = QHBoxLayout()
        feed_layout.addWidget(QLabel("Feed Rate (mm/min):"))
        self.feed_rate_edit = QLineEdit()
        feed_layout.addWidget(self.feed_rate_edit)
        gcode_layout.addLayout(feed_layout)

        control_layout.addWidget(gcode_group)

        # Action Buttons
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)

        # Animation Speed for Animation (moved here from G-code section)
        speed_layout = QHBoxLayout()
        self.animation_speed_label = QLabel("Animation Speed (mm/s):")
        speed_layout.addWidget(self.animation_speed_label)
        self.animation_speed_edit = QLineEdit()
        speed_layout.addWidget(self.animation_speed_edit)
        action_layout.addLayout(speed_layout)

        # First row - Generate and View Tool Path (full width)
        first_row_layout = QHBoxLayout()
        self.animate_button = QPushButton("Generate and View Tool Path")
        self.animate_button.clicked.connect(self.animate_path)
        first_row_layout.addWidget(self.animate_button)
        action_layout.addLayout(first_row_layout)

        # Second row - Pause, Hide G-Code Points, Save G-Code
        second_row_layout = QHBoxLayout()
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_animation_pause)
        self.pause_button.setEnabled(False)
        second_row_layout.addWidget(self.pause_button)

        self.static_plot_button = QPushButton("Hide G-Code Points")
        self.static_plot_button.clicked.connect(self.toggle_static_dots)
        second_row_layout.addWidget(self.static_plot_button)

        self.generate_button = QPushButton("Save G-Code")
        self.generate_button.clicked.connect(self.generate_and_save_gcode)
        second_row_layout.addWidget(self.generate_button)

        action_layout.addLayout(second_row_layout)

        control_layout.addWidget(action_group)

        # Add stretch to push everything to top
        control_layout.addStretch()

        # Connect display units radio buttons
        self.display_inch_radio.toggled.connect(self.on_display_units_changed)

        # Set default values after UI elements are created
        QTimer.singleShot(0, self.set_default_2d_values)

        return panel_2d

    def switch_to_2d_mode(self):
        """Switch UI to 2D mode."""
        self.is_3d_mode = False
        self.selection_label.setText("DXF Entity Selection")
        self.selection_stack.setCurrentIndex(0)  # Show 2D selection canvas
        if hasattr(self, "control_stack"):
            self.control_stack.setCurrentIndex(0)  # Show 2D control panel
        print("Switched to 2D mode")

    def get_dxf_units_to_mm(self, units_code):
        """Convert DXF units code to millimeter conversion factor."""
        units_mapping = {
            0: 1.0,  # Unitless
            1: 25.4,  # Inches
            2: 304.8,  # Feet
            3: 1609344.0,  # Miles
            4: 1.0,  # Millimeters
            5: 10.0,  # Centimeters
            6: 1000.0,  # Meters
            7: 1000000.0,  # Kilometers
            8: 25.4 / 1000,  # Microinches
            9: 25.4 / 12,  # Mils
            10: 91440.0,  # Yards
            11: 0.1,  # Angstroms
            12: 1e-6,  # Nanometers
            13: 1e-3,  # Microns
            14: 10.0,  # Decimeters
            15: 100.0,  # Decameters
            16: 10000.0,  # Hectometers
            17: 1e9,  # Gigameters
            18: 149597870700000.0,  # Astronomical units
            19: 9.4607304725808e18,  # Light years
            20: 3.0857e16,  # Parsecs
        }
        return units_mapping.get(units_code, 1.0)

    def load_dxf_file_internal(self, file_path):
        """Internal method to load DXF file."""
        # Read DXF file
        doc = ezdxf.readfile(file_path)

        # Detect DXF units
        units_code = 0
        if "$INSUNITS" in doc.header:
            units_code = doc.header["$INSUNITS"]

        self.unit_to_mm = self.get_dxf_units_to_mm(units_code)

        # Get model space
        msp = doc.modelspace()

        # Extract entities
        self.entities = []
        for entity in msp:
            if entity.dxftype() in ["LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "SPLINE"]:
                self.entities.append(entity)

        # Reset cutting order
        self.cutting_order = []
        if hasattr(self, "cutting_list"):
            self.cutting_list.clear()

        # Plot entities
        self.plot_entities()

    def plot_entities(self):
        """Plot DXF entities on the selection canvas."""
        print(f"plot_entities called. Entities count: {len(self.entities) if hasattr(self, 'entities') else 'None'}")

        if not hasattr(self, "entities") or not self.entities:
            print("No entities to plot")
            ax = self.selection_canvas.ax
            ax.clear()
            ax.set_title("No entities loaded")
            self.selection_canvas.draw()
            return

        ax = self.selection_canvas.ax
        ax.clear()
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)

        # Entity colors
        colors = {
            "LINE": "#1f77b4",  # blue
            "ARC": "#ff7f0e",  # orange
            "CIRCLE": "#2ca02c",  # green
            "LWPOLYLINE": "#d62728",  # red
            "POLYLINE": "#9467bd",  # purple
            "SPLINE": "#8c564b",  # brown
        }

        self.entity_centers = {}

        # Calculate unit conversion factor: DXF units -> display units
        dxf_to_mm = getattr(self, "unit_to_mm", 1.0)  # DXF units to mm
        display_is_inches = not self.display_mm_radio.isChecked()
        display_factor = 1.0 / 25.4 if display_is_inches else 1.0  # mm to display units
        unit_factor = dxf_to_mm * display_factor  # DXF units to display units

        print(f"Starting to plot {len(self.entities)} entities")
        print(f"Unit conversion: DXF -> mm: {dxf_to_mm}, mm -> display: {display_factor}, total factor: {unit_factor}")
        for i, entity in enumerate(self.entities):
            entity_type = entity.dxftype()
            color = colors.get(entity_type, "black")
            print(f"Plotting entity {i}: {entity_type}")

            if entity_type == "LINE":
                x1, y1 = entity.dxf.start.x * unit_factor, entity.dxf.start.y * unit_factor
                x2, y2 = entity.dxf.end.x * unit_factor, entity.dxf.end.y * unit_factor
                ax.plot([x1, x2], [y1, y2], color=color, linewidth=2)
                # Store center for clicking
                self.entity_centers[i] = ((x1 + x2) / 2, (y1 + y2) / 2)
                ax.text((x1 + x2) / 2, (y1 + y2) / 2, str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))

            elif entity_type == "ARC":
                center = entity.dxf.center
                radius = entity.dxf.radius
                start_angle = math.radians(entity.dxf.start_angle)
                end_angle = math.radians(entity.dxf.end_angle)

                if end_angle < start_angle:
                    end_angle += 2 * math.pi

                theta = np.linspace(start_angle, end_angle, 100)
                x = (center.x + radius * np.cos(theta)) * unit_factor
                y = (center.y + radius * np.sin(theta)) * unit_factor
                ax.plot(x, y, color=color, linewidth=2)

                # Store center for clicking
                mid_angle = (start_angle + end_angle) / 2
                center_x = (center.x + radius * 0.7 * np.cos(mid_angle)) * unit_factor
                center_y = (center.y + radius * 0.7 * np.sin(mid_angle)) * unit_factor
                self.entity_centers[i] = (center_x, center_y)
                ax.text(center_x, center_y, str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))

            elif entity_type == "CIRCLE":
                center = entity.dxf.center
                radius = entity.dxf.radius
                circle = plt.Circle((center.x * unit_factor, center.y * unit_factor), radius * unit_factor, fill=False, color=color, linewidth=2)
                ax.add_patch(circle)

                # Store center for clicking
                self.entity_centers[i] = (center.x * unit_factor, center.y * unit_factor)
                ax.text(center.x, center.y, str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))

            elif entity_type == "SPLINE":
                try:
                    if hasattr(entity, "construction_tool"):
                        bspline = entity.construction_tool()
                        t_values = np.linspace(0, 1, 100)
                        curve_points = [bspline.point(t) for t in t_values]
                        curve_x = [p[0] * unit_factor for p in curve_points]
                        curve_y = [p[1] * unit_factor for p in curve_points]
                        ax.plot(curve_x, curve_y, color=color, linewidth=2)

                        # Store center for clicking
                        middle_idx = len(curve_x) // 2
                        self.entity_centers[i] = (curve_x[middle_idx], curve_y[middle_idx])
                        ax.text(curve_x[middle_idx], curve_y[middle_idx], str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))
                    elif hasattr(entity, "control_points"):
                        control_points = entity.control_points
                        if control_points:
                            x_coords = [p[0] * unit_factor for p in control_points]
                            y_coords = [p[1] * unit_factor for p in control_points]
                            ax.plot(x_coords, y_coords, color=color, linewidth=2, linestyle="--")

                            # Store center for clicking
                            middle_idx = len(control_points) // 2
                            self.entity_centers[i] = (x_coords[middle_idx], y_coords[middle_idx])
                            ax.text(x_coords[middle_idx], y_coords[middle_idx], str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))
                except Exception as e:
                    print(f"Error plotting SPLINE {i}: {e}")

            elif entity_type in ["LWPOLYLINE", "POLYLINE"]:
                if entity_type == "LWPOLYLINE":
                    vertices = list(entity.vertices())
                    x_coords = [v[0] * unit_factor for v in vertices]
                    y_coords = [v[1] * unit_factor for v in vertices]
                else:
                    vertices = list(entity.vertices())
                    x_coords = [v.dxf.location.x * unit_factor for v in vertices]
                    y_coords = [v.dxf.location.y * unit_factor for v in vertices]

                if x_coords and y_coords:
                    if hasattr(entity, "dxf") and hasattr(entity.dxf, "closed") and entity.dxf.closed:
                        x_coords.append(x_coords[0])
                        y_coords.append(y_coords[0])

                    ax.plot(x_coords, y_coords, color=color, linewidth=2)

                    # Store center for clicking
                    middle_idx = len(x_coords) // 2
                    self.entity_centers[i] = (x_coords[middle_idx], y_coords[middle_idx])
                    ax.text(x_coords[middle_idx], y_coords[middle_idx], str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))

        # Determine display units
        display_unit = "mm" if self.display_mm_radio.isChecked() else "inch"

        title = f"DXF Entities: {len(self.entities)} objects"
        if hasattr(self, "loaded_filename"):
            title += f" - {self.loaded_filename}"

        ax.set_title(title)
        ax.set_xlabel(f"X ({display_unit})")
        ax.set_ylabel(f"Y ({display_unit})")

        # Ensure the plot is scaled properly
        ax.relim()
        ax.autoscale()

        self.selection_canvas.draw()

    def on_entity_click(self, x, y):
        """Handle entity selection by clicking."""
        if not self.entity_centers:
            return

        # Find closest entity center
        min_distance = float("inf")
        closest_entity = None

        for entity_idx, (cx, cy) in self.entity_centers.items():
            distance = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if distance < min_distance:
                min_distance = distance
                closest_entity = entity_idx

        # Add to cutting order if close enough (allow duplicates)
        if closest_entity is not None and min_distance < 1.0:  # Adjust threshold as needed
            self.cutting_order.append(closest_entity)

            # Add to list widget
            entity_type = self.entities[closest_entity].dxftype()
            item_text = f"Entity {closest_entity} ({entity_type})"
            self.cutting_list.addItem(item_text)

            print(f"Added entity {closest_entity} to cutting order (total: {len(self.cutting_order)})")

    def customize_entity_parameters(self, item):
        """Open dialog to customize entity parameters."""
        # Extract entity index from item text
        text = item.text()
        try:
            entity_idx = int(text.split()[1])
        except (IndexError, ValueError):
            return

        if entity_idx >= len(self.entities):
            return

        entity = self.entities[entity_idx]
        entity_type = entity.dxftype()

        # Don't allow customization for LINE entities
        if entity_type == "LINE":
            QMessageBox.information(self, "Info", "LINE entities cannot be customized (they only have 2 points).")
            return

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Customize Entity {entity_idx}")
        dialog.setModal(True)

        layout = QFormLayout(dialog)

        # Custom point count
        points_spinbox = QSpinBox()
        points_spinbox.setRange(0, 1000)  # Allow 0 to reset to default

        # Get current custom value or calculate default
        row = self.cutting_list.row(item)
        custom_key = f"{row}_{entity_idx}"
        current_params = self.custom_entity_params.get(custom_key, {})

        # Get max segment length from UI
        try:
            max_segment_length = float(self.max_segment_length_edit.text())
            # Convert to mm if display is in inches
            if hasattr(self, "display_inch_radio") and self.display_inch_radio.isChecked():
                max_segment_length *= 25.4
        except ValueError:
            max_segment_length = 0.5  # Default

        default_points = self.calculate_default_points(entity, max_segment_length)
        points_spinbox.setValue(current_params.get("num_points", default_points))

        layout.addRow(f"Number of Points for {entity.dxftype()} (0 = default):", points_spinbox)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            num_points = points_spinbox.value()

            if num_points == default_points:
                # Reset to default - remove custom parameters
                if custom_key in self.custom_entity_params:
                    del self.custom_entity_params[custom_key]

                # Reset item text to default
                item_text = f"Entity {entity_idx} ({entity.dxftype()})"
                item.setText(item_text)

                print(f"Reset entity {entity_idx} to default parameters")
            else:
                # Store custom parameters
                self.custom_entity_params[custom_key] = {"num_points": num_points}

                # Update list item text to show customization
                item_text = f"Entity {entity_idx} ({entity.dxftype()}) [Custom: {num_points} pts]"
                item.setText(item_text)

                print(f"Customized entity {entity_idx}: num_points={num_points}")

    def entity_to_points(self, entity, scale=1.0, max_segment_length=0.5, entity_idx=None):
        """Convert a DXF entity to a list of points using max_segment_length or custom parameters."""
        points = []

        if entity.dxftype() == "LINE":
            points.append((entity.dxf.start.x * scale, entity.dxf.start.y * scale))
            points.append((entity.dxf.end.x * scale, entity.dxf.end.y * scale))

        elif entity.dxftype() == "CIRCLE":
            center = entity.dxf.center
            radius = entity.dxf.radius * scale
            circumference = 2 * math.pi * radius

            # Check for custom parameters
            custom_key = self._get_custom_param_key(entity_idx)
            if custom_key and custom_key in self.custom_entity_params:
                num_segments = self.custom_entity_params[custom_key]["num_points"] - 1
            else:
                num_segments = max(8, int(math.ceil(circumference / max_segment_length)))

            for i in range(num_segments + 1):
                angle = i * 2 * math.pi / num_segments
                x = center.x * scale + radius * math.cos(angle)
                y = center.y * scale + radius * math.sin(angle)
                points.append((x, y))

        elif entity.dxftype() == "ARC":
            center = entity.dxf.center
            radius = entity.dxf.radius * scale
            start_angle = math.radians(entity.dxf.start_angle)
            end_angle = math.radians(entity.dxf.end_angle)

            if end_angle < start_angle:
                end_angle += 2 * math.pi

            angle_span = end_angle - start_angle
            arc_length = radius * angle_span

            # Check for custom parameters
            custom_key = self._get_custom_param_key(entity_idx)
            if custom_key and custom_key in self.custom_entity_params:
                num_segments = self.custom_entity_params[custom_key]["num_points"] - 1
            else:
                num_segments = max(2, int(math.ceil(arc_length / max_segment_length)))

            for i in range(num_segments + 1):
                angle = start_angle + i * angle_span / num_segments
                x = center.x * scale + radius * math.cos(angle)
                y = center.y * scale + radius * math.sin(angle)
                points.append((x, y))

        elif entity.dxftype() == "SPLINE":
            try:
                if hasattr(entity, "construction_tool"):
                    try:
                        bspline = entity.construction_tool()
                        sample_points = 100
                        t_values = np.linspace(0, 1, sample_points)
                        curve_points = [bspline.point(t) for t in t_values]

                        curve_length = 0
                        for i in range(1, len(curve_points)):
                            dx = curve_points[i][0] - curve_points[i - 1][0]
                            dy = curve_points[i][1] - curve_points[i - 1][1]
                            curve_length += math.sqrt(dx * dx + dy * dy)

                        # Check for custom parameters
                        custom_key = self._get_custom_param_key(entity_idx)
                        if custom_key and custom_key in self.custom_entity_params:
                            num_segments = self.custom_entity_params[custom_key]["num_points"] - 1
                        else:
                            num_segments = max(10, int(math.ceil(curve_length / max_segment_length)))

                        t_values = np.linspace(0, 1, num_segments)
                        final_points = [bspline.point(t) for t in t_values]

                        for point in final_points:
                            points.append((point[0] * scale, point[1] * scale))
                    except Exception as e:
                        print(f"Error using construction_tool for SPLINE: {e}")

                if not points and hasattr(entity, "control_points"):
                    control_points = entity.control_points

                    # Check for custom parameters
                    custom_key = self._get_custom_param_key(entity_idx)
                    if custom_key and custom_key in self.custom_entity_params:
                        total_segments = self.custom_entity_params[custom_key]["num_points"] - 1
                    else:
                        total_segments = max(10, int(50 * len(control_points) / max_segment_length))

                    segments_per_edge = max(1, total_segments // (len(control_points) - 1))

                    for i in range(len(control_points) - 1):
                        p1 = control_points[i]
                        p2 = control_points[i + 1]
                        for t in range(segments_per_edge + 1):
                            alpha = t / segments_per_edge
                            x = p1[0] * (1 - alpha) + p2[0] * alpha
                            y = p1[1] * (1 - alpha) + p2[1] * alpha
                            points.append((x * scale, y * scale))
            except Exception as e:
                print(f"Error processing SPLINE entity: {e}")

        elif entity.dxftype() in ["LWPOLYLINE", "POLYLINE"]:
            if entity.dxftype() == "LWPOLYLINE":
                for vertex in entity.vertices():
                    points.append((vertex[0] * scale, vertex[1] * scale))
            else:
                for vertex in entity.vertices():
                    points.append((vertex.dxf.location.x * scale, vertex.dxf.location.y * scale))

            if hasattr(entity, "dxf") and hasattr(entity.dxf, "closed") and entity.dxf.closed:
                points.append(points[0])

        return points

    def _get_custom_param_key(self, entity_idx):
        """Get the custom parameter key for an entity index."""
        if entity_idx is None:
            return None
        # Find the row in cutting_order that corresponds to this entity_idx
        for row, e_idx in enumerate(self.cutting_order):
            if e_idx == entity_idx:
                return f"{row}_{entity_idx}"
        return None

    def manual_order_path(self, entities, order, scale=1.0, max_segment_length=0.5, left_to_right=True):
        """Create an ordered cutting path from entities."""
        if not entities or not order:
            return []

        all_paths = []
        for idx in order:
            if idx < len(entities):
                path = self.entity_to_points(entities[idx], scale, max_segment_length, entity_idx=idx)
                if path:
                    all_paths.append(path)

        if not all_paths:
            return []

        first_path = all_paths[0][:]

        if left_to_right:
            if first_path[0][0] > first_path[-1][0]:
                first_path = first_path[::-1]
        else:
            if first_path[0][0] < first_path[-1][0]:
                first_path = first_path[::-1]

        flattened_path = first_path
        prev_end_point = first_path[-1]

        for path in all_paths[1:]:
            path_copy = path[:]
            start_point = path_copy[0]
            end_point = path_copy[-1]

            dist_to_start = ((prev_end_point[0] - start_point[0]) ** 2 + (prev_end_point[1] - start_point[1]) ** 2) ** 0.5
            dist_to_end = ((prev_end_point[0] - end_point[0]) ** 2 + (prev_end_point[1] - end_point[1]) ** 2) ** 0.5

            if dist_to_end < dist_to_start:
                path_copy = path_copy[::-1]

            flattened_path.extend(path_copy)
            prev_end_point = path_copy[-1]

        return flattened_path

    def calculate_default_points(self, entity, max_segment_length=0.5):
        """Calculate default number of points for an entity."""
        if entity.dxftype() == "LINE":
            return 2
        elif entity.dxftype() == "ARC":
            radius = entity.dxf.radius * self.unit_to_mm
            start_angle = math.radians(entity.dxf.start_angle)
            end_angle = math.radians(entity.dxf.end_angle)
            if end_angle < start_angle:
                end_angle += 2 * math.pi
            arc_length = radius * (end_angle - start_angle)
            return max(2, int(arc_length / max_segment_length))
        elif entity.dxftype() == "CIRCLE":
            radius = entity.dxf.radius * self.unit_to_mm
            circumference = 2 * math.pi * radius
            return max(8, int(circumference / max_segment_length))
        elif entity.dxftype() in ["LWPOLYLINE", "POLYLINE"]:
            return max(len(list(entity.vertices())), 2)
        elif entity.dxftype() == "SPLINE":
            return max(len(entity.control_points), 10)
        elif entity.dxftype() == "ELLIPSE":
            major_axis = entity.dxf.major_axis
            semi_major = math.sqrt(major_axis.x**2 + major_axis.y**2) * self.unit_to_mm
            return max(8, int(2 * math.pi * semi_major / max_segment_length))
        else:
            return 10

    def on_cutting_order_changed(self):
        """Handle when cutting order is changed by drag/drop."""
        # Update cutting_order based on list contents
        new_order = []
        for i in range(self.cutting_list.count()):
            item = self.cutting_list.item(i)
            text = item.text()
            try:
                entity_idx = int(text.split()[1])
                new_order.append(entity_idx)
            except (IndexError, ValueError):
                continue

        self.cutting_order = new_order
        print(f"Cutting order updated: {self.cutting_order}")

    def generate_cutting_path(self):
        """Generate the cutting path from current settings."""
        if not self.entities or not self.cutting_order:
            QMessageBox.warning(self, "Warning", "No entities or cutting order defined.")
            return None

        try:
            # Get parameters
            scale = float(self.scale_factor_edit.text())
            max_segment_length = float(self.max_segment_length_edit.text())

            # Convert max_segment_length to mm if display is in inches
            if hasattr(self, "display_inch_radio") and self.display_inch_radio.isChecked():
                max_segment_length *= 25.4

            left_to_right = self.left_to_right_radio.isChecked()

            # Generate path
            points = self.manual_order_path(self.entities, self.cutting_order, scale, max_segment_length, left_to_right)

            if not points:
                return None

            points = np.array(points)

            # Apply unit conversion
            points = points * self.unit_to_mm

            # Remove duplicates
            points = np.array([p for i, p in enumerate(points) if i == 0 or not np.allclose(p, points[i - 1])])

            if len(points) == 0:
                return None
            x_offset = float(self.x_offset_edit.text())
            y_offset = float(self.y_offset_edit.text())

            # Convert offsets to mm if display is in inches
            display_is_inches = not self.display_mm_radio.isChecked()
            if display_is_inches:
                x_offset *= 25.4
                y_offset *= 25.4

            points[:, 0] -= points[:, 0].min()
            points[:, 1] -= points[:, 1].min()
            points[:, 0] += x_offset
            points[:, 1] += y_offset

            return points

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating cutting path: {str(e)}")
            return None

    def animate_path(self):
        """Animate the tool path with constant speed."""
        points = self.generate_cutting_path()
        if points is None:
            return

        self.points = points  # Keep in mm for calculations

        # Convert points to display units for plotting
        display_is_inches = not self.display_mm_radio.isChecked()
        display_points = points / 25.4 if display_is_inches else points

        try:
            tool_speed = float(self.animation_speed_edit.text())
            # Convert to mm/s if display is in inches
            if hasattr(self, "display_inch_radio") and self.display_inch_radio.isChecked():
                tool_speed *= 25.4
        except ValueError:
            tool_speed = DEFAULT_ANIMATION_SPEED  # Default speed

        # Store if static dots were shown before clearing
        dots_were_shown = self.show_static_dots

        # Clear animation canvas
        ax = self.animation_canvas.ax
        ax.clear()
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)

        # Show animation zoom controls
        if hasattr(self, "anim_zoom_in_button"):
            self.anim_zoom_in_button.show()
            self.anim_zoom_out_button.show()
            self.anim_zoom_fit_button.show()

        # Reset static dots state after clearing
        self.static_dots_plot = None
        self.show_static_dots = False

        # Set limits with margin
        x_min, x_max = np.min(display_points[:, 0]), np.max(display_points[:, 0])
        y_min, y_max = np.min(display_points[:, 1]), np.max(display_points[:, 1])
        margin = max((x_max - x_min), (y_max - y_min)) * 0.05
        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(y_min - margin, y_max + margin)

        # Plot complete path (light gray)
        ax.plot(display_points[:, 0], display_points[:, 1], "lightgray", linewidth=1, alpha=0.5)

        # Restore static dots if they were shown
        if dots_were_shown:
            self.static_dots_plot = ax.scatter(display_points[:, 0], display_points[:, 1], c="black", s=STATIC_DOTS_SIZE, alpha=STATIC_DOTS_ALPHA, zorder=1)
            self.show_static_dots = True

        # Initialize tool and progress line
        from matplotlib import patches

        # Scale tool radius based on display units
        tool_radius = 0.5
        if display_is_inches:
            tool_radius /= 25.4  # Convert mm to inches

        self.tool = patches.Circle((display_points[0][0], display_points[0][1]), tool_radius, color="red", zorder=10)
        ax.add_patch(self.tool)

        (self.traveled_line,) = ax.plot([], [], "blue", linewidth=2)

        ax.set_title("Tool Path Animation")
        display_unit = "mm" if self.display_mm_radio.isChecked() else "inch"
        ax.set_xlabel(f"X ({display_unit})")
        ax.set_ylabel(f"Y ({display_unit})")

        # Pre-compute path information for constant speed
        segment_vectors = points[1:] - points[:-1]
        segment_lengths = np.linalg.norm(segment_vectors, axis=1)
        self.cumulative_distances = np.cumsum(np.insert(segment_lengths, 0, 0))
        total_length = self.cumulative_distances[-1]

        # Animation parameters
        fps = 30
        total_time = total_length / tool_speed
        self.total_frames = int(total_time * fps)
        interval = 1000 / fps

        # Reset animation state
        self.animate_frame = 0
        self.animation_paused = False

        # Start animation timer
        if hasattr(self, "animation_timer") and self.animation_timer:
            self.animation_timer.stop()

        self.animation_timer = self.animation_canvas.fig.canvas.new_timer(interval=int(interval))
        self.animation_timer.add_callback(lambda: self.update_animation(tool_speed, fps))
        self.animation_timer.start()

        # Enable pause button
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Pause")

        self.animation_canvas.draw()

    def update_animation(self, tool_speed, fps):
        """Update animation frame with constant speed and looping."""
        if self.points is None:
            return

        # Check if animation completed - restart if so
        if self.animate_frame >= self.total_frames:
            self.animate_frame = 0  # Restart animation

        # Calculate current position based on constant speed
        time = self.animate_frame / fps
        distance = time * tool_speed
        total_length = self.cumulative_distances[-1]
        distance = distance % total_length  # Loop the distance

        # Find segment using binary search
        segment_idx = np.searchsorted(self.cumulative_distances, distance, side="right") - 1
        segment_idx = max(0, min(segment_idx, len(self.points) - 2))

        # Calculate position within segment
        segment_start_dist = self.cumulative_distances[segment_idx]
        segment_length = self.cumulative_distances[segment_idx + 1] - segment_start_dist

        if segment_length > 0:
            segment_progress = (distance - segment_start_dist) / segment_length
        else:
            segment_progress = 0

        # Interpolate position
        current_pos = self.points[segment_idx] + segment_progress * (self.points[segment_idx + 1] - self.points[segment_idx])

        # Convert to display coordinates
        display_is_inches = not self.display_mm_radio.isChecked()
        if display_is_inches:
            current_pos = current_pos / 25.4

        # Update tool position
        self.tool.center = (current_pos[0], current_pos[1])

        # Update traveled path
        if segment_idx >= len(self.points) - 1:
            # Convert all points to display coordinates
            display_all_points = self.points / 25.4 if display_is_inches else self.points
            self.traveled_line.set_data(display_all_points[:, 0], display_all_points[:, 1])
        else:
            # Convert traveled points to display coordinates
            traveled_points = np.vstack([self.points[: segment_idx + 1], self.points[segment_idx + 1]])
            display_traveled = traveled_points / 25.4 if display_is_inches else traveled_points
            # Replace last point with current_pos (already converted)
            display_traveled[-1] = current_pos
            self.traveled_line.set_data(display_traveled[:, 0], display_traveled[:, 1])

        self.animate_frame += 1
        self.animation_canvas.draw()

    def update_animation_frame(self, frame):
        """Update a single animation frame."""
        if not hasattr(self, "animation_frame_positions") or frame >= len(self.animation_frame_positions):
            return self.tool_point, self.current_path

        x, y, path_length = self.animation_frame_positions[frame]

        # Update tool position
        self.tool_point.set_data([x], [y])

        # Update current path
        points = self.generate_cutting_path()
        if points and path_length > 0:
            current_points = points[: min(path_length, len(points))]
            if current_points:
                path_x = [p[0] for p in current_points]
                path_y = [p[1] for p in current_points]
                self.current_path.set_data(path_x, path_y)

        return self.tool_point, self.current_path

    def stop_animation(self):
        """Stop the current animation."""
        if hasattr(self, "animation") and self.animation:
            self.animation.event_source.stop()
            self.animation = None

        # Reset button
        self.animate_button.setText("Animate")
        self.animate_button.clicked.disconnect()
        self.animate_button.clicked.connect(self.animate_path)
        self.pause_button.setEnabled(False)

    def toggle_animation_pause(self):
        """Toggle animation pause/resume."""
        if not hasattr(self, "animation_timer") or self.animation_timer is None:
            return

        if self.animation_paused:
            self.animation_timer.start()
            self.pause_button.setText("Pause")
            self.animation_paused = False
        else:
            self.animation_timer.stop()
            self.pause_button.setText("Resume")
            self.animation_paused = True

    def toggle_static_dots(self):
        """Toggle static dots on/off in the animation canvas."""
        if self.points is None:
            QMessageBox.warning(self, "Warning", "No cutting path generated yet!")
            return

        ax = self.animation_canvas.ax

        if self.show_static_dots:
            # Hide static dots
            if self.static_dots_plot:
                self.static_dots_plot.remove()
                self.static_dots_plot = None
            self.show_static_dots = False
            self.static_plot_button.setText("Show G-Code Points")
        else:
            # Show static dots
            self.static_dots_plot = ax.scatter(self.points[:, 0], self.points[:, 1], c="black", s=STATIC_DOTS_SIZE, alpha=STATIC_DOTS_ALPHA, zorder=1)
            self.show_static_dots = True
            self.static_plot_button.setText("Hide G-Code Points")

        self.animation_canvas.draw()

    def generate_and_save_gcode(self):
        """Generate G-code and save to file."""
        points = self.generate_cutting_path()
        if points is None:
            QMessageBox.warning(self, "No Path", "No cutting path to generate. Please add entities to the cutting sequence.")
            return

        try:
            feed_rate = float(self.feed_rate_edit.text() or "200.0")
        except ValueError:
            feed_rate = 200.0

        # Generate G-code
        gcode = generate_gcode(points, feed_rate)

        # Save to file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save G-code", f"{self.loaded_filename.rsplit('.', 1)[0]}.ngc", "G-code Files (*.ngc *.gcode);;All Files (*)")

        if file_path:
            try:
                with open(file_path, "w") as f:
                    f.write(gcode)
                QMessageBox.information(self, "G-code Saved", f"G-code saved successfully to {file_path}\n\nTotal points: {len(points)}")
            except Exception as e:
                QMessageBox.critical(self, "Error Saving G-code", f"Failed to save G-code: {str(e)}")

    def remove_selected_entity(self):
        """Remove selected entities from cutting order."""
        selected_items = self.cutting_list.selectedItems()
        if not selected_items:
            return

        # Get selected rows in reverse order to avoid index shifting
        selected_rows = sorted([self.cutting_list.row(item) for item in selected_items], reverse=True)

        # Remove from list widget and cutting order
        for row in selected_rows:
            if 0 <= row < len(self.cutting_order):
                self.cutting_list.takeItem(row)
                removed_entity = self.cutting_order.pop(row)
                print(f"Removed entity {removed_entity} from cutting order")

    def set_default_2d_values(self):
        """Set default values for 2D controls."""
        # Determine current display units
        is_inches = hasattr(self, "display_inch_radio") and self.display_inch_radio.isChecked()
        unit_factor = 1.0 / 25.4 if is_inches else 1.0

        if hasattr(self, "max_segment_length_edit"):
            default_value = DEFAULT_MAX_SEGMENT_LENGTH * unit_factor
            self.max_segment_length_edit.setText(f"{default_value:.4f}")
        if hasattr(self, "feed_rate_edit"):
            self.feed_rate_edit.setText("120")
        if hasattr(self, "scale_factor_edit"):
            self.scale_factor_edit.setText(str(DEFAULT_SCALE_FACTOR))
        if hasattr(self, "x_offset_edit"):
            default_value = DEFAULT_OFFSET * unit_factor
            self.x_offset_edit.setText(f"{default_value:.4f}")
        if hasattr(self, "y_offset_edit"):
            default_value = DEFAULT_OFFSET * unit_factor
            self.y_offset_edit.setText(f"{default_value:.4f}")
        if hasattr(self, "animation_speed_edit"):
            default_value = DEFAULT_ANIMATION_SPEED * unit_factor
            self.animation_speed_edit.setText(f"{default_value:.1f}")

    def on_display_units_changed(self, checked):
        """Handle display units change between mm and inches."""
        # Prevent re-entrant calls
        if getattr(self, "_processing_units_change", False):
            return

        # The inch radio toggled signal is connected
        # If checked=True, user selected inches, convert mm values to inches
        # If checked=False, user selected mm, convert inch values to mm
        if checked:
            # Switching to inches: divide by 25.4
            factor = 1.0 / 25.4
            unit_text = "inch/s"
        else:
            # Switching to mm: multiply by 25.4
            factor = 25.4
            unit_text = "mm/s"

        self._processing_units_change = True
        try:
            # Update labels
            if hasattr(self, "animation_speed_label"):
                self.animation_speed_label.setText(f"Animation Speed ({unit_text}):")

            # Convert max segment length
            if hasattr(self, "max_segment_length_edit") and self.max_segment_length_edit.text():
                try:
                    current_value = float(self.max_segment_length_edit.text())
                    new_value = current_value * factor
                    self.max_segment_length_edit.setText(f"{new_value:.4f}")
                except ValueError:
                    pass  # Keep current value if not a valid number

            # Convert X offset
            if hasattr(self, "x_offset_edit") and self.x_offset_edit.text():
                try:
                    current_value = float(self.x_offset_edit.text())
                    new_value = current_value * factor
                    self.x_offset_edit.setText(f"{new_value:.4f}")
                except ValueError:
                    pass

            # Convert Y offset
            if hasattr(self, "y_offset_edit") and self.y_offset_edit.text():
                try:
                    current_value = float(self.y_offset_edit.text())
                    new_value = current_value * factor
                    self.y_offset_edit.setText(f"{new_value:.4f}")
                except ValueError:
                    pass

            # Convert animation speed
            if hasattr(self, "animation_speed_edit") and self.animation_speed_edit.text():
                try:
                    current_value = float(self.animation_speed_edit.text())
                    new_value = current_value * factor
                    self.animation_speed_edit.setText(f"{new_value:.1f}")
                except ValueError:
                    pass

            # Update the plot labels
            self.plot_entities()
        finally:
            self._processing_units_change = False


def generate_gcode(points, feed_rate=200.0, wire_current=1000):
    """Generate G-code from a list of points."""
    if len(points) == 0:
        return ""

    gcode_lines = []

    # Header
    gcode_lines.append("; Hot Wire CNC G-code")
    gcode_lines.append("; Generated by Hot Wire G-code Generator")
    gcode_lines.append("")
    gcode_lines.append("G21 ; Set units to millimeters")
    gcode_lines.append("G90 ; Absolute positioning")
    gcode_lines.append("G92 X0 Y0 Z0 ; Set current position as origin")
    gcode_lines.append("")

    # Set wire current
    gcode_lines.append(f"M3 S{wire_current} ; Set wire current")
    gcode_lines.append("")

    # Move to first point
    first_point = points[0]
    gcode_lines.append(f"G0 X{first_point[0]:.3f} Y{first_point[1]:.3f} ; Rapid move to start")
    gcode_lines.append("")

    # Generate cutting moves
    for i, point in enumerate(points[1:], 1):
        gcode_lines.append(f"G1 X{point[0]:.3f} Y{point[1]:.3f} F{feed_rate} ; Cut to point {i}")

    # Footer
    gcode_lines.append("")
    gcode_lines.append("M5 ; Turn off wire")
    gcode_lines.append("G0 Z10 ; Lift wire")
    gcode_lines.append("M30 ; Program end")

    return "\n".join(gcode_lines)
