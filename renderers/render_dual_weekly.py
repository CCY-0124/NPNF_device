#!/usr/bin/env python3
"""
Dual Weekly View Renderer
Weekly timetable with TODO panel and datetime
"""

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Display dimensions
EPD_WIDTH = 800
EPD_HEIGHT = 480

# Layout parameters
TITLE_FONT_SIZE = 26
TITLE_PADDING = 25
DAY_FONT_SIZE = 14
TIME_FONT_SIZE = 12
TASK_FONT_SIZE = 12
DATETIME_FONT_SIZE = 32
PANEL_MARGIN = 5
HEADER_HEIGHT = 20
TIME_COL_WIDTH = 55
TABLE_MARGIN_BOTTOM = 5
FOOTER_PADDING = 40

FONT_PATHS = {
    'title': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'day': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'time': "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    'task': "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    'datetime': "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
}

TIME_START_HOUR = 8
TIME_END_HOUR = 24
TIME_LABEL_X = 6
TIME_LABEL_Y_OFFSET = 4

# Colors
WHITE = 255
BLACK = 0
GRAY_LEVEL_1 = 80
GRAY_LEVEL_3 = 192

def transform_tasks_to_weekly_format(api_todos: List[Dict], week_start_date: datetime) -> Dict[str, List]:
    """Transform API tasks to weekly format"""
    tasks_by_day = {
        'Monday': [], 'Tuesday': [], 'Wednesday': [], 'Thursday': [],
        'Friday': [], 'Saturday': [], 'Sunday': []
    }
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    week_start = week_start_date.date() if isinstance(week_start_date, datetime) else week_start_date
    week_end = week_start + timedelta(days=6)
    
    for task in api_todos:
        if not task.get('start_time') or not task.get('end_time') or not task.get('start_date'):
            continue
        
        try:
            task_date = datetime.strptime(task['start_date'], '%Y-%m-%d').date()
        except:
            continue
        
        if task_date < week_start or task_date > week_end:
            continue
        
        day_index = task_date.weekday()
        day_name = day_names[day_index]
        
        start_time = task['start_time']
        end_time = task['end_time']
        if len(start_time) > 5:
            start_time = start_time[:5]
        if len(end_time) > 5:
            end_time = end_time[:5]
        
        # Filter tasks: only include tasks within 8am-12am (08:00-00:00, 16 hours)
        try:
            start_parts = start_time.split(':')
            start_h = int(start_parts[0])
            # Skip tasks that start before 8am (8am to 12am midnight is included)
            if start_h < 8:
                continue
        except:
            continue
        
        tasks_by_day[day_name].append({
            'start_time': start_time,
            'end_time': end_time,
            'title': task.get('title', 'Untitled')
        })
    
    return tasks_by_day

def load_fonts():
    """Load fonts with fallback"""
    fonts = {}
    font_sizes = {
        'title': TITLE_FONT_SIZE,
        'day': DAY_FONT_SIZE,
        'time': TIME_FONT_SIZE,
        'task': TASK_FONT_SIZE,
        'datetime': DATETIME_FONT_SIZE,
    }
    
    for name, path in FONT_PATHS.items():
        size = font_sizes.get(name, 12)
        try:
            fonts[name] = ImageFont.truetype(path, size)
        except:
            fonts[name] = ImageFont.load_default()
    
    return fonts

