#!/usr/bin/env python3
"""
E-ink Display Service
Continuously polls API for updates and refreshes the display
"""

import sys
import os
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path

# Import API client
try:
    from api_client import fetch_device_data
except ImportError:
    print("Error: api_client not found")
    sys.exit(1)

# Import e-ink library with dynamic path detection
EINK_AVAILABLE = False
epd7in5_V2 = None

# Try multiple possible paths for Waveshare library
possible_paths = [
    Path.home() / 'e-Paper' / 'RaspberryPi_JetsonNano' / 'python' / 'lib',
    Path('/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib'),
    Path('/home/npnf/e-Paper/RaspberryPi_JetsonNano/python/lib'),
    Path('/usr/local/lib/python3/dist-packages'),
    Path('/usr/lib/python3/dist-packages'),
]

for lib_path in possible_paths:
    if lib_path.exists():
        try:
            sys.path.insert(0, str(lib_path))
            from waveshare_epd import epd7in5_V2
            EINK_AVAILABLE = True
            print(f"Found Waveshare library at: {lib_path}")
            break
        except ImportError:
            continue

if not EINK_AVAILABLE:
    print("Error: e-ink library (waveshare_epd) not found")
    print("Tried paths:")
    for path in possible_paths:
        exists = "✓" if path.exists() else "✗"
        print(f"  {exists} {path}")
    print("\nPlease install Waveshare library:")
    print("  cd ~")
    print("  git clone https://github.com/waveshare/e-Paper.git")
    print("  cd e-Paper/RaspberryPi_JetsonNano/python")
    print("  sudo python3 setup.py install")
    sys.exit(1)

# Configuration - try to load from config file first, then environment variable
CONFIG_FILE = Path(__file__).parent / 'device_config.json'
DEVICE_TOKEN = os.getenv('EINK_DEVICE_TOKEN', '')

# Try to load from config file if not in environment
if not DEVICE_TOKEN and CONFIG_FILE.exists():
    try:
        import json
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                DEVICE_TOKEN = config.get('device_token', '')
        except PermissionError:
            # If permission denied, try to fix or use environment variable
            import os
            import stat
            try:
                # Try to make readable
                current_uid = os.getuid()
                file_stat = os.stat(CONFIG_FILE)
                # If file is owned by different user, we can't fix it here
                # But we can try to read it anyway (might work if in same group)
                print(f"Warning: Config file permission issue. File owned by UID {file_stat.st_uid}, current UID {current_uid}")
                print("Trying to read anyway...")
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    DEVICE_TOKEN = config.get('device_token', '')
            except Exception as e:
                print(f"Error reading config file: {e}")
                print("Please fix file permissions: chmod 640 device_config.json")
                pass
    except (json.JSONDecodeError, KeyError):
        pass  # Continue to check environment variable

if not DEVICE_TOKEN:
    print("Error: Device token not found")
    print("Please either:")
    print("  1. Run the setup script: python3 setup.py")
    print("  2. Set environment variable: export EINK_DEVICE_TOKEN='your_token'")
    sys.exit(1)

# Polling configuration
POLL_INTERVAL = int(os.getenv('EINK_POLL_INTERVAL', '60'))  # Default: 60 seconds
MIN_REFRESH_INTERVAL = 300  # Minimum 5 minutes between display refreshes (to preserve e-ink lifespan)
DISPLAY_SLEEPING = False  # Track if display is in sleep mode

# Global state
running = True
last_config = None
last_refresh_time = 0
partial_refresh_count = 0  # Counter for partial refreshes
MAX_PARTIAL_REFRESHES = 5  # Full refresh after this many partial refreshes (to clear ghosting)
epd = None
current_display_mode = None  # Track current display mode from API config

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global running
    print("\nShutting down...")
    running = False
    if epd:
        try:
            epd.sleep()
        except:
            pass

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def should_refresh_display(current_config, last_config, last_refresh_time):
    """Determine if display should be refreshed"""
    current_time = time.time()
    
    # Always refresh if config changed
    if last_config is None or current_config != last_config:
        return True
    
    # Don't refresh too frequently (preserve e-ink lifespan)
    if current_time - last_refresh_time < MIN_REFRESH_INTERVAL:
        return False
    
    # Refresh if it's been a while (even if nothing changed)
    return True

