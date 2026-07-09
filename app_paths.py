import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ALARMS_FILE = os.path.join(BASE_DIR, "Alarms", "alarms.pkl")
WORKER_FILE = os.path.join(BASE_DIR, "worker.py")

DARK_THEME_FILE = os.path.join(BASE_DIR, "UI", "style", "darkTheme_styles.qss")
LIGHT_THEME_FILE = os.path.join(BASE_DIR, "UI", "style", "lightTheme_styles.qss")

BLACK_ICON_FILE = os.path.join(BASE_DIR, "image", "alarm_icon.ico")
WHITE_ICON_FILE = os.path.join(BASE_DIR, "image", "alarm_icon_white.ico")
BLACK_ICON_FALLBACK_FILE = os.path.join(BASE_DIR, "image", "alarm_icon.png")
WHITE_ICON_FALLBACK_FILE = os.path.join(BASE_DIR, "image", "alarm_icon_white.png")

SOUND_FILE = os.path.join(BASE_DIR, "audio", "alarm_sound.wav")
