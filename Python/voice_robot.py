
import os
import time
import asyncio
from pathlib import Path

import serial
import numpy as np
import soundfile as sf
import pygame
import edge_tts

from dotenv import load_dotenv
from groq import Groq


# ==========================================
# CONFIGURATION
# ==========================================

PORT = "COM6"
BAUD_RATE = 921600

SAMPLE_RATE = 16000
RECORD_SECONDS = 10

TOTAL_SAMPLES = SAMPLE_RATE * RECORD_SECONDS
TOTAL_BYTES = TOTAL_SAMPLES * 2

VOICE_THRESHOLD = 500
SLEEP_AFTER_SECONDS = 15

VOICE = "en-US-AvaNeural"
VOICE_RATE = "-4%"
VOICE_PITCH = "+4Hz"
VOICE_VOLUME = "+0%"

CHAT_MODEL = "openai/gpt-oss-20b"
STT_MODEL = "whisper-large-v3-turbo"

BASE_DIR = Path(__file__).parent

AUDIO_FILE = BASE_DIR / "voice_input.wav"
RESPONSE_FILE = BASE_DIR / "response.mp3"


# ==========================================
# AI SETUP
# ==========================================

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

conversation = [
    {
        "role": "system",
        "content": (
            "You are Ava, a cute, sweet, warm and intelligent female personal "
            "voice assistant. Your personality is friendly, cheerful, expressive "
            "and natural. Speak as if you are smiling gently while talking. "
            "Use natural conversational phrasing, gentle enthusiasm, occasional "
            "playful humour and warm expressions. Do not sound childish, robotic, "
            "exaggerated or overly dramatic. Avoid excessive exclamation marks. "
            "Keep responses concise and easy to understand when spoken aloud. "
            "Respond in English by default. Understand Tamil too, and respond in "
            "Tamil when the user speaks Tamil. Remember the conversation history "
            "and use it for follow-up questions."
        )
    }
]

ser = None
noise_floor = 200.0

# True while ESP32 is sending binary microphone audio.
recording_in_progress = False


# ==========================================
# ESP32 SERIAL CONNECTION
# ==========================================

def send_command(command):

    if ser is None or not ser.is_open:
        raise ConnectionError("ESP32 serial connection is not available.")

    ser.write((command + "\n").encode("ascii"))
    ser.flush()


def connect_esp32():

    global ser

    print("\nConnecting to Ava's ESP32...")

    ser = serial.Serial(
        PORT,
        BAUD_RATE,
        timeout=0.25,
        write_timeout=3
    )

    # ESP32 may restart when the serial port opens.
    time.sleep(2.5)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # IMPORTANT:
    # Do not send IDLE here.
    # The ESP32 firmware starts Ava in SLEEPING state.

    print("ESP32 connected.")
    print("Ava is sleeping. Press the button to wake her.")


def disconnect_esp32():

    global ser

    if ser is not None and ser.is_open:

        try:

            if not recording_in_progress:

                print("\nSending Ava to sleep...")

                send_command("SLEEP")
                time.sleep(0.7)

            else:

                print(
                    "\nAudio transfer was incomplete. "
                    "Not sending commands during binary recording."
                )

        except Exception as error:

            print(f"Shutdown warning: {error}")

        finally:

            ser.close()

    print("Ava program disconnected.")


# ==========================================
# BUTTON WAKE-UP
# ==========================================

def wait_for_button():

    print("\nAva is sleeping.")
    print("Press the physical button to wake her.")

    while True:

        if ser is None or not ser.is_open:
            raise ConnectionError("ESP32 connection lost.")

        message = ser.readline().decode(
            "ascii",
            errors="ignore"
        ).strip()

        if message == "WAKE":

            print("\nPhysical button pressed!")
            print("Ava is waking up...")

            # ESP32 performs its waking animation for 1.2 seconds.
            time.sleep(1.3)

            return


# ==========================================
# MICROPHONE RECORDING
# ==========================================

def record_frame():

    global recording_in_progress

    if recording_in_progress:
        raise RuntimeError("A microphone recording is already active.")

    audio_data = bytearray()

    send_command("RECORD")
    recording_in_progress = True

    deadline = time.monotonic() + 15

    try:

        while len(audio_data) < TOTAL_BYTES:

            if time.monotonic() > deadline:

                raise TimeoutError(
                    f"Microphone timeout: received "
                    f"{len(audio_data)} of {TOTAL_BYTES} bytes."
                )

            remaining = TOTAL_BYTES - len(audio_data)

            chunk = ser.read(min(4096, remaining))

            if chunk:
                audio_data.extend(chunk)

        recording_in_progress = False

        return np.frombuffer(
            audio_data,
            dtype=np.int16
        ).copy()

    except KeyboardInterrupt:

        # Finish draining the current recording before sending SLEEP.
        print("\nFinishing current audio transfer...")

        drain_deadline = time.monotonic() + 15

        while (
            len(audio_data) < TOTAL_BYTES
            and time.monotonic() < drain_deadline
        ):

            remaining = TOTAL_BYTES - len(audio_data)

            chunk = ser.read(min(4096, remaining))

            if chunk:
                audio_data.extend(chunk)

        if len(audio_data) == TOTAL_BYTES:
            recording_in_progress = False

        raise


