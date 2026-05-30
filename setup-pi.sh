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

# 3. Handle Python package installation in editable mode via pyproject.toml
if [ -f "pyproject.toml" ]; then
    echo "📦 Compiling and installing project dependencies in EDITABLE mode..."
    "$HOME/voice_env/bin/pip" install -e .
    echo "✅ Pyproject package dependencies compiled and linked successfully."
else
    echo "❌ Error: pyproject.toml not found in the current folder. Cannot verify dependencies."
    exit 1
fi

# 4. Inject System LGPIO Bindings into the Virtual Environment
echo "🔗 Injecting native lgpio architecture hooks into virtual environment..."
VENV_PACKAGES="$HOME/voice_env/lib/python3.13/site-packages"

# Symlink the main Python wrapper module if not already present
if [ ! -f "$VENV_PACKAGES/lgpio.py" ]; then
    ln -s /usr/lib/python3/dist-packages/lgpio.py "$VENV_PACKAGES/"
    echo "   -> Linked lgpio.py core wrapper"
fi

# Locate and dynamically symlink the architecture-specific shared C-library object
SYS_SO_FILE=$(ls /usr/lib/python3/dist-packages/_lgpio.cpython-313-*.so 2>/dev/null || true)
if [ -n "$SYS_SO_FILE" ]; then
    SO_FILENAME=$(basename "$SYS_SO_FILE")
    if [ ! -f "$VENV_PACKAGES/$SO_FILENAME" ]; then
        ln -s "$SYS_SO_FILE" "$VENV_PACKAGES/"
        echo "   -> Linked hardware binary: $SO_FILENAME"
    fi
else
    echo "⚠️ Warning: Native system _lgpio binary object not found. Hardware edge detection may fail."
fi

# 5. Prompt for system hardware configuration adjustments
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
echo "Everything is primed. You can now run diagnostics completely WITHOUT sudo:"
echo "python oled_hello.py"
echo "python button_test.py"
echo ""