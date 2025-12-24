#!/usr/bin/env python3

import sys
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import API client
try:
    from api_client import get_yearly_data, EINK_DEVICE_TOKEN as API_DEFAULT_TOKEN
    USE_API = True
except ImportError:
    print("Warning: api_client not found, using sample data")
    USE_API = False
    API_DEFAULT_TOKEN = ''

# Device token - set this from environment variable, api_client, or config file
DEVICE_TOKEN = os.getenv('EINK_DEVICE_TOKEN', '') or API_DEFAULT_TOKEN

# E-ink display (optional - only needed for actual hardware)
USE_EINK_DISPLAY = False  # Set to True if you have e-ink hardware
if USE_EINK_DISPLAY:
    try:
        sys.path.insert(0, '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib')
        from waveshare_epd import epd7in5_V2
        EINK_AVAILABLE = True
    except ImportError:
        print("Warning: e-ink library not found, will export PNG instead")
        EINK_AVAILABLE = False
else:
    EINK_AVAILABLE = False

# Display dimensions (7.5" e-ink display)
EPD_WIDTH = 800
EPD_HEIGHT = 480

# Layout parameters
TITLE_FONT_SIZE = 24
MONTH_FONT_SIZE = 12
CELL_FONT_SIZE = 8  # Font size for date number (smaller for yearly view)
PANEL_MARGIN = 8
MONTH_SPACING = 4  # Space between months
CELL_SPACING = 1  # Space between day cells (smaller for yearly view)
DAY_HEADER_PADDING = 2  # Vertical padding for day header row (top and bottom)

TITLE_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONTH_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CELL_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def load_font(font_path, size):
    """
    Load font with fallback to default font if path doesn't exist.
    Works cross-platform (Linux/Windows).
    """
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()

USE_4GRAY_MODE = True

# Sample monthly hours per day (total hours worked that day)
# This will be used for all months - in real app, you'd have data per month
MONTHLY_HOURS = {
    1: 1.5,
    2: 3.0,
    3: 5.0,
    4: 7.5,
    5: 0.5,
    6: 2.5,
    7: 4.5,
    8: 6.5,
    9: 1.0,
    10: 3.5,
    11: 5.5,
    12: 7.0,
    13: 1.8,
    14: 2.2,
    15: 4.2,
    16: 6.2,
    17: 0.8,
    18: 2.8,
    19: 5.8,
    20: 7.8,
    21: 1.2,
    22: 3.2,
    23: 4.8,
    24: 6.8,
    25: 0.6,
    26: 2.6,
    27: 5.2,
    28: 6.0,
    29: 1.9,
    30: 3.9,
    31: 5.9,
}


def days_in_month(dt):
    first_day = dt.replace(day=1)
    next_month = first_day.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    return last_day.day

def calculate_hours_from_tasks(todos, month_date):
    """
    Calculate total hours per day from API tasks for a specific month.
    
    Args:
        todos: List of tasks from API
        month_date: Date in the month (datetime object)
    
    Returns:
        dict mapping day number to total hours
    """
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
            
            # Parse times
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

def get_yearly_hours_from_api(year):
    """
    Fetch yearly hours from API and transform to monthly hours format.
    Returns dict mapping (month, day) to hours.
    """
    if not USE_API or not DEVICE_TOKEN:
        print("Using sample data (API not configured)")
        return None
    
    try:
        print(f"Fetching data from API for year {year}...")
        data = get_yearly_data(DEVICE_TOKEN, year)
        
        if not data:
            print("No data received from API, using sample data")
            return None
        
        config = data.get('config', {})
        todos = data.get('todos', [])
        
        view_type = config.get('view_type', 'weekly')
        if view_type != 'yearly':
            print(f"Warning: View type is {view_type}, but yearly view is expected. Using yearly.")
        
        print(f"Received {len(todos)} tasks from API")
        
        # Group by month
        yearly_hours = {}
        for month in range(1, 13):
            month_date = datetime(year, month, 1)
            monthly_hours = calculate_hours_from_tasks(todos, month_date)
            yearly_hours[month] = monthly_hours
        
        return yearly_hours
        
    except Exception as e:
        print(f"Error fetching from API: {e}")
        print("Using sample data")
        return None


