import os
import sys
import json
import numpy as np
from vosk import Model, KaldiRecognizer

try:
    import sounddevice as sd
except OSError:
    print("❌ Error: PortAudio library missing or broken.")
    sys.exit(1)

def main():
    model_path = "model"
    
    print("--------------------------------------------------------")
    print("🎙️ The Pi of Pi: Offline Voice Recognition Diagnostic")
    print("--------------------------------------------------------")
    
    if not os.path.exists(model_path):
        print(f"❌ Error: Acoustic model folder '{model_path}' not found.")
        sys.exit(1)
        
    print("🤖 Loading lightweight acoustic speech model into memory...")
    model = Model(model_path)
    
    sample_rate = 16000
    recognizer = KaldiRecognizer(model, sample_rate)
    recognizer.SetWords(True) 
    
    print("\n🚀 Opening microphone stream on device (hw:0,0). Speak numbers clearly!")
    print("Press Ctrl+C to terminate the stream at any time.\n")
    
    # Callback function optimized for the hardware's 2-channel payload layout
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio Hardware Status Flag: {status}", file=sys.stderr)
            
        # 1. Convert the raw buffer into a 2D numpy matrix [frames, channels]
        # 'int16' matches our dtype definition below
        audio_data = np.frombuffer(indata, dtype=np.int16).reshape(-1, 2)
        
        # 2. Extract Channel 0 (the primary hardware I2S line)
        left_channel = audio_data[:, 0]
        
        # 3. Ship the isolated mono byte stream down to the underlying C++ engine
        recognizer.AcceptWaveform(left_channel.tobytes())

    try:
        # We explicitly target device=0, channels=2 to match (hw:0,0) perfectly
        with sd.RawInputStream(device=0,
                               samplerate=sample_rate, 
                               blocksize=4000, 
                               dtype='int16', 
                               channels=2, 
                               callback=audio_callback):
            
            while True:
                result_bytes = recognizer.Result()
                if len(result_bytes) > 0:
                    result_dict = json.loads(result_bytes)
                    text = result_dict.get("text", "")
                    if text:
                        print(f"👂 Heard phrase: \033[1;32m{text}\033[0m")
                        
                sd.sleep(100)
                
    except KeyboardInterrupt:
        print("\n\n🧹 Closing audio capture lane. Hardware stream released.")
    except Exception as e:
        print(f"\n❌ Failed to open audio device stream: {e}")

if __name__ == "__main__":
    main()