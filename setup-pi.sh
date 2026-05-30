#!/usr/bin/env bash

# Exit immediately if any command fails
set -e

echo "🚀 Running internal repository configuration for The Pi of Pi..."

# 1. Establish the isolated Python Virtual Environment
# Creating it in the user's home directory keeps it separated from code updates
echo "🐍 Initializing Python Virtual Environment (voice_env)..."
if [ ! -d "$HOME/voice_env" ]; then
    python3 -m venv "$HOME/voice_env"
    echo "✅ Created fresh virtual environment at $HOME/voice_env"
else
    echo "ℹ️ Existing virtual environment found at $HOME/voice_env"
fi

# 2. Upgrade base pip ecosystem installation tools
echo "⚙️ Upgrading core package management tools (pip, setuptools, wheel)..."
"$HOME/voice_env/bin/pip" install --upgrade pip setuptools wheel

# 3. Install Python requirements from the repository
if [ -f "requirements.txt" ]; then
    echo "📦 Installing repository Python dependencies from requirements.txt..."
    "$HOME/voice_env/bin/pip" install -r requirements.txt
    echo "✅ Python requirements installed successfully."
else
    echo "⚠️ Warning: requirements.txt not found in current directory. Skipping pip installation."
fi

# 4. Prompt for system hardware configuration adjustments
echo ""
echo "--------------------------------------------------------"
echo "🛠️ Hardware Configuration Options"
echo "--------------------------------------------------------"
read -p "Do you want to optimize /boot/firmware/config.txt for the SPI OLED right now? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create a backup of the config file just in case
    sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak
    
    # Check if spi0-1cs is already present; if not, safely append it to the [all] block
    if ! grep -q "dtoverlay=spi0-1cs" /boot/firmware/config.txt; then
        echo "Updating system device overlays..."
        # Append to the end of the file
        sudo bash -c 'cat << EOF >> /boot/firmware/config.txt

# --- Added by Pi-Practice Setup Automation ---
# Force rebuild standard SPI device paths on boot for SH1106 OLED
dtoverlay=spi0-1cs
EOF'
        echo "✅ Hardware overlay added. A system reboot will be required later."
    else
        echo "ℹ️ SPI device overlay already present. Skipping file modification."
    fi
fi

echo ""
echo "--------------------------------------------------------"
echo "🎉 Setup Script Execution Complete!"
echo "--------------------------------------------------------"
echo "To test your OLED screen panel using your virtual environment, run:"
echo "sudo ~/voice_env/bin/python oled_hello.py"
echo ""