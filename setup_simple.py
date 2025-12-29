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
from pathlib import Path

# Configuration paths
SCRIPT_DIR = Path(__file__).parent.absolute()
CONFIG_FILE = SCRIPT_DIR / 'device_config.json'
WPA_SUPPLICANT = Path('/etc/wpa_supplicant/wpa_supplicant.conf')

def setup_wifi():
    """Setup WiFi connection."""
    print("\n" + "=" * 60)
    print("WiFi Setup")
    print("=" * 60)
    
    # Check if running as root
    if os.geteuid() != 0:
        print("\nError: WiFi setup requires root privileges.")
        print("Please run with sudo: sudo python3 setup_simple.py")
        return False
    
    ssid = input("\nEnter WiFi network name (SSID): ").strip()
    if not ssid:
        print("Error: WiFi name cannot be empty.")
        return False
    
    password = input("Enter WiFi password: ").strip()
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
    
    return True

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

def main():
    """Main setup function."""
    print("\n" + "=" * 60)
    print("Simple E-Ink Display Setup")
    print("=" * 60)
    print("\nThis script will help you set up:")
    print("  1. WiFi connection")
    print("  2. Device token")
    
    # WiFi setup
    setup_wifi()
    
    # Device token setup
    if not setup_device_token():
        print("\nError: Device token setup failed.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print(f"\nConfiguration saved to: {CONFIG_FILE}")
    print("\nNext steps:")
    print("  1. If you configured WiFi, you may need to reboot:")
    print("     sudo reboot")
    print("  2. Start the e-ink service:")
    print("     sudo systemctl start eink.service")
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

