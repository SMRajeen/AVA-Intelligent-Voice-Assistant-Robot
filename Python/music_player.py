
import random
from pathlib import Path

import pygame


# ==========================================
# AVA MUSIC LIBRARY
# ==========================================

BASE_DIR = Path(__file__).parent
MUSIC_DIR = BASE_DIR / "music"

SUPPORTED_FORMATS = {".mp3"}
SONGS_PER_SELECTION = 3

pygame.mixer.init()


def get_song_title(file_path):
    title = file_path.stem
    title = title.replace("_", " ")
    title = title.replace("-", " ")
    return " ".join(title.split())


def scan_music_library():

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    return sorted(
        [
            file
            for file in MUSIC_DIR.iterdir()
            if file.is_file()
            and file.suffix.lower() in SUPPORTED_FORMATS
        ],
        key=lambda file: file.name.lower()
    )


def get_random_songs(count=SONGS_PER_SELECTION):

    songs = scan_music_library()

    if not songs:
        return []

    return random.sample(
        songs,
        min(count, len(songs))
    )


def display_song_choices(songs):

    print("\n========== AVA MUSIC ==========")

    for index, song in enumerate(songs, start=1):
        print(f"{index}. {get_song_title(song)}")

    print("===============================\n")


def select_song_by_voice(transcribed_text, choices):

    """Identify a numbered song selection from transcribed speech."""

    text = transcribed_text.lower().strip()

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "first": 1,
        "second": 2,
        "third": 3,
        "1": 1,
        "2": 2,
        "3": 3,
        "ஒன்று": 1,
        "இரண்டு": 2,
        "மூன்று": 3
    }

    for word, number in number_words.items():

        if word in text:

            index = number - 1

            if 0 <= index < len(choices):
                return choices[index]

    return None

# ==========================================
# MUSIC PLAYBACK
# ==========================================

def play_song(song):

    if not song or not Path(song).is_file():
        print("Song file not found.")
        return

    print(f"\nNow playing: {get_song_title(song)}")

    try:

        pygame.mixer.music.load(str(song))
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)

        pygame.mixer.music.unload()

        print("Playback finished.")

    except Exception as error:

        print(f"Playback error: {error}")


# ==========================================
# PLAYBACK TEST
# ==========================================


if __name__ == "__main__":

    library = scan_music_library()

    print(f"Found {len(library)} songs.")

    choices = get_random_songs()

    if not choices:
        print("No songs available.")

    else:

        display_song_choices(choices)

        while True:

            spoken_text = input(
                "Simulate Ava's speech recognition: "
            )

            selected_song = select_song_by_voice(
                spoken_text,
                choices
            )

            if selected_song:

                print(
                    f"\nSelected: {get_song_title(selected_song)}"
                )

                play_song(selected_song)
                break

            print("Please say a valid song number.")

    pygame.mixer.quit()

