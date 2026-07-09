import os
import sys
import time
import ctypes
import winreg
from datetime import datetime, timedelta
from plyer import notification
import winsound
from alarm_model import Alarm
from alarm_storage import clear_alarms, load_alarms, save_alarms
from app_paths import (
    BLACK_ICON_FILE,
    BLACK_ICON_FALLBACK_FILE,
    SOUND_FILE,
    WHITE_ICON_FILE,
    WHITE_ICON_FALLBACK_FILE,
)

APP_TITLE = "Desktop Notifier"

if os.name != "nt":
    BLACK_ICON_FILE = BLACK_ICON_FALLBACK_FILE
    WHITE_ICON_FILE = WHITE_ICON_FALLBACK_FILE


def fix_windows_app_id():
    """Forces Windows to see this script as a unique App, changing 'Python' to our name."""
    try:
        myappid = "Desktop Notifier by Lekkinhas"  # Any unique string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"[Worker] Error setting app ID: {e}")
        pass


def is_dark_mode():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 0
    except FileNotFoundError:
        return False


def create_test_alarm_if_empty():
    """Creates a temporary test alarm 1 minute from now if no file exists."""
    if not load_alarms():
        now_plus_one = datetime.now() + timedelta(minutes=1)
        test_time = now_plus_one.strftime("%H:%M")

        # Creating a test alarm using our object blueprint (Runs everyday by default)
        test_alarm = Alarm(time_str=test_time, title="Test Alarm worked!")
        try:
            save_alarms([test_alarm])
        except Exception as e:
            print(f"[Worker] Error creating test alarm: {e}")
            return

        print(f"[Test] No alarms found. Created a test alarm for {test_time}!")
        print("Keep this script running and watch your Windows notification center!")


def main_worker_loop():
    fix_windows_app_id()
    print("[Worker] Background worker started. Monitoring alarms...")

    icon_to_use = WHITE_ICON_FILE if is_dark_mode() else BLACK_ICON_FILE
    if not icon_to_use:
        print(f"[Icon Missing] Not found at: {icon_to_use}.")

    # Run the test check
    # create_test_alarm_if_empty()

    while True:
        now = datetime.now()
        print(f"[Worker] Checking alarms at {now.strftime('%Y-%m-%d %H:%M:%S')}...")
        # 1. Safely load the alarms from the pickle file
        alarms = load_alarms()

        file_needs_update = False
        current_date = now.strftime("%Y-%m-%d")

        # 2. Iterate through your custom Alarm objects
        for alarm in alarms:
            if alarm.should_trigger():
                print(f"[Worker] Triggering alarm: {alarm.title}")

                try:
                    # Fire the native desktop notification using plyer
                    notification.notify(
                        title=alarm.title,
                        message=f"It's {alarm.time_str}! Click to dismiss.",
                        app_name=APP_TITLE,
                        app_icon=str(icon_to_use),
                        timeout=10,  # Notification disappears after 10 seconds
                    )
                except Exception as e:
                    print(f"[Worker] Error showing notification: {e}")
                    print("Retrying with default icon instead.")

                    try:
                        notification.notify(
                            title=alarm.title,
                            message=f"It's {alarm.time_str}! Click to dismiss.",
                            app_name=APP_TITLE,
                            app_icon=None,
                            timeout=10,  # Notification disappears after 10 seconds
                        )
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
    if "--background" in sys.argv:
        print("Launched by GUI. Starting background worker loop...")
        main_worker_loop()
    else:
        menu()
