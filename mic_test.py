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
    print("🎙️ The Pi of Pi: Microphone Audio Diagnostic")
    print("--------------------------------------------------------")
    
    if not os.path.exists(model_path):
        print(f"❌ Error: Acoustic model folder '{model_path}' not found.")
        sys.exit(1)
        
    print("🤖 Loading lightweight acoustic speech model into memory...")
    model = Model(model_path)
    
    VOSK_RATE = 16000
    recognizer = KaldiRecognizer(model, VOSK_RATE)
    recognizer.SetWords(True) 
    
    HW_RATE = 48000
    
    print(f"\n🚀 Opening microphone stream on device (hw:0,0) at native {HW_RATE}Hz...")
    print("Speak or tap the mic. Press Ctrl+C to stop.\n")
    
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio Hardware Status Flag: {status}", file=sys.stderr)
            
        # 1. Interpret raw data buffer explicitly as 16-bit PCM integers
        raw_samples = np.frombuffer(indata, dtype=np.int16)
        
        if len(raw_samples) == 0:
            return

        # 2. Extract Left channel data
        left_channel = raw_samples[0::2]
        
        # 3. Downsample 48kHz -> 16kHz
        downsampled_data = left_channel[0::3]
        
        # 4. DIAGNOSTIC: Calculate real-time root-mean-square (Volume Level)
        # This checks if the mic is actually sending audio energy
        rms = np.sqrt(np.mean(downsampled_data.astype(np.float32)**2))
        
        # Print a simple visual audio level indicator
        meter = "■" * int(rms / 500)
        print(f"🎙️ Signal Level (RMS): {rms:6.1f} | {meter[:40]}", end="\r")
        
        # 5. Safely pass data to Vosk inside a protective block
        try:
            if len(downsampled_data) > 0:
                recognizer.AcceptWaveform(downsampled_data.tobytes())
        except Exception:
            # Prevent the engine crash from killing the script so we can see the logs
            pass

    try:
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
                        print(f"\nHeard phrase: \033[1;32m{text}\033[0m")
                        
                sd.sleep(40)
                
    except KeyboardInterrupt:
        print("\n\n🧹 Closing audio capture lane. Hardware stream released.")
    except Exception as e:
        print(f"\n❌ Failed to open audio device stream: {e}")

if __name__ == "__main__":
    main()