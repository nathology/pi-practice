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
        # 1. Baseline Pi string tracking memory metrics (300 digits)
        self.pi_digits = (
            "314159265358979323846264338327950288419716939937510582097494459230"
            "781640628620899862803482534211706798214808651328230664709384460955"
            "058223172535940812848111745028410270193852110555964462294895493038"
            "196442881097566593344612847564823378678316527120190914564856692346"
            "034861045432664821339360726024914127372458700660631558817488152092"
        )
        
        # 2. Layout Configuration Adjustments
        self.WINDOW_SIZE = 20          # Base target digit slot width
        self.MIN_INDEX = -20           # Fully clear screen margin bounds
        self.MAX_INDEX = len(self.pi_digits) - self.WINDOW_SIZE
        
        # State Machine Variables
        self.mode = "SPLASH"           # Modes: SPLASH, STUDY, TEST
        self.study_index = 0           # Active operational pointer index tracking
        self.needs_refresh = True
        self.running = True
        
        # Test mode tracking structures
        self.test_attempts = []
        self.test_target_offset = 0
        self.first_fail_index = None   # Tracks the absolute index of Noah's first mistake
        
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

    def get_view_string(self, start_idx, mask_past_fail=True):
        """Generates visual layouts inserting decimal points contextually with failure masking."""
        s = ""
        for i in range(self.WINDOW_SIZE):
            abs_idx = start_idx + i
            if abs_idx < 0 or abs_idx >= len(self.pi_digits):
                s += " "
            # If reviewing a mistake, blank out any upcoming digits past the failure point
            elif mask_past_fail and self.first_fail_index is not None and abs_idx > self.first_fail_index:
                s += " "
            else:
                s += self.pi_digits[abs_idx]
                
        # Contextually inject the decimal point right next to the '3' (absolute index 0)
        slot_of_three = -start_idx
        if 0 <= slot_of_three < len(s) and s[slot_of_three] == "3":
            s = s[:slot_of_three + 1] + "." + s[slot_of_three + 1:]
        return s

    def handle_left(self):
        """Fires when Left Button drops down."""
        # Moving explicitly lifts any active failure study masks
        self.first_fail_index = None
        
        if self.mode != "STUDY":
            return
        step = self.WINDOW_SIZE if self.btn_menu.is_pressed else 1
        self.study_index = max(self.MIN_INDEX, self.study_index - step)
        self.needs_refresh = True

    def handle_right(self):
        """Fires when Right Button drops down."""
        # Moving explicitly lifts any active failure study masks
        self.first_fail_index = None
        
        if self.mode != "STUDY":
            return
        step = self.WINDOW_SIZE if self.btn_menu.is_pressed else 1
        self.study_index = min(self.MAX_INDEX, self.study_index + step)
        self.needs_refresh = True

    def handle_menu_long_press(self):
        """Fires when center menu key passes 1.5s threshold."""
        if self.mode == "STUDY":
            self.mode = "TEST"
            self.test_attempts = []
            self.first_fail_index = None  
            self.test_target_offset = self.study_index + self.WINDOW_SIZE
            print(f"🚀 Entering TEST Mode. Target offset starting index: {self.test_target_offset}")
        elif self.mode == "TEST":
            self.mode = "STUDY"
            if self.first_fail_index is not None:
                print(f"👈 Test exited. Aligning Study window to test baseline offset: {self.test_target_offset}")
                self.study_index = self.test_target_offset
            else:
                print("👈 Test exited perfectly with no errors.")
            
        self.needs_refresh = True

    def process_voice_input(self, text_chunk):
        """Tokenizes speech segments and scores accuracy against target array."""
        if self.first_fail_index is not None:
            return

        words = text_chunk.split()
        for word in words:
            if self.first_fail_index is not None:
                break

            actual_digits_attempted = sum(1 for char, _ in self.test_attempts if char != '.')
            current_test_idx = self.test_target_offset + actual_digits_attempted
            
            if current_test_idx >= len(self.pi_digits):
                break

            if word == "point":
                is_correct = (current_test_idx == 1)
                self.test_attempts.append((".", is_correct))
                self.needs_refresh = True
                
                if not is_correct:
                    self.first_fail_index = current_test_idx
                    break
                    
            elif word in self.word_map:
                if current_test_idx < 0:
                    continue
                    
                digit = self.word_map[word]
                expected_digit = self.pi_digits[current_test_idx]
                is_correct = (digit == expected_digit)
                
                self.test_attempts.append((digit, is_correct))
                self.needs_refresh = True
                
                if not is_correct:
                    self.first_fail_index = current_test_idx
                    break

    def render_display(self):
        """Clears canvas buffers and drafts UI assets onto glass matrix geometry."""
        with canvas(self.device) as draw:
            if self.mode == "SPLASH":
                draw.rectangle((0, 0, 127, 63), outline="white", fill="black")
                draw.text((24, 15), "THE PI OF PI", fill="white")
                draw.text((20, 38), "🤖 Loading Vosk...", fill="white")
                
            elif self.mode == "STUDY":
                draw.text((1, 0), "STUDY MODE", fill="white")
                
                # Digit tracking reflects exactly how many characters have scrolled past the right edge
                memorized_count = self.study_index + self.WINDOW_SIZE
                draw.text((72, 0), f"Digits: {max(0, memorized_count)}", fill="white")
                draw.line((0, 11, 127, 11), fill="white")
                
                # Mask future items if coming off a test error
                view_str = self.get_view_string(self.study_index, mask_past_fail=True)
                draw.text((2, 28), view_str, fill="white")
                
            elif self.mode == "TEST":
                draw.text((1, 0), "TEST MODE", fill="white")
                draw.line((0, 11, 127, 11), fill="white")
                
                # The reference line always displays the full target segment uncensored
                base_str = self.get_view_string(self.study_index, mask_past_fail=False)
                draw.text((2, 16), base_str, fill="white")
                draw.line((0, 29, 127, 29), fill="white")
                
                total_attempts = len(self.test_attempts)
                max_visible = self.WINDOW_SIZE + 1
                if total_attempts <= max_visible:
                    visible_slice = self.test_attempts
                else:
                    visible_slice = self.test_attempts[-max_visible:]
                    
                start_x = 2
                char_width = 6
                y_pos = 38
                
                for i, (char, is_correct) in enumerate(visible_slice):
                    cur_x = start_x + (i * char_width)
                    draw.text((cur_x, y_pos), char, fill="white")
                    
                    if not is_correct:
                        draw.line((cur_x, y_pos, cur_x + 4, y_pos + 8), fill="white")
                        draw.line((cur_x + 4, y_pos, cur_x, y_pos + 8), fill="white")

    def run_loop(self):
        """Primary thread processing orchestration gate."""
        with sd.InputStream(device=0, samplerate=48000, channels=2, 
                            dtype='int16', blocksize=4800, 
                            callback=audio_producer_callback):
            
            print("\n🚀 System Initialized completely! Handheld engine running.")
            
            while self.running:
                try:
                    audio_data = audio_queue.get_nowait()
                    if self.mode == "TEST" and self.first_fail_index is None:
                        if self.recognizer.AcceptWaveform(audio_data):
                            res = json.loads(self.recognizer.Result())
                            text = res.get("text", "")
                            if text:
                                print(f"🎙️ Captured speech tokens: {text}")
                                self.process_voice_input(text)
                except queue.Empty:
                    pass
                
                if self.needs_refresh:
                    self.render_display()
                    self.needs_refresh = False
                    
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