#!/bin/bash
# Deployment script for Raspberry Pi
# Automatically sets up e-ink display service

set -e

echo "=========================================="
echo "E-ink Display Service Deployment"
echo "=========================================="
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please do not run as root. Run as pi user."
   exit 1
fi

# Configuration
EINK_DIR="$HOME/eink"
SERVICE_NAME="eink.service"

echo "Step 1: Checking dependencies..."
echo "-----------------------------------"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    sudo apt update
    sudo apt install -y python3 python3-pip
fi

# Check pip packages
echo "Installing Python packages..."
pip3 install --user Pillow requests

# Check Waveshare library
if [ ! -d "$HOME/e-Paper" ]; then
    echo "Installing Waveshare e-Paper library..."
    cd ~
    git clone https://github.com/waveshare/e-Paper.git
    cd e-Paper/RaspberryPi_JetsonNano/python
    sudo python3 setup.py install
    cd ~
fi

echo
echo "Step 2: Setting up directory..."
echo "-----------------------------------"

# Create directory
mkdir -p "$EINK_DIR"
cd "$EINK_DIR"

echo "Working directory: $EINK_DIR"
echo
echo "Please ensure all Python files are in this directory:"
echo "  - api_client.py"
echo "  - eink_service.py"
echo "  - renderers.py"
echo "  - render_*.py (all renderer files)"
echo

read -p "Press Enter when files are ready..."

echo
echo "Step 3: Configuring API..."
echo "-----------------------------------"

# Update API_BASE in api_client.py
if [ -f "api_client.py" ]; then
    echo "Current API_BASE in api_client.py:"
    grep "API_BASE" api_client.py | head -1
    
    read -p "Enter your server URL (e.g., http://192.168.1.100:3001/api): " API_URL
    
    if [ ! -z "$API_URL" ]; then
        sed -i "s|API_BASE = \".*\"|API_BASE = \"$API_URL\"|" api_client.py
        echo "API_BASE updated to: $API_URL"
    fi
else
    echo "Warning: api_client.py not found!"
fi

echo
echo "Step 4: Setting up device token..."
echo "-----------------------------------"

read -p "Enter your device token: " DEVICE_TOKEN

if [ -z "$DEVICE_TOKEN" ]; then
    echo "Error: Device token is required!"
    exit 1
fi

echo
echo "Step 5: Testing connection..."
echo "-----------------------------------"

export EINK_DEVICE_TOKEN="$DEVICE_TOKEN"

echo "Testing API connection..."
if python3 test_api_connection.py; then
    echo "API connection test passed!"
else
    echo "Warning: API connection test failed. Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo
echo "Testing renderers..."
if python3 test_renderers.py; then
    echo "Renderer test passed!"
else
    echo "Warning: Renderer test failed. Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo
echo "Step 6: Setting up systemd service..."
echo "-----------------------------------"

# Update service file with device token
if [ -f "eink.service" ]; then
    sed -i "s|Environment=\"EINK_DEVICE_TOKEN=.*\"|Environment=\"EINK_DEVICE_TOKEN=$DEVICE_TOKEN\"|" eink.service
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=$EINK_DIR|" eink.service
    sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $EINK_DIR/eink_service.py|" eink.service
    
    # Copy to systemd
    sudo cp eink.service /etc/systemd/system/
    sudo systemctl daemon-reload
    
    echo "Service file installed"
else
    echo "Error: eink.service not found!"
    exit 1
fi

echo
echo "Step 7: Starting service..."
echo "-----------------------------------"

# Enable and start service
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "Service started!"
echo
echo "Step 8: Verifying service..."
echo "-----------------------------------"

sleep 2
sudo systemctl status "$SERVICE_NAME" --no-pager

echo
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo
echo "Useful commands:"
echo "  View logs:        sudo journalctl -u $SERVICE_NAME -f"
echo "  Check status:     sudo systemctl status $SERVICE_NAME"
echo "  Restart service:  sudo systemctl restart $SERVICE_NAME"
echo "  Stop service:     sudo systemctl stop $SERVICE_NAME"
echo




