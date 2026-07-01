# ⏰ Desktop Notifier

A sleek, native Windows desktop notification utility built with **Python**, **PyQt6**, and **Plyer**. The application uses a split-process architecture to separate the management interface from the time-tracking worker, ensuring lightweight background execution.

---

## 🚀 Key Features

- **Dual-Process Architecture:** A PyQt6 GUI manages your custom alert schedule, while a completely hidden, zero-overhead background worker process (`worker.py`) handles clock synchronization.
- **System Tray Integration:** Closing the GUI window minimizes the application directly to the Windows Hidden Icons drawer, keeping it alive out of sight.
- **Smart Time Synchronization:** The worker loop dynamically calculates precise micro-sleep intervals, firing notifications down to the exact millisecond the clock turns without draining CPU resources.
- **Dynamic Theme Adaptation:** Automatically reads the Windows Registry on startup to serve a contrasting white icon for Dark Mode or a black icon for Light Mode taskbars.
- **Singleton Lock:** Uses native Windows Mutex controls to prevent accidental duplicate instances of the application or duplicate worker threads.

---

## 📂 Project Structure

```text
Desktop-Notifier/
├── main.py                # Main PyQt6 graphical management menu
├── worker.py              # Stealth CLI/Background alert checking worker
├── alarm_model.py         # Shared blueprint/object rules for Alarm serialization
├── gui.py                 # Generated UI interface from Qt Designer
├── image/
│   ├── alarm_icon_light.ico  # White icon variant (for Dark Taskbars)
│   └── alarm_icon_dark.ico   # Black icon variant (for Light Taskbars)
├── audio/
│   └── alarm_sound.wav    # Custom alert audio file
└── Desktop-Notifier/
    └── alarms.pkl         # Local persistent binary storage file for alerts
```

## 🛠️ Installation & Setup

### 1. Prerequisites

Make sure you have Python 3.10 or higher installed on your Windows machine. You can check your version by running:

```bash
python --version
```

### 2. Install Dependencies

Install the required external libraries with pip:

```bash
pip install PyQt6 plyer
```

Libraries such as winsound, winreg and ctypes are built into python on Windows platforms.

### 3. Running the App

To launch the complete application with the management window interface and hidden system tracking, run:

```bash
python main.py
```
