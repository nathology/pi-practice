import sys
import time
from gpiozero import Button
from signal import pause

# -------------------------------------------------------------------
# Hardware Pin Mapping Configuration
# Adjust these GPIO numbers to match your actual physical jumper wires!
# -------------------------------------------------------------------
BUTTON_LEFT_PIN  = 5   # Example GPIO pin for Left/Back
BUTTON_MENU_PIN  = 6   # Example GPIO pin for Menu/Select
BUTTON_RIGHT_PIN = 13  # Example GPIO pin for Right/Next

print("--------------------------------------------------------")
print("🎮 The Pi of Pi: Interactive Button Diagnostic")
print("--------------------------------------------------------")
print(f"Mapping Left Button  -> GPIO {BUTTON_LEFT_PIN}")
print(f"Mapping Menu Button  -> GPIO {BUTTON_MENU_PIN}")
print(f"Mapping Right Button -> GPIO {BUTTON_RIGHT_PIN}")
print("Press Ctrl+C to exit the diagnostic tool.\n")

try:
    # Initialize buttons with built-in internal pull-up resistors.
    # This assumes the other side of your physical button is wired to a GND pin.
    btn_left  = Button(BUTTON_LEFT_PIN,  pull_up=True, bounce_time=0.05)
    btn_menu  = Button(BUTTON_MENU_PIN,  pull_up=True, bounce_time=0.05)
    btn_right = Button(BUTTON_RIGHT_PIN, pull_up=True, bounce_time=0.05)
except Exception as e:
    print(f"❌ Failed to bind GPIO registers: {e}")
    sys.exit(1)

# Define clean callback functions for hardware events
def left_pressed():
    print("👈 [LEFT BUTTON] Pressed / Registered!")

def menu_pressed():
    print("🔘 [MENU/SELECT BUTTON] Pressed / Registered!")

def right_pressed():
    print("👉 [RIGHT BUTTON] Pressed / Registered!")

# Link the physical electrical drop (falling edge) to our functions
btn_left.when_pressed  = left_pressed
btn_menu.when_pressed  = menu_pressed
btn_right.when_pressed = right_pressed

print("🚀 Listening for physical hardware interactions... Press away!")

try:
    # Put the main thread to sleep cleanly, waiting exclusively for hardware interrupts
    pause()
except KeyboardInterrupt:
    print("\n🧹 Diagnostics closed gracefully. Hardware lanes released.")