import pygame
import os
from logger import writeLog

# Define the path to the sounds directory
SOUNDS_DIR = os.path.join(os.path.dirname(__file__), 'sounds')

def initialize_pygame():
    pygame.mixer.init()

def play_sound(file_name):
    writeLog(f"Attempting to play sound: {file_name}", "DEBUG")
    pygame.mixer.init()
    mp3_path = os.path.join(SOUNDS_DIR, f"{file_name}.mp3")
    wav_path = os.path.join(SOUNDS_DIR, f"{file_name}.wav")
    if os.path.exists(mp3_path):
        pygame.mixer.music.load(mp3_path)
    elif os.path.exists(wav_path):
        pygame.mixer.music.load(wav_path)
    else:
        writeLog(f"Sound file {file_name}.mp3 or {file_name}.wav not found", "ERROR")
        return
    pygame.mixer.music.play()

def play_notification_sound():
    writeLog("Playing notification sound", "DEBUG")
    play_sound("notification")

def play_buy_sound():
    writeLog("Playing buy sound", "DEBUG")
    play_sound("buy")

def play_available_sound():
    writeLog("Playing available sound", "DEBUG")
    play_sound("available")

# Initialize pygame mixer
initialize_pygame()