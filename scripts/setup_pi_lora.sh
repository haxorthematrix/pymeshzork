#!/bin/bash
# PyMeshZork Raspberry Pi LoRa Setup Script
# For use with Adafruit Radio + OLED Bonnet (RFM95W)
#
# Run with: sudo bash setup_pi_lora.sh

set -e

echo "========================================"
echo "PyMeshZork Raspberry Pi LoRa Setup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo bash $0"
    exit 1
fi

# Get the actual user (not root)
REAL_USER=${SUDO_USER:-$USER}
REAL_HOME=$(eval echo ~$REAL_USER)

echo "Installing for user: $REAL_USER"
echo "Home directory: $REAL_HOME"
echo ""

# Update system
echo "[1/6] Updating system packages..."
apt-get update
apt-get upgrade -y

# Install system dependencies
echo "[2/6] Installing system dependencies..."
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    i2c-tools \
    libgpiod2 \
    fonts-dejavu

# Enable I2C and SPI
echo "[3/7] Enabling I2C and SPI interfaces..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
    raspi-config nonint do_i2c 0
fi

if ! grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
    raspi-config nonint do_spi 0
fi

# Apply Pi 4 specific SPI fixes
echo "[4/7] Applying Pi 4 SPI fixes..."
CONFIG_TXT=""
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_TXT="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_TXT="/boot/config.txt"
fi

if [ -n "$CONFIG_TXT" ]; then
    # Add spi0-0cs overlay to disable kernel chip select management
    # This allows software control of the CS pin (needed for RFM95W)
    if ! grep -q "^dtoverlay=spi0-0cs" "$CONFIG_TXT"; then
        echo "Adding dtoverlay=spi0-0cs for software CS control..."
        echo "dtoverlay=spi0-0cs" >> "$CONFIG_TXT"
    fi

    # Disable vc4-kms-v3d on Pi 4 as it interferes with SPI timing
    # This is necessary for reliable SPI communication with the LoRa radio
    if grep -q "^dtoverlay=vc4-kms-v3d" "$CONFIG_TXT"; then
        echo "Disabling vc4-kms-v3d (conflicts with SPI on Pi 4)..."
        sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d  # Disabled for LoRa SPI/' "$CONFIG_TXT"
    fi
fi

# Add user to required groups
echo "[5/7] Adding user to gpio, i2c, spi groups..."
usermod -a -G gpio,i2c,spi $REAL_USER

# Clone or update PyMeshZork
echo "[6/7] Setting up PyMeshZork..."
INSTALL_DIR="$REAL_HOME/pymeshzork"

if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    sudo -u $REAL_USER git pull
else
    echo "Cloning PyMeshZork..."
    sudo -u $REAL_USER git clone https://github.com/haxorthematrix/pymeshzork.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Check out the LoRa branch if it exists
if git branch -r | grep -q "scenario-b-lora-hat"; then
    sudo -u $REAL_USER git checkout scenario-b-lora-hat
fi

# Create virtual environment and install
echo "[7/7] Installing Python dependencies..."
sudo -u $REAL_USER python3 -m venv "$INSTALL_DIR/.venv"
sudo -u $REAL_USER "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
sudo -u $REAL_USER "$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR[lora]"

# Create config file template
CONFIG_DIR="$REAL_HOME/.pymeshzork"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating config file template..."
    sudo -u $REAL_USER mkdir -p "$CONFIG_DIR"
    sudo -u $REAL_USER cat > "$CONFIG_FILE" << 'EOF'
{
  "lora": {
    "enabled": true,
    "frequency": 915.0,
    "tx_power": 23
  },
  "game": {
    "player_name": "Adventurer",
    "brief_mode": false,
    "auto_save": true
  }
}
EOF
    echo "Config created at: $CONFIG_FILE"
fi

# Create launch script
LAUNCH_SCRIPT="$INSTALL_DIR/run_zork_lora.sh"
sudo -u $REAL_USER cat > "$LAUNCH_SCRIPT" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python -m pymeshzork.cli --lora "$@"
EOF
chmod +x "$LAUNCH_SCRIPT"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Hardware setup required:"
echo "  1. Power off the Raspberry Pi"
echo "  2. Attach the Adafruit Radio + OLED Bonnet"
echo "  3. Attach antenna to the radio (IMPORTANT!)"
echo "  4. Power on and reboot"
echo ""
echo "To run PyMeshZork with LoRa:"
echo "  cd $INSTALL_DIR"
echo "  ./run_zork_lora.sh"
echo ""
echo "Or manually:"
echo "  source $INSTALL_DIR/.venv/bin/activate"
echo "  zork --lora"
echo ""
echo "Edit your player name in: $CONFIG_FILE"
echo ""
echo "A reboot is required for I2C/SPI changes."
read -p "Reboot now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    reboot
fi
