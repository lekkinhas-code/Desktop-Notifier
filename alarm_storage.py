import os
import pickle

from app_paths import ALARMS_FILE


def load_alarms(default=None):
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
    os.makedirs(os.path.dirname(ALARMS_FILE), exist_ok=True)
    with open(ALARMS_FILE, "wb") as file:
        pickle.dump(alarms, file)


def clear_alarms():
    if os.path.exists(ALARMS_FILE):
        os.remove(ALARMS_FILE)
