"""Background worker that fires alarm notifications.

main.py starts this script with --background as a hidden process. Once a
minute it reloads the saved alarms and, for each one that is due, shows a
desktop notification and plays the alarm sound.

Run it directly (without --background) to get a small console menu for testing.
"""

import os
import sys
import time
import winreg
from datetime import datetime
from plyer import notification
import winsound
from alarm_storage import clear_alarms, load_alarms, save_alarms
from app_paths import (
    BLACK_ICON_FILE,
    BLACK_ICON_FALLBACK_FILE,
    SOUND_FILE,
    WHITE_ICON_FILE,
    WHITE_ICON_FALLBACK_FILE,
)

APP_TITLE = "Desktop Notifier"

# .ico files only work on Windows, so use the .png versions elsewhere
if os.name != "nt":
    BLACK_ICON_FILE = BLACK_ICON_FALLBACK_FILE
    WHITE_ICON_FILE = WHITE_ICON_FALLBACK_FILE


def is_dark_mode():
    """Returns True if Windows is using a dark taskbar (SystemUsesLightTheme == 0)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 0
    except FileNotFoundError:
        return False


def main_worker_loop():
    """Checks the alarms once a minute, forever, firing the ones that are due."""
    print("[Worker] Background worker started. Monitoring alarms...")

    # Pick the icon that contrasts with the taskbar. It is chosen once, at startup.
    icon_to_use = WHITE_ICON_FILE if is_dark_mode() else BLACK_ICON_FILE
    if not os.path.exists(icon_to_use):
        print(f"[Icon Missing] Not found at: {icon_to_use}.")
        icon_to_use = None

    while True:
        now = datetime.now()
        print(f"[Worker] Checking alarms at {now.strftime('%Y-%m-%d %H:%M:%S')}...")
        # 1. Safely load the alarms from the pickle file
        #    (reloaded every minute so changes made in the GUI are picked up)
        alarms = load_alarms()

        file_needs_update = False
        current_date = now.strftime("%Y-%m-%d")

        # 2. Iterate through your custom Alarm objects
        for alarm in alarms:
            if alarm.should_trigger(now=now):
                print(f"[Worker] Triggering alarm: {alarm.title}")

                try:
                    # Fire the native desktop notification using plyer.
                    # On Windows this call blocks until the timeout ends.
                    notification.notify(
                        title=alarm.title,
                        message=f"It's {alarm.time_str}!",
                        app_name=APP_TITLE,
                        app_icon=icon_to_use,
                        timeout=10,  # Notification disappears after 10 seconds
                    )
                    print("[Worker] Notification sent.")
                except Exception as e:
                    print(f"[Worker] Error showing notification: {e}")
                    print("Retrying with default icon instead.")

                    try:
                        notification.notify(
                            title=alarm.title,
                            message=f"It's {alarm.time_str}!",
                            app_name=APP_TITLE,
                            app_icon=None,
                            timeout=5,  # Notification disappears after 5 seconds
                        )
                        print("[Worker] Notification sent without icon.")
                    except Exception as critical_error:
                        print(f"[Notification Failed Completely]: {critical_error}")

                if SOUND_FILE and os.path.exists(SOUND_FILE):
                    # Plays the user's custom .wav file asynchronously (doesn't freeze the loop)
                    winsound.PlaySound(
                        SOUND_FILE, winsound.SND_FILENAME | winsound.SND_ASYNC
                    )
                else:
                    # Default system beep fallback if no file or missing file
                    print(f"[Audio Error] File missing at: {SOUND_FILE}")
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

                # Mark it as triggered for today so it doesn't loop-spam this exact minute
                alarm.last_triggered_date = current_date
                file_needs_update = True

        # 3. If an alarm triggered, re-save the file to update its 'last_triggered_date'
        if file_needs_update:
            try:
                save_alarms(alarms)
            except Exception as e:
                print(f"[Worker] Error updating file state: {e}")

        # 4. Sleep until the start of the next minute
        now = datetime.now()
        # 60 seconds minus current seconds and fractions of a second
        time_to_sleep = 60 - now.second - (now.microsecond / 1_000_000.0)

        # A tiny safety buffer (0.1s) ensures we actually cross the minute threshold
        # instead of waking up at 11:59:59.999 due to tiny system clock roundings.
        time.sleep(time_to_sleep + 0.1)


def cleanAlarms():
    """Utility function to clear all alarms (for testing purposes)."""
    clear_alarms()
    print("[Worker] All alarms cleared.")


def menu():
    """Simple console menu for testing."""
    while True:
        print("=== Desktop Notifier Worker Menu ===")
        print("1. Clear all alarms")
        print("2. Activate Worker")
        print("3. Exit")
        option = input("Enter your choice: ")

        if option == "1":
            cleanAlarms()
        elif option == "2":
            main_worker_loop()
        elif option == "3":
            print("Exiting worker. Goodbye!")
            break
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    # main.py passes --background; running the file by hand opens the test menu
    if "--background" in sys.argv:
        print("Launched by GUI. Starting background worker loop...")
        main_worker_loop()
    else:
        menu()
