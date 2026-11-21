
import os
import time
import asyncio
from pathlib import Path

import serial
import numpy as np
import soundfile as sf
import pygame
import edge_tts
import music_player

from dotenv import load_dotenv
from groq import Groq


# ==========================================
# CONFIGURATION
# ==========================================

PORT = "COM6"
BAUD_RATE = 921600

SAMPLE_RATE = 16000

FRAME_SECONDS = 1
FRAME_SAMPLES = SAMPLE_RATE * FRAME_SECONDS
FRAME_BYTES = FRAME_SAMPLES * 2

MAX_UTTERANCE_SECONDS = 10
MAX_UTTERANCE_FRAMES = MAX_UTTERANCE_SECONDS // FRAME_SECONDS

VOICE_THRESHOLD = 200
UTTERANCE_END_SILENCE = 1.5
SLEEP_AFTER_SECONDS = 7

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
audio_transfer_active = False


# ==========================================
# TERMINAL PROGRESS BAR
# ==========================================

def show_progress(received, total):

    percent = int((received / total) * 100) if total else 100

    width = 30
    filled = int(width * percent / 100)

    bar = "#" * filled + "-" * (width - filled)

    print(
        f"\rMicrophone transfer: [{bar}] {percent:3d}%",
        end="",
        flush=True
    )

    if received >= total:
        print()


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
        timeout=1,
        write_timeout=3
    )

    time.sleep(2)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print("ESP32 connected. Ava is sleeping.")
    print("Press the physical button to wake Ava.")


def disconnect_esp32():

    global ser

    if ser is not None and ser.is_open:

        try:
            send_command("SLEEP")
            ser.flush()
            time.sleep(1.5)

            # Prevent USB serial control lines from triggering ESP32 reset.
            ser.dtr = False
            ser.rts = False

            time.sleep(0.2)

        except Exception as error:
            print(f"Shutdown warning: {error}")

        finally:
            ser.close()

    print("Ava is sleeping.")


def wait_for_button():

    print("\nWaiting for the wake button...")

    while True:

        line = ser.readline().decode(
            "utf-8",
            errors="ignore"
        ).strip()

        if line == "WAKE":

            print("\nButton pressed. Ava is waking up...")

            time.sleep(1.25)

            return


# ==========================================
# ONE-SECOND MICROPHONE FRAME
# ==========================================

def record_frame():

    global ser

    send_command("RECORD")

    expected_bytes = FRAME_BYTES
    audio_data = bytearray()

    deadline = time.monotonic() + 20

    while len(audio_data) < expected_bytes:

        if time.monotonic() > deadline:

            raise TimeoutError(
                f"Microphone timeout: received "
                f"{len(audio_data)} of {expected_bytes} bytes"
            )

        remaining = expected_bytes - len(audio_data)

        chunk = ser.read(min(remaining, 4096))

        if chunk:

            audio_data.extend(chunk)

            show_progress(
                len(audio_data),
                expected_bytes
            )

    print("\nChecking ESP32 frame completion...")

    ser.timeout = 2

    while True:

        line = ser.readline().decode(
            "utf-8",
            errors="ignore"
        ).strip()

        if line.startswith("FRAME_DONE:"):

            samples = int(line.split(":")[1])

            if samples != FRAME_SAMPLES:

                raise RuntimeError(
                    f"ESP32 sent {samples} samples; "
                    f"expected {FRAME_SAMPLES}"
                )

            break

        if not line:
            continue

    print("Microphone frame received successfully.")

    return np.frombuffer(
        audio_data,
        dtype=np.int16
    ).copy()


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


def capture_utterance(first_frame):

    """Collect speech until 1.5 seconds of silence or a 10-second limit."""

    frames = [first_frame]

    silence_frames = 0

    while len(frames) < MAX_UTTERANCE_FRAMES:

        frame = record_frame()

        frames.append(frame)

        if is_speech(frame):

            silence_frames = 0

        else:

            silence_frames += 1

            if (
                silence_frames * FRAME_SECONDS
                >= UTTERANCE_END_SILENCE
            ):
                break

    return np.concatenate(frames)


# ==========================================
# SPEECH RECOGNITION
# ==========================================

