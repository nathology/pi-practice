import os
import sys
import json
from vosk import Model, KaldiRecognizer

try:
    import sounddevice as sd
except OSError:
    print("❌ Error: PortAudio library missing or broken.")
    sys.exit(1)

def main():
    model_path = "model"
    
    print("--------------------------------------------------------")
    print("🎙️ The Pi of Pi: Optimized Voice Recognition Test")
    print("--------------------------------------------------------")
    
    if not os.path.exists(model_path):
        print(f"❌ Error: Acoustic model folder '{model_path}' not found.")
        sys.exit(1)
        
    print("🤖 Loading lightweight acoustic speech model...")
    model = Model(model_path)
    
    # Pristine target variables match our ALSA plugin configuration exactly
    RATE = 16000
    recognizer = KaldiRecognizer(model, RATE)
    recognizer.SetWords(True) 
    
    # Target our custom ALSA plugin device name string
    DEVICE_NAME = "vosk_mic"
    
    print(f"\n🚀 Listening via ALSA virtual device '{DEVICE_NAME}' ({RATE}Hz Mono)...")
    print("Speak numbers clearly into the mic! Press Ctrl+C to stop.\n")
    
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Status: {status}", file=sys.stderr)
        # indata is already a pristine 16000Hz mono byte block!
        recognizer.AcceptWaveform(bytes(indata))

    try:
        # Open our clean virtual device channel
        with sd.RawInputStream(device=DEVICE_NAME,
                               samplerate=RATE, 
                               blocksize=4000, 
                               dtype='int16', 
                               channels=1, 
                               callback=audio_callback):
            
            while True:
                result_bytes = recognizer.Result()
                if len(result_bytes) > 0:
                    result_dict = json.loads(result_bytes)
                    text = result_dict.get("text", "")
                    if text:
                        print(f"Heard phrase: \033[1;32m{text}\033[0m")
                        
                sd.sleep(50)
                
    except KeyboardInterrupt:
        print("\n\n🧹 Closing audio stream cleanly.")
    except Exception as e:
        print(f"\n❌ Failed to open audio device stream: {e}")

if __name__ == "__main__":
    main()