def render_dual_weekly(data: Dict[str, Any], config: Dict[str, Any]) -> Image.Image:
    """
    Render dual-pane weekly timetable view with TODO panel
    
    Args:
        data: {'todos': [...]} - Task data from API
        config: Device configuration with 'display_mode' ('4gray' or 'bw')
    
    Returns:
        PIL Image ready for display
    """
    display_mode = config.get('display_mode', '4gray')  # Default to 4-gray mode
    todos = data.get('todos', [])
    today = datetime.now()
    days_since_monday = today.weekday()
    monday = (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6)
    week_title = f"{monday.strftime('%b %d')}-{sunday.strftime('%d, %Y')}"
    
    tasks = transform_tasks_to_weekly_format(todos, monday)
    fonts = load_fonts()
    
    width = EPD_WIDTH
    height = EPD_HEIGHT
    image = Image.new('L', (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    
    # Panels: left 60%, right 40%
    left_width = int(width * 0.6)
    right_x = left_width + PANEL_MARGIN
    right_width = max(0, width - right_x - PANEL_MARGIN)
    
    # Title
    bbox = draw.textbbox((0, 0), week_title, font=fonts['title'])
    title_x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((title_x, TITLE_PADDING), week_title, font=fonts['title'], fill=BLACK)
    
    # Table area
    table_start_y = HEADER_HEIGHT + TITLE_PADDING + TITLE_FONT_SIZE + 5
    table_start_x = TIME_COL_WIDTH
    table_width = left_width - table_start_x - PANEL_MARGIN
    table_height = height - table_start_y - TABLE_MARGIN_BOTTOM
    
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_col_width = table_width // len(day_names)
    
    # Day headers
    for i, day_name in enumerate(day_names):
        x = table_start_x + i * day_col_width
        bbox = draw.textbbox((0, 0), day_name, font=fonts['day'])
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = x + (day_col_width - text_w) // 2
        text_y = table_start_y + (HEADER_HEIGHT - text_h) // 2
        draw.text((text_x, text_y), day_name, font=fonts['day'], fill=BLACK)
    
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
    
    
    def time_to_slot_index(time_str):
        try:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1])
            slot_index = (hour - TIME_START_HOUR) * 2
            if minute >= 30:
                slot_index += 1
            return max(0, slot_index)
        except:
            return 0
    
    # Draw tasks
    day_name_map = {
        'Monday': 'Mon', 'Tuesday': 'Tue', 'Wednesday': 'Wed', 'Thursday': 'Thu',
        'Friday': 'Fri', 'Saturday': 'Sat', 'Sunday': 'Sun',
        'Mon': 'Mon', 'Tue': 'Tue', 'Wed': 'Wed', 'Thu': 'Thu',
        'Fri': 'Fri', 'Sat': 'Sat', 'Sun': 'Sun'
    }
    day_index_map = {day: i for i, day in enumerate(day_names)}
    
    for day_name, day_tasks in tasks.items():
        short_day = day_name_map.get(day_name, day_name)
        if short_day not in day_index_map:
            continue
        
        day_index = day_index_map[short_day]
        day_x = table_start_x + day_index * day_col_width
        
        for task in day_tasks:
            start_time = task.get('start_time', '')
            end_time = task.get('end_time', '')
            if not start_time or not end_time:
                continue
            
            try:
                start_parts = start_time.split(':')
                end_parts = end_time.split(':')
                start_h, start_m = int(start_parts[0]), int(start_parts[1])
                end_h, end_m = int(end_parts[0]), int(end_parts[1])
                start_minutes = start_h * 60 + start_m
                end_minutes = end_h * 60 + end_m
                if end_minutes < start_minutes:
                    end_minutes += 24 * 60
                duration_hours = (end_minutes - start_minutes) / 60.0
            except:
                continue
            
            start_slot = time_to_slot_index(start_time)
            end_slot = time_to_slot_index(end_time)
            
            if end_slot < start_slot:
                end_slot = len(time_slots)
            
            # Ensure end_slot is at least start_slot + 1 to avoid invalid rectangle
            if end_slot <= start_slot:
                end_slot = start_slot + 1
            
            start_y = int(table_start_y + HEADER_HEIGHT + start_slot * row_height)
            end_y = int(table_start_y + HEADER_HEIGHT + end_slot * row_height)
            
            # Ensure end_y is greater than start_y
            if end_y <= start_y:
                end_y = start_y + int(row_height)
            
            margin = 2
            task_rect = [day_x + margin, start_y + margin, 
                        day_x + day_col_width - margin, end_y - margin]
            
            # Final validation: ensure rectangle is valid
            if task_rect[3] <= task_rect[1]:
                continue
            
            # Draw task rectangle based on mode
            if display_mode == 'bw':
                # Black and white mode: use outline only
                draw.rectangle(task_rect, outline=BLACK, width=1)
            else:
                # 4-gray mode: use fill only (like before)
                if duration_hours <= 1.0:
                    draw.rectangle(task_rect, fill=GRAY_LEVEL_3, outline=None)
                else:
                    gray_level = GRAY_LEVEL_1 if duration_hours > 3.0 else GRAY_LEVEL_3
                    draw.rectangle(task_rect, fill=gray_level, outline=None)
            
            # Draw task title if there's enough space
            task_title = task.get('title', '')
            if task_title and (end_y - start_y) >= TASK_FONT_SIZE + 4:
                text_x = task_rect[0] + 3
                text_y = task_rect[1] + 2
                max_text_width = task_rect[2] - task_rect[0] - 6
                
                bbox = draw.textbbox((0, 0), task_title, font=fonts['task'])
                text_width = bbox[2] - bbox[0]
                
                if text_width > max_text_width:
                    while text_width > max_text_width - 10 and len(task_title) > 0:
                        task_title = task_title[:-1]
                        bbox = draw.textbbox((0, 0), task_title + "...", font=fonts['task'])
                        text_width = bbox[2] - bbox[0]
                    task_title = task_title + "..."
                
                draw.text((text_x, text_y), task_title, font=fonts['task'], fill=BLACK)
    
    # Draw time labels
    for i, time_str in enumerate(time_slots):
        y = int(table_start_y + HEADER_HEIGHT + i * row_height)
        if i in time_labels:
            label_y = y - TIME_LABEL_Y_OFFSET
            draw.text((TIME_LABEL_X, label_y), time_labels[i], font=fonts['time'], fill=BLACK)
    
    # Right panel - TODO and date
    available_height = height - (HEADER_HEIGHT + TITLE_PADDING + TITLE_FONT_SIZE + 5) - PANEL_MARGIN
    footer_h = DATETIME_FONT_SIZE + FOOTER_PADDING
    usable_height = max(0, available_height - footer_h)
    square_size = max(0, min(right_width - PANEL_MARGIN, usable_height))
    square_start_y = HEADER_HEIGHT + TITLE_PADDING + TITLE_FONT_SIZE + 5
    square_rect = [right_x, square_start_y, right_x + square_size, square_start_y + square_size]
    draw.rectangle(square_rect, outline=BLACK, width=1)
    
    # TODO title
    draw.text((square_rect[0] + 6, square_rect[1] + 6), "TODO", font=fonts['day'], fill=BLACK)
    
    # TODO sections - extract tasks from todos
    today_date = today.date()
    daily_todos = []
    today_todos = []
    upcoming_todos = []
    
    # Track seen tasks to avoid duplicates (especially for recurring tasks)
    seen_titles = set()
    
    # Get all tasks that are shown in calendar (to exclude them from TODO)
    calendar_task_titles = set()
    for day_tasks in tasks.values():
        for task in day_tasks:
            calendar_task_titles.add(task.get('title', ''))
    
    for task in todos:
        title = task.get('title', 'Untitled')
        if not title or title == 'Untitled':
            continue
        
        # Skip tasks that are already shown in calendar
        if title in calendar_task_titles:
            continue
        
        # Skip completed tasks
        completed = task.get('completed', False) or task.get('is_completed', False) or task.get('status') == 'completed'
        if completed:
            continue
        
        # Check if task is scheduled (is_schedule = true with valid time)
        is_schedule = task.get('is_schedule', False)
        start_time = task.get('start_time')
        end_time = task.get('end_time')
        has_time = start_time and end_time and start_time.strip() and end_time.strip() and start_time != 'null' and end_time != 'null'
        
        # Scheduled tasks with time in 8am-12am range are shown in calendar, skip them
        if is_schedule and has_time:
            try:
                start_time_clean = start_time.strip()
                if len(start_time_clean) > 5:
                    start_time_clean = start_time_clean[:5]
                start_parts = start_time_clean.split(':')
                start_h = int(start_parts[0])
                # If task is in 8am-12am range, it's shown in calendar, skip
                if start_h >= 8:
                    continue
            except:
                pass
        
        # Include non-scheduled tasks or scheduled tasks outside 8am-12am range
        # Categorize by section first, then by date
        section = task.get('section', '').lower()
        is_recurring = task.get('is_recurring', False)
        
        # For recurring tasks, only show once (use parent_task_id if available, otherwise use title)
        task_key = task.get('parent_task_id', title) if is_recurring else title
        if task_key in seen_titles:
            continue
        seen_titles.add(task_key)
        
        if section == 'daily':
            daily_todos.append(title)
        elif section == 'today':
            today_todos.append(title)
        elif section == 'upcoming':
            upcoming_todos.append(title)
        else:
            # No section, categorize by date
            task_date = None
            if task.get('start_date'):
                try:
                    task_date = datetime.strptime(task['start_date'], '%Y-%m-%d').date()
                except:
                    pass
            
            if task_date:
                if task_date == today_date:
                    today_todos.append(title)
                elif task_date > today_date:
                    upcoming_todos.append(title)
                else:
                    daily_todos.append(title)
            else:
                # No date, treat as daily
                daily_todos.append(title)
    
    sections = [
        ("Daily", daily_todos[:3]),  # Limit to 3 items per section
        ("Today", today_todos[:3]),
        ("Upcoming", upcoming_todos[:3]),
    ]
    section_font = fonts['task']
    y = square_rect[1] + 6 + DAY_FONT_SIZE + 6
    for title, items in sections:
        draw.text((square_rect[0] + 8, y), title, font=section_font, fill=BLACK)
        y += TASK_FONT_SIZE + 4
        # Only draw items if there are any
        if items:
            for item in items:
                draw.text((square_rect[0] + 12, y), f"- {item}", font=fonts['time'], fill=BLACK)
                y += TIME_FONT_SIZE + 3
                if y > square_rect[3] - TIME_FONT_SIZE:
                    break
        y += 4
        if y > square_rect[3] - TASK_FONT_SIZE:
            break
    
    # Date footer (no time)
    datetime_y = square_rect[3] + (FOOTER_PADDING // 2)
    date_line = today.strftime("%Y %m %d")
    weekday_abbr = today.strftime("%a").upper()
    date_weekday_line = f"{date_line} {weekday_abbr}"
    
    def center_text_y(base_y, text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = right_x + (right_width - text_w) // 2
        draw.text((x, base_y), text, font=font, fill=BLACK)
    
    center_text_y(datetime_y, date_weekday_line, fonts['datetime'])
    
    return image