def transcribe_audio(audio):

    sf.write(
        AUDIO_FILE,
        audio,
        SAMPLE_RATE
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
# FACIAL EXPRESSION DETECTION
# ==========================================

def detect_expression(text):

    text = text.lower().strip()

    love_words = [
        "love", "lovely", "romantic", "romance", "adore",
        "miss you", "i miss", "i love", "love you",
        "kiss", "hug", "sweetheart", "darling",
        "beautiful", "gorgeous", "cute", "affection",
        "valentine", "encourage", "encouragement",
        "motivate", "motivation", "support me",
        "believe in you", "you can do it",
        "proud of you", "well done", "good job",
        "ஊக்கம்", "உற்சாகம்", "பாசம்", "காதல்",
        "அன்பு", "அழகு"
    ]

    angry_words = [
        "angry", "anger", "furious", "hate",
        "annoyed", "annoying", "frustrated",
        "frustrating", "irritated", "mad at",
        "stupid", "ridiculous", "unacceptable",
        "கோபம்", "வெறுப்பு"
    ]

    sad_words = [
        "sad", "upset", "lonely", "depressed",
        "disappointed", "heartbroken", "cry",
        "crying", "unhappy", "hurt",
        "வருத்தம்", "சோகம்"
    ]

    surprised_words = [
        "wow", "amazing", "unbelievable",
        "surprised", "surprise", "shocking",
        "astonishing", "incredible", "வியப்பு"
    ]

    happy_words = [
        "happy", "excited", "awesome", "excellent",
        "great news", "thank you", "thanks",
        "wonderful", "fantastic", "congratulations",
        "மகிழ்ச்சி", "நன்றி", "வாழ்த்துக்கள்"
    ]

    confused_words = [
        "confused", "i don't understand",
        "dont understand", "not sure",
        "what do you mean", "unclear",
        "huh", "குழப்பம்"
    ]

    thinking_words = [
        "how do", "how can", "how to", "why",
        "what is", "what are", "explain",
        "calculate", "solve", "debug", "code",
        "program", "problem", "issue", "help me",
        "எப்படி", "ஏன்", "என்ன"
    ]

    if any(word in text for word in angry_words):
        return "ANGRY"

    if any(word in text for word in sad_words):
        return "SAD"

    if any(word in text for word in love_words):
        return "LOVE"

    if any(word in text for word in surprised_words):
        return "SURPRISED"

    if any(word in text for word in happy_words):
        return "HAPPY"

    if any(word in text for word in confused_words):
        return "CONFUSED"

    if "?" in text or any(word in text for word in thinking_words):
        return "THINKING"

    return "IDLE"


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


def speak(text, expression="IDLE"):

    print("\nPreparing Ava's voice...")

    asyncio.run(
        generate_speech(text)
    )

    print(f"\nAva: {text}\n")

    supported_expressions = {
        "LOVE",
        "ANGRY",
        "HAPPY",
        "SAD",
        "SURPRISED",
        "CONFUSED",
        "THINKING"
    }

    if expression in supported_expressions:

        send_command(f"TALK_{expression}")

    else:

        send_command("SPEAKING")

    pygame.mixer.music.load(str(RESPONSE_FILE))

    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():

        pygame.time.Clock().tick(30)

    pygame.mixer.music.unload()

    send_command("IDLE")


# ==========================================
# AVA MUSIC ASSISTANT
# ==========================================

def is_music_request(text):

    text = text.lower()

    triggers = [
        "sing me a song",
        "sing a song",
        "play me a song",
        "play a song",
        "play some music",
        "sing something",
        "i want music",
        "let's listen to music",
        "lets listen to music",
        "பாட்டு பாடு",
        "பாட்டு போடு",
        "ஒரு பாட்டு பாடு"
    ]

    return any(trigger in text for trigger in triggers)


def listen_for_song_selection():

    print("\nWaiting for your song selection...")

    send_command("LISTENING")

    deadline = time.monotonic() + 20

    while time.monotonic() < deadline:

        frame = record_frame()

        if is_speech(frame):

            send_command("THINKING")

            audio = capture_utterance(frame)

            selected_text = transcribe_audio(audio)

            print(f"\nSong selection: {selected_text}")

            return selected_text

    return None



def handle_music_request():

    choices = music_player.get_random_songs(3)

    if not choices:
        speak("Sorry, I couldn't find any songs in my music library.")
        return

    # Open the song selection screen.
    send_command("MUSIC_MENU")

    song_names = []

    for index, song in enumerate(choices, start=1):

        title = music_player.get_song_title(song)

        # Keep serial display text ASCII-safe.
        display_title = (
            title.encode("ascii", errors="ignore")
            .decode("ascii")
            .strip()
        )

        if not display_title:
            display_title = f"Track {index}"

        song_names.append(display_title)

        send_command(
            f"MUSIC_SONG:{index}:{display_title}"
        )

    print("\nAva's display is showing three songs.")

    message = (
        "Of course! Here are three songs for you. "
        "Which one would you like to hear? "
    )

    speak(message, "HAPPY")

    selected_text = listen_for_song_selection()

    if not selected_text:

        send_command("MUSIC_STOP")

        speak("I couldn't hear your selection. Let's try again later.")
        return

    selected_song = music_player.select_song_by_voice(
        selected_text,
        choices
    )

    if not selected_song:

        send_command("MUSIC_STOP")

        speak("Sorry, I couldn't identify that song number.")
        return

    selected_index = choices.index(selected_song) + 1

    selected_title = music_player.get_song_title(
        selected_song
    )

    display_title = (
        selected_title.encode("ascii", errors="ignore")
        .decode("ascii")
        .strip()
    )

    if not display_title:
        display_title = "Unknown Track"

    # Highlight the chosen song.
    send_command(f"MUSIC_SELECT:{selected_index}")

    print(f"\nAva selected: {selected_title}")

    speak(
        f"Great choice! Now playing {selected_title}.",
        "HAPPY"
    )

    # Switch from the selection menu to the cassette player.
    send_command(f"MUSIC_PLAY:{display_title}")

    try:

        music_player.play_song(selected_song)

    finally:

        # Restore Ava's normal face.
        send_command("MUSIC_STOP")

    print("\nAva has finished playing the song.")

# ==========================================
# AWAKE CONVERSATION
# ==========================================

def run_awake_session():

    last_response_time = time.monotonic()

    print("\nAva is listening. Speak naturally.")
    print("Maximum input per message: 10 seconds.")

    while True:

        if (
            time.monotonic() - last_response_time
            >= SLEEP_AFTER_SECONDS
        ):

            send_command("SLEEP")

            print("\nAva is going to sleep.")

            return

        frame = record_frame()

        if not is_speech(frame):

            send_command("IDLE")

            continue

        print("\nVoice detected. Capturing your message...")

        send_command("LISTENING")

        audio = capture_utterance(frame)

        send_command("THINKING")

        print("\nUnderstanding your speech...")

        user_text = transcribe_audio(audio)

        print(f"\nYou: {user_text}")
        if is_music_request(user_text):

            handle_music_request()

            last_response_time = time.monotonic()

            print("\nAva is ready for your next message.")

            continue

        if not user_text:

            send_command("IDLE")

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

        # Detect the expression associated with the conversation.
        user_expression = detect_expression(user_text)

        # Keep Ava thinking while generating the response.
        send_command("THINKING")

        answer = generate_response(user_text)

        # Select an expression using both the user's message
        # and Ava's generated response.
        response_expression = detect_expression(
            user_text + " " + answer
        )

        if response_expression == "IDLE":
            response_expression = user_expression

        print(
            f"\nAva's expression: {response_expression}"
        )

        speak(
            answer,
            response_expression
        )

        last_response_time = time.monotonic()

        print("\nAva is ready for your next message.")


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    print("===================================")
    print("             AVA ROBOT")
    print("===================================")

    print("Wake method: Physical button (GPIO32)")
    print("Maximum voice input: 10 seconds")
    print("Sleep timeout: 7 seconds")
    print("Voice: AvaNeural")

    print("===================================")

    pygame.mixer.init()

    try:

        connect_esp32()

        while True:

            wait_for_button()

            speak(
                "Hey! I'm awake. What would you like to talk about?"
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
