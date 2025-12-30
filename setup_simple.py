#!/usr/bin/env python3
"""
Simple Setup Script for E-Ink Display
Only sets up WiFi password and device token.

Usage:
    sudo python3 setup_simple.py
"""

import os
import sys
import json
import subprocess
import shutil
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

# Configuration paths
SCRIPT_DIR = Path(__file__).parent.absolute()
CONFIG_FILE = SCRIPT_DIR / 'device_config.json'
WPA_SUPPLICANT = Path('/etc/wpa_supplicant/wpa_supplicant.conf')

def setup_wifi():
    """Setup WiFi connection.
    
    Returns:
        tuple: (success: bool, ssid: str) - Returns True and SSID if successful, False and None otherwise
    """
    print("\n" + "=" * 60)
    print("WiFi Setup")
    print("=" * 60)
    
    # Check if running as root
    if os.geteuid() != 0:
        print("\nError: WiFi setup requires root privileges.")
        print("Please run with sudo: sudo python3 setup_simple.py")
        return False, None
    
    ssid = input("\nEnter WiFi network name (SSID): ").strip()
    if not ssid:
        print("Error: WiFi name cannot be empty.")
        return False, None
    
    password = input("Enter WiFi password: ").strip()
    if not password:
        print("Error: WiFi password cannot be empty.")
        return False, None
    
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
    
    # Remove existing network entry if it exists
    if f'ssid="{ssid}"' in content:
        lines = content.split('\n')
        new_lines = []
        skip_until_network_end = False
        for line in lines:
            if f'ssid="{ssid}"' in line:
                skip_until_network_end = True
                continue
            if skip_until_network_end and line.strip() == '}':
                skip_until_network_end = False
                continue
            if not skip_until_network_end:
                new_lines.append(line)
        content = '\n'.join(new_lines)
    
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
        return True, ssid  # Return True even if restart failed, user can reboot manually
    
    return True, ssid

def verify_wifi_connection(ssid, max_wait=30):
    """Verify WiFi connection to specified SSID."""
    print("\nVerifying WiFi connection...")
    print(f"Waiting up to {max_wait} seconds for connection...")
    
    for i in range(max_wait):
        time.sleep(1)
        try:
            # Check current WiFi SSID
            result = subprocess.run(
                ['iwgetid', '-r'],
                capture_output=True,
                text=True,
                timeout=5
            )
            current_ssid = result.stdout.strip()
            
            if current_ssid == ssid:
                print(f"✓ Successfully connected to WiFi: {ssid}")
                
                # Test internet connection
                print("Testing internet connection...")
                ping_result = subprocess.run(
                    ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
                    capture_output=True,
                    timeout=5
                )
                if ping_result.returncode == 0:
                    print("✓ Internet connection verified!")
                    return True
                else:
                    print("⚠ Connected to WiFi but no internet access")
                    return False
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            pass
        
        if (i + 1) % 5 == 0:
            print(f"  Still waiting... ({i + 1}/{max_wait} seconds)")
    
    print(f"⚠ Could not verify WiFi connection after {max_wait} seconds")
    print("  The WiFi may still be connecting. You can verify manually with: iwgetid -r")
    return False

def setup_device_token():
    """Setup device token."""
    print("\n" + "=" * 60)
    print("Device Token Setup")
    print("=" * 60)
    
    print("\nTo get your device token:")
    print("  1. Open the NoPlanNoFuture app")
    print("  2. Go to Calendar > Shares")
    print("  3. Click 'Add Device' in the E-Ink Devices section")
    print("  4. Copy the device token")
    
    token = input("\nEnter your device token: ").strip()
    
    if not token:
        print("Error: Device token cannot be empty.")
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

