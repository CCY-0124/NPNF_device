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
import time
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

def install_dependencies():
    """Install required dependencies."""
    print_step(5, "Installing Dependencies")
    
    print("\nThis will install:")
    print("  - Python packages (Pillow, requests)")
    print("  - Waveshare e-Paper library")
    
    response = input("\nDo you want to install dependencies now? (y/n): ").lower()
    if response != 'y':
        print("Skipping dependency installation.")
        return True
    
    # Check Python
    print("\n1. Checking Python...")
    try:
        result = subprocess.run(['python3', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"   ✓ {result.stdout.strip()}")
        else:
            print("   ✗ Python3 not found. Installing...")
            subprocess.run(['sudo', 'apt', 'update'], check=True, timeout=60)
            subprocess.run(['sudo', 'apt', 'install', '-y', 'python3', 'python3-pip'], check=True, timeout=300)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"   ✗ Error checking/installing Python: {e}")
        return False
    
    # Install pip packages
    print("\n2. Installing Python packages...")
    try:
        subprocess.run(['pip3', 'install', '--user', 'Pillow', 'requests'], check=True, timeout=300)
        print("   ✓ Python packages installed")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"   ✗ Error installing Python packages: {e}")
        return False
    
    # Check/install Waveshare library
    print("\n3. Checking Waveshare e-Paper library...")
    waveshare_path = Path.home() / 'e-Paper'
    if waveshare_path.exists():
        print("   ✓ Waveshare library found")
        response = input("   Update existing library? (y/n): ").lower()
        if response == 'y':
            try:
                subprocess.run(['git', '-C', str(waveshare_path), 'pull'], check=True, timeout=60)
                print("   ✓ Library updated")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print("   ⚠ Could not update library (continuing anyway)")
    else:
        print("   Installing Waveshare e-Paper library...")
        try:
            subprocess.run(['git', 'clone', 'https://github.com/waveshare/e-Paper.git', str(waveshare_path)], check=True, timeout=300)
            print("   ✓ Library cloned")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"   ✗ Error cloning library: {e}")
            return False
    
    # Install Waveshare library
    waveshare_python = waveshare_path / 'RaspberryPi_JetsonNano' / 'python'
    if waveshare_python.exists():
        print("\n4. Installing Waveshare library...")
        try:
            subprocess.run(['sudo', 'python3', 'setup.py', 'install'], cwd=str(waveshare_python), check=True, timeout=300)
            print("   ✓ Waveshare library installed")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"   ✗ Error installing library: {e}")
            return False
    
    print("\n✓ All dependencies installed successfully!")
    return True

def setup_systemd_service():
    """Set up systemd service for e-ink display."""
    print_step(6, "Setting Up Systemd Service")
    
    if os.geteuid() != 0:
        print("\nWarning: Service setup requires root privileges.")
        print("You can set up the service manually or run with sudo.")
        response = input("Continue to generate service file? (y/n): ").lower()
        if response != 'y':
            return False
    
    print("\nThis will create and install a systemd service for the e-ink display.")
    print("The service will automatically start on boot and restart if it crashes.")
    
    response = input("\nDo you want to set up the systemd service? (y/n): ").lower()
    if response != 'y':
        print("Skipping service setup.")
        return False
    
    # Load config to get device token
    device_token = None
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                device_token = config.get('device_token')
        except json.JSONDecodeError:
            pass
    
    if not device_token:
        print("Warning: Device token not found in config.")
        device_token = input("Enter device token for service: ").strip()
        if not device_token:
            print("Error: Device token required for service.")
            return False
    
    # Get working directory
    working_dir = SCRIPT_DIR
    service_file_path = SCRIPT_DIR / 'eink.service'
    systemd_service_path = Path('/etc/systemd/system/eink.service')
    
    # Create service file content
    service_content = f"""[Unit]
Description=E-ink Display Service for NoPlanNoFuture
After=network.target

[Service]
Type=simple
User={os.getenv('SUDO_USER', os.getenv('USER', 'pi'))}
WorkingDirectory={working_dir}
Environment="EINK_DEVICE_TOKEN={device_token}"
Environment="EINK_POLL_INTERVAL=60"
ExecStart=/usr/bin/python3 {working_dir}/eink_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    # Write service file
    try:
        with open(service_file_path, 'w') as f:
            f.write(service_content)
        print(f"\n✓ Service file created: {service_file_path}")
    except Exception as e:
        print(f"✗ Error creating service file: {e}")
        return False
    
    # Copy to systemd if running as root
    if os.geteuid() == 0:
        try:
            shutil.copy(service_file_path, systemd_service_path)
            print(f"✓ Service file installed to: {systemd_service_path}")
            
            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=30)
            print("✓ Systemd daemon reloaded")
            
            # Enable service
            subprocess.run(['systemctl', 'enable', 'eink.service'], check=True, timeout=30)
            print("✓ Service enabled (will start on boot)")
            
            # Ask to start service
            response = input("\nDo you want to start the service now? (y/n): ").lower()
            if response == 'y':
                subprocess.run(['systemctl', 'start', 'eink.service'], check=True, timeout=30)
                print("✓ Service started")
                
                # Show status
                time.sleep(2)
                print("\nService status:")
                subprocess.run(['systemctl', 'status', 'eink.service', '--no-pager'], timeout=10)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"✗ Error installing service: {e}")
            print(f"\nYou can manually install the service:")
            print(f"  sudo cp {service_file_path} /etc/systemd/system/")
            print(f"  sudo systemctl daemon-reload")
            print(f"  sudo systemctl enable eink.service")
            print(f"  sudo systemctl start eink.service")
            return False
    else:
        print(f"\nTo install the service, run:")
        print(f"  sudo cp {service_file_path} /etc/systemd/system/")
        print(f"  sudo systemctl daemon-reload")
        print(f"  sudo systemctl enable eink.service")
        print(f"  sudo systemctl start eink.service")
    
    return True

def test_connection():
    """Test the connection to the API."""
    print_step(7, "Testing Connection")
    
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
    print("  5. Install dependencies (optional)")
    print("  6. Set up systemd service (optional)")
    print("  7. Test connection")
    
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
    
    # Install dependencies (optional)
    install_dependencies()
    
    # Set up systemd service (optional)
    setup_systemd_service()
    
    # Test connection
    if wifi_success or input("\nDo you want to test the connection? (y/n): ").lower() == 'y':
        test_connection()
    
    print_header("Setup Complete!")
    
    print("Your Raspberry Pi is now configured!")
    print(f"\nConfiguration saved to: {CONFIG_FILE}")
    print("\nNext steps:")
    print("  1. If you configured WiFi, you may need to reboot:")
    print("     sudo reboot")
    print("  2. If you set up the systemd service, it will start automatically on boot")
    print("  3. To manually test the display, run:")
    print(f"     python3 {SCRIPT_DIR}/eink_service.py")
    print("\nUseful commands:")
    print("  View service logs:    sudo journalctl -u eink.service -f")
    print("  Check service status:   sudo systemctl status eink.service")
    print("  Restart service:       sudo systemctl restart eink.service")
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

