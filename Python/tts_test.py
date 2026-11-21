
import asyncio
import edge_tts
import pygame

VOICE = "en-US-AvaNeural"

RATE = "-3%"
PITCH = "+4Hz"
VOLUME = "+0%"

TEXT = (
    "Heyyy! I'm VoiceRobot! "
    "Aww, it's so nice to meet you! "
    "Hmm... what shall we talk about today? "
    "I'm listening!"
)

OUTPUT_FILE = "response.mp3"

async def generate_speech():
    communicate = edge_tts.Communicate(
        TEXT,
        VOICE,
        rate=RATE,
        pitch=PITCH,
        volume=VOLUME
    )

    await communicate.save(OUTPUT_FILE)

def play_speech():
    pygame.mixer.init()
    pygame.mixer.music.load(OUTPUT_FILE)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    pygame.mixer.music.unload()
    pygame.mixer.quit()

async def main():
    print("Preparing VoiceRobot...")
    await generate_speech()

    print("Playing female voice...")
    play_speech()

    print("Voice test completed!")

asyncio.run(main())
