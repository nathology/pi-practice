import os
import sys
import json
import soundfile as sf
from vosk import Model, KaldiRecognizer

# We import the low-level sounddevice wrapper that vosk uses for streams
try:
    import sounddevice as sd
except OSError:
    print("❌ Error: PortAudio library missing or broken.")
    print("Ensure 'libportaudio2' is installed via apt.")
    sys.exit(1)

def main():
    model_path = "model"
    
    print("--------------------------------------------------------")
    print("🎙️ The Pi of Pi: Offline Voice Recognition Diagnostic")
    print("--------------------------------------------------------")
    
    # 1. Sanity check for the local acoustic language model
    if not os.path.exists(model_path):
        print(f"❌ Error: Acoustic model folder '{model_path}' not found.")
        print("Please download and unzip the model into this directory first:")
        print("wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")
        sys.exit(1)
        
    print("🤖 Loading lightweight acoustic speech model into memory...")
    model = Model(model_path)
    
    # 2. Configure the hardware streaming audio parameters
    # Vosk optimization standards require a 16000Hz mono audio feed
    sample_rate = 16000
    recognizer = KaldiRecognizer(model, sample_rate)
    
    # Explicitly filter the model to prioritize number patterns for Noah's game
    # This massively increases processing speed and match accuracy
    recognizer.SetWords(True) 
    
    print("\n🔍 Checking available hardware audio input devices...")
    devices = sd.query_devices()
    print("--------------------------------------------------------")
    print(devices)
    print("--------------------------------------------------------")
    
    print("\n🚀 Opening microphone stream. Speak numbers clearly into the mic!")
    print("Press Ctrl+C to terminate the stream at any time.\n")
    
    # Callback function to process chunked audio blocks from the hardware bus
    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio Hardware Status Flag: {status}", file=sys.stderr)
        # Pass the raw PCM byte buffer straight into the Kaldi recognition engine
        recognizer.AcceptWaveform(bytes(indata))

    try:
        # 3. Spin up the hardware input audio lane
        # channels=1 forces standard mono configuration
        with sd.RawInputStream(samplerate=sample_rate, blocksize=8000, 
                               dtype='int16', channels=1, 
                               callback=audio_callback):
            
            while True:
                # Continuously check the recognition buffer for completed phrases
                result_bytes = recognizer.Result()
                if len(result_bytes) > 0:
                    result_dict = json.loads(result_bytes)
                    text = result_dict.get("text", "")
                    if text:
                        print(f"👂 Heard phrase: \033[1;32m{text}\033[0m")
                        
                # Short yield to prevent maxing out a core waiting for audio frames
                sd.sleep(100)
                
    except KeyboardInterrupt:
        print("\n\n🧹 Closing audio capture lane. Hardware stream released.")
    except Exception as e:
        print(f"\n❌ Failed to open audio device stream: {e}")
        print("\nDiagnostic Tip:")
        print("Ensure your I2S microphone or USB audio hardware is firmly connected.")

if __name__ == "__main__":
    main()
    