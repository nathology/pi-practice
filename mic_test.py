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
    
    # Vosk MUST receive 16000Hz mono data
    VOSK_RATE = 16000
    recognizer = KaldiRecognizer(model, VOSK_RATE)
    recognizer.SetWords(True) 
    
    # Hardware constraints for googlevoicehat-soundcard overlay
    HW_RATE = 44100
    
    print(f"\n🚀 Opening microphone stream on device (hw:0,0) at native {HW_RATE}Hz...")
    print("Speak numbers clearly into the mic! Press Ctrl+C to stop.\n")
    
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio Hardware Status Flag: {status}", file=sys.stderr)
            
        # 1. Convert the raw buffer into a 2D numpy matrix [frames, 2 channels]
        audio_data = np.frombuffer(indata, dtype=np.int16).reshape(-1, 2)
        
        # 2. Extract Channel 0 (Left channel data)
        left_channel = audio_data[:, 0]
        
        # 3. Mathematically downsample from 44100Hz to 16000Hz
        # Determine the target index array mapping
        duration = len(left_channel) / HW_RATE
        num_target_samples = int(duration * VOSK_RATE)
        
        src_indices = np.arange(len(left_channel))
        target_indices = np.linspace(0, len(left_channel) - 1, num_target_samples)
        
        # Linearly interpolate the signal array into the new sample density
        downsampled_data = np.interp(target_indices, src_indices, left_channel).astype(np.int16)
        
        # 4. Ship the perfectly downsampled mono stream to Vosk
        recognizer.AcceptWaveform(downsampled_data.tobytes())

    try:
        # Open hardware stream at 44100Hz, stereo (channels=2)
        with sd.RawInputStream(device=0,
                               samplerate=HW_RATE, 
                               blocksize=6000, # Clean buffer chunk size for 44.1kHz
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