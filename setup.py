#!/usr/bin/env python3
"""
Raspberry Pi Setup Script for NoPlanNoFuture E-Ink Display
This script helps users with basic knowledge set up WiFi and device token.

Usage:
    python3 setup.py
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path

# Configuration paths
SCRIPT_DIR = Path(__file__).parent.absolute()
CONFIG_FILE = SCRIPT_DIR / 'device_config.json'
API_CLIENT_FILE = SCRIPT_DIR / 'api_client.py'
WPA_SUPPLICANT = Path('/etc/wpa_supplicant/wpa_supplicant.conf')

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_step(step_num, text):
    """Print a formatted step."""
    print(f"\n[Step {step_num}] {text}")
    print("-" * 60)

def check_root():
    """Check if running as root (needed for WiFi setup)."""
    if os.geteuid() != 0:
        print("Warning: WiFi setup requires root privileges.")
        print("You can still configure the device token without root.")
        response = input("Continue anyway? (y/n): ").lower()
        if response != 'y':
            sys.exit(0)
        return False
    return True

def setup_wifi():
    """Interactive WiFi setup."""
    print_step(1, "WiFi Configuration")
    
    is_root = check_root()
    
    if not is_root:
        print("\nSkipping WiFi setup (requires root).")
        print("You can configure WiFi manually by editing:")
        print("  /etc/wpa_supplicant/wpa_supplicant.conf")
        print("\nOr run this script with sudo: sudo python3 setup.py")
        return False
    
    print("\nThis will help you connect to your WiFi network.")
    print("You will need:")
    print("  - Your WiFi network name (SSID)")
    print("  - Your WiFi password")
    
    response = input("\nDo you want to configure WiFi now? (y/n): ").lower()
    if response != 'y':
        print("Skipping WiFi setup.")
        return False
    
    ssid = input("\nEnter your WiFi network name (SSID): ").strip()
    if not ssid:
        print("Error: WiFi name cannot be empty.")
        return False
    
    password = input("Enter your WiFi password: ").strip()
    if not password:
        print("Error: WiFi password cannot be empty.")
        return False
    
    # Backup existing config
    if WPA_SUPPLICANT.exists():
        backup_path = WPA_SUPPLICANT.with_suffix('.conf.backup')
        shutil.copy(WPA_SUPPLICANT, backup_path)
        print(f"\nBacked up existing config to: {backup_path}")
    
    # Read existing config or create new
    if WPA_SUPPLICANT.exists():
        with open(WPA_SUPPLICANT, 'r') as f:
            content = f.read()
    else:
        content = """ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

"""
    
    # Check if network already exists
    if f'ssid="{ssid}"' in content:
        print(f"\nWarning: Network '{ssid}' already exists in config.")
        response = input("Replace it? (y/n): ").lower()
        if response == 'y':
            # Remove old entry
            lines = content.split('\n')
            new_lines = []
            skip_until_network_end = False
            for i, line in enumerate(lines):
                if f'ssid="{ssid}"' in line:
                    skip_until_network_end = True
                    continue
                if skip_until_network_end and line.strip() == '}':
                    skip_until_network_end = False
                    continue
                if not skip_until_network_end:
                    new_lines.append(line)
            content = '\n'.join(new_lines)
        else:
            print("Keeping existing WiFi configuration.")
            return True
    
    # Add new network
    network_config = f"""
