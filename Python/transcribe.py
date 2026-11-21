
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Load the API key from .env
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY was not found in .env")

# Connect to Groq
client = Groq(api_key=api_key)

# Locate the recorded audio
audio_path = Path(__file__).parent / "voice_test.wav"

if not audio_path.exists():
    raise FileNotFoundError(
        "voice_test.wav not found. Run record_voice.py first."
    )

print("Sending your voice to Groq...")
print("Recognizing speech...")

try:
    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3-turbo",
            response_format="json",
            temperature=0.0
        )

    print("\nYour recognized words:")
    print(transcription.text)

except Exception as error:
    print("\nSpeech recognition failed:")
    print(error)
