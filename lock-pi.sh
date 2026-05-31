#!/bin/bash
echo "🔒 Re-enabling OverlayFS and Write Protection..."
sudo raspi-config nonint enable_overlayfs
sudo raspi-config nonint enable_bootro

echo "🔄 Freezing filesystem and rebooting into secure mode..."
sleep 3
sudo reboot