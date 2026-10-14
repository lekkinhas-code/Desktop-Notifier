"""Absolute paths to every file the app uses, resolved from the project folder.

Using absolute paths means the app finds its files no matter which folder it
was launched from.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Saved alarms
ALARMS_FILE = os.path.join(BASE_DIR, "Alarms", "alarms.pkl")

# Qt stylesheets for the two themes
DARK_THEME_FILE = os.path.join(BASE_DIR, "UI", "style", "darkTheme_styles.qss")
LIGHT_THEME_FILE = os.path.join(BASE_DIR, "UI", "style", "lightTheme_styles.qss")

# App icons: black for light taskbars, white for dark ones.
# The .ico files are used on Windows; the .png fallbacks everywhere else.
BLACK_ICON_FILE = os.path.join(BASE_DIR, "image", "alarm_icon.ico")
WHITE_ICON_FILE = os.path.join(BASE_DIR, "image", "alarm_icon_white.ico")
BLACK_ICON_FALLBACK_FILE = os.path.join(BASE_DIR, "image", "alarm_icon.png")
WHITE_ICON_FALLBACK_FILE = os.path.join(BASE_DIR, "image", "alarm_icon_white.png")

# Icons used inside the main window
STATUS_ON_ICON_FILE = os.path.join(BASE_DIR, "UI", "images", "toggle_on.svg")
STATUS_OFF_ICON_FILE = os.path.join(BASE_DIR, "UI", "images", "toggle_off.svg")
EDIT_BLACK_BUTTON_ICON_FILE = os.path.join(BASE_DIR, "UI", "images", "edit_black.svg")
EDIT_WHITE_BUTTON_ICON_FILE = os.path.join(BASE_DIR, "UI", "images", "edit_white.png")


# Sound played when an alarm goes off
SOUND_FILE = os.path.join(BASE_DIR, "audio", "alarm_sound.wav")
