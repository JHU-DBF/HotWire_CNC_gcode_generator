3D Hotwire G-Code Application - Implementation Plan (Revised)
1. High-Level Goal

(Unchanged) Extend the 2D DXF-to-G-code application to support 3D models from STEP files, allowing users to select geometry and generate 4-axis G-code with advanced path control.
2. Analysis of User Workflow (Revised)

The workflow now incorporates advanced path controls and more detailed visualization options, while maintaining a clear, step-by-step process.

Workflow Comparison:

Step
	

2D Mode (DXF)
	

3D Mode (STEP)

1. Load File
	

User clicks "Load File", selects a .dxf file. UI switches to 2D mode.
	

User clicks "Load File", selects a .step file. UI switches to 3D mode.

2. Select Geometry
	

The 2D entities appear. The user clicks on entities in the plot to select them.
	

A "Profile Selector" pop-up appears, showing the 3D model with numbered faces. The user selects the faces that define the left and right profiles by clicking the numbers on the plot.

3. Sequence Toolpath
	

Selected entities appear in the "Cutting Sequence" list for ordering.
	

The pop-up closes. The main 3D view displays the edges from the selected faces, colored and numbered. The user clicks on the 3D edges to add them to the left and right "Cutting Sequence" lists.

4. Add Path Modifiers
	

N/A
	

The user clicks "Add Lead-in" or "Add Lead-out". A dialog appears to set X/Y distances. This adds a special "Lead" item to the lists. Dragging a "Lead" item to the start/end of a list automatically changes its type, with a notification pop-up.

5. Visualize & Generate
	

The bottom panel shows the 2D animation. User generates G-code.
	

The user can now click "Show Wire Length Plot" to see a graph in a new window. The bottom panel can be toggled between a 2D toolpath animation and a full 3D animation. The user generates the final G-code.
3. Detailed Implementation Steps (Revised)
Phase 1: UI Unification and Advanced Controls

    Unified File Loading & Mode Switching:

        A single "Load File" button will open a QFileDialog that accepts both *.dxf and *.step files.

        The application will switch the UI mode and control panels based on the selected file's extension.

    Main Window Layout for 3D Mode:

        The main visualization area will be a vertical QSplitter.

            Top Panel: MatplotlibCanvas3D for interactive 3D profile edge selection. Must support full 3D navigation (rotate, pan, zoom) and entity picking.

            Bottom Panel: A QStackedWidget (self.animation_stack) containing two canvases:

                MatplotlibCanvas for the 2D toolpath animation.

                MatplotlibCanvas3D for the new 3D cutting animation.

    Revised 3D Control Panel (self.panel_3d):

        File & Parameters Group: "Load File" button, QLineEdits for "Gantry Gap (mm)" and "Y-Offset (mm)".

        Cutting Sequence Group:

            QListWidget (self.left_sequence_list) labeled "Left Profile Sequence".

            QListWidget (self.right_sequence_list) labeled "Right Profile Sequence".

            QPushButton ("Add Lead-in") and QPushButton ("Add Lead-out").

        Actions Group:

            QPushButton ("Animate Path").

            QRadioButtons to toggle the bottom panel view ("2D Animation", "3D Animation").

            QPushButton ("Show Wire Length Plot").

            QPushButton ("Generate G-Code").

Phase 2: New Dialogs for 3D Mode

    ProfileSelectorDialog(QDialog) Class:

        (Unchanged from previous plan) This pop-up is for selecting faces. It will feature a navigable 3D plot with clickable numbers, automatic left/right assignment based on Y-coordinates, and drag-and-drop lists for correction.

    LeadInOutDialog(QDialog) Class (New):

        A simple modal dialog launched by the "Add Lead-in/out" buttons.

        Contains QLineEdits for "X Distance (mm)" and "Y Distance (mm)".

        Returns the X/Y values upon clicking "OK".

    WireLengthDialog(QDialog) Class (New):

        A non-modal dialog to display the wire length analysis.

        Contains a MatplotlibCanvas that will be populated with the wire length plot, including max, min, and average lines, similar to the notebook visualization.

Phase 3: Post-Selection and Lead-in/out Logic

    on_3d_entity_click Method: (Unchanged) Handles clicking on 3D edges in the top panel and adds them to the appropriate sequence list.

    add_leadinout Method (New):

        Connected to the "Add Lead-in/out" buttons.

        Opens the LeadInOutDialog.

        On "OK", it adds a special item to the currently active sequence list (e.g., "Lead-in (X:10, Y:0)").

    Smart Drag-and-Drop Logic (New):

        The rowsMoved signal handler for the sequence QListWidgets will be enhanced.

        It will check the text of the moved item. If it starts with "Lead-".

        It checks the new row index. If the item is now at row 0 and its text is "Lead-out", it will automatically change the text to "Lead-in".

        If the item is now at the last row and its text is "Lead-in", it will change it to "Lead-out".

        In either case of an automatic change, a QMessageBox.information() pop-up will appear to notify the user (e.g., "Lead-out was moved to the start and has been converted to a Lead-in.").

Phase 4: G-Code and New Visualizations

    generate_cutting_path_3d Method:

        Must be updated to parse the "Lead-in/out" items from the sequence lists.

        It will calculate the start/end points of the main path and prepend/append the straight-line lead-in/out moves based on the specified X/Y distances.

    show_wire_length_plot Method (New):

        This method will first call the path generation logic to get the final XYAZ coordinates.

        It will then call a new calculate_hotwire_lengths function (ported from the notebook).

        Finally, it will instantiate the WireLengthDialog, generate the plot on its canvas, and show the window.

    animate_path_3d Method (New):

        This method will generate a 3D animation of the gantry movements in the bottom panel's 3D canvas.

        It will show both gantry paths (XY and AZ) in 3D space, connected by a line representing the hot wire, closely mimicking the notebook's 3D animation.

4. Revised Class Structure

# ... imports ...

class ProfileSelectorDialog(QDialog): ...
class LeadInOutDialog(QDialog): ...
class WireLengthDialog(QDialog): ...

class HotWireGCodeApp(QMainWindow):
    def __init__(self): ...
    
    def setup_ui(self):
        # ... Main window with vertical splitter and stacked widgets ...

    def on_file_loaded(self): ...
    
    def setup_3d_mode(self, path): ...
    
    def update_profiles_from_faces(self, face_lists): ...
    
    def plot_3d_profiles(self): ...
    
    def on_3d_entity_click(self, event): ...

    def add_leadinout(self, lead_type): # new
        # Opens LeadInOutDialog and adds item to list.

    def on_sequence_item_moved(self): # new
        # Handles smart re-ordering of lead-in/out items.

    def generate_cutting_path_3d(self): # updated
        # Now parses lead-in/out items.
    
    def animate_path_3d(self): # new
        # Logic for 3D animation in the bottom panel.

    def show_wire_length_plot(self): # new
        # Calculates lengths and shows WireLengthDialog.

    # ... other methods ...

This comprehensive plan incorporates your latest feedback, creating a powerful, flexible, and intuitive application for both 2D and 3D hot wire cutting.