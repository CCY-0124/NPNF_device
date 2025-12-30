#!/usr/bin/env python3
"""
Dual Monthly View Renderer
Monthly calendar with TODO panel and datetime
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
HEADER_FONT_SIZE = 14
CELL_FONT_SIZE = 14
PANEL_MARGIN = 5
HEADER_HEIGHT = 26
CELL_SPACING = 2
DATETIME_FONT_SIZE = 32
FOOTER_PADDING = 40

FONT_PATHS = {
    'title': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'header': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'cell': "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    'day': "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    'time': "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    'datetime': "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
}

# Colors
WHITE = 255
BLACK = 0
GRAY_LEVEL_1 = 80
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
        'day': HEADER_FONT_SIZE,
        'time': 12,
        'datetime': DATETIME_FONT_SIZE,
    }
    
    for name, path in FONT_PATHS.items():
        size = font_sizes.get(name, 12)
        try:
            fonts[name] = ImageFont.truetype(path, size)
        except:
            fonts[name] = ImageFont.load_default()
    
    return fonts

def render_dual_monthly(data: Dict[str, Any], config: Dict[str, Any]) -> Image.Image:
    """
    Render dual-pane monthly calendar view with TODO panel
    
    Args:
        data: {'todos': [...]} - Task data from API
        config: Device configuration with 'display_mode' ('4gray' or 'bw')
    
    Returns:
        PIL Image ready for display
    """
    display_mode = config.get('display_mode', '4gray')  # Default to 4-gray mode
    todos = data.get('todos', [])
    today = datetime.now()
    first_day = today.replace(day=1)
    total_days = days_in_month(today)
    first_weekday = first_day.weekday()
    month_title = first_day.strftime("%B %Y")
    
    # Calculate hours from tasks
    monthly_hours = calculate_hours_from_tasks(todos, first_day)
    
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
    bbox = draw.textbbox((0, 0), month_title, font=fonts['title'])
    title_x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((title_x, TITLE_PADDING), month_title, font=fonts['title'], fill=BLACK)
    
    # Left panel: Monthly calendar (60%)
    grid_top = HEADER_HEIGHT + TITLE_PADDING + TITLE_FONT_SIZE + 5
    grid_left = PANEL_MARGIN
    grid_width = left_width - 2 * PANEL_MARGIN
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
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = x + (cell_width - text_w) // 2
        text_y = grid_top + (HEADER_HEIGHT - text_h) // 2
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
        
        # Draw calendar cell based on mode
        if display_mode == 'bw':
            # Black and white mode: fill with black if has tasks
            if hours > 0:
                draw.rectangle(rect, fill=BLACK, outline=BLACK, width=1)
            else:
                draw.rectangle(rect, outline=BLACK, width=1)
        else:
            # 4-gray mode: use fill only (like before)
            draw.rectangle(rect, fill=GRAY_LEVEL_3, outline=None)
        
        # Day number
        day_label = str(day)
        bbox = draw.textbbox((0, 0), day_label, font=fonts['cell'])
        # In bw mode, use white text if cell is filled with black
        text_color = WHITE if (display_mode == 'bw' and hours > 0) else BLACK
        draw.text((rect[0] + 4, rect[1] + 2), day_label, font=fonts['cell'], fill=text_color)
        
        # Hours as stacked rectangles
        if hours > 0:
            rounded_hours = round(hours * 2) / 2.0
            num_full_rects = int(rounded_hours)
            has_half = (rounded_hours - num_full_rects) >= 0.5
            
            rect_width = 18
            rect_height = 2
            rect_spacing = 2
            start_x = rect[2] - 6
            bottom_y = rect[3] - 4
            
            # In bw mode, if cell is already filled with black, don't draw hour rectangles
            if not (display_mode == 'bw' and hours > 0):
                for i in range(num_full_rects):
                    y_bottom = bottom_y - i * (rect_height + rect_spacing)
                    y_top = y_bottom - rect_height
                    hour_rect = [start_x - rect_width, y_top, start_x, y_bottom]
                    draw.rectangle(hour_rect, fill=BLACK, outline=None)
                
                if has_half:
                    y_bottom = bottom_y - num_full_rects * (rect_height + rect_spacing)
                    y_top = y_bottom - rect_height
                    hour_rect = [start_x - rect_width // 2, y_top, start_x, y_bottom]
                    draw.rectangle(hour_rect, fill=BLACK, outline=None)
    
    # Right panel: TODO square and date
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
    
    # Track seen tasks to avoid duplicates
    # For daily tasks, use parent_task_id; for others, use title
    seen_daily_parent_ids = set()
    seen_titles = set()
    
    # Track daily task parent_ids and their valid instances
    # If all instances of a parent are deleted, don't show the task
    daily_parent_instances = {}  # parent_id -> list of (instance_date, deleted_at)
    
    # First pass: collect all daily task instances to check if parent is deleted
    for task in todos:
        section = task.get('section', '').lower()
        if section == 'daily' and task.get('parent_task_id'):
            parent_id = task.get('parent_task_id')
            instance_date = task.get('instance_date')
            deleted_at = task.get('deleted_at')
            if parent_id not in daily_parent_instances:
                daily_parent_instances[parent_id] = []
            daily_parent_instances[parent_id].append({
                'instance_date': instance_date,
                'deleted_at': deleted_at,
                'task': task
            })
    
    # Check which parent tasks should be shown (have at least one valid instance for today or future)
    valid_daily_parent_ids = set()
    for parent_id, instances in daily_parent_instances.items():
        has_valid_future_instance = False
        for instance in instances:
            # Skip if instance is deleted
            if instance['deleted_at']:
                continue
            # Check if instance_date is today or future
            if instance['instance_date']:
                try:
                    instance_date = datetime.strptime(instance['instance_date'], '%Y-%m-%d').date()
                    if instance_date >= today_date:
                        has_valid_future_instance = True
                        break
                except:
                    pass
        if has_valid_future_instance:
            valid_daily_parent_ids.add(parent_id)
    
    for task in todos:
        title = task.get('title', 'Untitled')
        if not title or title == 'Untitled':
            continue
        
        # Skip deleted tasks
        if task.get('deleted_at'):
            continue
        
        # Skip completed tasks
        completed = task.get('completed', False) or task.get('is_completed', False) or task.get('status') == 'completed'
        if completed:
            continue
        
        # Check section early to determine if this is a daily task
        section = task.get('section', '').lower()
        is_daily_task = (section == 'daily')
        
        # For non-daily tasks, skip recurring task instances (they have instance_date and parent_task_id)
        # For daily tasks, we want to include instances but deduplicate by parent_task_id
        # Also, only show daily task instances for today or future dates, and only if parent has valid instances
        if is_daily_task and task.get('instance_date') and task.get('parent_task_id'):
            parent_id = task.get('parent_task_id')
            # Skip if parent task has no valid future instances (all deleted or all past)
            if parent_id not in valid_daily_parent_ids:
                continue
            # For daily tasks with instance_date, only show if instance_date is today or future
            try:
                instance_date = datetime.strptime(task['instance_date'], '%Y-%m-%d').date()
                if instance_date < today_date:
                    continue  # Skip past instances
            except:
                pass  # If parsing fails, continue with the task
        elif not is_daily_task and task.get('instance_date') and task.get('parent_task_id'):
            continue
        
        # Check if task is scheduled (is_schedule = true with valid time)
        is_schedule = task.get('is_schedule', False)
        start_time = task.get('start_time')
        end_time = task.get('end_time')
        has_time = start_time and end_time and start_time.strip() and end_time.strip() and start_time != 'null' and end_time != 'null'
        
        # Check if task is in current month for calendar display
        task_date = None
        if task.get('start_date'):
            try:
                task_date = datetime.strptime(task['start_date'], '%Y-%m-%d').date()
            except:
                pass
        
        # Scheduled tasks with time are shown in calendar, skip them
        # BUT: if task has section "upcoming" or is outside current month, include it in TODO
        if is_schedule and has_time:
            # For upcoming section tasks, always show in TODO
            if section == 'upcoming':
                pass  # Don't skip, show in TODO
            # For tasks outside current month, show in TODO even if scheduled
            elif task_date:
                # Check if task is in current month
                today_first = today_date.replace(day=1)
                if today_first.month == 12:
                    next_month = today_first.replace(year=today_first.year + 1, month=1)
                else:
                    next_month = today_first.replace(month=today_first.month + 1)
                last_day = (next_month - timedelta(days=1)).day
                month_start = today_first
                month_end = today_first.replace(day=last_day)
                
                if task_date < month_start or task_date > month_end:
                    pass  # Task is outside current month, show in TODO
                else:
                    continue  # Task is in current month calendar, skip from TODO
            else:
                continue  # No date, skip scheduled tasks with time
        
        # Include non-scheduled tasks
        # Categorize by section first, then by date
        
        # Deduplicate: for daily tasks, use parent_task_id; for others, use title
        if is_daily_task:
            # For daily tasks, use parent_task_id for deduplication
            parent_id = task.get('parent_task_id')
            if parent_id:
                if parent_id in seen_daily_parent_ids:
                    continue
                seen_daily_parent_ids.add(parent_id)
            else:
                # Fallback to title if no parent_id
                if title in seen_titles:
                    continue
                seen_titles.add(title)
        else:
            # For non-daily tasks, use title for deduplication
            if title in seen_titles:
                continue
            seen_titles.add(title)
        
        if section == 'daily':
            daily_todos.append(title)
        elif section == 'today':
            today_todos.append(title)
        elif section == 'upcoming':
            upcoming_todos.append(title)
        else:
            # No section, categorize by date
            # Reuse task_date if already parsed, otherwise parse it
            if task_date is None and task.get('start_date'):
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
    section_font = fonts['time']
    y = square_rect[1] + 6 + HEADER_FONT_SIZE + 6
    for title, items in sections:
        draw.text((square_rect[0] + 8, y), title, font=section_font, fill=BLACK)
        y += 12 + 4
        # Only draw items if there are any
        if items:
            for item in items:
                draw.text((square_rect[0] + 12, y), f"- {item}", font=fonts['time'], fill=BLACK)
                y += 12 + 3
                if y > square_rect[3] - 12:
                    break
        y += 4
        if y > square_rect[3] - 12:
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

