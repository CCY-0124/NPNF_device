#!/bin/bash
# Update script for E-ink Display Service
# Updates code and dependencies

set -e

echo "=========================================="
echo "E-ink Display Service Update"
echo "=========================================="
echo

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EINK_DIR="$SCRIPT_DIR"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please do not run as root. Run as regular user."
   exit 1
fi

cd "$EINK_DIR"

echo "Step 1: Updating code from repository..."
echo "-----------------------------------"

# Check if this is a git repository
if [ -d ".git" ]; then
    echo "Detected git repository. Pulling latest changes..."
    git pull || {
        echo "Warning: Git pull failed. Continuing with manual update..."
    }
else
    echo "Not a git repository. Skipping git pull."
    echo "If you want to update from git, please:"
    echo "  1. Initialize git: git init"
    echo "  2. Add remote: git remote add origin <your-repo-url>"
    echo "  3. Pull: git pull origin main"
fi

echo
echo "Step 2: Updating Python dependencies..."
echo "-----------------------------------"

# Update system packages
echo "Updating Python packages via apt..."
sudo apt update
sudo apt install -y --upgrade python3-pil python3-requests python3-rpi.gpio || {
    echo "Warning: Failed to update via apt, trying pip with --break-system-packages..."
    pip3 install --user --upgrade --break-system-packages Pillow requests RPi.GPIO || {
        echo "Warning: Failed to update some packages"
    }
}

# Check Waveshare library
if [ -d "$HOME/e-Paper" ]; then
    echo "Updating Waveshare e-Paper library..."
    cd "$HOME/e-Paper"
    git pull || {
        echo "Warning: Failed to update Waveshare library"
    }
    cd "$HOME/e-Paper/RaspberryPi_JetsonNano/python"
    sudo python3 setup.py install --no-deps || {
        echo "Warning: Failed to reinstall Waveshare library"
    }
    cd "$EINK_DIR"
else
    echo "Waveshare library not found. Installing..."
    cd ~
    git clone https://github.com/waveshare/e-Paper.git || {
        echo "Warning: Failed to clone Waveshare library"
    }
    if [ -d "$HOME/e-Paper" ]; then
        cd "$HOME/e-Paper/RaspberryPi_JetsonNano/python"
        sudo python3 setup.py install --no-deps || {
            echo "Warning: Failed to install Waveshare library"
        }
    fi
    cd "$EINK_DIR"
fi

echo
echo "Step 3: Verifying configuration..."
echo "-----------------------------------"

# Check if config file exists
if [ -f "device_config.json" ]; then
    echo "Configuration file found: device_config.json"
else
    echo "Warning: device_config.json not found"
    echo "Please run setup.py to configure your device"
fi

# Check if service is running
if systemctl is-active --quiet eink.service 2>/dev/null; then
    echo
    echo "Step 4: Restarting service..."
    echo "-----------------------------------"
    echo "E-ink service is running. Restarting..."
    sudo systemctl restart eink.service
    sleep 2
    sudo systemctl status eink.service --no-pager || true
else
    echo
    echo "Step 4: Service status..."
    echo "-----------------------------------"
    echo "E-ink service is not running"
    echo "To start the service, run: sudo systemctl start eink.service"
fi

echo
echo "=========================================="
echo "Update Complete!"
echo "=========================================="
echo
echo "Useful commands:"
echo "  View logs:        sudo journalctl -u eink.service -f"
echo "  Check status:     sudo systemctl status eink.service"
echo "  Restart service:  sudo systemctl restart eink.service"
echo












