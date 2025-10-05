#!/usr/bin/env python3
"""
Matplotlib canvas classes for embedding plots in PySide6 widgets.
"""

import time
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from constants import ZOOM_FACTOR, GRID_ALPHA, CLICK_THRESHOLD_SECONDS, PAN_THRESHOLD_PIXELS


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

        if distance > PAN_THRESHOLD_PIXELS:
            self.is_panning = True

            # Calculate pan delta
            x_min, x_max = self.ax.get_xlim()
            y_min, y_max = self.ax.get_ylim()

            # Convert pixel movement to data coordinates
            x_range = x_max - x_min
            y_range = y_max - y_min

            dx_data = -dx * x_range / self.fig.get_figwidth() / self.fig.dpi
            dy_data = -dy * y_range / self.fig.get_figheight() / self.fig.dpi

            # Update axis limits
            self.ax.set_xlim(x_min + dx_data, x_max + dx_data)
            self.ax.set_ylim(y_min + dy_data, y_max + dy_data)
            self.draw()

            # Update pan start for continuous panning
            self.pan_start = (event.x, event.y)

    def on_release(self, event):
        """Handle mouse release events."""
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


class MatplotlibCanvas3D(FigureCanvas):
    """3D Matplotlib canvas for embedding 3D plots in PySide6 widgets."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.grid(True, alpha=GRID_ALPHA)

        # Enable 3D navigation (rotation, zoom, pan)
        # The 3D axes already have built-in mouse interaction
        # We just need to make sure it's enabled
        self.ax.mouse_init()

        # Parent reference for entity selection
        self.parent_widget = parent

        # Click detection state (kept for compatibility but 3D uses picker events)
        self.last_click_time = 0
        self.click_threshold = CLICK_THRESHOLD_SECONDS
        self.is_panning = False
        self.pan_start = None
        self.press_time = 0

    def on_press(self, event):
        """Handle mouse press events."""
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

        if distance > PAN_THRESHOLD_PIXELS:
            self.is_panning = True

            # Calculate pan delta
            x_min, x_max = self.ax.get_xlim()
            y_min, y_max = self.ax.get_ylim()

            # Convert pixel movement to data coordinates
            x_range = x_max - x_min
            y_range = y_max - y_min

            dx_data = -dx * x_range / self.fig.get_figwidth() / self.fig.dpi
            dy_data = -dy * y_range / self.fig.get_figheight() / self.fig.dpi

            # Update axis limits
            self.ax.set_xlim(x_min + dx_data, x_max + dx_data)
            self.ax.set_ylim(y_min + dy_data, y_max + dy_data)
            self.draw()

            # Update pan start for continuous panning
            self.pan_start = (event.x, event.y)

    def on_release(self, event):
        """Handle mouse release events."""
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
