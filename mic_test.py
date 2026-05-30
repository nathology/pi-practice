import os
import sys
import json
from vosk import Model, KaldiRecognizer

try:
    import sounddevice as sd
    import numpy as np
except OSError:
    print("❌ Error: PortAudio library missing or broken.")
    sys.exit(1)

def main():
    model_path = "model"
    
    print("--------------------------------------------------------")
    print("🎙️ The Pi of Pi: System Default Voice Test")
    print("--------------------------------------------------------")
    
    if not os.path.exists(model_path):
        print(f"❌ Error: Acoustic model folder '{model_path}' not found.")
        sys.exit(1)
        
    print("🤖 Loading lightweight acoustic speech model...")
    model = Model(model_path)
    
    RATE = 16000
    recognizer = KaldiRecognizer(model, RATE)
    recognizer.SetWords(True) 
    
    print(f"\n🚀 Opening default system audio channel ({RATE}Hz Mono)...")
    print("Speak numbers clearly into the mic! Press Ctrl+C to stop.\n")
    
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Hardware Audio Flag: {status}", file=sys.stderr)
            
        # SANITY CHECK: Ensure we aren't sending pure silence strings to Vosk.
        # If the incoming data block is completely dead/empty, skip passing it to Kaldi
        audio_array = np.frombuffer(indata, dtype=np.int16)
        if len(audio_array) == 0 or np.all(audio_array == 0):
            return
            
        try:
            recognizer.AcceptWaveform(audio_array.tobytes())
        except Exception:
            # Shield the callback execution thread from Kaldi state exceptions
            pass

    try:
        # device=None forces sounddevice to target the newly defined .asoundrc default
        with sd.RawInputStream(device=None,
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