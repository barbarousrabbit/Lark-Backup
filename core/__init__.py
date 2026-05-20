"""
Core functionality module package
"""
# Add the parent directory to sys.path to avoid repeating this in every module
import os
import sys

# Only add the parent directory to sys.path when imported as a package
if __name__ != "__main__":
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)