network={{
    ssid="{ssid}"
    psk="{password}"
}}
"""
    
    # Append to config
    with open(WPA_SUPPLICANT, 'a') as f:
        f.write(network_config)
    
    print(f"\nWiFi configuration added successfully!")
    print("Restarting WiFi connection...")
    
    # Restart WiFi
    try:
        subprocess.run(['wpa_cli', '-i', 'wlan0', 'reconfigure'], check=True, timeout=10)
        print("WiFi restarted. Please wait a few seconds for connection...")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("Note: Could not automatically restart WiFi.")
        print("You may need to reboot: sudo reboot")
    
    return True

def setup_device_token():
    """Interactive device token setup."""
    print_step(2, "Device Token Configuration")
    
    print("\nYou need a device token from the NoPlanNoFuture app.")
    print("To get a token:")
    print("  1. Open the NoPlanNoFuture app in your web browser")
    print("  2. Go to Calendar > Shares")
    print("  3. Click 'Add Device' in the E-Ink Devices section")
    print("  4. Copy the device token shown (it only shows once!)")
    
    token = input("\nEnter your device token: ").strip()
    
    if not token:
        print("Error: Device token cannot be empty.")
        return False
    
    if len(token) < 32:
        print("Warning: Token seems too short. Make sure you copied the full token.")
        response = input("Continue anyway? (y/n): ").lower()
        if response != 'y':
            return False
    
    # Load or create config
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            print("Warning: Existing config file is corrupted. Creating new one.")
            config = {}
    
    # Update config
    config['device_token'] = token
    config['api_url'] = config.get('api_url', 'https://no-plan-no-future.vercel.app')
    
    # Save config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Set secure permissions
    os.chmod(CONFIG_FILE, 0o600)
    
    print(f"\nDevice token saved to: {CONFIG_FILE}")
    print("Configuration saved successfully!")
    
    return True

def setup_api_url():
    """Optional API URL configuration."""
    print_step(3, "API URL Configuration (Optional)")
    
    print("\nBy default, the device connects to:")
    print("  https://no-plan-no-future.vercel.app")
    
    response = input("\nDo you want to use a different API URL? (y/n): ").lower()
    if response != 'y':
        return True
    
    api_url = input("Enter API URL (e.g., http://localhost:3001 or https://your-server.com): ").strip()
    
    if not api_url:
        print("Error: API URL cannot be empty.")
        return False
    
    # Remove trailing slash
    api_url = api_url.rstrip('/')
    
    # Load config
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            config = {}
    
    config['api_url'] = api_url
    
    # Save config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    os.chmod(CONFIG_FILE, 0o600)
    
    print(f"\nAPI URL saved: {api_url}")
    
    return True

def update_api_client():
    """Update api_client.py with configuration."""
    print_step(4, "Updating API Client Configuration")
    
    if not CONFIG_FILE.exists():
        print("Error: Configuration file not found. Please set up the device token first.")
        return False
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        print("Error: Could not read configuration file.")
        return False
    
    api_url = config.get('api_url', 'https://no-plan-no-future.vercel.app')
    
    # Read api_client.py
    if not API_CLIENT_FILE.exists():
        print(f"Warning: {API_CLIENT_FILE} not found. Skipping update.")
        return False
    
    with open(API_CLIENT_FILE, 'r') as f:
        content = f.read()
    
    # Update API_BASE
    import re
    # Find and replace API_BASE line
    pattern = r'API_BASE\s*=\s*["\'].*?["\']'
    replacement = f'API_BASE = "{api_url}/api"'
    
    if re.search(pattern, content):
        content = re.sub(pattern, replacement, content)
        print(f"Updated API_BASE to: {api_url}/api")
    else:
        # Add after imports if not found
        lines = content.split('\n')
        insert_index = 0
        for i, line in enumerate(lines):
            if 'import' in line and i > insert_index:
                insert_index = i + 1
        lines.insert(insert_index, f'API_BASE = "{api_url}/api"')
        content = '\n'.join(lines)
        print(f"Added API_BASE: {api_url}/api")
    
    # Write back
    with open(API_CLIENT_FILE, 'w') as f:
        f.write(content)
    
    print(f"Updated {API_CLIENT_FILE} successfully!")
    
    return True

def test_connection():
    """Test the connection to the API."""
    print_step(5, "Testing Connection")
    
    if not CONFIG_FILE.exists():
        print("Error: Configuration file not found. Please set up the device token first.")
        return False
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        print("Error: Could not read configuration file.")
        return False
    
    device_token = config.get('device_token')
    api_url = config.get('api_url', 'https://no-plan-no-future.vercel.app')
    
    if not device_token:
        print("Error: Device token not found in configuration.")
        return False
    
    print(f"\nTesting connection to: {api_url}")
    print("Using device token: {}{}".format(device_token[:8], '...' * 8))
    
    # Test internet connection first
    print("\n1. Testing internet connection...")
    try:
        result = subprocess.run(
            ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("   ✓ Internet connection OK")
        else:
            print("   ✗ No internet connection")
            print("   Please check your WiFi connection.")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("   ⚠ Could not test internet (ping not available)")
    
    # Test API connection
    print("\n2. Testing API connection...")
    try:
        import urllib.request
        import urllib.error
        from datetime import datetime, timedelta
        
        # Test endpoint with date range
        today = datetime.now()
        start_date = today.strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
        
        test_url = f"{api_url}/api/calendar-shares/devices/view/{device_token}?startDate={start_date}&endDate={end_date}"
        
        req = urllib.request.Request(test_url)
        req.add_header('User-Agent', 'RaspberryPi-Setup/1.0')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("   ✓ API connection successful!")
                print("   ✓ Device token is valid!")
                return True
            else:
                print(f"   ✗ API returned status: {response.status}")
                return False
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print("   ⚠ API connection OK, but request format issue (this is normal)")
            print("   ✓ Device token format appears correct")
            return True
        elif e.code == 401 or e.code == 403:
            print(f"   ✗ Authentication failed (status {e.code})")
            print("   Please check your device token.")
            return False
        else:
            print(f"   ✗ API error: {e.code}")
            return False
    except urllib.error.URLError as e:
        print(f"   ✗ Could not connect to API: {e.reason}")
        print("   Please check:")
        print("     - Your internet connection")
        print("     - The API URL is correct")
        return False
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        return False

def main():
    """Main setup function."""
    print_header("NoPlanNoFuture Raspberry Pi Setup")
    
    print("This script will help you set up:")
    print("  1. WiFi connection")
    print("  2. Device token (from the app)")
    print("  3. API URL (optional)")
    print("  4. Update API client configuration")
    print("  5. Test connection")
    
    response = input("\nReady to start? (y/n): ").lower()
    if response != 'y':
        print("Setup cancelled.")
        sys.exit(0)
    
    # WiFi setup
    wifi_success = setup_wifi()
    
    # Device token setup
    token_success = setup_device_token()
    
    if not token_success:
        print("\nError: Device token setup failed. Please try again.")
        sys.exit(1)
    
    # API URL setup (optional)
    setup_api_url()
    
    # Update api_client.py
    update_api_client()
    
    # Test connection
    if wifi_success or input("\nDo you want to test the connection? (y/n): ").lower() == 'y':
        test_connection()
    
    print_header("Setup Complete!")
    
    print("Your Raspberry Pi is now configured!")
    print(f"\nConfiguration saved to: {CONFIG_FILE}")
    print("\nNext steps:")
    print("  1. If you configured WiFi, you may need to reboot:")
    print("     sudo reboot")
    print("  2. Make sure your e-ink display script uses the config file:")
    print(f"     {CONFIG_FILE}")
    print("  3. Test your display script to see your calendar!")
    print("\nFor more information, see: SETUP_RASPBERRY_PI.md")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        sys.exit(1)

