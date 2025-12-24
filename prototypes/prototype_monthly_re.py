#!/usr/bin/env python3

import sys
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import API client
try:
    from api_client import get_monthly_data, EINK_DEVICE_TOKEN as API_DEFAULT_TOKEN
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
TITLE_FONT_SIZE = 20
HEADER_FONT_SIZE = 14
CELL_FONT_SIZE = 14  # Font size for date number
PANEL_MARGIN = 8
HEADER_HEIGHT = 26
TITLE_HEIGHT = 28
CELL_SPACING = 2  # Space between cells

TITLE_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
HEADER_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
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
    Calculate total hours per day from API tasks.
    
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

def get_monthly_hours_from_api(month_date):
    """
    Fetch monthly hours from API and transform to MONTHLY_HOURS format.
    Returns dict mapping day number to hours.
    """
    if not USE_API or not DEVICE_TOKEN:
        print("Using sample data (API not configured)")
        return MONTHLY_HOURS
    
    try:
        print(f"Fetching data from API for month {month_date.strftime('%Y-%m')}...")
        data = get_monthly_data(DEVICE_TOKEN, month_date)
        
        if not data:
            print("No data received from API, using sample data")
            return MONTHLY_HOURS
        
        config = data.get('config', {})
        todos = data.get('todos', [])
        
        view_type = config.get('view_type', 'weekly')
        if view_type != 'monthly':
            print(f"Warning: View type is {view_type}, but monthly view is expected. Using monthly.")
        
        print(f"Received {len(todos)} tasks from API")
        hours_by_day = calculate_hours_from_tasks(todos, month_date)
        return hours_by_day
        
    except Exception as e:
        print(f"Error fetching from API: {e}")
        print("Using sample data")
        return MONTHLY_HOURS


def main():
    today = datetime.now()
    first_day = today.replace(day=1)
    total_days = days_in_month(today)
    first_weekday = first_day.weekday()  # Monday=0
    month_title = first_day.strftime("%B %Y")
    
    # Get monthly hours from API or use sample data
    MONTHLY_HOURS_DATA = get_monthly_hours_from_api(first_day)
    
    print(f"Monthly hours loaded: {len(MONTHLY_HOURS_DATA)} days with data")

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
    GRAY_LEVEL_1 = 80   # Dark grey
    GRAY_LEVEL_2 = 128  # Medium grey
    GRAY_LEVEL_3 = 192  # Light grey

    if USE_EINK_DISPLAY and EINK_AVAILABLE:
        if USE_4GRAY_MODE:
            epd.init_4Gray()
            print("4-gray mode initialized")
            print(f"Display GRAY1={epd.GRAY1}, GRAY2={epd.GRAY2}, GRAY3={epd.GRAY3}")
            epd.Clear()
            GRAY_LEVEL_1 = epd.GRAY1
            GRAY_LEVEL_2 = epd.GRAY2
            GRAY_LEVEL_3 = epd.GRAY3
        else:
            epd.init()
            epd.Clear()

    image = Image.new('L', (width, height), WHITE)
    draw = ImageDraw.Draw(image)

    # Load fonts with fallback
    title_font = load_font(TITLE_FONT_PATH, TITLE_FONT_SIZE)
    header_font = load_font(HEADER_FONT_PATH, HEADER_FONT_SIZE)
    cell_font = load_font(CELL_FONT_PATH, CELL_FONT_SIZE)

    # Title centered
    bbox = draw.textbbox((0, 0), month_title, font=title_font)
    title_x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((title_x, PANEL_MARGIN), month_title, font=title_font, fill=BLACK)

    # Grid dimensions
    grid_top = PANEL_MARGIN + TITLE_HEIGHT
    grid_left = PANEL_MARGIN
    grid_width = width - 2 * PANEL_MARGIN
    grid_height = height - grid_top - PANEL_MARGIN

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    cols = 7
    rows = 6  # Enough for any month
    cell_width = grid_width / cols
    cell_height = (grid_height - HEADER_HEIGHT) / rows

    # Day-of-week headers
    for i, day_name in enumerate(day_names):
        x = grid_left + i * cell_width
        bbox = draw.textbbox((0, 0), day_name, font=header_font)
        text_x = x + (cell_width - (bbox[2] - bbox[0])) // 2
        text_y = grid_top
        draw.text((text_x, text_y), day_name, font=header_font, fill=BLACK)

    # Draw calendar cells with frames (each day separated)
    start_y = grid_top + HEADER_HEIGHT
    for day in range(1, total_days + 1):
        offset = first_weekday + (day - 1)
        row = offset // cols
        col = offset % cols
        x0 = grid_left + col * cell_width
        y0 = start_y + row * cell_height
        x1 = x0 + cell_width
        y1 = y0 + cell_height

        hours = MONTHLY_HOURS_DATA.get(day, 0)

        # Cell rectangle with spacing (each day separated from others)
        rect = [
            int(x0) + CELL_SPACING,
            int(y0) + CELL_SPACING,
            int(x1) - CELL_SPACING,
            int(y1) - CELL_SPACING
        ]

        # Draw light grey fill for each day (no outline)
        draw.rectangle(rect, fill=GRAY_LEVEL_2, outline=None)

        # Day number (bigger)
        day_label = str(day)
        bbox = draw.textbbox((0, 0), day_label, font=cell_font)
        draw.text((rect[0] + 4, rect[1] + 2), day_label, font=cell_font, fill=BLACK)

        # Hours as stacked rectangles (each rectangle = 1 hour, stacked bottom to top)
        if hours > 0:
            # Round to nearest 0.5 hours
            rounded_hours = round(hours * 2) / 2.0
            num_full_rects = int(rounded_hours)
            has_half = (rounded_hours - num_full_rects) >= 0.5
            
            # Rectangle dimensions for hour indicators (vertical stacking)
            rect_width = 18  # 50% wider (was 12)
            rect_height = 2  # Height of each rectangle (adjustable)
            rect_spacing = 2  # 1 pixel spacing between stacks
            start_x = rect[2] - 6  # Right side of cell
            bottom_y = rect[3] - 4  # Start from bottom
            
            # Draw full rectangles (1 hour each), stacking from bottom to top
            for i in range(num_full_rects):
                y_bottom = bottom_y - i * (rect_height + rect_spacing)
                y_top = y_bottom - rect_height
                hour_rect = [start_x - rect_width, y_top, start_x, y_bottom]
                draw.rectangle(hour_rect, fill=BLACK, outline=None)
            
            # Draw half rectangle if needed (half width)
            if has_half:
                y_bottom = bottom_y - num_full_rects * (rect_height + rect_spacing)
                y_top = y_bottom - rect_height
                hour_rect = [start_x - rect_width // 2, y_top, start_x, y_bottom]
                draw.rectangle(hour_rect, fill=BLACK, outline=None)

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
        output_file = f"eink_monthly_{today.strftime('%Y%m%d_%H%M%S')}.png"
        # Convert to RGB for better PNG display (grayscale to RGB)
        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
        rgb_image.paste(image, (0, 0))
        rgb_image.save(output_file, 'PNG')
        print(f"Image saved as: {output_file}")
        print(f"   Size: {width}x{height} pixels")


if __name__ == "__main__":
    main()
