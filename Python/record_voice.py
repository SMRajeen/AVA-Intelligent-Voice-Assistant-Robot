
import serial
import numpy as np
import soundfile as sf
import time

PORT = "COM6"
BAUD_RATE = 921600
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

TOTAL_SAMPLES = SAMPLE_RATE * RECORD_SECONDS
TOTAL_BYTES = TOTAL_SAMPLES * 2

print("Connecting to ESP32...")

ser = serial.Serial(
    PORT,
    BAUD_RATE,
    timeout=5
)

time.sleep(2)

print("Recording started!")
print("Speak clearly into the INMP441 microphone.")

audio_data = bytearray()

try:
    while len(audio_data) < TOTAL_BYTES:
        remaining = TOTAL_BYTES - len(audio_data)

        chunk = ser.read(min(4096, remaining))

        if chunk:
            audio_data.extend(chunk)

        progress = len(audio_data) / TOTAL_BYTES * 100
        print(f"\rRecording: {progress:.1f}%", end="")

finally:
    ser.close()

print("\nRecording received!")

audio = np.frombuffer(
    audio_data,
    dtype=np.int16
)

sf.write(
    "voice_test.wav",
    audio,
    SAMPLE_RATE
)

print("Saved as voice_test.wav")
