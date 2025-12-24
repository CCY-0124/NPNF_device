#!/usr/bin/env python3
"""
Dual Yearly View Renderer
Yearly calendar showing 12 months in a grid
"""

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Display dimensions
EPD_WIDTH = 800
EPD_HEIGHT = 480

# Layout parameters
TITLE_FONT_SIZE = 24
MONTH_FONT_SIZE = 12
CELL_FONT_SIZE = 8
PANEL_MARGIN = 8
MONTH_SPACING = 4
CELL_SPACING = 1
DAY_HEADER_PADDING = 2

FONT_PATHS = {
    'title': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'month': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'cell': "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}

# Colors
WHITE = 255
BLACK = 0
GRAY_LEVEL_2 = 192
GRAY_LEVEL_3 = 128

def days_in_month(dt):
    """Get number of days in a month"""
    first_day = dt.replace(day=1)
    next_month = first_day.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return last_day.day

def calculate_hours_from_tasks(todos: List[Dict], month_date: datetime) -> Dict[int, float]:
    """Calculate total hours per day from API tasks for a specific month"""
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
        'month': MONTH_FONT_SIZE,
        'cell': CELL_FONT_SIZE,
    }
    
    for name, path in FONT_PATHS.items():
        size = font_sizes.get(name, 12)
        try:
            fonts[name] = ImageFont.truetype(path, size)
        except:
            fonts[name] = ImageFont.load_default()
    
    return fonts

def render_dual_yearly(data: Dict[str, Any], config: Dict[str, Any]) -> Image.Image:
    """
    Render yearly calendar view showing 12 months
    
    Args:
        data: {'todos': [...]} - Task data from API
        config: Device configuration
    
    Returns:
        PIL Image ready for display
    """
    todos = data.get('todos', [])
    today = datetime.now()
    year = today.year
    year_title = str(year)
    
    # Group tasks by month
    yearly_hours = {}
    for month in range(1, 13):
        month_date = datetime(year, month, 1)
        monthly_hours = calculate_hours_from_tasks(todos, month_date)
        yearly_hours[month] = monthly_hours
    
    fonts = load_fonts()
    
    width = EPD_WIDTH
    height = EPD_HEIGHT
    image = Image.new('L', (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    
    # Title
    bbox = draw.textbbox((0, 0), year_title, font=fonts['title'])
    title_x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((title_x, PANEL_MARGIN), year_title, font=fonts['title'], fill=BLACK)
    
    # Grid: 3 rows, 4 columns for 12 months
    title_height = TITLE_FONT_SIZE + PANEL_MARGIN + 10
    grid_top = title_height
    grid_left = PANEL_MARGIN
    grid_width = width - 2 * PANEL_MARGIN
    grid_height = height - grid_top - PANEL_MARGIN
    
    month_rows = 3
    month_cols = 4
    month_width = (grid_width - (month_cols - 1) * MONTH_SPACING) / month_cols
    month_height = (grid_height - (month_rows - 1) * MONTH_SPACING) / month_rows
    
    day_names = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    cols = 7
    rows = 6
    
    # Draw each month
    for month in range(1, 13):
        month_row = (month - 1) // month_cols
        month_col = (month - 1) % month_cols
        
        month_x = grid_left + month_col * (month_width + MONTH_SPACING)
        month_y = grid_top + month_row * (month_height + MONTH_SPACING)
        
        month_date = datetime(year, month, 1)
        month_name = month_date.strftime("%b")
        total_days = days_in_month(month_date)
        first_weekday = month_date.weekday()
        
        # Month title
        month_bbox = draw.textbbox((0, 0), month_name, font=fonts['month'])
        month_text_x = month_x + (month_width - (month_bbox[2] - month_bbox[0])) // 2
        draw.text((month_text_x, month_y), month_name, font=fonts['month'], fill=BLACK)
        
        # Calendar grid within month
        month_header_height = MONTH_FONT_SIZE + 4
        calendar_top = month_y + month_header_height
        calendar_left = month_x
        calendar_width = month_width
        calendar_height = month_height - month_header_height
        
        day_header_height = CELL_FONT_SIZE + DAY_HEADER_PADDING * 2
        cell_width = calendar_width / cols
        cell_height = (calendar_height - day_header_height) / rows
        
        # Draw day headers
        day_header_y = calendar_top + DAY_HEADER_PADDING
        for i, day_name in enumerate(day_names):
            x = calendar_left + i * cell_width
            day_bbox = draw.textbbox((0, 0), day_name, font=fonts['cell'])
            text_x = x + (cell_width - (day_bbox[2] - day_bbox[0])) // 2
            draw.text((text_x, day_header_y), day_name, font=fonts['cell'], fill=BLACK)
        
        # Draw calendar cells
        start_y = calendar_top + day_header_height
        for day in range(1, total_days + 1):
            offset = first_weekday + (day - 1)
            row = offset // cols
            col = offset % cols
            x0 = calendar_left + col * cell_width
            y0 = start_y + row * cell_height
            x1 = x0 + cell_width
            y1 = y0 + cell_height
            
            hours = yearly_hours.get(month, {}).get(day, 0)
            
            cell_size = min(cell_width, cell_height) - CELL_SPACING * 2
            center_x = (x0 + x1) / 2
            center_y = (y0 + y1) / 2
            rect = [
                int(center_x - cell_size / 2),
                int(center_y - cell_size / 2),
                int(center_x + cell_size / 2),
                int(center_y + cell_size / 2)
            ]
            
            bg_color = GRAY_LEVEL_2 if hours > 0 else WHITE
            draw.rectangle(rect, fill=bg_color, outline=None)
            
            # Day number
            text_color = WHITE if bg_color == GRAY_LEVEL_3 else BLACK
            day_label = str(day)
            day_bbox = draw.textbbox((0, 0), day_label, font=fonts['cell'])
            day_text_x = center_x - (day_bbox[2] - day_bbox[0]) / 2
            day_text_y = center_y - (day_bbox[3] - day_bbox[1]) / 2
            draw.text((day_text_x, day_text_y), day_label, font=fonts['cell'], fill=text_color)
    
    return image

