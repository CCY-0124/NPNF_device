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
   echo "Please do not run as root. Run as regular user."
   exit 1
fi

# Configuration - detect current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_DIR="$(pwd)"

# Use current directory if script is run from project directory, otherwise use script directory
if [ -f "$CURRENT_DIR/api_client.py" ] || [ -f "$CURRENT_DIR/eink_service.py" ]; then
    EINK_DIR="$CURRENT_DIR"
else
    EINK_DIR="$SCRIPT_DIR"
fi

# Get current user
CURRENT_USER="$USER"
SERVICE_NAME="eink.service"

echo "Detected working directory: $EINK_DIR"
echo "Detected user: $CURRENT_USER"

echo "Step 1: Checking dependencies..."
echo "-----------------------------------"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    sudo apt update
    sudo apt install -y python3 python3-pip
fi

# Install Python packages using apt (system packages)
echo "Installing Python packages via apt..."
sudo apt update
sudo apt install -y python3-pil python3-requests python3-rpi.gpio || {
    echo "Warning: Some packages not available via apt, trying pip with --break-system-packages..."
    pip3 install --user --break-system-packages Pillow requests RPi.GPIO || {
        echo "Error: Failed to install Python packages"
        exit 1
    }
}

# Verify packages are installed
echo "Verifying Python packages..."
python3 -c "import PIL; import requests; print('PIL and requests: OK')" || {
    echo "Error: Failed to import required packages"
    exit 1
}

# Check Waveshare library
if [ ! -d "$HOME/e-Paper" ]; then
    echo "Installing Waveshare e-Paper library..."
    cd ~
    git clone https://github.com/waveshare/e-Paper.git
    cd e-Paper/RaspberryPi_JetsonNano/python
    # Install without dependencies to avoid Jetson.GPIO issue
    sudo python3 setup.py install --no-deps || {
        echo "Warning: setup.py install failed, trying alternative method..."
        # Alternative: manually copy library
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        sudo mkdir -p "/usr/local/lib/python3.${PYTHON_VERSION#*.}/dist-packages/waveshare_epd"
        sudo cp -r lib/waveshare_epd/* "/usr/local/lib/python3.${PYTHON_VERSION#*.}/dist-packages/waveshare_epd/"
        sudo touch "/usr/local/lib/python3.${PYTHON_VERSION#*.}/dist-packages/waveshare_epd/__init__.py"
    }
    cd ~
else
    echo "Waveshare library directory already exists, skipping clone."
    echo "If you need to reinstall, run: cd ~/e-Paper/RaspberryPi_JetsonNano/python && sudo python3 setup.py install --no-deps"
fi

echo
echo "Step 2: Setting up directory..."
echo "-----------------------------------"

# Change to working directory
cd "$EINK_DIR"

echo "Working directory: $EINK_DIR"
echo

# Check for required files
MISSING_FILES=()
[ ! -f "api_client.py" ] && MISSING_FILES+=("api_client.py")
[ ! -f "eink_service.py" ] && MISSING_FILES+=("eink_service.py")
[ ! -f "renderers/renderers.py" ] && [ ! -f "renderers.py" ] && MISSING_FILES+=("renderers.py or renderers/renderers.py")

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "Warning: Some required files are missing:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    echo
    read -p "Press Enter to continue anyway, or Ctrl+C to cancel..."
else
    echo "Required files found in current directory."
fi

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
if [ -f "test_api_connection.py" ] && python3 test_api_connection.py; then
    echo "API connection test passed!"
else
    echo "Warning: API connection test failed or test file not found. Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo
echo "Testing renderers..."
if [ -f "test_renderers.py" ] && python3 test_renderers.py; then
    echo "Renderer test passed!"
else
    echo "Warning: Renderer test failed or test file not found. Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo
echo "Step 6: Setting up systemd service..."
echo "-----------------------------------"

# Create or update service file
if [ -f "eink.service" ]; then
    # Use existing service file
    TEMP_SERVICE=$(mktemp)
    cp eink.service "$TEMP_SERVICE"
else
    # Create service file from template
    echo "Creating eink.service file..."
    TEMP_SERVICE=$(mktemp)
    cat > "$TEMP_SERVICE" << EOF
[Unit]
Description=E-ink Display Service for NoPlanNoFuture
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$EINK_DIR
Environment="EINK_DEVICE_TOKEN=$DEVICE_TOKEN"
Environment="EINK_POLL_INTERVAL=60"
ExecStart=/usr/bin/python3 $EINK_DIR/eink_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
fi

# Update service file with current values
sed -i "s|Environment=\"EINK_DEVICE_TOKEN=.*\"|Environment=\"EINK_DEVICE_TOKEN=$DEVICE_TOKEN\"|" "$TEMP_SERVICE"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$EINK_DIR|" "$TEMP_SERVICE"
sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $EINK_DIR/eink_service.py|" "$TEMP_SERVICE"
sed -i "s|^User=.*|User=$CURRENT_USER|" "$TEMP_SERVICE"

# Copy to systemd
sudo cp "$TEMP_SERVICE" /etc/systemd/system/eink.service
rm "$TEMP_SERVICE"
sudo systemctl daemon-reload

echo "Service file installed with:"
echo "  User: $CURRENT_USER"
echo "  WorkingDirectory: $EINK_DIR"
echo "  Device Token: ${DEVICE_TOKEN:0:8}..."

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









