# HotWire CNC G-code Generator

This repository contains a Python-based toolset for generating G-code for 4-axis hot wire CNC machines. It provides functionality to import DXF files, visualize entities, optimize cutting paths, and generate G-code for hotwire foam cutting.

## Features

- **DXF File Import**: Load and parse standard DXF files to extract entities (lines, arcs, circles, polylines, splines)
- **Entity Visualization**: Interactive plotting of all entities with color coding by entity type
- **Manual Path Ordering**: Define custom cutting order for complex profiles
- **Path Optimization**: Automatically optimize cutting paths to minimize movement
- **Toolpath Animation**: Interactive visualization of the cutting process before generation
- **G-code Generation**: Output standard G-code compatible with most hot wire CNC controllers

## Requirements

- Python 3.6+
- Required packages:
  - ezdxf
  - numpy
  - matplotlib
  - scipy (for advanced spline handling)
  - IPython (for notebook interface)

## Installation

```
# Clone the repository
git clone https://github.com/yourusername/hotwire-gcode-generator.git
cd hotwire-gcode-generator
```

# Install dependencies
```
pip install ezdxf numpy matplotlib scipy ipython
```

## Usage

### Quick Start

The easiest way to use this tool is through the included Jupyter notebook:

```
jupyter notebook hotwire_gcode.ipynb
```

### Basic Workflow

1. **Import DXF file**
   ```
   entities = read_cad_file("your_design.dxf")
   ```

2. **Visualize the entities**
   ```
   plot_entities(entities)
   ```

3. **Define cutting order manually**
   ```
   order = [13, 9, 10, 7, 8, 1, 2, 3, 4, 12]  # Entity indices
   points = manual_order_path(entities, order)
   ```

4. **Scale and adjust as needed**
   ```
   points = np.array(points)
   points = points * 25.4  # Convert from inches to mm
   points[:, 0] -= points[:, 0].min()  # Shift to start at x=0
   ```

5. **Visualize the cutting path**
   ```
   plt.scatter(*zip(*points), c=np.linspace(0, 1, len(points)), cmap="viridis", s=0.5)
   plt.colorbar(label="Path order")
   plt.gca().set_aspect("equal", adjustable="box")
   plt.show()
   ```

6. **Animate the toolpath**
   ```
   ani = animate_tool_path(points, tool_speed=0.5, tool_size=0.025, fps=30)
   from IPython.display import HTML
   HTML(ani.to_jshtml())
   ```

7. **Generate G-code**
   ```
   gcode = generate_gcode(points, feed_rate=200.0, wire_current=1000)
   with open("output.ngc", "w") as f:
       f.write("\n".join(gcode))
   ```

## Key Functions

- `read_cad_file(file_path)`: Import DXF files and extract entities
- `entity_to_points(entity, scale=1.0)`: Convert DXF entities to point lists
- `plot_entities(entities)`: Visualize all entities with type identification
- `manual_order_path(entities, order)`: Create a cutting path with custom entity order
- `animate_tool_path(points)`: Generate an interactive animation of the cutting process
- `generate_gcode(points, feed_rate, wire_current)`: Create G-code for the cutting path

## G-code Output

The generated G-code includes:
- Standard setup commands (G17, G21, G90, etc.)
- Wire heating control (M3/M5)
- 4-axis synchronized movement (X,Y for one end, A,Z for the other)
- Feed rate and dwell time control

Example:
```
G0 X0.000 Y10.000 A0.000 Z10.000; Rapid move to start position
G1 X20.000 Y15.000 A20.000 Z15.000
G1 X40.000 Y12.000 A40.000 Z12.000
```

## Performance Notes

For large files or complex animations, you may experience performance issues. Some tips:

- Reduce the number of points in arcs and splines by adjusting `points_per_arc`
- Lower the `fps` parameter in animations for smoother playback
- Use the optimized animation function for large point sets

## Contact

Developed by Koji  
Email: dbf@koji.space

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.