import pygame

def initialize_pygame():
    pygame.mixer.init()

def play_notification_sound():
    pygame.mixer.music.load('sounds/alert.wav')
    pygame.mixer.music.play()

def play_buy_sound():
    pygame.mixer.music.load('sounds/alert_buy.wav')
    pygame.mixer.music.play()

def play_available_sound():
    pygame.mixer.music.load('sounds/alert_available.wav')
    pygame.mixer.music.play()

# Initialize pygame mixer
initialize_pygame()