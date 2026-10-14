# Desktop Notifier

A sleek, native Windows desktop notification utility built with **Python** and **PyQt6**. A single lightweight process manages your alarms and keeps checking them from the system tray, even while the window is closed.

---

## Key Features

- **Single-Process Scheduler:** The alarm checks run on a timer inside the app itself (`alarm_scheduler.py`), so there is no hidden background process to manage, and the alarm list has a single owner that saves every change.
- **System Tray Integration:** Closing the GUI window minimizes the application directly to the Windows Hidden Icons drawer, keeping it alive out of sight.
- **Native Notifications:** Alarms show up as native Windows notifications through the tray icon, without ever freezing the window.
- **Smart Time Synchronization:** The scheduler calculates the exact time left until the next minute, firing notifications right as the clock turns without draining CPU resources.
- **Weekly Schedules:** Pick the days each alarm repeats on with a row of day toggles, and turn alarms on or off or edit them at any time.
- **Dynamic Theme Adaptation:** Automatically reads the Windows Registry to serve a contrasting white icon for Dark Mode or a black icon for Light Mode taskbars, and the window can follow the system theme or use a Dark or Light theme.
- **Singleton Lock:** Uses native Windows Mutex controls to prevent accidental duplicate instances of the application.

---

## Project Structure

```text
Desktop-Notifier/
├── main.py                # Main PyQt6 window, system tray and notifications
├── alarm_scheduler.py     # Timer that checks the alarms once a minute
├── alarm_model.py         # Alarm object and day-name rules
├── alarm_storage.py       # Loads and saves the alarm list
├── app_paths.py           # Absolute paths to every file the app uses
├── gui.py                 # Generated UI interface from Qt Designer (from UI/menu.ui)
├── requirements.txt       # Python dependencies
├── UI/
│   ├── menu.ui            # Qt Designer layout
│   ├── style/             # Dark and light theme stylesheets (.qss)
│   └── images/            # Toggle, arrow and edit button icons
├── image/
│   ├── alarm_icon.ico / .png        # Black icon variant (for Light Taskbars)
│   └── alarm_icon_white.ico / .png  # White icon variant (for Dark Taskbars)
├── audio/
│   └── alarm_sound.wav    # Custom alert audio file
└── Alarms/
    └── alarms.pkl         # Local persistent binary storage file for alerts (created on first save)
```

## Installation & Setup

### 1. Prerequisites

Make sure you have Python 3.10 or higher installed on your Windows machine. You can check your version by running:

```bash
python --version
```

### 2. Install Dependencies

Install the required external libraries with pip:

```bash
pip install -r requirements.txt
```

Libraries such as winsound, winreg and ctypes are built into python on Windows platforms.

### 3. Running the App

To launch the application with the management window and its system tray icon, run:

```bash
python main.py
```

## Future Updates & Roadmap

Here are some of the features and improvements I imagined for the app and plan on adding/changing:

- [ ] **Custom Alert Sounds:** Let users upload their own `.mp3` or `.wav` files for notifications.
- [ ] **Snooze Option:** Add a quick 5, 10, or 15-minute snooze button directly on the alert popups.
- [x] ~~**New day selector:** I don't really love how the day selector is working, so I plan on changing that.~~
- [x] ~~**Deactivate alarm:** I forgot to implement the option to deactivate the alarms and really need to add that.~~
- [x] ~~**Edit Alarm:** Config the option to edit the alarm, I also forgot to add that.~~
- [ ] **Timer:** I catch myself using it more than I thought throughout my day, so I want to implement that.
- [ ] **Pomodoro Timer:** Add a Pomodoro timer with a bunch of available configs to facilitate my studying.
- [ ] **Timezone Alarm:** Add an option to create alarms based on different timezones, it helps to set international meetings for example.
- [ ] **JSON for the alarms:** Option to import/export alarms through JSON files.
- [ ] **Modern Windows Toasts:** Replace the legacy balloon tips with native Windows toast notifications that support action buttons (needed for Snooze/Dismiss), stay on screen until dismissed and show up in the Action Center.
- [ ] **Missed Alarm Catch-up:** Fire alarms that were missed while the PC was asleep or shut down, with a "You missed X alarms" summary.
- [ ] **One-time Alarms:** Create alarms for a specific date (e.g. "20 Oct at 15:00") that disable or delete themselves after firing.
- [ ] **Next Alarm Display:** Show a countdown to the next alarm in the table, the tray tooltip and the status bar (e.g. "Next: Morning workout in 2h 14m").
- [ ] **Sort, Search & Duplicate:** Sort and search the alarm list, and duplicate an existing alarm to quickly create a similar one.
- [ ] **Ring Until Dismissed:** Option to keep the sound ringing (or repeat it N times) until the alarm is dismissed, plus a volume setting.
- [ ] **Health Indicator:** Warn through the tray icon or status bar if the alarm checks stop or fall behind.