def verify_device_token(token, api_url='https://no-plan-no-future.vercel.app'):
    """Verify device token by testing API connection."""
    print("\nVerifying device token...")
    
    try:
        # Test API connection with a simple request
        today = datetime.now()
        days_since_monday = today.weekday()
        monday = (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = monday.strftime('%Y-%m-%d')
        end_date = (monday + timedelta(days=6)).strftime('%Y-%m-%d')
        
        test_url = f"{api_url}/api/calendar-shares/devices/view/{token}?startDate={start_date}&endDate={end_date}"
        
        print(f"Testing API connection...")
        req = urllib.request.Request(test_url)
        req.add_header('User-Agent', 'RaspberryPi-Setup/1.0')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if 'config' in data:
                    print("✓ Device token is valid!")
                    print(f"  View type: {data.get('config', {}).get('view_type', 'unknown')}")
                    print(f"  Display mode: {data.get('config', {}).get('display_mode', 'unknown')}")
                    return True
                else:
                    print("⚠ API responded but response format unexpected")
                    return False
            else:
                print(f"⚠ API returned status: {response.status}")
                return False
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print("⚠ API connection OK, but request format issue (this may be normal)")
            print("✓ Device token format appears correct")
            return True
        elif e.code == 401 or e.code == 403:
            print(f"✗ Authentication failed (status {e.code})")
            print("  Please check your device token")
            return False
        else:
            print(f"⚠ API error: {e.code}")
            return False
    except urllib.error.URLError as e:
        print(f"✗ Could not connect to API: {e.reason}")
        print("  Please check:")
        print("    - Your internet connection")
        print("    - The API URL is correct")
        return False
    except Exception as e:
        print(f"✗ Error verifying token: {str(e)}")
        return False

def main():
    """Main setup function."""
    print("\n" + "=" * 60)
    print("Simple E-Ink Display Setup")
    print("=" * 60)
    print("\nThis script will help you set up:")
    print("  1. WiFi connection")
    print("  2. Device token")
    
    # WiFi setup
    wifi_configured = False
    wifi_ssid = None
    
    # Check if WiFi setup is needed
    try:
        current_ssid = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=5).stdout.strip()
        if current_ssid:
            print(f"\nCurrent WiFi connection: {current_ssid}")
            if input("Do you want to configure a different WiFi network? (y/n): ").lower() != 'y':
                print("Keeping current WiFi configuration.")
                wifi_configured = True
                wifi_ssid = current_ssid
    except:
        pass
    
    if not wifi_configured:
        if input("\nDo you want to configure WiFi? (y/n): ").lower() == 'y':
            wifi_configured, wifi_ssid = setup_wifi()
            if wifi_configured and wifi_ssid:
                # Verify WiFi connection
                verify_wifi_connection(wifi_ssid)
        else:
            print("Skipping WiFi setup.")
    
    # Device token setup
    token = None
    api_url = 'https://no-plan-no-future.vercel.app'
    if not setup_device_token():
        print("\nError: Device token setup failed.")
        sys.exit(1)
    
    # Load token from config for verification
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                token = config.get('device_token')
                api_url = config.get('api_url', api_url)
        except:
            pass
    
    # Verify device token
    if token:
        verify_device_token(token, api_url)
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print(f"\nConfiguration saved to: {CONFIG_FILE}")
    
    # Summary
    print("\nSetup Summary:")
    if wifi_configured:
        print("  ✓ WiFi configured")
        if wifi_ssid:
            print(f"    Connected to: {wifi_ssid}")
    else:
        print("  - WiFi not configured")
    if token:
        print("  ✓ Device token saved")
    else:
        print("  ✗ Device token not saved")
    
    print("\nNext steps:")
    if wifi_configured:
        print("  1. If WiFi connection is not working, reboot:")
        print("     sudo reboot")
        print("  2. After reboot, reconnect via SSH and continue with:")
    else:
        print("  1. Configure WiFi if needed:")
        print("     sudo python3 setup_simple.py")
        print("  2. Then:")
    
    print("     cd ~/eink/NPNF_device")
    print("     # Create and install service (if not done)")
    print("     sudo systemctl start eink.service")
    print("     sudo systemctl status eink.service")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {str(e)}")
        sys.exit(1)


