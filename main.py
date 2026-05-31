import os
import sys
import json
import time
import queue
import threading
import numpy as np
import RPi.GPIO as GPIO
from gpiozero import Button
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from luma.core.render import canvas
from PIL import ImageFont

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
        # 1. Thread Synchronization Lock (Prevents state mutation mid-render)
        self.lock = threading.Lock()
        
        # 2. Baseline Pi string tracking memory metrics (1000 CORRECT decimal digits)
        self.pi_digits = (
            "314159265358979323846264338327950288419716939937510582097494459230"
            "781640628620899862803482534211706798214808651328230664709384460955"
            "058223172535940812848111745028410270193852110555964462294895493038"
            "196442881097566593344612847564823378678316527120190914564856692346"
            "034861045432664821339360726024914127372458700660631558817488152092"
            "096282925409171536436789259036001133053054882046652138414695194151"
            "160943305727036575959195309218611738193261179310511854807446237996"
            "274956735188575272489122793818301194912983367336244065664308602139"
            "494639522473719070217986094370277053921717629317675238467481846766"
            "940513200056812714526356082778577134275778960917363717872146844090"
            "122495343014654958537105079227968925892354201995611212902196086403"
            "441815981362977477130996051870721134999999837297804995105973173281"
            "609631859502445945534690830264252230825334468503526193118817101000"
            "313783875288658753320838142061717766914730359825349042875546873115"
            "956286388235378759375195778185778053217122680661300192787661119590"
            "92164201989"
        )
        
        # 3. Layout Configuration Adjustments (Optimized for Larger Sizing)
        self.WINDOW_SIZE = 12          
        self.MIN_INDEX = -12           
        self.MAX_INDEX = len(self.pi_digits) - self.WINDOW_SIZE
        
        # State Machine Variables
        self.mode = "SPLASH"           
        self.study_index = 0           
        self.needs_refresh = True
        self.running = True
        self.chord_active = False      
        
        # Test mode tracking structures
        self.test_attempts = {}        
        self.first_fail_index = None   
        self.test_point_spoken = False
        self.test_point_correct = False
        
        # Dictionary converting spoken words to string characters
        self.word_map = {
            "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3",
            "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
            "nine": "9"
        }

        # 4. Initialize Hardware Buttons via gpiozero (Tuned 30ms Debounce Window)
        print("🎮 Connecting tactile switches to GPIO registers...")
        self.btn_left = Button(5, pull_up=True, bounce_time=0.03)
        self.btn_menu = Button(6, pull_up=True, bounce_time=0.03, hold_time=1.5)
        self.btn_right = Button(13, pull_up=True, bounce_time=0.03)
        
        self.btn_menu.when_pressed = self.handle_menu_press
        self.btn_left.when_pressed = self.handle_left
        self.btn_right.when_pressed = self.handle_right
        self.btn_menu.when_held = self.handle_menu_long_press
        
        # 5. Load High-Legibility Scaled TrueType Fonts
        print("🔤 Loading large TrueType fonts into memory...")
        try:
            self.font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 11)
            self.font_main = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 15)
        except IOError:
            try:
                self.font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
                self.font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 15)
            except IOError:
                print("⚠️ Warning: DejaVu TrueType fonts missing. Falling back to default styling.")
                self.font_header = ImageFont.load_default()
                self.font_main = ImageFont.load_default()

        if hasattr(self.font_main, 'getbbox'):
            self.char_width = self.font_main.getbbox("0")[2]
        else:
            self.char_width = 8  

        # 6. Initialize OLED Hardware Interface Panel
        print("📺 Activating SPI SH1106 OLED Display Screen...")
        try:
            self.serial = spi(device=0, port=0, gpio_DC=24, gpio_RST=25)
            self.device = sh1106(self.serial, width=128, height=64, rotate=0)
        except Exception as e:
            print(f"❌ Screen Init Failure: {e}")
            sys.exit(1)

        self.render_display()

        # 7. Initialize Offline Audio Recognition Architecture
        print("🤖 Loading machine learning speech files into memory...")
        if not os.path.exists("model"):
            print("❌ Error: 'model' directory missing.")
            sys.exit(1)
        self.model = Model("model")
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.recognizer.SetWords(True)
        
        self.mode = "STUDY"
        self.needs_refresh = True

    def get_absolute_x(self, abs_idx):
        """Computes a fixed, un-jerkable absolute pixel offset from index 0."""
        if abs_idx <= 0:
            return abs_idx * self.char_width
            
        x = abs_idx * self.char_width
        x += 6  
        
        if abs_idx > 1:
            num_spaces = (abs_idx - 1) // 10
            x += num_spaces * 7  
            
        return x

    def handle_menu_press(self):
        """Fires the instant the Center button transitions to down/low status."""
        with self.lock:
            self.chord_active = False      

    def handle_left(self):
        """Fires when Left Button drops down."""
        with self.lock:
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
        with self.lock:
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
        with self.lock:
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
        with self.lock:
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
        with self.lock:
            with canvas(self.device) as draw:
                if self.mode == "SPLASH":
                    draw.rectangle((0, 0, 127, 63), outline="white", fill="black")
                    draw.text((15, 15), "THE PI OF PI", fill="white")
                    draw.text((12, 38), "🤖 Loading...", fill="white")
                    return
                    
                # 1. RENDER TRUNCATED PARITY HEADER SECTION
                mode_text = "STUDY" if self.mode == "STUDY" else "TEST"
                draw.text((1, 0), mode_text, font=self.font_header, fill="white")
                
                memorized_count = self.study_index + self.WINDOW_SIZE
                draw.text((68, 0), f"Digits: {max(0, memorized_count)}", font=self.font_header, fill="white")
                draw.line((0, 13, 127, 13), fill="white")
                
                # 2. LARGE VIEWPORT-MAPPED GRID ROW ENGINE (y=26)
                start_x = 6
                y_pos = 26
                
                window_left_x = self.get_absolute_x(self.study_index)
                
                for i in range(self.WINDOW_SIZE):
                    abs_idx = self.study_index + i
                    char_to_draw = " "
                    draw_sandwich_x = False
                    
                    show_dot = (abs_idx == 0)
                    
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
                    
                    cur_x = start_x + self.get_absolute_x(abs_idx) - window_left_x
                    
                    if char_to_draw != " ":
                        draw.text((cur_x, y_pos), char_to_draw, font=self.font_main, fill="white")
                    
                    if show_dot:
                        draw.text((cur_x + self.char_width - 2, y_pos), ".", font=self.font_main, fill="white")
                        
                    if draw_sandwich_x:
                        # Scaled 'X' Above the large character
                        draw.line((cur_x + 1, y_pos - 8, cur_x + self.char_width - 2, y_pos - 3), fill="white")
                        draw.line((cur_x + self.char_width - 2, y_pos - 8, cur_x + 1, y_pos - 3), fill="white")
                        
                        # Scaled 'X' Below the large character
                        draw.line((cur_x + 1, y_pos + 19, cur_x + self.char_width - 2, y_pos + 24), fill="white")
                        draw.line((cur_x + self.char_width - 2, y_pos + 19, cur_x + 1, y_pos + 24), fill="white")

    def run_loop(self):
        """Primary thread processing orchestration gate."""
        with sd.InputStream(device=0, samplerate=48000, channels=2, 
                            dtype='int16', blocksize=4800, 
                            callback=audio_producer_callback):
            
            print("\n🚀 System Initialized completely! Handheld engine running.")
            
            while self.running:
                # -----------------------------------------------------------
                # PATH A: STUDY MODE (Strict Isolation)
                # -----------------------------------------------------------
                if self.mode == "STUDY":
                    while not audio_queue.empty():
                        try:
                            audio_queue.get_nowait()
                        except queue.Empty:
                            break

                # -----------------------------------------------------------
                # PATH B: TEST MODE (Active Voice Processing)
                # -----------------------------------------------------------
                elif self.mode == "TEST" and self.first_fail_index is None:
                    while not audio_queue.empty():
                        try:
                            audio_data = audio_queue.get_nowait()
                            if self.recognizer.AcceptWaveform(audio_data):
                                res = json.loads(self.recognizer.Result())
                                text = res.get("text", "")
                                if text:
                                    print(f"🎙️ Captured speech tokens: {text}")
                                    self.process_voice_input(text)
                        except queue.Empty:
                            break
                
                # -----------------------------------------------------------
                # DISPLAY REFRESH ENGINE
                # -----------------------------------------------------------
                if self.needs_refresh:
                    self.needs_refresh = False
                    self.render_display()
                    
                time.sleep(0.01)


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