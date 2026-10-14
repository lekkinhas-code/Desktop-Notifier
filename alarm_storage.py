"""Reads and writes the alarm list on disk.

Only the main window calls these: it loads the alarms once at startup and
saves after every change.
"""

import os
import pickle

from app_paths import ALARMS_FILE


def load_alarms(default=None):
    """
    Loads the saved list of Alarm objects.

    :param default: List to fall back on if the file is missing, unreadable or
        doesn't contain a list. A copy is returned so the caller's list isn't shared.
    """
    if default is None:
        default = []

    if not os.path.exists(ALARMS_FILE):
        return list(default)

    try:
        with open(ALARMS_FILE, "rb") as file:
            loaded_alarms = pickle.load(file)
    except Exception as error:
        print(f"Storage error: {error}")
        return list(default)

    return loaded_alarms if isinstance(loaded_alarms, list) else list(default)


def save_alarms(alarms):
    """Writes the full list of alarms to disk, creating the folder if needed."""
    os.makedirs(os.path.dirname(ALARMS_FILE), exist_ok=True)
    with open(ALARMS_FILE, "wb") as file:
        pickle.dump(alarms, file)
