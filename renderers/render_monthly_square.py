#!/usr/bin/env python3
"""
Monthly Square View Renderer
Monthly calendar with hours displayed as squares (2 per row)
"""

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Display dimensions
EPD_WIDTH = 800
EPD_HEIGHT = 480

# Layout parameters
TITLE_FONT_SIZE = 20
HEADER_FONT_SIZE = 14
CELL_FONT_SIZE = 14
PANEL_MARGIN = 8
HEADER_HEIGHT = 26
TITLE_HEIGHT = 28
CELL_SPACING = 2

FONT_PATHS = {
    'title': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'header': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'cell': "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}

# Colors
WHITE = 255
BLACK = 0
GRAY_LEVEL_2 = 128
GRAY_LEVEL_3 = 192

def days_in_month(dt):
    """Get number of days in a month"""
    first_day = dt.replace(day=1)
    next_month = first_day.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return last_day.day

def calculate_hours_from_tasks(todos: List[Dict], month_date: datetime) -> Dict[int, float]:
    """Calculate total hours per day from API tasks"""
    hours_by_day = {}
    first_day = month_date.replace(day=1)
    last_day = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    
    for task in todos:
        if not task.get('start_time') or not task.get('end_time') or not task.get('start_date'):
            continue
        
        try:
            task_date = datetime.strptime(task['start_date'], '%Y-%m-%d')
            if task_date < first_day or task_date > last_day:
                continue
            
            start_parts = task['start_time'].split(':')
            end_parts = task['end_time'].split(':')
            start_h, start_m = int(start_parts[0]), int(start_parts[1])
            end_h, end_m = int(end_parts[0]), int(end_parts[1])
            
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            
            duration_hours = (end_minutes - start_minutes) / 60.0
            day = task_date.day
            hours_by_day[day] = hours_by_day.get(day, 0) + duration_hours
        except Exception:
            continue
    
    return hours_by_day

def load_fonts():
    """Load fonts with fallback"""
    fonts = {}
    font_sizes = {
        'title': TITLE_FONT_SIZE,
        'header': HEADER_FONT_SIZE,
        'cell': CELL_FONT_SIZE,
    }
    
    for name, path in FONT_PATHS.items():
        size = font_sizes.get(name, 12)
        try:
            fonts[name] = ImageFont.truetype(path, size)
        except:
            fonts[name] = ImageFont.load_default()
    
    return fonts

def render_monthly_square(data: Dict[str, Any], config: Dict[str, Any]) -> Image.Image:
    """
    Render monthly calendar with hours as squares (2 per row)
    
    Args:
        data: {'todos': [...]} - Task data from API
        config: Device configuration
    
    Returns:
        PIL Image ready for display
    """
    todos = data.get('todos', [])
    today = datetime.now()
    first_day = today.replace(day=1)
    total_days = days_in_month(today)
    first_weekday = first_day.weekday()
    month_title = first_day.strftime("%B %Y")
    
    monthly_hours = calculate_hours_from_tasks(todos, first_day)
    fonts = load_fonts()
    
    width = EPD_WIDTH
    height = EPD_HEIGHT
    image = Image.new('L', (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    
    # Title
    bbox = draw.textbbox((0, 0), month_title, font=fonts['title'])
    title_x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((title_x, PANEL_MARGIN), month_title, font=fonts['title'], fill=BLACK)
    
    # Grid dimensions
    grid_top = PANEL_MARGIN + TITLE_HEIGHT
    grid_left = PANEL_MARGIN
    grid_width = width - 2 * PANEL_MARGIN
    grid_height = height - grid_top - PANEL_MARGIN
    
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    cols = 7
    rows = 6
    cell_width = grid_width / cols
    cell_height = (grid_height - HEADER_HEIGHT) / rows
    
    # Day-of-week headers
    for i, day_name in enumerate(day_names):
        x = grid_left + i * cell_width
        bbox = draw.textbbox((0, 0), day_name, font=fonts['header'])
        text_x = x + (cell_width - (bbox[2] - bbox[0])) // 2
        text_y = grid_top
        draw.text((text_x, text_y), day_name, font=fonts['header'], fill=BLACK)
    
    # Draw calendar cells
    start_y = grid_top + HEADER_HEIGHT
    for day in range(1, total_days + 1):
        offset = first_weekday + (day - 1)
        row = offset // cols
        col = offset % cols
        x0 = grid_left + col * cell_width
        y0 = start_y + row * cell_height
        x1 = x0 + cell_width
        y1 = y0 + cell_height
        
        hours = monthly_hours.get(day, 0)
        
        rect = [
            int(x0) + CELL_SPACING,
            int(y0) + CELL_SPACING,
            int(x1) - CELL_SPACING,
            int(y1) - CELL_SPACING
        ]
        
        draw.rectangle(rect, fill=GRAY_LEVEL_3, outline=None)
        
        # Day number
        day_label = str(day)
        bbox = draw.textbbox((0, 0), day_label, font=fonts['cell'])
        draw.text((rect[0] + 4, rect[1] + 2), day_label, font=fonts['cell'], fill=BLACK)
        
        # Hours as squares (2 per row)
        if hours > 0:
            rounded_hours = round(hours * 2) / 2.0
            total_squares = int(rounded_hours * 2)
            
            square_size = 5
            spacing = 2
            row_spacing = 2
            start_x = rect[2] - 6
            bottom_y = rect[3] - 4
            
            row_y = bottom_y
            remaining_squares = total_squares
            
            while remaining_squares > 0:
                squares_in_row = min(2, remaining_squares)
                x = start_x
                for _ in range(squares_in_row):
                    square_coords = [x - square_size, row_y - square_size, x, row_y]
                    draw.rectangle(square_coords, fill=BLACK, outline=None)
                    x -= (square_size + spacing)
                
                remaining_squares -= squares_in_row
                row_y -= (square_size + row_spacing)
    
    return image

