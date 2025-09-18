#!/usr/bin/env python3
"""
Launcher script for Hot Wire CNC G-code Generator GUI

Checks for dependencies and installs them if needed, then launches the application.
"""

import sys
import subprocess
import importlib.util


def check_package(package_name):
    """Check if a package is installed."""
    spec = importlib.util.find_spec(package_name)
    return spec is not None


def install_package(package_name):
    """Install a package using pip."""
    print(f"Installing {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"Successfully installed {package_name}")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to install {package_name}")
        return False


def main():
    """Main launcher function."""
    print("Hot Wire CNC G-code Generator - Checking dependencies...")

    # Required packages
    packages = {"numpy": "numpy", "PySide6": "PySide6", "matplotlib": "matplotlib", "ezdxf": "ezdxf"}

    missing_packages = []

    # Check for missing packages
    for module_name, package_name in packages.items():
        if not check_package(module_name):
            missing_packages.append(package_name)
            print(f"Missing: {package_name}")
        else:
            print(f"Found: {package_name}")

    # Install missing packages
    if missing_packages:
        print(f"\nInstalling {len(missing_packages)} missing packages...")
        for package in missing_packages:
            if not install_package(package):
                print(f"Error: Failed to install {package}")
                print("Please install manually with: pip install " + " ".join(missing_packages))
                return 1
        print("All dependencies installed successfully!")
    else:
        print("All dependencies are available.")

    # Launch the application
    print("\nLaunching Hot Wire CNC G-code Generator...")
    try:
        import hotwire_gcode_app

        hotwire_gcode_app.main()
    except Exception as e:
        print(f"Error launching application: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
