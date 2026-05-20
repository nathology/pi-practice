"""

"""

import RPi.GPIO as GPIO
import time

# Use Broadcom (BCM) pin numbering
GPIO.setmode(GPIO.BCM)

# List of all standard usable GPIO pins on a Pi Zero 2 W
POSSIBLE_PINS = [2, 3, 4, 17, 27, 22, 10, 9, 11, 5, 6, 13, 19, 26, 14, 15, 18, 23, 24, 25, 8, 7, 12, 16, 20, 21]

print("Initializing pins... setting up internal pull-up resistors.")
for pin in POSSIBLE_PINS:
    try:
        # Most handhelds wire buttons to connect to Ground when pressed,
        # so we set an internal Pull-Up resistor to look for a drop in voltage.
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except RuntimeError:
        # Skip pins that might be actively used by your I2S microphone or screen
        continue

print("\n=== GAMEPI BUTTON SCANNER IS LIVE ===")
print("Press any physical button on your device. Press Ctrl+C to exit.\n")

try:
    # Keep track of pins that are currently pressed down so we don't spam the screen
    pressed_pins = set()
    
    while True:
        for pin in POSSIBLE_PINS:
            try:
                # If the pin reads LOW (0), the button is being pushed to Ground
                if GPIO.input(pin) == GPIO.LOW:
                    if pin not in pressed_pins:
                        print(f" Detected button press on: BCM GPIO {pin}")
                        pressed_pins.add(pin)
                else:
                    if pin in pressed_pins:
                        pressed_pins.remove(pin)
            except RuntimeError:
                continue
                
        time.sleep(0.05) # Tiny delay to save CPU cycles

except KeyboardInterrupt:
    print("\nCleaning up GPIO states...")
    GPIO.cleanup()
    print("Scanner closed.")