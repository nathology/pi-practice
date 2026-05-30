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
    
    # Vosk strictly demands a 16000Hz stream
    VOSK_RATE = 16000
    recognizer = KaldiRecognizer(model, VOSK_RATE)
    recognizer.SetWords(True) 
    
    # Target the rigid hardware clock profile of the I2S microphone
    HW_RATE = 48000
    
    print(f"\n🚀 Opening microphone stream on device (hw:0,0) at native {HW_RATE}Hz...")
    print("Speak numbers clearly into the mic! Press Ctrl+C to stop.\n")
    
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio Hardware Status Flag: {status}", file=sys.stderr)
            
        # 1. Cast the raw buffer into a flat 1D array of 16-bit integers
        raw_samples = np.frombuffer(indata, dtype=np.int16)
        
        # 2. De-interleave the channels instantly:
        # Since it's stereo, even indices [0, 2, 4...] are Left channel data.
        left_channel = raw_samples[0::2]
        
        # 3. Downsample from 48kHz to 16kHz by pulling every 3rd sample.
        # This is blazingly fast and keeps memory alignments completely static.
        downsampled_data = left_channel[0::3]
        
        # 4. Hand the mono 16kHz chunk to Vosk
        recognizer.AcceptWaveform(downsampled_data.tobytes())

    try:
        # Open hardware stream at 48000Hz, stereo (channels=2)
        # blocksize=4800 captures exactly 100ms chunks, avoiding thread lag
        with sd.RawInputStream(device=0,
                               samplerate=HW_RATE, 
                               blocksize=4800, 
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
                        
                sd.sleep(40) # Keep looping tightly to empty the Vosk queue
                
    except KeyboardInterrupt:
        print("\n\n🧹 Closing audio capture lane. Hardware stream released.")
    except Exception as e:
        print(f"\n❌ Failed to open audio device stream: {e}")

if __name__ == "__main__":
    main()