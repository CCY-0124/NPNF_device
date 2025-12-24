#!/usr/bin/env python3

import sys
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import API client
try:
    from api_client import get_weekly_data, EINK_DEVICE_TOKEN as API_DEFAULT_TOKEN
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
TITLE_FONT_SIZE = 26
TITLE_PADDING = 15
DAY_FONT_SIZE = 14
TIME_FONT_SIZE = 12
TASK_FONT_SIZE = 12
DATETIME_FONT_SIZE = 24
CLOCK_FONT_SIZE = 36
PANEL_MARGIN = 5
HEADER_HEIGHT = 20
TIME_COL_WIDTH = 55
TABLE_MARGIN_BOTTOM = 5
FOOTER_PADDING = 40

# Font paths (Linux)
TITLE_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DAY_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TIME_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
TASK_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DATETIME_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
CLOCK_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

def load_font(font_path, size):
    """
    Load font with fallback to default font if path doesn't exist.
    Works cross-platform (Linux/Windows).
    """
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()

TIME_START_HOUR = 8
TIME_END_HOUR = 24
TIME_LABEL_X = 6
TIME_LABEL_Y_OFFSET = 4

USE_4GRAY_MODE = True

# Sample data (fallback if API is not available)
SAMPLE_TASKS = {
    'Monday': [
        {'start_time': '09:00', 'end_time': '10:30', 'title': 'Team Meeting'},
        {'start_time': '14:00', 'end_time': '16:00', 'title': 'Project Review'},
    ],
    'Tuesday': [
        {'start_time': '10:00', 'end_time': '11:00', 'title': 'Client Call'},
        {'start_time': '15:30', 'end_time': '17:00', 'title': 'Workshop'},
    ],
    'Wednesday': [
        {'start_time': '09:30', 'end_time': '10:00', 'title': 'Standup'},
        {'start_time': '13:00', 'end_time': '18:00', 'title': 'Development'},
    ],
    'Thursday': [
        {'start_time': '11:00', 'end_time': '12:30', 'title': 'Lunch Meeting'},
        {'start_time': '14:00', 'end_time': '15:00', 'title': 'Code Review'},
    ],
    'Friday': [
        {'start_time': '09:00', 'end_time': '12:00', 'title': 'Planning'},
        {'start_time': '16:00', 'end_time': '17:00', 'title': 'Weekly Review'},
    ],
}

SAMPLE_TODO_ITEMS = [
    "Order new modules",
    "Review PR #42",
    "Write tests for auth",
    "Plan next sprint",
]

def transform_api_tasks_to_weekly_format(api_todos, week_start_date):
    """
    Transform API task data to the weekly TASKS format.
    
    Args:
        api_todos: List of tasks from API (each has start_date, start_time, end_time, title, etc.)
        week_start_date: Monday date (datetime object)
    
    Returns:
        dict in format: {'Monday': [...], 'Tuesday': [...], ...}
    """
    tasks_by_day = {
        'Monday': [],
        'Tuesday': [],
        'Wednesday': [],
        'Thursday': [],
        'Friday': [],
        'Saturday': [],
        'Sunday': []
    }
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for task in api_todos:
        # Only include scheduled tasks with time
        if not task.get('start_time') or not task.get('end_time') or not task.get('start_date'):
            continue
        
        # Parse task date
        try:
            task_date = datetime.strptime(task['start_date'], '%Y-%m-%d')
        except:
            continue
        
        # Check if task is in this week
        week_end = week_start_date + timedelta(days=6)
        if task_date < week_start_date or task_date > week_end:
            continue
        
        # Get day of week (0=Monday, 6=Sunday)
        day_index = task_date.weekday()
        day_name = day_names[day_index]
        
        # Normalize time format (remove seconds if present: "14:30:00" -> "14:30")
        start_time = task['start_time']
        end_time = task['end_time']
        if len(start_time) > 5:  # Has seconds
            start_time = start_time[:5]
        if len(end_time) > 5:  # Has seconds
            end_time = end_time[:5]
        
        # Add task to appropriate day
        tasks_by_day[day_name].append({
            'start_time': start_time,
            'end_time': end_time,
            'title': task.get('title', 'Untitled')
        })
    
    return tasks_by_day

