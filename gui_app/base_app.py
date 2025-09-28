#!/usr/bin/env python3
"""
Base application class with common functionality for both 2D and 3D modes.
"""

from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, QLabel, QStackedWidget, QGroupBox, QFileDialog, QMessageBox
from PySide6.QtCore import Qt

import ezdxf
import cadquery as cq
import numpy as np

from constants import ENTRY_EXIT_CONFIG, ZOOM_FACTOR, DXF_UNITS_TO_MM
from canvases import MatplotlibCanvas, MatplotlibCanvas3D


class BaseHotWireApp(QMainWindow):
    """Base application class with common functionality."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hot Wire CNC G-code Generator")
        self.setGeometry(100, 100, 1400, 800)

        # Common data storage
        self.loaded_filename = "None"
        self.unit_to_mm = 1.0

        # Entry/Exit configuration system (from notebook)
        self.entry_exit_config = ENTRY_EXIT_CONFIG.copy()

        # Animation control
        self.animation_timer = None
        self.animation_paused = False
        self.animate_frame = 0

    def setup_base_ui(self):
        """Setup the base user interface layout."""
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

        # Top: Selection canvas with custom navigation (supports both 2D and 3D)
        selection_widget = QWidget()
        selection_layout = QVBoxLayout(selection_widget)
        self.selection_label = QLabel("DXF Entity Selection")
        selection_layout.addWidget(self.selection_label)

        # Stacked widget for 2D and 3D selection canvases
        self.selection_stack = QStackedWidget()
        self.selection_canvas = MatplotlibCanvas(self, width=8, height=6)  # 2D canvas
        self.selection_canvas_3d = MatplotlibCanvas3D(self, width=8, height=6)  # 3D canvas
        self.selection_stack.addWidget(self.selection_canvas)
        self.selection_stack.addWidget(self.selection_canvas_3d)
        selection_layout.addWidget(self.selection_stack)

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

        # Bottom: Animation canvas with zoom controls (supports both 2D and 3D animations)
        animation_widget = QWidget()
        animation_layout = QVBoxLayout(animation_widget)
        animation_layout.addWidget(QLabel("Tool Path Animation"))

        # Stacked widget for 2D and 3D animations
        self.animation_stack = QStackedWidget()
        self.animation_canvas = MatplotlibCanvas(self, width=8, height=4)  # 2D animation
        self.animation_canvas_3d = MatplotlibCanvas3D(self, width=8, height=4)  # 3D animation
        self.animation_stack.addWidget(self.animation_canvas)
        self.animation_stack.addWidget(self.animation_canvas_3d)
        animation_layout.addWidget(self.animation_stack)

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

        # Show zoom controls by default (like top panel)
        self.anim_zoom_in_button.show()
        self.anim_zoom_out_button.show()
        self.anim_zoom_fit_button.show()

        animation_layout.addLayout(self.anim_zoom_layout)
        viz_splitter.addWidget(animation_widget)

        main_splitter.addWidget(viz_widget)

        # Right side - Control panel (to be implemented by subclasses)
        control_widget = self.create_control_panel()
        main_splitter.addWidget(control_widget)

        # Set splitter proportions
        main_splitter.setSizes([1000, 400])
        viz_splitter.setSizes([450, 450])

    def create_control_panel(self):
        """Create the control panel. To be implemented by subclasses."""
        control_widget = QWidget()
        control_widget.setMaximumWidth(400)
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins

        # File Operations (unified for both modes)
        file_group = QGroupBox("File Operations")
        file_layout = QVBoxLayout(file_group)

        self.load_button = QPushButton("Load DXF or STEP File")
        self.load_button.clicked.connect(self.load_file)
        file_layout.addWidget(self.load_button)

        control_layout.addWidget(file_group)

        return control_widget

    def load_file(self):
        """Load a DXF or STEP file and display entities."""
        # Use instance method to avoid matplotlib event conflicts
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Load File")
        dialog.setNameFilter("Supported Files (*.dxf *.step *.stp);;DXF Files (*.dxf);;STEP Files (*.step *.stp);;All Files (*)")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            file_paths = dialog.selectedFiles()
            if file_paths:
                file_path = file_paths[0]
            else:
                return
        else:
            return

        file_ext = Path(file_path).suffix.lower()
        self.loaded_filename = Path(file_path).name

        try:
            if file_ext == ".dxf":
                self.load_dxf_file_internal(file_path)
                if hasattr(self, "switch_to_2d_mode"):
                    self.switch_to_2d_mode()
            elif file_ext in [".step", ".stp"]:
                self.load_step_file_internal(file_path)
                if hasattr(self, "switch_to_3d_mode"):
                    self.switch_to_3d_mode()
            else:
                QMessageBox.warning(self, "Unsupported File", "Please select a DXF or STEP file.")
        except Exception as e:
            QMessageBox.critical(self, "Error Loading File", f"Failed to load file: {str(e)}")

    def load_dxf_file_internal(self, file_path):
        """Load DXF file. To be implemented by subclasses."""
        entities, unit_to_mm = load_dxf_entities(file_path)
        self.unit_to_mm = unit_to_mm
        return entities, unit_to_mm

    def load_step_file_internal(self, file_path):
        """Load STEP file. To be implemented by subclasses."""
        faces, face_centers, units_to_mm = load_step_faces(file_path)
        return faces, face_centers, units_to_mm

    def zoom_in(self):
        """Zoom in on the selection canvas."""
        if hasattr(self, "is_3d_mode") and self.is_3d_mode:
            ax = self.selection_canvas_3d.ax
            # Get current limits
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            zlim = ax.get_zlim()

            # Calculate new limits (zoom in)
            zoom_factor = 1 / ZOOM_FACTOR
            x_center = (xlim[0] + xlim[1]) / 2
            y_center = (ylim[0] + ylim[1]) / 2
            z_center = (zlim[0] + zlim[1]) / 2

            x_range = (xlim[1] - xlim[0]) * zoom_factor / 2
            y_range = (ylim[1] - ylim[0]) * zoom_factor / 2
            z_range = (zlim[1] - zlim[0]) * zoom_factor / 2

            ax.set_xlim(x_center - x_range, x_center + x_range)
            ax.set_ylim(y_center - y_range, y_center + y_range)
            ax.set_zlim(z_center - z_range, z_center + z_range)
            self.selection_canvas_3d.draw()
        else:
            ax = self.selection_canvas.ax
            # Get current limits
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()

            # Calculate new limits (zoom in)
            zoom_factor = 1 / ZOOM_FACTOR
            x_center = (xlim[0] + xlim[1]) / 2
            y_center = (ylim[0] + ylim[1]) / 2

            x_range = (xlim[1] - xlim[0]) * zoom_factor / 2
            y_range = (ylim[1] - ylim[0]) * zoom_factor / 2

            ax.set_xlim(x_center - x_range, x_center + x_range)
            ax.set_ylim(y_center - y_range, y_center + y_range)
            self.selection_canvas.draw()

    def zoom_out(self):
        """Zoom out on the selection canvas."""
        if hasattr(self, "is_3d_mode") and self.is_3d_mode:
            ax = self.selection_canvas_3d.ax
            # Get current limits
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            zlim = ax.get_zlim()

            # Calculate new limits (zoom out)
            zoom_factor = ZOOM_FACTOR
            x_center = (xlim[0] + xlim[1]) / 2
            y_center = (ylim[0] + ylim[1]) / 2
            z_center = (zlim[0] + zlim[1]) / 2

            x_range = (xlim[1] - xlim[0]) * zoom_factor / 2
            y_range = (ylim[1] - ylim[0]) * zoom_factor / 2
            z_range = (zlim[1] - zlim[0]) * zoom_factor / 2

            ax.set_xlim(x_center - x_range, x_center + x_range)
            ax.set_ylim(y_center - y_range, y_center + y_range)
            ax.set_zlim(z_center - z_range, z_center + z_range)
            self.selection_canvas_3d.draw()
        else:
            ax = self.selection_canvas.ax
            # Get current limits
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()

            # Calculate new limits (zoom out)
            zoom_factor = ZOOM_FACTOR
            x_center = (xlim[0] + xlim[1]) / 2
            y_center = (ylim[0] + ylim[1]) / 2

            x_range = (xlim[1] - xlim[0]) * zoom_factor / 2
            y_range = (ylim[1] - ylim[0]) * zoom_factor / 2

            ax.set_xlim(x_center - x_range, x_center + x_range)
            ax.set_ylim(y_center - y_range, y_center + y_range)
            self.selection_canvas.draw()

    def zoom_fit(self):
        """Fit the view to show all content."""
        if hasattr(self, "is_3d_mode") and self.is_3d_mode:
            ax = self.selection_canvas_3d.ax

            # For 3D mode, use the same logic as plot_3d_profiles for consistent results
            if hasattr(self, "left_profile_entities") and hasattr(self, "right_profile_entities"):
                all_points = []
                for entity in self.left_profile_entities + self.right_profile_entities:
                    all_points.extend(entity)

                if all_points:
                    all_points = np.array(all_points)
                    x_min, x_max = all_points[:, 0].min(), all_points[:, 0].max()
                    y_min, y_max = all_points[:, 1].min(), all_points[:, 1].max()
                    z_min, z_max = all_points[:, 2].min(), all_points[:, 2].max()

                    # Add padding
                    x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1
                    y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1
                    z_pad = (z_max - z_min) * 0.1 if z_max > z_min else 1

                    ax.set_xlim(x_min - x_pad, x_max + x_pad)
                    ax.set_ylim(y_min - y_pad, y_max + y_pad)
                    ax.set_zlim(z_min - z_pad, z_max + z_pad)

                    self.selection_canvas_3d.draw()
                    return

            # Fallback: Get all plotted data (original logic)
            all_x, all_y, all_z = [], [], []

            for line in ax.lines:
                x_data = line.get_xdata()
                y_data = line.get_ydata()
                if hasattr(line, "get_zdata"):
                    z_data = line.get_zdata()
                else:
                    z_data = [0] * len(x_data)

                all_x.extend(x_data)
                all_y.extend(y_data)
                all_z.extend(z_data)

            # Add text positions
            for text in ax.texts:
                pos = text.get_position()
                if len(pos) >= 3:
                    all_x.append(pos[0])
                    all_y.append(pos[1])
                    all_z.append(pos[2])
                else:
                    all_x.append(pos[0])
                    all_y.append(pos[1])
                    all_z.append(0)

            if all_x and all_y:
                # Add some padding
                padding = 0.1
                x_range = max(all_x) - min(all_x)
                y_range = max(all_y) - min(all_y)
                z_range = max(all_z) - min(all_z) if all_z else 1
                # Ensure minimum z range to prevent singular transformation
                z_range = max(z_range, 1.0)

                x_pad = x_range * padding
                y_pad = y_range * padding
                z_pad = z_range * padding

                ax.set_xlim(min(all_x) - x_pad, max(all_x) + x_pad)
                ax.set_ylim(min(all_y) - y_pad, max(all_y) + y_pad)

                # Set z limits with minimum separation to prevent singular transformation
                z_min = min(all_z) if all_z else -0.5
                z_max = max(all_z) if all_z else 0.5
                if abs(z_max - z_min) < 0.1:  # If range is too small
                    z_center = (z_max + z_min) / 2
                    z_min = z_center - 0.5
                    z_max = z_center + 0.5
                ax.set_zlim(z_min - z_pad, z_max + z_pad)

                self.selection_canvas_3d.draw()
        else:
            ax = self.selection_canvas.ax

            # Get all plotted data
            all_x, all_y = [], []

            for line in ax.lines:
                all_x.extend(line.get_xdata())
                all_y.extend(line.get_ydata())

            # Add text positions
            for text in ax.texts:
                pos = text.get_position()
                all_x.append(pos[0])
                all_y.append(pos[1])

            if all_x and all_y:
                # Add some padding
                padding = 0.1
                x_range = max(all_x) - min(all_x)
                y_range = max(all_y) - min(all_y)

                x_pad = x_range * padding if x_range > 0 else 1
                y_pad = y_range * padding if y_range > 0 else 1

                ax.set_xlim(min(all_x) - x_pad, max(all_x) + x_pad)
                ax.set_ylim(min(all_y) - y_pad, max(all_y) + y_pad)

                self.selection_canvas.draw()

    def anim_zoom_in(self):
        """Zoom in on the animation canvas."""
        ax = self.animation_canvas.ax
        # Get current limits
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Calculate new limits (zoom in)
        zoom_factor = 1 / ZOOM_FACTOR
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2

        x_range = (xlim[1] - xlim[0]) * zoom_factor / 2
        y_range = (ylim[1] - ylim[0]) * zoom_factor / 2

        ax.set_xlim(x_center - x_range, x_center + x_range)
        ax.set_ylim(y_center - y_range, y_center + y_range)
        self.animation_canvas.draw()

    def anim_zoom_out(self):
        """Zoom out on the animation canvas."""
        ax = self.animation_canvas.ax
        # Get current limits
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Calculate new limits (zoom out)
        zoom_factor = ZOOM_FACTOR
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2

        x_range = (xlim[1] - xlim[0]) * zoom_factor / 2
        y_range = (ylim[1] - ylim[0]) * zoom_factor / 2

        ax.set_xlim(x_center - x_range, x_center + x_range)
        ax.set_ylim(y_center - y_range, y_center + y_range)
        self.animation_canvas.draw()

    def anim_zoom_fit(self):
        """Fit the animation view to show all content."""
        ax = self.animation_canvas.ax

        # Get all plotted data
        all_x, all_y = [], []

        for line in ax.lines:
            all_x.extend(line.get_xdata())
            all_y.extend(line.get_ydata())

        if all_x and all_y:
            # Add some padding
            padding = 0.1
            x_range = max(all_x) - min(all_x)
            y_range = max(all_y) - min(all_y)

            x_pad = x_range * padding if x_range > 0 else 1
            y_pad = y_range * padding if y_range > 0 else 1

            ax.set_xlim(min(all_x) - x_pad, max(all_x) + x_pad)
            ax.set_ylim(min(all_y) - y_pad, max(all_y) + y_pad)

            self.animation_canvas.draw()


def get_dxf_units_to_mm(units_code):
    """Convert DXF units code to millimeter conversion factor."""
    return DXF_UNITS_TO_MM.get(units_code, 1.0)


def load_dxf_entities(file_path):
    """Load entities from a DXF file and return them with unit conversion factor."""
    # Read DXF file
    doc = ezdxf.readfile(file_path)

    # Detect DXF units
    units_code = 0
    if "$INSUNITS" in doc.header:
        units_code = doc.header["$INSUNITS"]

    unit_to_mm = get_dxf_units_to_mm(units_code)

    # Get model space
    msp = doc.modelspace()

    # Extract entities
    entities = []
    for entity in msp:
        if entity.dxftype() in ["LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "SPLINE"]:
            entities.append(entity)

    return entities, unit_to_mm


def load_step_faces(file_path):
    """Load faces from a STEP file and return them with face centers and units."""
    # Import the STEP file using cadquery
    model = cq.importers.importStep(file_path)

    # Extract all faces
    all_faces = model.faces().vals()
    print(f"Found {len(all_faces)} faces in the STEP file")

    faces = []
    face_centers = []

    # Store faces and calculate centers
    for face in all_faces:
        faces.append(face)
        center = face.Center()
        face_centers.append((center.x, center.y, center.z))

    # Detect units from STEP file
    units_to_mm = 1.0  # Default to mm
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "SI_UNIT($,.METRE.)" in content:
                units_to_mm = 1000.0  # Convert from meters to mm
            elif "SI_UNIT($,.MILLIMETRE.)" in content:
                units_to_mm = 1.0  # Already in mm
            elif "INCH" in content.upper():
                units_to_mm = 25.4  # Convert from inches to mm
            else:
                # Calculate model dimensions
                print("Could not find explicit unit declaration in STEP file, estimating based on model size...")
                # pop up a warning message box
                bbox = model.val().BoundingBox()
                x_size = abs(bbox.xmax - bbox.xmin)
                y_size = abs(bbox.ymax - bbox.ymin)
                z_size = abs(bbox.zmax - bbox.zmin)
                max_dimension = max(x_size, y_size, z_size)

                # Heuristic: if max dimension is very small, likely in meters
                # If very large, likely in mm or inches
                if max_dimension < 1.0:
                    units_to_mm = 1000.0  # Assume meters, convert to mm
                elif max_dimension > 1000.0:
                    units_to_mm = 1.0  # Assume already in mm
                elif 10.0 < max_dimension < 100.0:
                    units_to_mm = 25.4  # Likely inches, convert to mm
                else:
                    units_to_mm = 1.0  # Default to mm
                QMessageBox.warning(None, "Warning", "Could not find explicit unit declaration in STEP file, estimating based on model size...")

            print(f"Detected STEP file units, conversion factor to mm: {units_to_mm}")
    except Exception as e:
        print(f"Could not detect STEP units, assuming mm: {e}")

    return faces, face_centers, units_to_mm
