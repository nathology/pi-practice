#!/usr/bin/env bash

# Exit immediately if any command fails
set -e

echo "🚀 Running internal repository configuration for The Pi of Pi..."

# 1. Establish the isolated Python Virtual Environment
echo "🐍 Initializing Python Virtual Environment (voice_env)..."
if [ ! -d "$HOME/voice_env" ]; then
    python3 -m venv "$HOME/voice_env"
    echo "✅ Created fresh virtual environment at $HOME/voice_env"
else
    echo "ℹ️ Existing virtual environment found at $HOME/voice_env"
fi

# 2. Upgrade base pip installation utilities
echo "⚙️ Upgrading core package management tools (pip, setuptools, wheel)..."
"$HOME/voice_env/bin/pip" install --upgrade pip setuptools wheel

# 3. Install Python project using pyproject.toml package links
if [ -f "pyproject.toml" ]; then
    echo "📦 Compiling and installing project dependencies via pyproject.toml..."
    # The dot tell pip to read the pyproject.toml file in the current working directory
    "$HOME/voice_env/bin/pip" install -e .
    echo "✅ Pyproject package dependencies compiled and installed successfully."
else
    echo "❌ Error: pyproject.toml not found in the current folder. Cannot verify dependencies."
    exit 1
fi

# 4. Prompt for system hardware configuration adjustments
echo ""
echo "--------------------------------------------------------"
echo "🛠️ Hardware Configuration Options"
echo "--------------------------------------------------------"
read -p "Do you want to optimize /boot/firmware/config.txt for the SPI OLED right now? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak
    
    if ! grep -q "dtoverlay=spi0-1cs" /boot/firmware/config.txt; then
        echo "Updating system device overlays..."
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