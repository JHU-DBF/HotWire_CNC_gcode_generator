#!/usr/bin/env python3
"""
Hot Wire CNC G-code Generator GUI Application

A PySide6-based GUI application for converting DXF files to G-code for hot wire CNC cutting.
"""

import sys
import math
import numpy as np
from pathlib import Path

# PySide6 imports
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, QLabel, QLineEdit, QListWidget, QGroupBox, QRadioButton, QFileDialog, QMessageBox, QAbstractItemView
from PySide6.QtCore import Qt

# Matplotlib imports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as patches

# CAD processing imports
import ezdxf

# Constants
DEFAULT_ANIMATION_SPEED = 50.0
DEFAULT_MAX_SEGMENT_LENGTH = 0.05
DEFAULT_SCALE_FACTOR = 1.0
DEFAULT_OFFSET = 0.0
CLICK_THRESHOLD_SECONDS = 0.3
PAN_THRESHOLD_PIXELS = 5
ZOOM_FACTOR = 1.1
GRID_ALPHA = 0.3
STATIC_DOTS_SIZE = 10
STATIC_DOTS_ALPHA = 0.6


class MatplotlibCanvas(FigureCanvas):
    """Matplotlib canvas for embedding plots in PySide6 widgets."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_aspect("equal")
        self.ax.grid(True, alpha=GRID_ALPHA)

        # Mouse and gesture handling
        self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.fig.canvas.mpl_connect("scroll_event", self.on_scroll)

        # Parent reference for entity selection
        self.parent_widget = parent

        # Pan and zoom state
        self.last_click_time = 0
        self.click_threshold = CLICK_THRESHOLD_SECONDS  # seconds
        self.is_panning = False
        self.pan_start = None
        self.press_time = 0

    def on_press(self, event):
        """Handle mouse press events."""
        import time

        if event.inaxes != self.ax:
            return

        self.press_time = time.time()
        self.pan_start = (event.x, event.y)
        self.is_panning = False

    def on_motion(self, event):
        """Handle mouse motion events for panning."""
        if self.pan_start is None or event.inaxes != self.ax:
            return

        # Check if we've moved enough to start panning
        dx = event.x - self.pan_start[0]
        dy = event.y - self.pan_start[1]
        distance = (dx**2 + dy**2) ** 0.5

        if distance > PAN_THRESHOLD_PIXELS:  # Start panning after threshold pixels of movement
            self.is_panning = True

            # Calculate pan amounts in data coordinates
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()

            # Convert pixel movement to data movement
            bbox = self.ax.get_window_extent()
            x_scale = (xlim[1] - xlim[0]) / bbox.width
            y_scale = (ylim[1] - ylim[0]) / bbox.height

            x_shift = -dx * x_scale
            y_shift = -dy * y_scale  # Invert Y direction for natural panning

            # Apply pan
            self.ax.set_xlim(xlim[0] + x_shift, xlim[1] + x_shift)
            self.ax.set_ylim(ylim[0] + y_shift, ylim[1] + y_shift)

            self.draw()
            self.pan_start = (event.x, event.y)

    def on_release(self, event):
        """Handle mouse release events."""
        import time

        if event.inaxes != self.ax:
            self.pan_start = None
            self.is_panning = False
            return

        current_time = time.time()
        click_duration = current_time - self.press_time

        # Only register clicks that aren't pans and are quick
        if not self.is_panning and click_duration < self.click_threshold and hasattr(self.parent_widget, "on_entity_click") and event.xdata is not None and event.ydata is not None:
            self.parent_widget.on_entity_click(event.xdata, event.ydata)

        self.pan_start = None
        self.is_panning = False

    def on_scroll(self, event):
        """Handle scroll events for zooming."""
        if event.inaxes != self.ax:
            return

        # Get current limits
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # Calculate zoom factor
        zoom_factor = ZOOM_FACTOR if event.step < 0 else 1 / ZOOM_FACTOR

        # Calculate new limits centered on cursor
        x_center = event.xdata if event.xdata else (xlim[0] + xlim[1]) / 2
        y_center = event.ydata if event.ydata else (ylim[0] + ylim[1]) / 2

        x_range = (xlim[1] - xlim[0]) * zoom_factor / 2
        y_range = (ylim[1] - ylim[0]) * zoom_factor / 2

        self.ax.set_xlim(x_center - x_range, x_center + x_range)
        self.ax.set_ylim(y_center - y_range, y_center + y_range)
        self.draw()


class HotWireGCodeApp(QMainWindow):
    """Main application window for the Hot Wire G-code Generator."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hot Wire CNC G-code Generator")
        self.setGeometry(100, 100, 1400, 800)

        # Data storage
        self.entities = []
        self.unit_to_mm = 1.0
        self.cutting_order = []
        self.entity_colors = {}
        self.entity_centers = {}  # Store entity center points for selection
        self.points = None
        self.animation = None
        self.loaded_filename = "None"
        self.custom_entity_params = {}  # Store custom parameters for entities
        self.static_colorbar = None  # Track colorbar for static plots
        self.animation_zoom_controls = None  # Track animation zoom controls
        self.show_static_dots = True  # Track if static dots are shown on animation
        self.static_dots_plot = None  # Track static dots plot object

        # Setup UI
        self.setup_ui()

        # Default values
        self.max_segment_length_edit.setText(str(DEFAULT_MAX_SEGMENT_LENGTH))
        self.feed_rate_edit.setText("120")
        self.scale_factor_edit.setText(str(DEFAULT_SCALE_FACTOR))
        self.x_offset_edit.setText(str(DEFAULT_OFFSET))
        self.y_offset_edit.setText(str(DEFAULT_OFFSET))
        self.animation_speed_edit.setText(str(DEFAULT_ANIMATION_SPEED))

        # Animation control
        self.animation_timer = None
        self.animation_paused = False
        self.animate_frame = 0

    def setup_ui(self):
        """Setup the user interface layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        central_widget_layout = QHBoxLayout(central_widget)
        central_widget_layout.addWidget(main_splitter)

        # Left side - Visualization
        viz_widget = QWidget()
        viz_layout = QVBoxLayout(viz_widget)

        # Visualization splitter (top/bottom)
        viz_splitter = QSplitter(Qt.Orientation.Vertical)
        viz_layout.addWidget(viz_splitter)

        # Top: Selection canvas with custom navigation
        selection_widget = QWidget()
        selection_layout = QVBoxLayout(selection_widget)
        selection_layout.addWidget(QLabel("DXF Entity Selection"))
        self.selection_canvas = MatplotlibCanvas(self, width=8, height=6)
        selection_layout.addWidget(self.selection_canvas)

        # Add custom zoom controls instead of full toolbar
        zoom_layout = QHBoxLayout()
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_fit_button = QPushButton("Fit to View")
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.zoom_fit_button.clicked.connect(self.zoom_fit)
        zoom_layout.addWidget(self.zoom_in_button)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.zoom_fit_button)
        selection_layout.addLayout(zoom_layout)

        viz_splitter.addWidget(selection_widget)

        # Bottom: Animation canvas with zoom controls
        animation_widget = QWidget()
        animation_layout = QVBoxLayout(animation_widget)
        animation_layout.addWidget(QLabel("Tool Path Animation"))
        self.animation_canvas = MatplotlibCanvas(self, width=8, height=4)
        animation_layout.addWidget(self.animation_canvas)

        # Animation zoom controls (initially hidden)
        self.anim_zoom_layout = QHBoxLayout()
        self.anim_zoom_in_button = QPushButton("Zoom In")
        self.anim_zoom_out_button = QPushButton("Zoom Out")
        self.anim_zoom_fit_button = QPushButton("Fit to View")
        self.anim_zoom_in_button.clicked.connect(self.anim_zoom_in)
        self.anim_zoom_out_button.clicked.connect(self.anim_zoom_out)
        self.anim_zoom_fit_button.clicked.connect(self.anim_zoom_fit)
        self.anim_zoom_layout.addWidget(self.anim_zoom_in_button)
        self.anim_zoom_layout.addWidget(self.anim_zoom_out_button)
        self.anim_zoom_layout.addWidget(self.anim_zoom_fit_button)

        # Hide zoom controls initially
        self.anim_zoom_in_button.hide()
        self.anim_zoom_out_button.hide()
        self.anim_zoom_fit_button.hide()

        animation_layout.addLayout(self.anim_zoom_layout)
        viz_splitter.addWidget(animation_widget)

        main_splitter.addWidget(viz_widget)

        # Right side - Control panel
        control_widget = self.create_control_panel()
        main_splitter.addWidget(control_widget)

        # Set splitter proportions
        main_splitter.setSizes([1000, 400])
        viz_splitter.setSizes([600, 300])

    def create_control_panel(self):
        """Create the control panel with all user controls."""
        control_widget = QWidget()
        control_widget.setMaximumWidth(400)
        control_layout = QVBoxLayout(control_widget)

        # File Operations
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout(file_group)

        self.load_button = QPushButton("Load DXF File")
        self.load_button.clicked.connect(self.load_dxf_file)
        file_layout.addWidget(self.load_button)

        control_layout.addWidget(file_group)

        # Cutting Order
        order_group = QGroupBox("Cutting Sequence")
        order_layout = QVBoxLayout(order_group)

        order_layout.addWidget(QLabel("Click entities on the plot to add them."))

        self.cutting_list = QListWidget()
        self.cutting_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.cutting_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Enable multi-select
        self.cutting_list.setMinimumHeight(300)  # Make it taller
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
        speed_layout.addWidget(QLabel("Animation Speed (mm/s):"))
        self.animation_speed_edit = QLineEdit()
        speed_layout.addWidget(self.animation_speed_edit)
        action_layout.addLayout(speed_layout)

        # Animation controls row - all buttons on same line
        anim_layout = QHBoxLayout()
        self.animate_button = QPushButton("Animate")
        self.animate_button.clicked.connect(self.animate_path)
        anim_layout.addWidget(self.animate_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_animation_pause)
        self.pause_button.setEnabled(False)
        anim_layout.addWidget(self.pause_button)

        self.static_plot_button = QPushButton("Hide G-Code Points")
        self.static_plot_button.clicked.connect(self.toggle_static_dots)
        anim_layout.addWidget(self.static_plot_button)

        action_layout.addLayout(anim_layout)

        self.generate_button = QPushButton("Generate and Save G-Code")
        self.generate_button.clicked.connect(self.generate_and_save_gcode)
        action_layout.addWidget(self.generate_button)

        control_layout.addWidget(action_group)

        # Add stretch to push everything to top
        control_layout.addStretch()

        return control_widget

    def get_dxf_units_to_mm(self, units_code):
        """Convert DXF units code to millimeter conversion factor."""
        units_mapping = {
            0: 1.0,  # Unitless (assume mm)
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

    def load_dxf_file(self):
        """Load a DXF file and display entities."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load DXF File", "", "DXF Files (*.dxf);;All Files (*)")

        if not file_path:
            return

        try:
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

            # Update UI
            self.loaded_filename = Path(file_path).name
            self.cutting_order = []
            self.cutting_list.clear()

            # Plot entities
            self.plot_entities()

        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", f"Error: {str(e)}")

    def plot_entities(self):
        """Plot DXF entities on the selection canvas."""
        if not self.entities:
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

        for i, entity in enumerate(self.entities):
            entity_type = entity.dxftype()
            color = colors.get(entity_type, "black")

            if entity_type == "LINE":
                x1, y1 = entity.dxf.start.x, entity.dxf.start.y
                x2, y2 = entity.dxf.end.x, entity.dxf.end.y
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
                x = center.x + radius * np.cos(theta)
                y = center.y + radius * np.sin(theta)
                ax.plot(x, y, color=color, linewidth=2)

                # Store center for clicking
                mid_angle = (start_angle + end_angle) / 2
                self.entity_centers[i] = (center.x + radius * 0.7 * np.cos(mid_angle), center.y + radius * 0.7 * np.sin(mid_angle))
                ax.text(self.entity_centers[i][0], self.entity_centers[i][1], str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))

            elif entity_type == "CIRCLE":
                center = entity.dxf.center
                radius = entity.dxf.radius
                circle = plt.Circle((center.x, center.y), radius, fill=False, color=color, linewidth=2)
                ax.add_patch(circle)

                # Store center for clicking
                self.entity_centers[i] = (center.x, center.y)
                ax.text(center.x, center.y, str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))

            elif entity_type == "SPLINE":
                try:
                    if hasattr(entity, "construction_tool"):
                        bspline = entity.construction_tool()
                        t_values = np.linspace(0, 1, 100)
                        curve_points = [bspline.point(t) for t in t_values]
                        curve_x = [p[0] for p in curve_points]
                        curve_y = [p[1] for p in curve_points]
                        ax.plot(curve_x, curve_y, color=color, linewidth=2)

                        # Store center for clicking
                        middle_idx = len(curve_x) // 2
                        self.entity_centers[i] = (curve_x[middle_idx], curve_y[middle_idx])
                        ax.text(curve_x[middle_idx], curve_y[middle_idx], str(i), fontsize=9, ha="center", va="center", bbox=dict(facecolor="white", alpha=0.7, pad=1, boxstyle="round"))
                    elif hasattr(entity, "control_points"):
                        control_points = entity.control_points
                        if control_points:
                            x_coords = [p[0] for p in control_points]
                            y_coords = [p[1] for p in control_points]
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
                    x_coords = [v[0] for v in vertices]
                    y_coords = [v[1] for v in vertices]
                else:
                    vertices = list(entity.vertices())
                    x_coords = [v.dxf.location.x for v in vertices]
                    y_coords = [v.dxf.location.y for v in vertices]

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

    def generate_cutting_path(self):
        """Generate the cutting path from current settings."""
        if not self.entities or not self.cutting_order:
            QMessageBox.warning(self, "Warning", "No entities or cutting order defined.")
            return None

        try:
            # Get parameters
            scale = float(self.scale_factor_edit.text())
            max_segment_length = float(self.max_segment_length_edit.text())
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

            # Apply offsets
            x_offset = float(self.x_offset_edit.text())
            y_offset = float(self.y_offset_edit.text())

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

        self.points = points

        try:
            tool_speed = float(self.animation_speed_edit.text())
        except ValueError:
            tool_speed = DEFAULT_ANIMATION_SPEED  # Default speed

        # Store if static dots were shown before clearing
        dots_were_shown = self.show_static_dots

        # Clear animation canvas
        ax = self.animation_canvas.ax
        ax.clear()
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)

        # Reset static dots state after clearing
        self.static_dots_plot = None
        self.show_static_dots = False

        # Set limits with margin
        x_min, x_max = np.min(points[:, 0]), np.max(points[:, 0])
        y_min, y_max = np.min(points[:, 1]), np.max(points[:, 1])
        margin = max((x_max - x_min), (y_max - y_min)) * 0.05
        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(y_min - margin, y_max + margin)

        # Plot complete path (light gray)
        ax.plot(points[:, 0], points[:, 1], "lightgray", linewidth=1, alpha=0.5)

        # Restore static dots if they were shown
        if dots_were_shown:
            self.static_dots_plot = ax.scatter(points[:, 0], points[:, 1], c="black", s=STATIC_DOTS_SIZE, alpha=STATIC_DOTS_ALPHA, zorder=1)
            self.show_static_dots = True

        # Initialize tool and progress line
        self.tool = patches.Circle((points[0][0], points[0][1]), 0.5, color="red", zorder=10)
        ax.add_patch(self.tool)

        (self.traveled_line,) = ax.plot([], [], "blue", linewidth=2)

        ax.set_title("Tool Path Animation")
        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")

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
        if self.animation_timer:
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

        # Update tool position
        self.tool.center = (current_pos[0], current_pos[1])

        # Update traveled path
        if segment_idx >= len(self.points) - 1:
            self.traveled_line.set_data(self.points[:, 0], self.points[:, 1])
        else:
            traveled_points = np.vstack([self.points[: segment_idx + 1], current_pos])
            self.traveled_line.set_data(traveled_points[:, 0], traveled_points[:, 1])

        self.animate_frame += 1
        self.animation_canvas.draw()

    def generate_gcode(self, points, feed_rate=200.0, wire_current=1000):
        """Generate G-code from points."""
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
        gcode.append(f"F{feed_rate} ; mm/min")
        gcode.append(f"M3 S{wire_current} ; Set wire current")
        gcode.append("G4 P2 ; Wait 2 seconds for wire to heat up")
        gcode.append("")

        # Move to first point
        first_point = points[0]
        gcode.append(f"G1 X{first_point[0]:.3f} Y{first_point[1]:.3f} A{first_point[0]:.3f} Z{first_point[1]:.3f}; Rapid move to start position")

        # Add cutting moves
        for point in points[1:]:
            gcode.append(f"G1 X{point[0]:.3f} Y{point[1]:.3f} A{point[0]:.3f} Z{point[1]:.3f}")

        # Footer
        gcode.append("")
        gcode.append("M5 ; Turn off wire heater")
        gcode.append("M2 ; End program")

        return gcode

    def generate_and_save_gcode(self):
        """Generate G-code and save to file."""
        points = self.generate_cutting_path()
        if points is None:
            return

        try:
            feed_rate = float(self.feed_rate_edit.text())
            gcode = self.generate_gcode(points, feed_rate, 1000)

            # Save file
            file_path, _ = QFileDialog.getSaveFileName(self, "Save G-Code", "", "G-Code Files (*.ngc);;All Files (*)")

            if file_path:
                with open(file_path, "w") as f:
                    for line in gcode:
                        f.write(line + "\n")

                QMessageBox.information(self, "Success", f"G-code saved to {Path(file_path).name}\nGenerated {len(gcode)} lines\nFeed rate: {feed_rate} mm/min\nOutput format: G-code (mm units)")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generating G-code: {str(e)}")

    def toggle_animation_pause(self):
        """Toggle animation pause/resume."""
        if self.animation_timer is None:
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

    def customize_entity_parameters(self, item):
        """Open dialog to customize entity parameters when double-clicked."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QSpinBox

        row = self.cutting_list.row(item)
        if row < 0 or row >= len(self.cutting_order):
            return

        entity_idx = self.cutting_order[row]
        entity = self.entities[entity_idx]
        entity_type = entity.dxftype()

        # Don't allow customization for LINE entities
        if entity_type == "LINE":
            QMessageBox.information(self, "Info", "LINE entities cannot be customized (they only have 2 points).")
            return

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Customize Entity {entity_idx} ({entity_type})")
        dialog.setModal(True)

        layout = QFormLayout(dialog)

        # Get current custom parameters or defaults
        current_params = self.custom_entity_params.get(f"{row}_{entity_idx}", {})

        # Get max segment length from UI
        try:
            max_segment_length = float(self.max_segment_length_edit.text())
        except ValueError:
            max_segment_length = 0.5  # Default

        # Number of points for curves
        points_spin = QSpinBox()
        points_spin.setRange(0, 1000)  # Allow 0 to reset to default
        default_points = self.calculate_default_points(entity, max_segment_length)
        points_spin.setValue(current_params.get("num_points", default_points))
        layout.addRow(f"Number of Points for {entity_type} (0 = default):", points_spin)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            num_points = points_spin.value()

            if num_points == 0:
                # Reset to default - remove custom parameters
                if f"{row}_{entity_idx}" in self.custom_entity_params:
                    del self.custom_entity_params[f"{row}_{entity_idx}"]

                # Reset item text to default
                item_text = f"Entity {entity_idx} ({entity_type})"
                item.setText(item_text)

                print(f"Reset entity {entity_idx} to default parameters")
            else:
                # Store custom parameters
                self.custom_entity_params[f"{row}_{entity_idx}"] = {"num_points": num_points}

                # Update list item text to show customization
                item_text = f"Entity {entity_idx} ({entity_type}) [Custom: {num_points} pts]"
                item.setText(item_text)

                print(f"Customized entity {entity_idx}: num_points={num_points}")

    def zoom_in(self):
        """Zoom in on the selection plot."""
        ax = self.selection_canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Zoom by factor of 0.8 (80% of current view)
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        x_range = (xlim[1] - xlim[0]) * 0.4
        y_range = (ylim[1] - ylim[0]) * 0.4

        ax.set_xlim(x_center - x_range, x_center + x_range)
        ax.set_ylim(y_center - y_range, y_center + y_range)
        self.selection_canvas.draw()

    def zoom_out(self):
        """Zoom out on the selection plot."""
        ax = self.selection_canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Zoom by factor of 1.25 (125% of current view)
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        x_range = (xlim[1] - xlim[0]) * 0.625
        y_range = (ylim[1] - ylim[0]) * 0.625

        ax.set_xlim(x_center - x_range, x_center + x_range)
        ax.set_ylim(y_center - y_range, y_center + y_range)
        self.selection_canvas.draw()

    def zoom_fit(self):
        """Fit the view to show all entities."""
        if not self.entities:
            return

        ax = self.selection_canvas.ax

        # Get bounds of all entities
        x_coords = []
        y_coords = []

        for entity in self.entities:
            if entity.dxftype() == "LINE":
                x_coords.extend([entity.dxf.start.x, entity.dxf.end.x])
                y_coords.extend([entity.dxf.start.y, entity.dxf.end.y])
            elif entity.dxftype() in ["ARC", "CIRCLE"]:
                center = entity.dxf.center
                radius = entity.dxf.radius
                x_coords.extend([center.x - radius, center.x + radius])
                y_coords.extend([center.y - radius, center.y + radius])
            elif entity.dxftype() in ["LWPOLYLINE", "POLYLINE"]:
                if entity.dxftype() == "LWPOLYLINE":
                    vertices = list(entity.vertices())
                    x_coords.extend([v[0] for v in vertices])
                    y_coords.extend([v[1] for v in vertices])
                else:
                    vertices = list(entity.vertices())
                    x_coords.extend([v.dxf.location.x for v in vertices])
                    y_coords.extend([v.dxf.location.y for v in vertices])

        if x_coords and y_coords:
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)

            # Add 5% margin
            x_margin = (x_max - x_min) * 0.05
            y_margin = (y_max - y_min) * 0.05

            ax.set_xlim(x_min - x_margin, x_max + x_margin)
            ax.set_ylim(y_min - y_margin, y_max + y_margin)
            self.selection_canvas.draw()

    def calculate_default_points(self, entity, max_segment_length=0.5):
        """Calculate default number of points for an entity based on its type and size."""
        entity_type = entity.dxftype()

        if entity_type == "CIRCLE":
            radius = entity.dxf.radius
            circumference = 2 * math.pi * radius
            # Calculate points based on max_segment_length
            return max(8, int(circumference / max_segment_length))
        elif entity_type == "ARC":
            radius = entity.dxf.radius
            start_angle = math.radians(entity.dxf.start_angle)
            end_angle = math.radians(entity.dxf.end_angle)
            if end_angle < start_angle:
                end_angle += 2 * math.pi
            arc_length = radius * (end_angle - start_angle)
            return max(3, int(arc_length / max_segment_length))
        elif entity_type == "SPLINE":
            # Estimate based on control points and segment length
            if hasattr(entity, "control_points"):
                return max(10, len(entity.control_points) * int(5 / max_segment_length))
            else:
                return max(10, int(50 / max_segment_length))  # Default for splines
        elif entity_type in ["LWPOLYLINE", "POLYLINE"]:
            # Based on number of vertices and estimated length
            if entity_type == "LWPOLYLINE":
                vertices = list(entity.vertices())
            else:
                vertices = list(entity.vertices())
            # Estimate total length and calculate points
            estimated_length = len(vertices) * 10  # rough estimate
            return max(len(vertices), int(estimated_length / max_segment_length))
        else:
            return max(10, int(20 / max_segment_length))  # Default based on segment length

    def on_cutting_order_changed(self):
        """Handle when cutting order is changed by drag/drop."""
        # Rebuild cutting_order from current list widget order
        new_order = []
        for i in range(self.cutting_list.count()):
            item = self.cutting_list.item(i)
            item_text = item.text()

            # Extract entity index from text like "Entity 5 (LINE)"
            try:
                start = item_text.find("Entity ") + 7
                end = item_text.find(" (")
                if start > 6 and end > start:
                    entity_idx = int(item_text[start:end])
                    new_order.append(entity_idx)
            except (ValueError, AttributeError):
                pass

        self.cutting_order = new_order
        print(f"Cutting order updated by drag/drop: {self.cutting_order}")

    def show_animation_zoom_controls(self, show=True):
        """Show or hide zoom controls for animation canvas."""
        if show:
            self.anim_zoom_in_button.show()
            self.anim_zoom_out_button.show()
            self.anim_zoom_fit_button.show()
        else:
            self.anim_zoom_in_button.hide()
            self.anim_zoom_out_button.hide()
            self.anim_zoom_fit_button.hide()

    def anim_zoom_in(self):
        """Zoom in on the animation plot."""
        ax = self.animation_canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        x_range = (xlim[1] - xlim[0]) * 0.4
        y_range = (ylim[1] - ylim[0]) * 0.4

        ax.set_xlim(x_center - x_range, x_center + x_range)
        ax.set_ylim(y_center - y_range, y_center + y_range)
        self.animation_canvas.draw()

    def anim_zoom_out(self):
        """Zoom out on the animation plot."""
        ax = self.animation_canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        x_range = (xlim[1] - xlim[0]) * 0.625
        y_range = (ylim[1] - ylim[0]) * 0.625

        ax.set_xlim(x_center - x_range, x_center + x_range)
        ax.set_ylim(y_center - y_range, y_center + y_range)
        self.animation_canvas.draw()

    def anim_zoom_fit(self):
        """Fit animation plot to show all path points."""
        if self.points is None:
            return

        ax = self.animation_canvas.ax

        x_min, x_max = np.min(self.points[:, 0]), np.max(self.points[:, 0])
        y_min, y_max = np.min(self.points[:, 1]), np.max(self.points[:, 1])

        # Add 5% margin
        x_margin = (x_max - x_min) * 0.05
        y_margin = (y_max - y_min) * 0.05

        ax.set_xlim(x_min - x_margin, x_max + x_margin)
        ax.set_ylim(y_min - y_margin, y_max + y_margin)
        self.animation_canvas.draw()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show main window
    window = HotWireGCodeApp()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
