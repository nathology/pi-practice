import time
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from luma.core.render import canvas
import RPi.GPIO as GPIO  # Import the underlying GPIO engine

def main():
    print("Initialising 1.3-inch SPI SH1106 OLED Display...")
    print("Connecting via Native Hardware SPI (Device 0)...")
    
    # Initialize the serial interface and device variable scope
    serial = None
    device = None
    
    try:
        # Hardware mapping strategy targeting /dev/spidev0.0
        serial = spi(device=0, port=0, gpio_DC=24, gpio_RST=25)
        device = sh1106(serial, width=128, height=64, rotate=0)
        
        print("Canvas binding complete. Sending text frame buffer...")
        
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white")
            draw.text((20, 15), "THE PI OF PI", fill="white")
            draw.text((25, 35), "Hello Noah! v3", fill="white")
            
        print("✅ Success! Check your physical OLED screen panel.")
        print("Keeping display active for 10 seconds before clean exit...")
        time.sleep(10)
        
    except Exception as e:
        print(f"\n❌ Hardware interface failure: {e}")
        
    finally:
        # The finally block ALWAYS runs before the script exits
        print("\n🧹 Releasing hardware pin registries cleanly...")
        GPIO.cleanup()
        print("Goodbye!")

if __name__ == "__main__":
    main()