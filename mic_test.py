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
            
        # 1. Convert the raw buffer into a 2D numpy matrix [frames, 2 channels]
        audio_data = np.frombuffer(indata, dtype=np.int16).reshape(-1, 2)
        
        # 2. Extract Channel 0 (Left channel data)
        left_channel = audio_data[:, 0]
        
        # 3. Mathematically downsample from 48000Hz down to 16000Hz (Exactly a 3:1 factor reduction)
        duration = len(left_channel) / HW_RATE
        num_target_samples = int(duration * VOSK_RATE)
        
        src_indices = np.arange(len(left_channel))
        target_indices = np.linspace(0, len(left_channel) - 1, num_target_samples)
        
        # Interpolate the signal array density cleanly
        downsampled_data = np.interp(target_indices, src_indices, left_channel).astype(np.int16)
        
        # 4. Hand the downsampled 16kHz mono chunk to Vosk
        recognizer.AcceptWaveform(downsampled_data.tobytes())

    try:
        # Open hardware stream at 48000Hz, stereo (channels=2)
        # blocksize=6000 cuts perfectly divisible slices out of a 48kHz flow
        with sd.RawInputStream(device=0,
                               samplerate=HW_RATE, 
                               blocksize=6000, 
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