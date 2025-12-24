#!/usr/bin/env python3
"""
Simple Renderer System for E-ink Displays
Automatically discovers and loads render functions from render_*.py files
"""

import os
import importlib.util
from typing import Dict, Callable, Optional
from PIL import Image

# Display dimensions
EPD_WIDTH = 800
EPD_HEIGHT = 480

# Renderer registry: {view_type: render_function}
RENDERERS: Dict[str, Callable] = {}

def load_renderers():
    """Automatically discover and load all render_*.py files"""
    global RENDERERS
    
    # Get directory where this file is located
    renderers_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Scan for render_*.py files
    for filename in os.listdir(renderers_dir):
        if filename.startswith('render_') and filename.endswith('.py'):
            # Extract view type from filename: render_weekly.py -> weekly
            view_type = filename[7:-3]  # Remove 'render_' prefix and '.py' suffix
            
            # Skip if already loaded
            if view_type in RENDERERS:
                continue
            
            # Load the module
            filepath = os.path.join(renderers_dir, filename)
            try:
                spec = importlib.util.spec_from_file_location(f"render_{view_type}", filepath)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for render function: render_weekly, render_monthly, etc.
                    render_func_name = f"render_{view_type}"
                    if hasattr(module, render_func_name):
                        RENDERERS[view_type] = getattr(module, render_func_name)
                        print(f"Loaded renderer: {view_type}")
                    else:
                        print(f"Warning: {filename} found but no {render_func_name} function")
            except Exception as e:
                print(f"Warning: Failed to load {filename}: {e}")

def get_renderer(view_type: str) -> Optional[Callable]:
    """Get render function for a view type"""
    return RENDERERS.get(view_type)

def list_renderers():
    """List all available renderers"""
    return list(RENDERERS.keys())

# Auto-load on import
load_renderers()