def main():
    today = datetime.now()
    year = today.year
    year_title = str(year)
    
    # Get yearly hours from API or use sample data
    YEARLY_HOURS_DATA = get_yearly_hours_from_api(year)
    
    if YEARLY_HOURS_DATA:
        print(f"Yearly hours loaded: {len(YEARLY_HOURS_DATA)} months with data")
    else:
        print("Using sample data for all months")

    # Initialize display (e-ink or create image)
    if USE_EINK_DISPLAY and EINK_AVAILABLE:
        print("Initializing e-ink display...")
        epd = epd7in5_V2.EPD()
        width = epd.width
        height = epd.height
    else:
        print("Creating image (PNG export mode)...")
        width = EPD_WIDTH
        height = EPD_HEIGHT
        epd = None

    WHITE = 255
    BLACK = 0
    
    # Gray levels for 4-gray mode
    GRAY_LEVEL_2 = 192  # Light grey
    GRAY_LEVEL_3 = 128  # Dark grey

    if USE_EINK_DISPLAY and EINK_AVAILABLE:
        if USE_4GRAY_MODE:
            epd.init_4Gray()
            print("4-gray mode initialized")
            print(f"Display GRAY1={epd.GRAY1}, GRAY2={epd.GRAY2}, GRAY3={epd.GRAY3}")
            epd.Clear()
            GRAY_LEVEL_2 = epd.GRAY2
            GRAY_LEVEL_3 = epd.GRAY3
        else:
            epd.init()
            epd.Clear()

    image = Image.new('L', (width, height), WHITE)
    draw = ImageDraw.Draw(image)

    # Load fonts with fallback
    title_font = load_font(TITLE_FONT_PATH, TITLE_FONT_SIZE)
    month_font = load_font(MONTH_FONT_PATH, MONTH_FONT_SIZE)
    cell_font = load_font(CELL_FONT_PATH, CELL_FONT_SIZE)

    # Title centered
    bbox = draw.textbbox((0, 0), year_title, font=title_font)
    title_x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((title_x, PANEL_MARGIN), year_title, font=title_font, fill=BLACK)

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

    # Day names (abbreviated for small calendar)
    day_names = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    cols = 7
    rows = 6  # Enough for any month

    # Draw each month
    for month in range(1, 13):
        month_row = (month - 1) // month_cols
        month_col = (month - 1) % month_cols
        
        month_x = grid_left + month_col * (month_width + MONTH_SPACING)
        month_y = grid_top + month_row * (month_height + MONTH_SPACING)
        
        # Month date object
        month_date = datetime(year, month, 1)
        month_name = month_date.strftime("%b")
        total_days = days_in_month(month_date)
        first_weekday = month_date.weekday()  # Monday=0
        
        # Month title
        month_bbox = draw.textbbox((0, 0), month_name, font=month_font)
        month_text_x = month_x + (month_width - (month_bbox[2] - month_bbox[0])) // 2
        draw.text((month_text_x, month_y), month_name, font=month_font, fill=BLACK)
        
        # Calendar grid within month
        month_header_height = MONTH_FONT_SIZE + 4
        calendar_top = month_y + month_header_height
        calendar_left = month_x
        calendar_width = month_width
        calendar_height = month_height - month_header_height
        
        # Day header row (very small)
        day_header_height = CELL_FONT_SIZE + DAY_HEADER_PADDING * 2
        cell_width = calendar_width / cols
        cell_height = (calendar_height - day_header_height) / rows
        
        # Draw day headers with padding
        day_header_y = calendar_top + DAY_HEADER_PADDING
        for i, day_name in enumerate(day_names):
            x = calendar_left + i * cell_width
            day_bbox = draw.textbbox((0, 0), day_name, font=cell_font)
            text_x = x + (cell_width - (day_bbox[2] - day_bbox[0])) // 2
            draw.text((text_x, day_header_y), day_name, font=cell_font, fill=BLACK)
        
        # Draw calendar cells (each day as a square)
        start_y = calendar_top + day_header_height
        for day in range(1, total_days + 1):
            offset = first_weekday + (day - 1)
            row = offset // cols
            col = offset % cols
            x0 = calendar_left + col * cell_width
            y0 = start_y + row * cell_height
            x1 = x0 + cell_width
            y1 = y0 + cell_height
            
            # Get hours for this day from API data or sample data
            if YEARLY_HOURS_DATA and month in YEARLY_HOURS_DATA:
                hours = YEARLY_HOURS_DATA[month].get(day, 0)
            else:
                hours = MONTHLY_HOURS.get(day, 0)
            
            # Cell rectangle with spacing (square shape)
            cell_size = min(cell_width, cell_height) - CELL_SPACING * 2
            center_x = (x0 + x1) / 2
            center_y = (y0 + y1) / 2
            rect = [
                int(center_x - cell_size / 2),
                int(center_y - cell_size / 2),
                int(center_x + cell_size / 2),
                int(center_y + cell_size / 2)
            ]
            
            # Assign background color based on hours: GRAY2 (light grey) if has hours, otherwise white
            bg_color = GRAY_LEVEL_2 if hours > 0 else WHITE
            
            # Draw background color
            draw.rectangle(rect, fill=bg_color, outline=None)
            
            # Day number (centered in square)
            # Use white text for dark grey background, black text for light grey or white
            text_color = WHITE if bg_color == GRAY_LEVEL_3 else BLACK
            day_label = str(day)
            day_bbox = draw.textbbox((0, 0), day_label, font=cell_font)
            day_text_x = center_x - (day_bbox[2] - day_bbox[0]) / 2
            day_text_y = center_y - (day_bbox[3] - day_bbox[1]) / 2
            draw.text((day_text_x, day_text_y), day_label, font=cell_font, fill=text_color)

    # Save as PNG or display on e-ink
    if USE_EINK_DISPLAY and EINK_AVAILABLE:
        print("Displaying on e-ink...")
        if USE_4GRAY_MODE:
            epd.display_4Gray(epd.getbuffer_4Gray(image))
        else:
            epd.display(epd.getbuffer(image.convert('1')))
        epd.sleep()
        print("Done!")
    else:
        # Export as PNG
        output_file = f"eink_yearly_{today.strftime('%Y%m%d_%H%M%S')}.png"
        # Convert to RGB for better PNG display (grayscale to RGB)
        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
        rgb_image.paste(image, (0, 0))
        rgb_image.save(output_file, 'PNG')
        print(f"Image saved as: {output_file}")
        print(f"   Size: {width}x{height} pixels")


if __name__ == "__main__":
    main()


