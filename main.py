import os
import sys
import json
import time
import queue
import numpy as np
import RPi.GPIO as GPIO
from gpiozero import Button
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from luma.core.render import canvas

# Thread-safe container for incoming background audio packets
audio_queue = queue.Queue()

def audio_producer_callback(indata, frames, time_info, status):
    """Background high-speed audio thread callback."""
    if status:
        pass
    # Downsample 48kHz Stereo down to 16kHz Mono instantly using fast indexing
    raw_samples = indata[:, 0][::3]
    audio_queue.put(raw_samples.tobytes())


class GameEngine:
    def __init__(self):
        # 1. Hardcoded Pi string baseline for tracking memory metrics (300 digits)
        self.pi_digits = (
            "314159265358979323846264338327950288419716939937510582097494459230"
            "781640628620899862803482534211706798214808651328230664709384460955"
            "058223172535940812848111745028410270193852110555964462294895493038"
            "196442881097566593344612847564823378678316527120190914564856692346"
            "034861045432664821339360726024914127372458700660631558817488152092"
        )
        
        # 2. State Machine Variables
        self.mode = "SPLASH"  # Modes: SPLASH, STUDY, TEST
        self.study_index = 0  # Starting window cursor index for study view
        self.needs_refresh = True
        self.running = True
        
        # Test mode tracking structures: list of tuples -> (digit_char, is_correct)
        self.test_attempts = []
        self.test_target_offset = 0
        
        # Dictionary converting spoken words to string characters
        self.word_map = {
            "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3",
            "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
            "nine": "9"
        }

        # 3. Initialize Hardware Buttons via gpiozero
        print("🎮 Connecting tactile switches to GPIO registers...")
        self.btn_left = Button(5, pull_up=True, bounce_time=0.05)
        self.btn_menu = Button(6, pull_up=True, bounce_time=0.05, hold_time=1.5)
        self.btn_right = Button(13, pull_up=True, bounce_time=0.05)
        
        # Bind events to local callback logic hooks
        self.btn_left.when_pressed = self.handle_left
        self.btn_right.when_pressed = self.handle_right
        self.btn_menu.when_held = self.handle_menu_long_press
        
        # 4. Initialize OLED Hardware Interface Panel
        print("📺 Activating SPI SH1106 OLED Display Screen...")
        try:
            self.serial = spi(device=0, port=0, gpio_DC=24, gpio_RST=25)
            self.device = sh1106(self.serial, width=128, height=64, rotate=0)
        except Exception as e:
            print(f"❌ Screen Init Failure: {e}")
            sys.exit(1)

        # Draw splash screen instantly while loading the heavy Vosk language model
        self.render_display()

        # 5. Initialize Offline Audio Recognition Architecture
        print("🤖 Loading machine learning speech files into memory...")
        if not os.path.exists("model"):
            print("❌ Error: 'model' directory missing.")
            sys.exit(1)
        self.model = Model("model")
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.recognizer.SetWords(True)
        
        # Transition out of splash mode into primary loop layout
        self.mode = "STUDY"
        self.needs_refresh = True

    def handle_left(self):
        """Fires when Left Button drops down."""
        if self.mode != "STUDY":
            return
        
        # If the Center/Menu button is held down while tapping this
        if self.btn_menu.is_pressed:
            self.study_index = max(0, self.study_index - 10)  # Scroll Page
        else:
            self.study_index = max(0, self.study_index - 1)   # Scroll Digit
        self.needs_refresh = True

    def handle_right(self):
        """Fires when Right Button drops down."""
        if self.mode != "STUDY":
            return
            
        max_idx = len(self.pi_digits) - 10
        if self.btn_menu.is_pressed:
            self.study_index = min(max_idx, self.study_index + 10) # Scroll Page
        else:
            self.study_index = min(max_idx, self.study_index + 1)  # Scroll Digit
        self.needs_refresh = True

    def handle_menu_long_press(self):
        """Fires exclusively when the center menu key passes the 1.5s threshold."""
        if self.mode == "STUDY":
            self.mode = "TEST"
            self.test_attempts = []
            # Start testing the user on the digits directly following the visible study window
            self.test_target_offset = self.study_index + 10
            print(f"🚀 Switching to TEST Mode. Target digit index starts at: {self.test_target_offset}")
        elif self.mode == "TEST":
            self.mode = "STUDY"
            print("👈 Returning to STUDY Mode.")
            
        self.needs_refresh = True

    def process_voice_input(self, text_chunk):
        """Tokenizes speech segments and scores accuracy against the target array."""
        words = text_chunk.split()
        for word in words:
            digit = self.word_map.get(word)
            if digit is not None:
                current_test_idx = self.test_target_offset + len(self.test_attempts)
                
                # Check bounding limit against max string length
                if current_test_idx >= len(self.pi_digits):
                    break
                    
                expected_digit = self.pi_digits[current_test_idx]
                is_correct = (digit == expected_digit)
                
                # Commit the verification outcome to the state matrix
                self.test_attempts.append((digit, is_correct))
                self.needs_refresh = True

    def render_display(self):
        """Clears canvas buffers and drafts UI assets onto glass matrix geometry."""
        with canvas(self.device) as draw:
            if self.mode == "SPLASH":
                draw.rectangle((0, 0, 127, 63), outline="white", fill="black")
                draw.text((24, 15), "THE PI OF PI", fill="white")
                draw.text((20, 38), "🤖 Loading Vosk...", fill="white")
                
            elif self.mode == "STUDY":
                # Header Section
                draw.text((0, 0), "MODE: STUDY", fill="white")
                range_str = f"Idx: {self.study_index}-{self.study_index+9}"
                draw.text((70, 0), range_str, fill="white")
                draw.line((0, 11, 127, 11), fill="white")
                
                # Render the 10 digits cleanly spaced out across the middle screen
                visible_digits = self.pi_digits[self.study_index : self.study_index + 10]
                
                # Formatting exception rule: display '3.' if looking at the absolute origin
                display_string = ""
                for idx, d in enumerate(visible_digits):
                    if self.study_index == 0 and idx == 0:
                        display_string += "3. "
                    else:
                        display_string += f"{d} "
                        
                draw.text((5, 28), display_string.strip(), fill="white")
                
            elif self.mode == "TEST":
                # Header Section
                draw.text((0, 0), "MODE: TEST", fill="white")
                draw.line((0, 11, 127, 11), fill="white")
                
                # Row 1: Draw the original study baseline sequence anchor text
                base_digits = self.pi_digits[self.study_index : self.study_index + 10]
                draw.text((0, 15), f"Base: {base_digits}", fill="white")
                
                # Row 2: Draw user spoken responses horizontally. Max view width = 11 symbols.
                # If Noah speaks more than 11 characters, slide the display window dynamically.
                max_visible_test = 11
                total_attempts = len(self.test_attempts)
                
                if total_attempts <= max_visible_test:
                    visible_slice = self.test_attempts
                else:
                    visible_slice = self.test_attempts[-max_visible_test:]
                    
                draw.text((0, 36), "Heard: ", fill="white")
                
                # Dynamically calculate coordinates to overlay an X over any errors
                start_x = 42
                char_width = 7
                y_pos = 36
                
                for i, (char, is_correct) in enumerate(visible_slice):
                    cur_x = start_x + (i * char_width)
                    draw.text((cur_x, y_pos), char, fill="white")
                    
                    if not is_correct:
                        # Draw a small bounding box X directly through the wrong number string character
                        draw.line((cur_x, y_pos, cur_x + 5, y_pos + 8), fill="white")
                        draw.line((cur_x + 5, y_pos, cur_x, y_pos + 8), fill="white")

    def run_loop(self):
        """Primary thread processing orchestration gate."""
        # Open hardware recording device 0 natively at 48000Hz Stereo parameters
        with sd.InputStream(device=0, samplerate=48000, channels=2, 
                            dtype='int16', blocksize=4800, 
                            callback=audio_producer_callback):
            
            print("\n🚀 System Initialized completely! Handheld engine running.")
            print("Use hardware buttons or speak numbers to test. Press Ctrl+C to terminate.")
            
            while self.running:
                # 1. Non-blocking audio queue consumption to maintain UI fluidness
                try:
                    audio_data = audio_queue.get_nowait()
                    if self.mode == "TEST":
                        if self.recognizer.AcceptWaveform(audio_data):
                            res = json.loads(self.recognizer.Result())
                            text = res.get("text", "")
                            if text:
                                print(f"🎙️ Captured speech tokens: {text}")
                                self.process_voice_input(text)
                except queue.Empty:
                    pass
                
                # 2. Sequential frame update check to prevent flashing
                if self.needs_refresh:
                    self.render_display()
                    self.needs_refresh = False
                    
                # Balanced sleep cycle to prevent processor spikes
                time.sleep(0.02)


if __name__ == "__main__":
    engine = None
    try:
        engine = GameEngine()
        engine.run_loop()
    except KeyboardInterrupt:
        print("\n🧹 Intercepting shutdown sequence signal...")
    finally:
        print("🔒 Releasing pin configurations safely. Goodbye!")
        GPIO.cleanup()