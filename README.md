# Hot Wire CNC G-code Generator GUI

A comprehensive PySide6-based GUI application for converting DXF files to optimized G-code for hot wire CNC foam cutting machines.

## Features

### Core Functionality
- **DXF File Loading**: Automatically detects DXF units ($INSUNITS) and converts to millimeters
- **Interactive Entity Selection**: Click on entities in the visualization to add them to cutting sequence
- **Drag & Drop Ordering**: Reorder cutting sequence by dragging items in the list widget
- **Multi-Selection Support**: Use Shift+Click or Ctrl+Click to select/deselect multiple entities
- **Real-time Path Visualization**: Preview complete tool path with numbered entities

### Advanced Cutting Path Control
- **First Path Direction**: Choose between "Left to Right →" or "← Right to Left" for initial cutting direction
- **Entity Customization**: Double-click entities to customize point count for curves (arcs, circles, splines)
- **Automatic Point Calculation**: Default points calculated based on max segment length for optimal quality
- **4-Axis G-code Generation**: Optimized for hot wire CNC with wire heating control

### Interactive Animation System
- **Constant Speed Animation**: Tool moves at realistic speed based on animation speed setting
- **Looping Animation**: Automatically restarts when complete for continuous preview
- **Pause/Resume Control**: Pause and resume animation at any point
- **Static G-Code Points Overlay**: Toggle to show/hide actual G-code points on animation canvas
- **Zoom & Pan Controls**: Interactive zoom and pan for both selection and animation views

### Advanced Visualization
- **Dual Canvas System**: Separate canvases for entity selection and path animation
- **Mouse Pan & Zoom**: Natural pan (drag) and zoom (scroll) with gesture filtering
- **Entity Highlighting**: Selected entities are highlighted in red with center markers
- **Grid Display**: Configurable grid for precise entity selection
- **Aspect Ratio Control**: Equal aspect ratio maintained for accurate geometry representation

### Parameter Control
- **Scale Factor**: Resize entire geometry with automatic unit conversion
- **X/Y Offset**: Translate cutting origin for precise positioning
- **Max Segment Length**: Controls curve discretization quality (affects point density)
- **Animation Speed**: Separate speed control for visualization (mm/s)
- **Feed Rate**: Cutting speed in G-code output (mm/min)
- **Wire Current**: Configurable wire heating current for G-code

### User Experience Features
- **Context-Sensitive Controls**: Buttons and options adapt based on current state
- **Real-time Updates**: Path regenerates automatically when parameters change
- **Error Handling**: Graceful handling of invalid inputs and file errors
- **Progress Feedback**: Visual feedback during file loading and processing
- **Compact Layout**: Efficient use of screen space with collapsible sections

## Installation

### Prerequisites
- Python 3.8 or higher
- PySide6-compatible system (Windows, macOS, Linux)

### Pre-built Executables

For users who prefer not to set up a Python environment, pre-built executables are available for Windows, macOS, and Linux. These standalone applications include all dependencies and can be run immediately without installation.

**Download the latest release** from the [GitHub Releases](https://github.com/JHU-DBF/HotWire_CNC_gcode_generator/releases) page.

### Setup (Development)

1. Create a virtual environment (recommended):

   ```bash
   python -m venv hotwire_env
   source hotwire_env/bin/activate  # On Windows: hotwire_env\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:

   ```bash
   python hotwire_gcode_app.py
   ```

## Usage Guide

### Basic Workflow
1. **Load DXF File**: Click "Load DXF File" to import your CAD drawing
2. **Select Entities**: Click on numbered entities in the selection plot to add them to cutting sequence
3. **Customize Direction**: Choose first path direction (Left to Right or Right to Left)
4. **Adjust Parameters**: Set scale, offsets, segment length, and other parameters
5. **Preview Animation**: Click "Animate" to visualize the cutting sequence
6. **Fine-tune**: Use "Show G-Code Points" to overlay actual cutting points
7. **Generate G-code**: Click "Generate and Save G-Code" to export the final file

### Advanced Features

#### Entity Customization
- Double-click any entity in the cutting sequence list
- For curves (arcs, circles, splines): Adjust the number of points
- Default values are calculated based on max segment length for optimal quality
- LINE entities cannot be customized (they only have 2 points)

#### Multi-Selection
- **Shift+Click**: Select range of entities
- **Ctrl+Click**: Toggle individual entity selection
- **Remove Selected**: Remove all selected entities at once

#### Animation Controls
- **Zoom In/Out/Fit**: Control animation view independently
- **Show G-Code Points**: Toggle actual cutting points overlay
- **Pause/Resume**: Control animation playback
- **Animation Speed**: Adjust visualization speed (separate from cutting speed)

#### Interactive Navigation
- **Pan**: Click and drag to move the view
- **Zoom**: Mouse wheel to zoom in/out
- **Selection Protection**: Pan/zoom gestures don't interfere with entity selection

## Parameters Reference

| Parameter | Description | Units | Default |
|-----------|-------------|-------|---------|
| Scale Factor | Resize entire geometry | - | 1.0 |
| X/Y Offset | Translate cutting origin | mm | 0.0 |
| Max Segment Length | Curve discretization quality | mm | 0.05 |
| Animation Speed | Visualization speed | mm/s | 50.0 |
| Feed Rate | Cutting speed in G-code | mm/min | 120 |
| Wire Current | Heating current | A | 1000 |

## Supported DXF Entities

- **Lines**: Straight cuts with exact endpoints
- **Arcs**: Curved cuts with configurable point density
- **Circles**: Full circular cuts with adaptive segmentation
- **Polylines**: Complex multi-segment paths (LW and regular)
- **Splines**: Smooth curves with B-spline reconstruction

## G-code Output Specifications

The generated G-code is optimized for 4-axis hot wire CNC machines:
- **Coordinate System**: X, Y for position, A/B for wire angles
- **Wire Control**: Automatic heating on/off commands
- **Path Optimization**: Minimizes non-cutting travel
- **Precision**: High-resolution point output based on segment length
- **Safety**: Includes proper G-code headers and comments

## Troubleshooting

### Common Issues
- **Import Errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`)
- **No Entities Visible**: Check DXF file contains supported entity types
- **Click Detection Issues**: Click closer to numbered entity labels
- **Animation Performance**: Reduce max segment length for complex geometries
- **Memory Issues**: Large DXF files may require more RAM

### File Format Notes
- Automatically detects DXF units via $INSUNITS header
- Supports DXF versions R12 through R2018
- Binary DXF files are supported
- Large files (>100MB) may require significant processing time

## Technical Architecture

### Core Components
- **MatplotlibCanvas**: Custom canvas class with pan/zoom and gesture handling
- **HotWireGCodeApp**: Main application window with PySide6 UI
- **Entity Processing**: DXF parsing and geometry conversion
- **Path Generation**: Optimized cutting path creation with direction control
- **Animation System**: Real-time path visualization with constant speed

### Key Algorithms
- **Curve Discretization**: Adaptive point generation based on segment length
- **Path Optimization**: Entity reordering for minimal travel distance
- **Unit Conversion**: Automatic scaling based on DXF unit detection
- **Animation Timing**: Constant speed calculation with distance-based timing

## Development Notes

This application uses modern Python practices:
- Type hints and comprehensive error handling
- Modular design with clear separation of concerns
- Extensive use of constants for maintainability
- Comprehensive documentation and user feedback

## License

This software is provided as-is for educational and research purposes in the hot wire CNC cutting domain.