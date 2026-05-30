import os
import sys
import json
import queue
import numpy as np
from vosk import Model, KaldiRecognizer

try:
    import sounddevice as sd
except OSError:
    print("❌ Error: PortAudio library missing or broken.")
    sys.exit(1)

# Thread-safe pipeline to bridge the background audio thread and the main thread
audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    if status:
        print(f"⚠️ Hardware Status Flag: {status}", file=sys.stderr)
    
    # indata arrives as a native numpy array of shape (frames, 2 channels)
    # 1. Isolate the Left channel: indata[:, 0]
    # 2. Instantly downsample 48kHz -> 16kHz by taking every 3rd sample: [::3]
    mono_16k = indata[:, 0][::3]
    
    # Push the raw array bytes into our thread-safe buffer queue
    audio_queue.put(mono_16k.tobytes())

def main():
    model_path = "model"
    
    print("--------------------------------------------------------")
    print("🎙️ The Pi of Pi: Thread-Safe Direct Hardware Voice Test")
    print("--------------------------------------------------------")
    
    if not os.path.exists(model_path):
        print(f"❌ Error: Acoustic model folder '{model_path}' not found.")
        sys.exit(1)
        
    print("🤖 Loading lightweight acoustic speech model...")
    model = Model(model_path)
    
    # Vosk initialization targeting strict 16000Hz mono data inputs
    recognizer = KaldiRecognizer(model, 16000)
    recognizer.SetWords(True) 
    
    # Explicitly target hardware Card 0 at its exact native hardware clock rate
    DEVICE_INDEX = 0
    HW_RATE = 48000
    CHANNELS = 2
    
    print(f"\n🚀 Opening hardware device {DEVICE_INDEX} directly at native {HW_RATE}Hz Stereo...")
    print("Streaming through isolated, thread-safe memory queue lanes.")
    print("Speak numbers clearly into the mic! Press Ctrl+C to stop.\n")
    
    try:
        # Open the physical stream. blocksize=4800 slices out clean 100ms chunks
        with sd.InputStream(device=DEVICE_INDEX,
                            samplerate=HW_RATE, 
                            channels=CHANNELS, 
                            dtype='int16', 
                            blocksize=4800, 
                            callback=audio_callback):
            
            while True:
                # Block execution until an audio chunk is safely produced by the hardware
                data = audio_queue.get()
                
                # Feed the data payload safely inside our single main execution thread
                if recognizer.AcceptWaveform(data):
                    result_dict = json.loads(recognizer.Result())
                    text = result_dict.get("text", "")
                    if text:
                        print(f"Heard phrase: \033[1;32m{text}\033[0m")
                else:
                    # Optional: Parse partial speech tracking results here if desired
                    pass
                
    except KeyboardInterrupt:
        print("\n\n🧹 Closing audio stream cleanly. Hardware lanes released.")
    except Exception as e:
        print(f"\n❌ Failed to open audio device stream: {e}")

if __name__ == "__main__":
    main()