def get_date_range_for_view(view_type):
    """Get start and end dates based on view type"""
    today = datetime.now()
    
    if view_type in ['weekly', 'dual_weekly']:
        days_since_monday = today.weekday()
        start_date = (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=6)
    elif view_type in ['dual_monthly', 'monthly_square', 'monthly_re']:
        start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        end_date = last_day
    elif view_type == 'dual_yearly':
        start_date = datetime(today.year, 1, 1)
        end_date = datetime(today.year, 12, 31)
    else:
        # Default to weekly
        days_since_monday = today.weekday()
        start_date = (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=6)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def update_display():
    """Fetch data and update display if needed"""
    global last_config, last_refresh_time, partial_refresh_count, epd, DISPLAY_SLEEPING, current_display_mode
    
    # Store last image hash to detect actual content changes
    if not hasattr(update_display, 'last_image_hash'):
        update_display.last_image_hash = None
    
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching data...")
        
        # First fetch to get view_type
        today = datetime.now()
        days_since_monday = today.weekday()
        monday = (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date, end_date = monday.strftime('%Y-%m-%d'), (monday + timedelta(days=6)).strftime('%Y-%m-%d')
        
        data = fetch_device_data(DEVICE_TOKEN, start_date, end_date)
        
        if not data:
            print("  Warning: No data received, skipping update")
            return
        
        config = data.get('config', {})
        view_type = config.get('view_type', 'weekly')
        
        # Fetch data with correct date range for view type
        start_date, end_date = get_date_range_for_view(view_type)
        data = fetch_device_data(DEVICE_TOKEN, start_date, end_date)
        
        if not data:
            print("  Warning: No data received, skipping update")
            return
        
        config = data.get('config', {})
        todos = data.get('todos', [])
        
        # Debug: print config to see what we're getting from API
        print(f"  Config from API: {config}")
        
        # Get display_mode from config (default to '4gray' if not specified)
        display_mode = config.get('display_mode', '4gray')
        print(f"  Raw display_mode from config: '{display_mode}'")
        if display_mode not in ['4gray', 'bw']:
            print(f"  Warning: Invalid display_mode '{display_mode}', defaulting to '4gray'")
            display_mode = '4gray'
        print(f"  Using display_mode: '{display_mode}'")
        
        # Check if display mode changed and reinitialize if needed
        if current_display_mode is not None and current_display_mode != display_mode:
            print(f"  Display mode changed from '{current_display_mode}' to '{display_mode}', reinitializing...")
            try:
                # Reinitialize display with new mode
                if display_mode == '4gray':
                    epd.init_4Gray()
                    print("  Display reinitialized (4-gray mode)")
                else:
                    epd.init()
                    if hasattr(epd, 'init_part'):
                        try:
                            epd.init_part()
                        except:
                            pass
                    print("  Display reinitialized (black/white mode)")
                DISPLAY_SLEEPING = False
                current_display_mode = display_mode
            except Exception as e:
                print(f"  Error reinitializing display for mode change: {e}")
                # Continue with old mode if reinitialization fails
        elif current_display_mode is None:
            # First time, just record the mode
            current_display_mode = display_mode
        
        # Check if we need to refresh
        config_key = (view_type, len(todos), display_mode)  # Include display_mode in change detection
        
        if not should_refresh_display(config_key, last_config, last_refresh_time):
            print(f"  Skipping refresh (too soon since last update)")
            return
        
        print(f"  View: {view_type}, Display Mode: {display_mode}, Tasks: {len(todos)}")
        
        # Use renderer system
        from renderers.renderers import get_renderer, list_renderers
        
        render_func = get_renderer(view_type)
        if not render_func:
            print(f"  Warning: Renderer for '{view_type}' not found")
            print(f"  Available renderers: {', '.join(list_renderers())}")
            return
        
        # Call render function with display mode
        render_config = config.copy()
        render_config['display_mode'] = display_mode
        image = render_func({'todos': todos}, render_config)
        
        # Calculate image hash to detect actual content changes
        import hashlib
        image_bytes = image.tobytes()
        current_hash = hashlib.md5(image_bytes).hexdigest()
        
        # If content hasn't changed at all, skip update
        if update_display.last_image_hash == current_hash:
            print("  Content unchanged, skipping update")
            return
        
        update_display.last_image_hash = current_hash
        
        # Display on e-ink
        print("  Updating display...")
        
        # Reinitialize display if it's in sleep mode (required before refresh)
        if DISPLAY_SLEEPING:
            try:
                if display_mode == '4gray':
                    epd.init_4Gray()
                    print("  Display reinitialized (4-gray mode)")
                else:
                    epd.init()
                    if hasattr(epd, 'init_part'):
                        try:
                            epd.init_part()
                        except:
                            pass
                    print("  Display reinitialized (black/white mode)")
                DISPLAY_SLEEPING = False
            except Exception as e:
                print(f"  Error reinitializing display: {e}")
                return
        
        # Determine if we need full refresh (to clear ghosting)
        need_full_refresh = (
            partial_refresh_count >= MAX_PARTIAL_REFRESHES or
            last_config is None or  # First update
            config_key != last_config  # Config or task count changed
        )
        
        if display_mode == '4gray':
            # 4-gray mode does not support partial update, always use full refresh
            epd.display_4Gray(epd.getbuffer_4Gray(image))
            partial_refresh_count = 0
            print("  Full refresh (4-gray mode)")
        else:
            # Black and white mode
            if need_full_refresh:
                epd.display(epd.getbuffer(image.convert('1')))
                partial_refresh_count = 0
                print("  Full refresh (clearing ghosting)")
            else:
                try:
                    epd.display_Partial(epd.getbuffer(image.convert('1')))
                    partial_refresh_count += 1
                    print(f"  Partial refresh ({partial_refresh_count}/{MAX_PARTIAL_REFRESHES})")
                except Exception as e:
                    print(f"  Partial update failed: {e}, using full refresh")
                    epd.display(epd.getbuffer(image.convert('1')))
                    partial_refresh_count = 0
        
        # Put display to sleep mode after refresh (protect screen from high voltage)
        try:
            epd.sleep()
            DISPLAY_SLEEPING = True
            print("  Display put to sleep mode (protecting screen)")
        except Exception as e:
            print(f"  Warning: Could not put display to sleep: {e}")
        
        last_config = config_key
        last_refresh_time = time.time()
        print("  Display updated successfully")
            
    except Exception as e:
        print(f"  Error updating display: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main service loop"""
    global epd, DISPLAY_SLEEPING, current_display_mode
    
    print("=" * 50)
    print("E-ink Display Service Starting...")
    print(f"Device Token: {DEVICE_TOKEN[:20]}...")
    print(f"Poll Interval: {POLL_INTERVAL} seconds")
    print(f"Min Refresh Interval: {MIN_REFRESH_INTERVAL} seconds")
    print("=" * 50)
    
    # Initialize e-ink display
    try:
        # Check for SPI devices before initializing
        spi_devices = ['/dev/spidev0.0', '/dev/spidev0.1']
        spi_found = False
        for spi_dev in spi_devices:
            if Path(spi_dev).exists():
                spi_found = True
                print(f"Found SPI device: {spi_dev}")
                break
        
        if not spi_found:
            print("Warning: SPI devices not found. Checking if SPI is enabled...")
            print("Troubleshooting:")
            print("  1. Enable SPI: sudo raspi-config -> Interface Options -> SPI -> Enable")
            print("  2. Check SPI modules: lsmod | grep spi")
            print("  3. Reboot after enabling SPI")
            print("  4. Check device files: ls -l /dev/spi*")
        
        # Try to fetch display_mode from API before initializing
        # Default to '4gray' if API call fails or config not available
        initial_display_mode = '4gray'
        try:
            print("Fetching device config to determine display mode...")
            today = datetime.now()
            days_since_monday = today.weekday()
            monday = (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            start_date, end_date = monday.strftime('%Y-%m-%d'), (monday + timedelta(days=6)).strftime('%Y-%m-%d')
            data = fetch_device_data(DEVICE_TOKEN, start_date, end_date)
            if data and 'config' in data:
                config = data.get('config', {})
                api_display_mode = config.get('display_mode', '4gray')
                if api_display_mode in ['4gray', 'bw']:
                    initial_display_mode = api_display_mode
                    print(f"  Display mode from API: {initial_display_mode}")
                else:
                    print(f"  Warning: Invalid display_mode '{api_display_mode}' in API, using default '4gray'")
            else:
                print("  Warning: Could not fetch config from API, using default '4gray'")
        except Exception as e:
            print(f"  Warning: Error fetching config: {e}, using default '4gray'")
        
        current_display_mode = initial_display_mode
        
        epd = epd7in5_V2.EPD()
        if initial_display_mode == '4gray':
            epd.init_4Gray()
            print("4-gray mode initialized (partial update not supported in 4-gray mode)")
        else:
            epd.init()
            print("Display initialized (black/white mode)")
            # Initialize partial update mode if available (only for black/white mode)
            if hasattr(epd, 'init_part'):
                try:
                    epd.init_part()
                    print("Partial update mode initialized")
                except Exception as e:
                    print(f"Warning: Could not initialize partial update mode: {e}")
        epd.Clear()
        DISPLAY_SLEEPING = False  # Display is initialized, not sleeping
        print("Display cleared and ready")
    except FileNotFoundError as e:
        print(f"Failed to initialize display: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if SPI is enabled:")
        print("     sudo raspi-config -> Interface Options -> SPI -> Enable")
        print("  2. Check SPI device files:")
        print("     ls -l /dev/spi*")
        print("  3. Check if user is in spi group:")
        print("     groups")
        print("     sudo usermod -a -G spi,gpio $USER")
        print("  4. Check SPI kernel modules:")
        print("     lsmod | grep spi")
        print("  5. Reboot after making changes")
        sys.exit(1)
    except PermissionError as e:
        print(f"Failed to initialize display: Permission denied")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Add user to spi and gpio groups:")
        print("     sudo usermod -a -G spi,gpio npnf")
        print("  2. Check current groups:")
        print("     groups")
        print("  3. You may need to log out and log back in")
        print("  4. Or restart the service after adding groups")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize display: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("\nFull error traceback:")
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("  1. Verify e-ink display is properly connected")
        print("  2. Check SPI is enabled: sudo raspi-config")
        print("  3. Check Waveshare library is installed correctly")
        print("  4. Try running as root to test: sudo python3 eink_service.py")
        sys.exit(1)
    
    # Initial update
    print("\nPerforming initial update...")
    update_display()
    
    # Main loop
    print(f"\nStarting polling loop (every {POLL_INTERVAL} seconds)...")
    print("Press Ctrl+C to stop\n")
    
    while running:
        try:
            time.sleep(POLL_INTERVAL)
            if running:  # Check again after sleep
                update_display()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)  # Wait a bit before retrying
    
    # Cleanup
    print("\nShutting down...")
    try:
        epd.sleep()
    except:
        pass
    print("Service stopped")

if __name__ == "__main__":
    main()

