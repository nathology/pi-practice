#!/bin/bash
echo "🔓 Disabling OverlayFS and Write Protection..."
sudo raspi-config nonint disable_bootro
sudo raspi-config nonint disable_overlayfs

echo "🔄 Rebooting into Read-Write mode in 3 seconds..."
sleep 3
sudo reboot