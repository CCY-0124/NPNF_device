# E-Ink Display Setup Guide

## Prerequisites
- Raspberry Pi with e-ink display connected
- Computer on the same network (for initial setup)
- Device token from NoPlanNoFuture app

## Step-by-Step Setup Instructions

### Step 1: Connect to Raspberry Pi

1. Connect the Raspberry Pi to your computer via USB cable or ensure both devices are on the same network
2. Wait approximately **1 minute** for the Raspberry Pi to fully boot

### Step 2: Open Command Prompt

**On Windows:**
- Press `Win + R`, type `cmd`, and press Enter
- Or search for "Command Prompt" in the Start menu

**On Mac/Linux:**
- Open Terminal

### Step 3: Connect via SSH

```bash
ssh npnf@raspberrypi.local
```

**Note:** When prompted for password, type `npnf` (the password will not be visible as you type). Press Enter after typing the password.

### Step 4: Navigate to Project Directory

```bash
cd ~/eink/NPNF_device
```

### Step 5: Run Setup Script

```bash
sudo python3 setup_simple.py
```

The script will guide you through:
1. WiFi setup (SSID and password)
2. Device token setup
3. **Automatic verification** of both WiFi and token

### Step 6: Enter Device Token

When prompted:
1. Open the NoPlanNoFuture app in your web browser
2. Go to **Calendar > Shares**
3. Click **"Add Device"** in the E-Ink Devices section
4. Copy the device token (it only shows once)
5. Paste the token when prompted

The script will automatically verify the token by testing the API connection.

### Step 7: Enter WiFi Credentials

When prompted:
1. Enter your WiFi network name (SSID)
2. Enter your WiFi password

The script will automatically verify the WiFi connection.

### Step 8: Reboot (if WiFi was configured)

```bash
sudo reboot
```

Wait for the Raspberry Pi to restart, then reconnect via SSH.

### Step 9: Install and Start Service

```bash
cd ~/eink/NPNF_device

# Create service file if it doesn't exist
cat > eink.service << 'EOF'
[Unit]
Description=E-ink Display Service for NoPlanNoFuture
After=network.target

[Service]
Type=simple
User=npnf
WorkingDirectory=/home/npnf/eink/NPNF_device
Environment="EINK_POLL_INTERVAL=60"
ExecStart=/usr/bin/python3 /home/npnf/eink/NPNF_device/eink_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Install service
sudo cp eink.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable eink.service
sudo systemctl start eink.service

# Check service status
sudo systemctl status eink.service
```

### Step 10: Troubleshooting

If you encounter any problems:
1. Check service logs: `sudo journalctl -u eink.service -f`
2. Verify configuration: `cat device_config.json`
3. Test API connection manually
4. **Call your best partner in the world for help**

## Verification

The setup script now automatically verifies:

### WiFi Verification
- Checks if connected to the specified SSID
- Tests internet connectivity
- Waits up to 30 seconds for connection

### Device Token Verification
- Tests API connection with the token
- Validates token format and authentication
- Displays device configuration (view type, display mode)

## Quick Reference

**SSH Connection:**
- Username: `npnf`
- Host: `raspberrypi.local`
- Password: `npnf`

**Project Directory:**
- `~/eink/NPNF_device`

**Useful Commands:**
```bash
# Check WiFi connection
iwgetid -r

# Check internet
ping -c 3 8.8.8.8

# View service logs
sudo journalctl -u eink.service -f

# Restart service
sudo systemctl restart eink.service

# Check service status
sudo systemctl status eink.service
```

