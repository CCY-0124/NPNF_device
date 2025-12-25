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

USE_4GRAY_MODE = True

# Global state
running = True
last_config = None
last_refresh_time = 0
epd = None

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
    global last_config, last_refresh_time
    
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
        
        # Check if we need to refresh
        config_key = (view_type, len(todos))  # Simple change detection
        
        if not should_refresh_display(config_key, last_config, last_refresh_time):
            print(f"  Skipping refresh (too soon since last update)")
            return
        
        print(f"  View: {view_type}, Tasks: {len(todos)}")
        
        # Use renderer system
        from renderers.renderers import get_renderer, list_renderers
        
        render_func = get_renderer(view_type)
        if not render_func:
            print(f"  Warning: Renderer for '{view_type}' not found")
            print(f"  Available renderers: {', '.join(list_renderers())}")
            return
        
        # Call render function
        image = render_func({'todos': todos}, config)
        
        # Display on e-ink
        print("  Updating display...")
        if USE_4GRAY_MODE:
            epd.display_4Gray(epd.getbuffer_4Gray(image))
        else:
            epd.display(epd.getbuffer(image.convert('1')))
        
        last_config = config_key
        last_refresh_time = time.time()
        print("  Display updated successfully")
            
    except Exception as e:
        print(f"  Error updating display: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main service loop"""
    global epd
    
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
        
        epd = epd7in5_V2.EPD()
        if USE_4GRAY_MODE:
            epd.init_4Gray()
            print("4-gray mode initialized")
        else:
            epd.init()
            print("Display initialized")
        epd.Clear()
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

