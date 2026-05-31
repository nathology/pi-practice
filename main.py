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
        # 1. Baseline Pi string tracking memory metrics (1000 decimal digits)
        self.pi_digits = (
            "314159265358979323846264338327950288419716939937510582097494459230"
            "781640628620899862803482534211706798214808651328230664709384460955"
            "058223172535940812848111745028410270193852110555964462294895493038"
            "196442881097566593344612847564823378678316527120190914564856692346"
            "034861045432664821339360726024914127372458700660631558817488152092"
            "096282925409171536437892590360011330530548820466521384146951941511"
            "609433057270365759591953092186117381932611793105118548074462379962"
            "749567351885752724891227938183011949129833673362440656643086021394"
            "946395224737190702179860943702770539217176293176752384674818467669"
            "405132000568127145263560827785771342757789609173637178721468440901"
            "224953430146549585371050792279689258923542019956112129021960864034"
            "418159813629774771309960518707211349999998372978049951059731732816"
            "096318595024459455346908302642522308253344685035261931188171010003"
            "137838752886587533208381420617177669147303598253490428755468731159"
            "562863882353787593751957781857780532171226806613001927876611195909"
            "2164201989"
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
        self.chord_active = False      # Protection flag tracking multi-button inputs
        
        # Test mode tracking structures
        self.test_attempts = {}        # Maps absolute_index -> (digit_char, is_correct)
        self.first_fail_index = None   # Tracks the absolute index of Noah's first mistake
        self.test_point_spoken = False
        self.test_point_correct = False
        
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
        self.btn_menu.when_pressed = self.handle_menu_press
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

    def handle_menu_press(self):
        """Fires the instant the Center button transitions to down/low status."""
        self.chord_active = False      

    def handle_left(self):
        """Fires when Left Button drops down."""
        if self.mode != "STUDY":
            return
            
        if self.btn_menu.is_pressed:
            self.chord_active = True   
            step = self.WINDOW_SIZE
        else:
            step = 1
            
        self.study_index = max(self.MIN_INDEX, self.study_index - step)
        self.needs_refresh = True

    def handle_right(self):
        """Fires when Right Button drops down."""
        if self.mode != "STUDY":
            return
            
        if self.btn_menu.is_pressed:
            self.chord_active = True   
            step = self.WINDOW_SIZE
        else:
            step = 1
            
        self.study_index = min(self.MAX_INDEX, self.study_index + step)
        self.needs_refresh = True

    def handle_menu_long_press(self):
        """Fires when center menu key passes 1.5s threshold without chord activity."""
        if self.chord_active:
            print("ℹ️ Ignoring long press: Modifier chord action was actively deployed.")
            return                     

        if self.mode == "STUDY":
            self.mode = "TEST"
            self.test_attempts = {}       
            self.test_point_spoken = False
            self.test_point_correct = False
            self.first_fail_index = None  
            print(f"🚀 Entering TEST Mode at digit index: {self.study_index + self.WINDOW_SIZE}")
        elif self.mode == "TEST":
            self.mode = "STUDY"
            print("👈 Test exited. Keeping matching alignment frames.")
            
        self.needs_refresh = True

    def process_voice_input(self, text_chunk):
        """Tokenizes speech segments and scores accuracy against target array."""
        if self.first_fail_index is not None:
            return

        words = text_chunk.split()
        for word in words:
            if self.first_fail_index is not None:
                break

            current_test_idx = self.study_index + self.WINDOW_SIZE
            
            if current_test_idx >= len(self.pi_digits):
                break

            if word == "point":
                is_correct = (current_test_idx == 1)
                self.test_point_spoken = True
                self.test_point_correct = is_correct
                self.test_attempts[current_test_idx] = (".", is_correct)
                self.needs_refresh = True
                
                if not is_correct:
                    self.first_fail_index = current_test_idx
                    self.study_index += 1 
                    break
                    
            elif word in self.word_map:
                if current_test_idx < 0:
                    continue
                    
                digit = self.word_map[word]
                expected_digit = self.pi_digits[current_test_idx]
                is_correct = (digit == expected_digit)
                
                self.test_attempts[current_test_idx] = (digit, is_correct)
                self.needs_refresh = True
                
                if is_correct:
                    self.study_index += 1
                else:
                    self.first_fail_index = current_test_idx
                    self.study_index += 1
                    break

    def render_display(self):
        """Clears canvas buffers and drafts UI assets onto glass matrix geometry."""
        with canvas(self.device) as draw:
            if self.mode == "SPLASH":
                draw.rectangle((0, 0, 127, 63), outline="white", fill="black")
                draw.text((24, 15), "THE PI OF PI", fill="white")
                draw.text((20, 38), "🤖 Loading Vosk...", fill="white")
                return
                
            # 1. RENDER PARITY HEADER SECTION
            mode_text = "STUDY MODE" if self.mode == "STUDY" else "TEST MODE"
            draw.text((1, 0), mode_text, fill="white")
            
            memorized_count = self.study_index + self.WINDOW_SIZE
            draw.text((72, 0), f"Digits: {max(0, memorized_count)}", fill="white")
            draw.line((0, 11, 127, 11), fill="white")
            
            # 2. UNIFIED GRID ROW ENGINE (y=28)
            start_x = 4
            char_width = 6
            y_pos = 28
            
            for i in range(self.WINDOW_SIZE):
                abs_idx = self.study_index + i
                char_to_draw = " "
                draw_sandwich_x = False
                show_dot = False
                
                if abs_idx == 0:
                    if self.mode == "STUDY":
                        show_dot = True
                    elif self.mode == "TEST" and self.test_point_spoken and self.test_point_correct:
                        show_dot = True
                
                if 0 <= abs_idx < len(self.pi_digits):
                    if self.mode == "STUDY":
                        char_to_draw = self.pi_digits[abs_idx]
                    elif self.mode == "TEST":
                        if abs_idx in self.test_attempts:
                            char_to_draw, is_correct = self.test_attempts[abs_idx]
                            if not is_correct:
                                draw_sandwich_x = True
                        elif abs_idx < (self.study_index + self.WINDOW_SIZE):
                            char_to_draw = self.pi_digits[abs_idx]
                
                cur_x = start_x + (i * char_width)
                if char_to_draw != " ":
                    draw.text((cur_x, y_pos), char_to_draw, fill="white")
                
                if show_dot:
                    draw.text((cur_x + 4, y_pos), ".", fill="white")
                    
                if draw_sandwich_x:
                    # Small 'X' Above the target slot frame bounding cell
                    draw.line((cur_x, y_pos - 6, cur_x + 4, y_pos - 2), fill="white")
                    draw.line((cur_x + 4, y_pos - 6, cur_x, y_pos - 2), fill="white")
                    
                    # Small 'X' Below the target slot frame bounding cell
                    draw.line((cur_x, y_pos + 10, cur_x + 4, y_pos + 14), fill="white")
                    draw.line((cur_x + 4, y_pos + 10, cur_x, y_pos + 14), fill="white")

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
        if engine and hasattr(engine, 'device'):
            engine.device.clear()
        GPIO.cleanup()