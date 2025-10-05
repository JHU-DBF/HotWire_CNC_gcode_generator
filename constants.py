#!/usr/bin/env python3
"""
Constants and configuration values for the Hot Wire CNC G-code Generator.
"""

# Animation and UI constants
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

# Entry/Exit configuration system (from notebook)
ENTRY_EXIT_CONFIG = {
    101: {"type": "entry", "distance": [10, 0]},
    102: {"type": "exit", "distance": [-10, 0]},
    103: {"type": "entry", "distance": [-10, 0]},
    104: {"type": "exit", "distance": [10, 0]},
    105: {"type": "entry", "distance": [0, -10]},
    106: {"type": "exit", "distance": [0, 10]},
}

# DXF units mapping
DXF_UNITS_TO_MM = {
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
