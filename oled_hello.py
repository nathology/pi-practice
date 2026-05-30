import time
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from luma.core.render import canvas

def main():
    print("Initialising 1.3-inch SPI SH1106 OLED Display...")
    print("Connecting via Native Hardware SPI (Device 0)...")
    
    try:
        # Hardware Mapping Strategy:
        # device=0 targets /dev/spidev0.0 (Native Chip Select 0 on Pin 24)
        # gpio_DC=24 mappings handle Data/Command, gpio_RST=25 handles Reset
        serial = spi(device=0, port=0, gpio_DC=24, gpio_RST=25)
        
        # Bind the serial interface to the SH1106 display driver engine
        device = sh1106(serial, width=128, height=64, rotate=0)
        
        print("Canvas binding complete. Sending text frame buffer...")
        
        # Open the drawing canvas context to render pixels
        with canvas(device) as draw:
            # Draw a border frame around the outer edge of the screen
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white")
            
            # Write your text strings centered on the glass matrix
            draw.text((20, 15), "THE PI OF PI", fill="white")
            draw.text((25, 35), "Hello Noah! v3", fill="white")
            
        print("✅ Success! Check your physical OLED screen panel.")
        print("Keeping display active for 10 seconds before clean exit...")
        time.sleep(10)
        
    except Exception as e:
        print(f"\n❌ Hardware interface initialization failure: {e}")
        print("\nDiagnostic Checklist:")
        print("1. Ensure you ran the script with 'sudo'")
        print("2. Ensure 'sudo ls -la /dev/spi*' shows spidev0.0 active")
        print("3. Check that your physical CS wire is connected firmly to Pin 24")

if __name__ == "__main__":
    main()