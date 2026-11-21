
import os
import time
from pathlib import Path

import serial
import soundfile as sf
import numpy as np
from dotenv import load_dotenv
from groq import Groq

# Configuration
PORT = "COM6"
BAUD_RATE = 921600
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

TOTAL_SAMPLES = SAMPLE_RATE * RECORD_SECONDS
TOTAL_BYTES = TOTAL_SAMPLES * 2

# Load API key
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

# Record fresh audio
print("Connecting to ESP32...")

ser = serial.Serial(PORT, BAUD_RATE, timeout=2)

try:
    time.sleep(2)

    print("\nSpeak now!")
    audio_data = bytearray()

    while len(audio_data) < TOTAL_BYTES:
        remaining = TOTAL_BYTES - len(audio_data)
        chunk = ser.read(min(4096, remaining))

        if chunk:
            audio_data.extend(chunk)

        progress = len(audio_data) / TOTAL_BYTES * 100
        print(f"\rRecording: {progress:.1f}%", end="")

finally:
    ser.close()

print("\nRecording completed!")

# Convert received audio
audio = np.frombuffer(audio_data, dtype=np.int16)

audio_path = Path(__file__).parent / "voice_test.wav"

sf.write(audio_path, audio, SAMPLE_RATE)

print("Sending fresh recording to Groq...")

# Speech recognition
try:
    with open(audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3-turbo",
            response_format="json",
            temperature=0.0
        )

    print("\nYou said:")
    print(result.text)

except Exception as error:
    print("Transcription error:", error)
