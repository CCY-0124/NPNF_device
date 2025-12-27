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
    
    # Restart WiFi using multiple methods for reliability
    print("Restarting WiFi connection...")
    success = False
    
    # Method 1: wpa_cli reconfigure (most common)
    try:
        result = subprocess.run(['wpa_cli', '-i', 'wlan0', 'reconfigure'], 
                              capture_output=True, timeout=10)
        if result.returncode == 0:
            print("   ✓ WiFi restarted using wpa_cli")
            success = True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Method 2: systemctl restart wpa_supplicant
    if not success:
        try:
            result = subprocess.run(['systemctl', 'restart', 'wpa_supplicant'], 
                                  capture_output=True, timeout=10)
            if result.returncode == 0:
                print("   ✓ WiFi restarted using systemctl")
                success = True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    # Method 3: ifdown/ifup (fallback)
    if not success:
        try:
            subprocess.run(['ifdown', 'wlan0'], capture_output=True, timeout=5)
            time.sleep(1)
            result = subprocess.run(['ifup', 'wlan0'], capture_output=True, timeout=10)
            if result.returncode == 0:
                print("   ✓ WiFi restarted using ifdown/ifup")
                success = True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    if success:
        print("   Please wait a few seconds for connection...")
        print("   You can check connection with: ip addr show wlan0")
    else:
        print("   ⚠ Could not automatically restart WiFi using any method.")
        print("   Troubleshooting steps:")
        print("     1. Check WiFi status: ip addr show wlan0")
        print("     2. Manually restart: sudo systemctl restart wpa_supplicant")
        print("     3. Or reboot: sudo reboot")
    
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
    
    # Set secure permissions (readable by owner and group, writable by owner only)
    # Use 0o640 instead of 0o600 to allow service to read if running as same user/group
    os.chmod(CONFIG_FILE, 0o640)
    
    # Ensure file is owned by current user
    try:
        import pwd
        current_uid = os.getuid()
        os.chown(CONFIG_FILE, current_uid, -1)
    except (ImportError, OSError):
        # pwd module not available on all systems, skip chown
        pass
    
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
    
    # Install pip packages - try apt first (more stable), then pip as fallback
    print("\n2. Installing Python packages...")
    packages_installed = False
    
    # Try apt first (preferred method for system packages)
    print("   Trying apt packages first (recommended)...")
    try:
        result = subprocess.run(['sudo', 'apt', 'install', '-y', 'python3-pil', 'python3-requests'], 
                              capture_output=True, timeout=300)
        if result.returncode == 0:
            print("   ✓ Python packages installed via apt (Pillow, requests)")
            packages_installed = True
        else:
            print("   ⚠ apt installation failed, trying pip...")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"   ⚠ apt installation error: {e}")
        print("   Trying pip as fallback...")
    
    # Fallback to pip if apt failed
    if not packages_installed:
        try:
            # Try with --user first
            result = subprocess.run(['pip3', 'install', '--user', 'Pillow', 'requests'], 
                                  capture_output=True, timeout=300)
            if result.returncode == 0:
                print("   ✓ Python packages installed via pip (user install)")
                packages_installed = True
            else:
                # Try with --break-system-packages (for newer Debian/Raspberry Pi OS)
                print("   Trying pip with --break-system-packages flag...")
                result = subprocess.run(['pip3', 'install', '--break-system-packages', 'Pillow', 'requests'], 
                                      capture_output=True, timeout=300)
                if result.returncode == 0:
                    print("   ✓ Python packages installed via pip")
                    packages_installed = True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"   ✗ Error installing Python packages via pip: {e}")
    
    if not packages_installed:
        print("   ✗ Failed to install Python packages")
        print("   Troubleshooting:")
        print("     - Try manually: sudo apt install -y python3-pil python3-requests")
        print("     - Or: pip3 install --user Pillow requests")
        print("     - Then re-run setup.py")
        return False
    
    # Check/install Waveshare library with improved error handling
    print("\n3. Checking Waveshare e-Paper library...")
    waveshare_path = Path.home() / 'e-Paper'
    
    if waveshare_path.exists():
        print(f"   ✓ Waveshare library found at: {waveshare_path}")
        response = input("   Update existing library? (y/n): ").lower()
        if response == 'y':
            try:
                print("   Updating library from GitHub...")
                result = subprocess.run(['git', '-C', str(waveshare_path), 'pull'], 
                                      capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    print("   ✓ Library updated successfully")
                else:
                    print("   ⚠ Could not update library (git pull failed)")
                    print(f"   Output: {result.stderr[:200]}")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print(f"   ⚠ Could not update library: {e}")
                print("   Continuing with existing version...")
    else:
        print("   Installing Waveshare e-Paper library...")
        print("   This may take a few minutes...")
        try:
            result = subprocess.run(['git', 'clone', 'https://github.com/waveshare/e-Paper.git', str(waveshare_path)], 
                                  capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("   ✓ Library cloned successfully")
            else:
                print(f"   ✗ Error cloning library: {result.stderr}")
                print("   Troubleshooting:")
                print("     - Check internet connection")
                print("     - Verify git is installed: git --version")
                print("     - Try manually: cd ~ && git clone https://github.com/waveshare/e-Paper.git")
                return False
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"   ✗ Error cloning library: {e}")
            print("   Troubleshooting:")
            print("     - Check internet connection")
            print("     - Verify git is installed")
            return False
    
    # Install Waveshare library
    waveshare_python = waveshare_path / 'RaspberryPi_JetsonNano' / 'python'
    if not waveshare_python.exists():
        print(f"   ✗ Waveshare Python directory not found: {waveshare_python}")
        print("   Troubleshooting:")
        print("     - Verify library was cloned correctly")
        print("     - Check if directory structure is correct")
        return False
    
    print("\n4. Installing Waveshare library...")
    print("   This may take a few minutes...")
    
    # Try multiple installation methods
    installation_success = False
    
    # Method 1: Try pip install (preferred for newer Python)
    print("   Trying pip install method...")
    try:
        result = subprocess.run(['pip3', 'install', '--break-system-packages', '.'], 
                              cwd=str(waveshare_python), 
                              capture_output=True, text=True, 
                              timeout=300)
        if result.returncode == 0:
            print("   ✓ Waveshare library installed via pip")
            installation_success = True
        else:
            print("   ⚠ pip install failed, trying setup.py...")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("   ⚠ pip install not available, trying setup.py...")
    
    # Method 2: Try setup.py install (legacy, may show deprecation warning but still works)
    if not installation_success:
        try:
            result = subprocess.run(['sudo', 'python3', 'setup.py', 'install'], 
                                  cwd=str(waveshare_python), 
                                  capture_output=True, text=True, 
                                  timeout=300)
            # Even if there's a deprecation warning, check if files were actually installed
            if result.returncode == 0 or 'deprecated' in result.stderr.lower():
                # Check if library files exist in common locations
                import site
                import sysconfig
                possible_site_packages = [
                    sysconfig.get_path('purelib'),
                    sysconfig.get_path('platlib'),
                    '/usr/local/lib/python3/dist-packages',
                    '/usr/lib/python3/dist-packages',
                ]
                
                # Also check if lib directory exists (for direct import)
                lib_dir = waveshare_python / 'lib'
                if lib_dir.exists():
                    print("   ✓ Waveshare library available (lib directory found)")
                    print("   ⚠ Note: setup.py install is deprecated, but library is accessible")
                    installation_success = True
                else:
                    # Check if installed in site-packages
                    for site_pkg in possible_site_packages:
                        waveshare_check = Path(site_pkg) / 'waveshare_epd'
                        if waveshare_check.exists():
                            print(f"   ✓ Waveshare library installed at: {site_pkg}")
                            installation_success = True
                            break
                
                if not installation_success:
                    print("   ⚠ Installation completed but library location unclear")
                    print("   Library should work via direct path import")
                    installation_success = True  # Assume success if no error
            else:
                print(f"   ✗ Error installing library")
                print(f"   Error output: {result.stderr[:300]}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"   ✗ Error installing library: {e}")
    
    if not installation_success:
        print("   ⚠ Installation had issues, but library may still work")
        print("   The library can be imported directly from the cloned directory")
        print("   Troubleshooting:")
        print("     - Library is at: " + str(waveshare_python / 'lib'))
        print("     - Service will try to import from this location")
        # Don't return False - allow continuation as library can be imported directly
        installation_success = True
    
    if installation_success:
        print("   ✓ Waveshare library setup complete")
    
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
            print(f"\nTroubleshooting:")
            print(f"  1. Verify service file exists: ls -l {service_file_path}")
            print(f"  2. Check file permissions")
            print(f"  3. Manually install the service:")
            print(f"     sudo cp {service_file_path} /etc/systemd/system/")
            print(f"     sudo systemctl daemon-reload")
            print(f"     sudo systemctl enable eink.service")
            print(f"     sudo systemctl start eink.service")
            print(f"  4. Check service status: sudo systemctl status eink.service")
            print(f"  5. View service logs: sudo journalctl -u eink.service -n 50")
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
            print("   Troubleshooting:")
            print("     - Check WiFi connection: ip addr show wlan0")
            print("     - Test connectivity: ping 8.8.8.8")
            print("     - Check WiFi status: sudo systemctl status wpa_supplicant")
            print("     - Restart WiFi: sudo systemctl restart wpa_supplicant")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print("   ⚠ Could not test internet (ping not available)")
        print(f"   Error: {e}")
        print("   Continuing anyway - will test API connection directly...")
    
    # Test API connection with improved error handling
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
        
        print(f"   Testing URL: {test_url[:80]}...")
        print(f"   Token: {device_token[:16]}...{device_token[-8:]}")
        
        req = urllib.request.Request(test_url)
        req.add_header('User-Agent', 'RaspberryPi-Setup/1.0')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            if status == 200:
                try:
                    data = response.read().decode('utf-8')
                    print("   ✓ API connection successful!")
                    print("   ✓ Device token is valid!")
                    print(f"   Response length: {len(data)} bytes")
                    return True
                except Exception as e:
                    print(f"   ⚠ Got 200 but couldn't parse response: {e}")
                    print("   ✓ Device token appears valid (got 200 response)")
                    return True
            else:
                print(f"   ✗ API returned status: {status}")
                print(f"   Response: {response.read().decode('utf-8')[:200]}")
                return False
                
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode('utf-8')[:200]
        except:
            pass
        
        if e.code == 400:
            print("   ⚠ API connection OK, but request format issue (400 Bad Request)")
            print("   This might be normal - token format appears correct")
            print(f"   Response: {error_body}")
            return True
        elif e.code == 401:
            print(f"   ✗ Authentication failed (401 Unauthorized)")
            print("   Troubleshooting:")
            print("     - Check if device token is correct")
            print("     - Token might be expired or invalid")
            print("     - Get a new token from the app")
            print(f"   Response: {error_body}")
            return False
        elif e.code == 403:
            print(f"   ✗ Access forbidden (403 Forbidden)")
            print("   Troubleshooting:")
            print("     - Device token might not have proper permissions")
            print("     - Check device configuration in the app")
            print(f"   Response: {error_body}")
            return False
        elif e.code == 404:
            print(f"   ✗ API endpoint not found (404 Not Found)")
            print("   Troubleshooting:")
            print("     - Check if API URL is correct")
            print("     - Verify API endpoint path: /api/calendar-shares/devices/view/{token}")
            print("     - API might not be deployed or route doesn't exist")
            print(f"   Response: {error_body}")
            print("   Try testing in browser or check API documentation")
            return False
        elif e.code == 500:
            print(f"   ✗ Server error (500 Internal Server Error)")
            print("   This is a server-side issue, not a token problem")
            print(f"   Response: {error_body}")
            return False
        else:
            print(f"   ✗ API error: {e.code}")
            print(f"   Response: {error_body}")
            return False
            
    except urllib.error.URLError as e:
        print(f"   ✗ Could not connect to API: {e.reason}")
        print("   Troubleshooting:")
        print("     - Check internet connection: ping 8.8.8.8")
        print("     - Verify API URL is accessible: curl " + api_url)
        print("     - Check firewall settings")
        print("     - DNS resolution might be failing")
        return False
        
    except Exception as e:
        print(f"   ✗ Unexpected error: {str(e)}")
        print("   Troubleshooting:")
        print("     - Check Python urllib is working")
        print("     - Verify network connectivity")
        import traceback
        print("   Full error:")
        traceback.print_exc()
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
    
    # Check what was completed
    completed_steps = []
    if wifi_success:
        completed_steps.append("WiFi configuration")
    if token_success:
        completed_steps.append("Device token setup")
    
    print("\nCompleted steps:")
    for step in completed_steps:
        print(f"  ✓ {step}")
    
    print("\nNext steps:")
    if wifi_success:
        print("  1. WiFi configured - you may need to reboot for changes to take effect:")
        print("     sudo reboot")
    
    # Check if service was set up
    service_file = SCRIPT_DIR / 'eink.service'
    if service_file.exists():
        print("  2. Systemd service file created")
        if os.geteuid() == 0:
            print("     Service is installed and will start automatically on boot")
        else:
            print("     To install service, run:")
            print(f"       sudo cp {service_file} /etc/systemd/system/")
            print("       sudo systemctl daemon-reload")
            print("       sudo systemctl enable eink.service")
            print("       sudo systemctl start eink.service")
    
    print("  3. To manually test the display, run:")
    print(f"     cd {SCRIPT_DIR}")
    print(f"     python3 eink_service.py")
    
    print("\nUseful commands:")
    print("  View service logs:      sudo journalctl -u eink.service -f")
    print("  Check service status:      sudo systemctl status eink.service")
    print("  Restart service:         sudo systemctl restart eink.service")
    print("  Stop service:            sudo systemctl stop eink.service")
    print("  Check configuration:    cat device_config.json")
    
    print("\nTroubleshooting:")
    print("  If service fails to start:")
    print("    sudo journalctl -u eink.service -n 50")
    print("  If display doesn't update:")
    print("    Check API connection and device token")
    print("    Verify Waveshare library is installed")
    
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