# ==========================================
# VOICE ACTIVITY DETECTION
# ==========================================

def is_speech(audio):

    global noise_floor

    if audio.size == 0:
        return False

    rms = float(
        np.sqrt(
            np.mean(audio.astype(np.float64) ** 2)
        )
    )

    threshold = max(
        VOICE_THRESHOLD,
        noise_floor * 2.2
    )

    detected = rms >= threshold

    if not detected:

        noise_floor = (
            noise_floor * 0.95
        ) + (
            rms * 0.05
        )

    return detected


# ==========================================
# SPEECH RECOGNITION
# ==========================================

def transcribe_audio(audio):

    sf.write(
        AUDIO_FILE,
        audio,
        SAMPLE_RATE,
        subtype="PCM_16"
    )

    with open(AUDIO_FILE, "rb") as audio_file:

        result = client.audio.transcriptions.create(
            file=audio_file,
            model=STT_MODEL,
            response_format="json",
            temperature=0.0
        )

    return result.text.strip()


# ==========================================
# AI RESPONSE
# ==========================================

def generate_response(user_text):

    conversation.append({
        "role": "user",
        "content": user_text
    })

    print("\nAva is thinking...")

    try:

        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=conversation,
            max_completion_tokens=300
        )

        answer = response.choices[0].message.content.strip()

        conversation.append({
            "role": "assistant",
            "content": answer
        })

        return answer

    except Exception:

        conversation.pop()
        raise


# ==========================================
# TEXT TO SPEECH
# ==========================================

async def generate_speech(text):

    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate=VOICE_RATE,
        pitch=VOICE_PITCH,
        volume=VOICE_VOLUME
    )

    await communicate.save(str(RESPONSE_FILE))


def speak(text):

    print("\nPreparing Ava's voice...")

    asyncio.run(
        generate_speech(text)
    )

    print(f"\nAva: {text}\n")

    send_command("SPEAKING")

    pygame.mixer.music.load(str(RESPONSE_FILE))
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():

        pygame.time.Clock().tick(30)

    pygame.mixer.music.unload()

    send_command("IDLE")


# ==========================================
# AWAKE CONVERSATION
# ==========================================

def run_awake_session():

    last_activity_time = time.monotonic()

    print("\nAva is listening. Speak naturally.")

    while True:

        # Sleep after 7 seconds without user speech.
        if (
            time.monotonic() - last_activity_time
            >= SLEEP_AFTER_SECONDS
        ):

            send_command("SLEEP")

            print("\nAva is going to sleep.")

            return "sleep"

        # Capture one complete 5-second recording.
        frame = record_frame()

        if not is_speech(frame):

            send_command("IDLE")
            continue

        # User speech detected.
        last_activity_time = time.monotonic()

        send_command("THINKING")

        print("\nUnderstanding your speech...")

        user_text = transcribe_audio(frame)

        print(f"\nYou: {user_text}")

        if not user_text:

            send_command("IDLE")
            last_activity_time = time.monotonic()
            continue

        if user_text.lower().strip(" .!?") in [
            "stop",
            "stop ava",
            "stop voicerobot",
            "goodbye",
            "exit",
            "quit"
        ]:

            speak(
                "Goodbye! I'll be here when you need me."
            )

            send_command("SLEEP")

            return "exit"

        answer = generate_response(user_text)

        speak(answer)

        # Start a fresh inactivity period after Ava finishes speaking.
        last_activity_time = time.monotonic()

        print("\nAva is ready for your next message.")


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    print("===================================")
    print("             AVA ROBOT")
    print("===================================")

    print("Wake method: Physical button")
    print("Conversation timeout: 7 seconds")
    print("Voice: AvaNeural")

    print("===================================")

    pygame.mixer.init()

    try:

        connect_esp32()

        # Initial startup is sleeping.
        # No greeting or apology at startup.

        while True:

            # Wait for physical button press.
            wait_for_button()

            # This apology happens only after waking from sleep.
            speak(
                "Sorry I slept. What were you saying?"
            )

            result = run_awake_session()

            if result == "exit":
                break

    except KeyboardInterrupt:

        print("\nStopping Ava...")

    except Exception as error:

        print(f"\nFatal error: {error}")

    finally:

        disconnect_esp32()

        pygame.mixer.quit()


if __name__ == "__main__":
    main()
