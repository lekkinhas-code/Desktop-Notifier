import sys
import os
import pickle
import subprocess
import winreg
import ctypes
from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QMessageBox,
    QAbstractItemView,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtCore import QTime
from gui import Ui_MainWindow
from alarm_model import Alarm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PKL_FILE = os.path.join(BASE_DIR, "Desktop-Notifier/alarms.pkl")
BLACK_ICON_PATH = os.path.join(BASE_DIR, "image/alarm_icon.ico")
WHITE_ICON_PATH = os.path.join(BASE_DIR, "image/alarm_icon_white.ico")


class MainWindow(QMainWindow):
    def __init__(self):
        self.mutex_name = "Global\\DesktopNotifier_SingleInstance_Mutex_Lock"
        # CreateMutexW returns a handle to a new or existing mutex object
        self.mutex = ctypes.windll.kernel32.CreateMutexW(None, False, self.mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()

        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            # Another instance is already running! Show a popup and exit immediately.
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("Desktop Notifier is already running!")
            msg.setInformativeText(
                "Check your hidden icons system tray next to the Windows clock."
            )
            msg.setWindowTitle("App Already Open")
            msg.exec()

            # Close this duplicate window safely
            sys.exit(0)

        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        style_file_path = os.path.join(BASE_DIR, "UI/style/style.qss")
        if os.path.exists(style_file_path):
            try:
                with open(style_file_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                print(f"[UI Warning] Failed to read style.qss: {e}")

        icon_to_use = WHITE_ICON_PATH if self.is_dark_mode() else BLACK_ICON_PATH
        if not icon_to_use:
            print(f"[Icon Missing] Not found at: {icon_to_use}.")

        if os.path.exists(icon_to_use):
            self.setWindowIcon(QIcon(icon_to_use))

        self.ui.Alert_timeEdit.setTime(QTime.currentTime())
        self.alarms = []
        self.worker_process = None

        # Table Model Setup
        self.table_model = QStandardItemModel(0, 2, self)
        self.table_model.setHorizontalHeaderLabels(["Time", "Alarm Name"])
        self.ui.Alert_tableView.setModel(self.table_model)

        self.ui.Alert_tableView.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.ui.Alert_tableView.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.ui.Alert_tableView.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.ui.Alert_tableView.alternatingRowColors()

        # Ensure headers stretch nicely
        self.ui.Alert_tableView.horizontalHeader().setStretchLastSection(True)
        self.ui.Alert_tableView.verticalHeader().setVisible(False)

        self.ui.Diary_radioButton.setChecked(True)
        self.ui.Weekdays_lineEdit.setDisabled(True)

        # Connections
        self.ui.Create_pushButton.clicked.connect(self.add_alarm)
        self.ui.Delete_pushButton.clicked.connect(self.delete_alarm)
        self.ui.Diary_radioButton.toggled.connect(self.toggle_days_input)

        # Tabs
        self.ui.actionAlarms_Dashboard.triggered.connect(
            lambda: self.ui.mainStackedWidget.setCurrentIndex(0)
        )
        self.ui.actionPreferences_Settings.triggered.connect(
            lambda: self.ui.mainStackedWidget.setCurrentIndex(1)
        )

        # --- SETUP SYSTEM TRAY ---
        self.init_system_tray()

        self.load_alarms()
        self.start_worker()

    def is_dark_mode(self):
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 0
        except FileNotFoundError:
            return False

    def init_system_tray(self):
        """Creates the hidden tray icon and its right-click menu."""
        self.tray_icon = QSystemTrayIcon(self)

        icon_to_use = WHITE_ICON_PATH if self.is_dark_mode() else BLACK_ICON_PATH
        if not icon_to_use:
            print(f"[Icon Missing] Not found at: {icon_to_use}.")

        # Load your custom app icon
        if os.path.exists(icon_to_use):
            self.tray_icon.setIcon(QIcon(icon_to_use))
        else:
            # Fallback to a standard system icon if yours is missing
            self.tray_icon.setIcon(
                self.style().standardIcon(
                    self.style().StandardPixmap.SP_MessageBoxInformation
                )
            )

        # self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxWarning))

        # Create a right-click context menu for the hidden icon
        tray_menu = QMenu()

        show_action = tray_menu.addAction("Open Notifier Menu")
        show_action.triggered.connect(self.showNormal)  # Brings window back

        quit_action = tray_menu.addAction("Exit Completely")
        quit_action.triggered.connect(self.completely_quit)  # Closes app and worker

        self.tray_icon.setContextMenu(tray_menu)

        # Double-clicking the tray icon will also open the window
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        # Make the icon visible in the hidden icons area
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        """Brings the window back up if the user double-clicks the tray icon."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()

    def closeEvent(self, event):
        """Overrides the 'X' button. Hides the window to the tray instead of closing."""
        if self.tray_icon.isVisible():
            event.ignore()  # Stop the window from actually closing
            self.hide()  # Hide the window visually

            # Show a small pop-up bubble letting the user know it's hidden down there
            self.tray_icon.showMessage(
                "Desktop Notifier",
                "App minimized to hidden icons. The worker is still active!",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            print("GUI minimized to system tray. Worker remains alive.")

    def completely_quit(self):
        """The true exit function triggered only via the tray's right-click menu."""
        print("Closing application and terminating background worker...")

        # Clean up the worker process
        if self.worker_process and self.worker_process.poll() is None:
            self.worker_process.terminate()
            self.worker_process.wait()

        self.tray_icon.hide()  # Remove icon from taskbar
        QApplication.quit()  # Shut down the entire PyQt app

    # --- KEEPING YOUR EXISTING CODE BELOW ---
    def toggle_days_input(self, checked):
        self.ui.Weekdays_lineEdit.setDisabled(checked)
        if checked:
            self.ui.Weekdays_lineEdit.clear()

    def load_alarms(self):
        if os.path.exists(PKL_FILE):
            try:
                with open(PKL_FILE, "rb") as f:
                    self.alarms = pickle.load(f)
            except:
                self.alarms = []
        self.update_table_display()

    def save_alarms(self):
        try:
            with open(PKL_FILE, "wb") as f:
                pickle.dump(self.alarms, f)
        except Exception as e:
            print(f"Storage error: {e}")

    def update_table_display(self):
        self.table_model.setRowCount(0)
        for alarm in self.alarms:
            self.table_model.appendRow(
                [QStandardItem(alarm.time_str), QStandardItem(alarm.title)]
            )

    def add_alarm(self):

        if os.path.exists(PKL_FILE):
            try:
                with open(PKL_FILE, "rb") as f:
                    self.alarms = pickle.load(f)
            except Exception as e:
                print(f"Could not sync file before writing: {e}")

        time_data = self.ui.Alert_timeEdit.time().toString("HH:mm")
        title_data = self.ui.Name_lineEdit.text().strip() or "Alarm Alert!"
        if self.ui.Diary_radioButton.isChecked():
            days_list = None
        else:
            raw_days = self.ui.Weekdays_lineEdit.text()
            days_list = (
                [d.strip().capitalize() for d in raw_days.split(",") if d.strip()]
                if raw_days.strip()
                else None
            )

        new_alarm = Alarm(time_str=time_data, title=title_data, days=days_list)
        self.alarms.append(new_alarm)
        self.save_alarms()
        self.update_table_display()
        self.ui.Name_lineEdit.clear()
        self.ui.Weekdays_lineEdit.clear()
        self.ui.Diary_radioButton.setChecked(True)
        self.ui.Weekdays_lineEdit.setDisabled(True)
        self.ui.Alert_timeEdit.setTime(QTime.currentTime())

    def delete_alarm(self):
        selected_indexes = self.ui.Alert_tableView.selectionModel().selectedRows()
        if selected_indexes:

            if os.path.exists(PKL_FILE):
                try:
                    with open(PKL_FILE, "rb") as f:
                        self.alarms = pickle.load(f)
                except:
                    pass

            del self.alarms[selected_indexes[0].row()]
            self.save_alarms()
            self.update_table_display()

    def start_worker(self):
        worker_path = os.path.join(BASE_DIR, "worker.py")
        if os.path.exists(worker_path):
            self.worker_process = subprocess.Popen(
                [sys.executable, worker_path, "--background"],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            print(f"[GUI] Spawned worker process at: {worker_path}")
        else:
            print(f"[GUI ERROR] Could not find worker.py at target path: {worker_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
