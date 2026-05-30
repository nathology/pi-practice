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

if [ ! -f "$VENV_PACKAGES/lgpio.py" ]; then
    ln -s /usr/lib/python3/dist-packages/lgpio.py "$VENV_PACKAGES/"
    echo "   -> Linked lgpio.py core wrapper"
fi

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

# 5. Fetch and unpack local offline speech recognition model
echo "🤖 Checking for local offline speech recognition model..."
if [ ! -d "model" ]; then
    echo "   -> Model folder not found. Downloading lightweight Vosk acoustic model..."
    wget -q --show-progress https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    
    echo "   -> Unpacking model payload..."
    unzip -q vosk-model-small-en-us-0.15.zip
    mv vosk-model-small-en-us-0.15 model
    rm vosk-model-small-en-us-0.15.zip
    echo "✅ Speech recognition model asset verified and ready."
else
    echo "ℹ️ Existing offline speech model asset verified at ./model."
fi

# 6. Prompt for system hardware configuration adjustments
echo ""
echo "--------------------------------------------------------"
echo "🛠️ Hardware Configuration Options"
echo "--------------------------------------------------------"
read -p "Do you want to check and optimize /boot/firmware/config.txt right now? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create a unified backup before applying alterations
    sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.bak
    echo "💾 Created a configuration backup at /boot/firmware/config.txt.bak"

    NEEDS_REBOOT=false

    # A. Check and apply SPI display overlay logic
    if ! grep -q "dtoverlay=spi0-1cs" /boot/firmware/config.txt; then
        echo "   -> Injecting SPI OLED screen overlay..."
        sudo bash -c 'cat << EOF >> /boot/firmware/config.txt

# --- Added by Pi-Practice Setup Automation ---
dtoverlay=spi0-1cs
EOF'
        NEEDS_REBOOT=true
    else
        echo "ℹ️ SPI device overlay already present. Skipping..."
    fi

    # B. Check and apply I2S microphone bus configuration
    if ! grep -q "dtoverlay=rpi-i2s-audio" /boot/firmware/config.txt; then
        echo "   -> Injecting I2S generic microphone bus driver overlays..."
        sudo bash -c 'cat << EOF >> /boot/firmware/config.txt

# --- Added by Pi-Practice Audio Automation ---
dtparam=i2s=on
dtoverlay=rpi-i2s-audio
EOF'
        NEEDS_REBOOT=true
    else
        echo "ℹ️ I2S microphone hardware overlay already present. Skipping..."
    fi

    # C. Handle final messaging conditional on what changed
    if [ "$NEEDS_REBOOT" = true ]; then
        echo "✅ System hardware entries injected! A system reboot is required to activate overlays."
    else
        echo "✅ All hardware configuration profiles match requirements perfectly."
    fi
fi

echo ""
echo "--------------------------------------------------------"
echo "🎉 Setup Script Execution Complete!"
echo "--------------------------------------------------------"
if [ "$NEEDS_REBOOT" = true ]; then
    echo "⚠️  Please type: 'sudo reboot' to initialize your physical screen and mic."
else
    echo "Everything is primed. You can now run diagnostics entirely WITHOUT sudo:"
    echo "python oled_hello.py"
    echo "python button_test.py"
    echo "python mic_test.py"
fi
echo ""