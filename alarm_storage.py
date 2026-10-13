"""Reads and writes the alarm list on disk.

Both the GUI and the worker use these functions, so the alarms file is how the
two processes share state.
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


def clear_alarms():
    """Deletes the alarms file, removing every saved alarm."""
    if os.path.exists(ALARMS_FILE):
        os.remove(ALARMS_FILE)
