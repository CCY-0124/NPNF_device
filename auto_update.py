#!/usr/bin/env python3
"""
Auto Update Script for E-ink Display Service
Can be triggered by:
1. Systemd timer (scheduled updates)
2. API command (remote trigger)
"""

import os
import sys
import subprocess
import json
import requests
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / 'device_config.json'
UPDATE_SCRIPT = SCRIPT_DIR / 'update.sh'
API_BASE = os.getenv('EINK_API_BASE', 'https://no-plan-no-future.vercel.app/api')

def load_config():
    """Load device configuration"""
    if not CONFIG_FILE.exists():
        return None
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def check_api_for_update_command(device_token):
    """Check API for update command"""
    try:
        url = f"{API_BASE}/calendar-shares/devices/update-check/{device_token}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('update_required', False)
        elif response.status_code == 404:
            # Endpoint doesn't exist yet, that's OK
            return False
        else:
            return False
    except Exception as e:
        print(f"Error checking API for update command: {e}")
        return False

def run_update():
    """Run the update script"""
    if not UPDATE_SCRIPT.exists():
        print(f"Error: Update script not found at {UPDATE_SCRIPT}")
        return False
    
    try:
        # Make sure script is executable
        os.chmod(UPDATE_SCRIPT, 0o755)
        
        # Run update script
        result = subprocess.run(
            ['bash', str(UPDATE_SCRIPT)],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running update script: {e}")
        return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto update script for E-ink Display Service')
    parser.add_argument('--check-api', action='store_true', 
                       help='Check API for update command before updating')
    parser.add_argument('--force', action='store_true',
                       help='Force update without checking API')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("E-ink Display Service Auto Update")
    print("=" * 50)
    print()
    
    # Load config to get device token
    config = load_config()
    device_token = config.get('device_token', '') if config else ''
    
    # Check API if requested
    if args.check_api:
        if not device_token:
            print("Warning: No device token found, skipping API check")
            should_update = True
        else:
            print("Checking API for update command...")
            should_update = check_api_for_update_command(device_token)
            
            if should_update:
                print("Update command received from API")
            else:
                print("No update command from API, skipping update")
                return 0
    else:
        should_update = True
    
    # Run update
    if should_update or args.force:
        print("Running update...")
        success = run_update()
        
        if success:
            print("\nUpdate completed successfully")
            return 0
        else:
            print("\nUpdate failed")
            return 1
    else:
        print("Update skipped")
        return 0

if __name__ == "__main__":
    sys.exit(main())