def get_tasks_from_api(week_start_date):
    """
    Fetch tasks from API and transform to weekly format.
    Returns TASKS dict or None on error.
    """
    if not USE_API or not DEVICE_TOKEN:
        print("Using sample data (API not configured)")
        return SAMPLE_TASKS
    
    try:
        print(f"Fetching data from API for week starting {week_start_date.strftime('%Y-%m-%d')}...")
        data = get_weekly_data(DEVICE_TOKEN, week_start_date)
        
        if not data:
            print("No data received from API, using sample data")
            return SAMPLE_TASKS
        
        config = data.get('config', {})
        todos = data.get('todos', [])
        
        view_type = config.get('view_type', 'weekly')
        if view_type != 'weekly':
            print(f"Warning: View type is {view_type}, but only weekly view is implemented. Using weekly.")
        
        print(f"Received {len(todos)} tasks from API")
        tasks = transform_api_tasks_to_weekly_format(todos, week_start_date)
        return tasks
        
    except Exception as e:
        print(f"Error fetching from API: {e}")
        print("Using sample data")
        return SAMPLE_TASKS

def main():
    today = datetime.now()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)
    week_title = f"{monday.strftime('%b %d')}-{sunday.strftime('%d, %Y')}"
    
    # Get tasks from API or use sample data
    TASKS = get_tasks_from_api(monday)
    TODO_ITEMS = SAMPLE_TODO_ITEMS  # TODO: Get from API later
    
    print(f"Tasks loaded: {sum(len(tasks) for tasks in TASKS.values())} total tasks")
    for day, tasks in TASKS.items():
        if tasks:
            print(f"  {day}: {len(tasks)} tasks")

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
        else:
            epd.init()
            epd.Clear()

    print("Creating dual-pane layout...")
    image = Image.new('L', (width, height), WHITE)
    draw = ImageDraw.Draw(image)

    # Load fonts with fallback
    title_font = load_font(TITLE_FONT_PATH, TITLE_FONT_SIZE)
    time_font = load_font(TIME_FONT_PATH, TIME_FONT_SIZE)
    day_font = load_font(DAY_FONT_PATH, DAY_FONT_SIZE)
    task_font = load_font(TASK_FONT_PATH, TASK_FONT_SIZE)
    datetime_font = load_font(DATETIME_FONT_PATH, DATETIME_FONT_SIZE)
    clock_font = load_font(CLOCK_FONT_PATH, CLOCK_FONT_SIZE)

    # Panels: left 60%, right 40%
    left_width = int(width * 0.6)
    right_x = left_width + PANEL_MARGIN
    right_width = max(0, width - right_x - PANEL_MARGIN)

    # Title centered over full width with padding
    bbox = draw.textbbox((0, 0), week_title, font=title_font)
    title_x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((title_x, TITLE_PADDING), week_title, font=title_font, fill=BLACK)

    # Table area
    table_start_y = HEADER_HEIGHT + TITLE_PADDING + TITLE_FONT_SIZE + 5
    table_start_x = TIME_COL_WIDTH
    table_width = left_width - table_start_x - PANEL_MARGIN
    table_height = height - table_start_y - TABLE_MARGIN_BOTTOM

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_col_width = table_width // len(day_names)

    for i, day_name in enumerate(day_names):
        x = table_start_x + i * day_col_width
        bbox = draw.textbbox((0, 0), day_name, font=day_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = x + (day_col_width - text_w) // 2
        text_y = table_start_y + (HEADER_HEIGHT - text_h) // 2
        draw.text((text_x, text_y), day_name, font=day_font, fill=BLACK)

    # Time slots
    time_slots = []
    time_labels = {}
    for hour in range(TIME_START_HOUR, TIME_END_HOUR):
        time_str = f"{hour:02d}:00"
        time_slots.append(time_str)
        time_labels[len(time_slots) - 1] = time_str
        time_slots.append(f"{hour:02d}:30")
    if TIME_END_HOUR == 24:
        time_slots.append("00:00")
        time_labels[len(time_slots) - 1] = "00:00"

    num_time_slots = len(time_slots)
    available_height = table_height - HEADER_HEIGHT
    row_height = available_height / num_time_slots

    def get_gray_level(duration_hours):
        # For tasks under 1 hour, use lightest gray (GRAY_LEVEL_3)
        if duration_hours <= 1.0:
            return GRAY_LEVEL_3
        elif duration_hours <= 3.0:
            return GRAY_LEVEL_2
        else:
            return GRAY_LEVEL_1

    def time_to_slot_index(time_str):
        try:
            # Handle both "14:30" and "14:30:00" formats
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            slot_index = (hour - TIME_START_HOUR) * 2
            if minute >= 30:
                slot_index += 1
            return max(0, slot_index)
        except:
            return 0

    def draw_tasks():
        if TASKS is None:
            return

        day_name_map = {
            'Monday': 'Mon', 'Tuesday': 'Tue', 'Wednesday': 'Wed', 'Thursday': 'Thu',
            'Friday': 'Fri', 'Saturday': 'Sat', 'Sunday': 'Sun',
            'Mon': 'Mon', 'Tue': 'Tue', 'Wed': 'Wed', 'Thu': 'Thu',
            'Fri': 'Fri', 'Sat': 'Sat', 'Sun': 'Sun'
        }

        day_index_map = {day: i for i, day in enumerate(day_names)}

        for day_name, tasks in TASKS.items():
            short_day = day_name_map.get(day_name, day_name)
            if short_day not in day_index_map:
                continue

            day_index = day_index_map[short_day]
            day_x = table_start_x + day_index * day_col_width

            for task in tasks:
                start_time = task.get('start_time', '')
                end_time = task.get('end_time', '')
                if not start_time or not end_time:
                    continue

                try:
                    # Handle both "14:30" and "14:30:00" formats
                    start_parts = start_time.split(':')
                    end_parts = end_time.split(':')
                    start_h, start_m = int(start_parts[0]), int(start_parts[1])
                    end_h, end_m = int(end_parts[0]), int(end_parts[1])
                    start_minutes = start_h * 60 + start_m
                    end_minutes = end_h * 60 + end_m
                    if end_minutes < start_minutes:
                        end_minutes += 24 * 60
                    duration_hours = (end_minutes - start_minutes) / 60.0
                except Exception as e:
                    print(f"Error parsing time for task '{task.get('title', 'Unknown')}': {e}")
                    continue

                gray_level = get_gray_level(duration_hours)
                start_slot = time_to_slot_index(start_time)
                end_slot = time_to_slot_index(end_time)

                if end_slot < start_slot:
                    end_slot = len(time_slots)

                start_y = int(table_start_y + HEADER_HEIGHT + start_slot * row_height)
                end_y = int(table_start_y + HEADER_HEIGHT + end_slot * row_height)

                margin = 2
                task_rect = [day_x + margin, start_y + margin, day_x + day_col_width - margin, end_y - margin]
                
                # For tasks under 1 hour, use light grey fill
                if duration_hours <= 1.0:
                    # Use lightest grey for short tasks
                    draw.rectangle(task_rect, fill=GRAY_LEVEL_3, outline=None)
                else:
                    # Fill for longer tasks
                    draw.rectangle(task_rect, fill=gray_level, outline=None)
                
                # Draw task title if there's enough space
                task_title = task.get('title', '')
                if task_title and (end_y - start_y) >= TASK_FONT_SIZE + 4:
                    # Calculate available space for text
                    text_x = task_rect[0] + 3
                    text_y = task_rect[1] + 2
                    max_text_width = task_rect[2] - task_rect[0] - 6
                    
                    # Truncate text if too long
                    bbox = draw.textbbox((0, 0), task_title, font=task_font)
                    text_width = bbox[2] - bbox[0]
                    
                    if text_width > max_text_width:
                        # Truncate and add ellipsis
                        while text_width > max_text_width - 10 and len(task_title) > 0:
                            task_title = task_title[:-1]
                            bbox = draw.textbbox((0, 0), task_title + "...", font=task_font)
                            text_width = bbox[2] - bbox[0]
                        task_title = task_title + "..."
                    
                    # Draw title text (use black for visibility on grey background)
                    draw.text((text_x, text_y), task_title, font=task_font, fill=BLACK)

    # Draw tasks and time labels
    draw_tasks()
    for i, time_str in enumerate(time_slots):
        y = int(table_start_y + HEADER_HEIGHT + i * row_height)
        if i in time_labels:
            label_y = y - TIME_LABEL_Y_OFFSET
            draw.text((TIME_LABEL_X, label_y), time_labels[i], font=time_font, fill=BLACK)

    # Right panel (40%)
    right_top_y = PANEL_MARGIN
    right_height = height - 2 * PANEL_MARGIN

    # TODO square: as large as possible, but leave room for date/time footer
    available_height = height - (HEADER_HEIGHT + TITLE_PADDING + TITLE_FONT_SIZE + 5) - PANEL_MARGIN
    footer_h = DATETIME_FONT_SIZE + CLOCK_FONT_SIZE + FOOTER_PADDING
    usable_height = max(0, available_height - footer_h)
    square_size = max(0, min(right_width - PANEL_MARGIN, usable_height))
    square_start_y = HEADER_HEIGHT + TITLE_PADDING + TITLE_FONT_SIZE + 5
    square_rect = [right_x, square_start_y, right_x + square_size, square_start_y + square_size]
    draw.rectangle(square_rect, outline=BLACK, width=1)

    # TODO title inside square, font size same as day_name
    todo_title = "TODO"
    draw.text((square_rect[0] + 6, square_rect[1] + 6), todo_title, font=day_font, fill=BLACK)

    # Sections as rows: Daily, Today, Upcoming (bold, same size as tasks)
    sections = [
        ("Daily", ["Check email", "Scrum sync", "Backup"]),
        ("Today", ["Ship feature", "Fix bug #102", "Review design"]),
        ("Upcoming", ["Sprint planning", "Refactor auth", "Benchmark I/O"]),
    ]
    section_font = load_font(DAY_FONT_PATH, TASK_FONT_SIZE)
    y = square_rect[1] + 6 + DAY_FONT_SIZE + 6
    for title, items in sections:
        draw.text((square_rect[0] + 8, y), title, font=section_font, fill=BLACK)
        y += TASK_FONT_SIZE + 4
        for item in items:
            draw.text((square_rect[0] + 12, y), f"- {item}", font=time_font, fill=BLACK)
            y += TIME_FONT_SIZE + 3
            if y > square_rect[3] - TIME_FONT_SIZE:
                break
        y += 4
        if y > square_rect[3] - TASK_FONT_SIZE:
            break

    # Lower area for current date/time (electronic clock style)
    datetime_y = square_rect[3] + (FOOTER_PADDING // 2)
    # Electronic clock style formatting: date and weekday on same line
    date_line = today.strftime("%Y %m %d")
    weekday_abbr = today.strftime("%a").upper()
    date_weekday_line = f"{date_line} {weekday_abbr}"
    time_line = today.strftime("%H:%M:%S")
    def center_text_y(base_y, text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = right_x + (right_width - text_w) // 2
        draw.text((x, base_y), text, font=font, fill=BLACK)
    # Draw date and weekday on same line
    center_text_y(datetime_y, date_weekday_line, datetime_font)
    # Draw time on next line
    time_y = datetime_y + DATETIME_FONT_SIZE + 6
    center_text_y(time_y, time_line, clock_font)

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
        output_file = f"eink_output_{today.strftime('%Y%m%d_%H%M%S')}.png"
        # Convert to RGB for better PNG display (grayscale to RGB)
        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
        rgb_image.paste(image, (0, 0))
        rgb_image.save(output_file, 'PNG')
        print(f"✅ Image saved as: {output_file}")
        print(f"   Size: {width}x{height} pixels")
        print(f"   Tasks displayed: {sum(len(tasks) for tasks in TASKS.values())}")

if __name__ == "__main__":
    main()
