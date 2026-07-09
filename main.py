import sys
import os
import subprocess

from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAbstractItemView,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtCore import QTime, qInstallMessageHandler, Qt
from gui import Ui_MainWindow
from alarm_model import Alarm
from alarm_storage import load_alarms, save_alarms
from app_paths import (
    BLACK_ICON_FILE,
    BLACK_ICON_FALLBACK_FILE,
    DARK_THEME_FILE,
    LIGHT_THEME_FILE,
    WHITE_ICON_FILE,
    WHITE_ICON_FALLBACK_FILE,
    WORKER_FILE,
)

IS_WINDOWS = os.name == "nt"
SINGLE_INSTANCE_MUTEX_NAME = "Global\\DesktopNotifier_SingleInstance_Mutex_Lock"
_APP_MUTEX_HANDLE = None

if IS_WINDOWS:
    import winreg
    import ctypes
else:
    pass


if not IS_WINDOWS:
    BLACK_ICON_FILE = BLACK_ICON_FALLBACK_FILE
    WHITE_ICON_FILE = WHITE_ICON_FALLBACK_FILE


def acquire_single_instance_lock():
    global _APP_MUTEX_HANDLE

    if not IS_WINDOWS:
        return True

    _APP_MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(
        None, False, SINGLE_INSTANCE_MUTEX_NAME
    )
    last_error = ctypes.windll.kernel32.GetLastError()

    if last_error == 183:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Desktop Notifier is already running.\n\nCheck the system tray near the clock.",
            "App Already Open",
            0x30,
        )
        return False

    return True


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.alarms = []
        self.worker_process = None
        self._setup_ui()
        self._apply_default_theme()
        self._apply_window_icon()
        self._setup_table()
        self._setup_form_state()
        self._connect_signals()
        self._setup_navigation()
        self.init_system_tray()
        self.load_alarms()
        self.start_worker()

    def _setup_ui(self):
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

    def _apply_default_theme(self):
        load_stylesheet(QApplication.instance(), DARK_THEME_FILE)

    def _apply_window_icon(self):
        icon_to_use = self._current_icon_path()
        if not icon_to_use:
            print(f"[Icon Missing] Not found at: {icon_to_use}.")
            return

        if os.path.exists(icon_to_use):
            self.setWindowIcon(QIcon(icon_to_use))

    def _setup_table(self):
        self.table_model = QStandardItemModel(0, 3, self)
        self.table_model.setHorizontalHeaderLabels(["Time", "Alarm Name", "Status"])
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
        self.ui.Alert_tableView.setAlternatingRowColors(True)
        self.ui.Alert_tableView.horizontalHeader().setStretchLastSection(True)
        self.ui.Alert_tableView.verticalHeader().setVisible(False)

    def _setup_form_state(self):
        self.ui.Alert_timeEdit.setTime(QTime.currentTime())
        self.ui.Diary_radioButton.setChecked(True)
        self.ui.Weekdays_lineEdit.setDisabled(True)
        self.ui.Theme_comboBox.setCurrentText("Dark Mode")

    def _connect_signals(self):
        self.ui.Create_pushButton.clicked.connect(self.add_alarm)
        self.ui.Delete_pushButton.clicked.connect(self.delete_alarm)
        self.ui.Diary_radioButton.toggled.connect(self.toggle_days_input)
        self.ui.Theme_comboBox.currentTextChanged.connect(self.on_theme_changed)
        self.table_model.itemChanged.connect(self.toggle_alarm_state)

    def _setup_navigation(self):
        self.ui.actionAlarms_Dashboard.triggered.connect(
            lambda: self.ui.mainStackedWidget.setCurrentIndex(0)
        )
        self.ui.actionPreferences_Settings.triggered.connect(
            lambda: self.ui.mainStackedWidget.setCurrentIndex(1)
        )

    def is_dark_mode(self):
        if not IS_WINDOWS:
            return True

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 0
        except FileNotFoundError:
            return False

    def on_theme_changed(self, selected_text):
        """Slot function triggered when the user picks a new theme in the combobox."""
        app_instance = QApplication.instance()
        load_stylesheet(app_instance, self._stylesheet_for_theme(selected_text))
        self._apply_window_icon()

    def init_system_tray(self):
        """Creates the hidden tray icon and its right-click menu."""
        self.tray_icon = QSystemTrayIcon(self)

        icon_to_use = self._current_icon_path()
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

        # Create a right-click context menu for the hidden icon
        tray_menu = QMenu()

        show_action = tray_menu.addAction("Open Notifier Menu")
        show_action.triggered.connect(self.showNormal)  # Brings window back
        show_action.triggered.connect(
            lambda: self.ui.Alert_timeEdit.setTime(QTime.currentTime())
        )

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

    def toggle_alarm_state(self, item):
        if item.column() != 2:
            return

        row = item.row()

        if 0 <= row < len(self.alarms):
            is_checked = item.checkState() == Qt.CheckState.Checked
            self.alarms[row].is_active = is_checked

            self.save_alarms()

    def load_alarms(self):
        self.alarms = load_alarms()
        self.update_table_display()

    def save_alarms(self):
        try:
            save_alarms(self.alarms)
        except Exception as error:
            print(f"Storage error: {error}")

    def update_table_display(self):
        self.table_model.setRowCount(0)
        for alarm in self.alarms:
            status_item = QStandardItem("")
            status_item.setCheckable(True)
            if getattr(alarm, "is_active", True):
                status_item.setCheckState(Qt.CheckState.Checked)
            else:
                status_item.setCheckState(Qt.CheckState.Unchecked)

            self.table_model.appendRow(
                [QStandardItem(alarm.time_str), QStandardItem(alarm.title), status_item]
            )

    def add_alarm(self):
        self.alarms = load_alarms(self.alarms)

        self.alarms.append(self._build_alarm_from_form())
        self._persist_alarm_changes(reset_form=True)

    def delete_alarm(self):
        selected_indexes = self.ui.Alert_tableView.selectionModel().selectedRows()
        if selected_indexes:
            self.alarms = load_alarms(self.alarms)

            del self.alarms[selected_indexes[0].row()]
            self._persist_alarm_changes()

    def start_worker(self):
        if os.path.exists(WORKER_FILE):
            self.worker_process = subprocess.Popen(
                [sys.executable, WORKER_FILE, "--background"],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            print(f"[GUI] Spawned worker process at: {WORKER_FILE}")
        else:
            print(f"[GUI ERROR] Could not find worker.py at target path: {WORKER_FILE}")

    def _current_icon_path(self):
        if self.is_dark_mode():
            return (
                WHITE_ICON_FILE
                if os.path.exists(WHITE_ICON_FILE)
                else WHITE_ICON_FALLBACK_FILE
            )
        return (
            BLACK_ICON_FILE
            if os.path.exists(BLACK_ICON_FILE)
            else BLACK_ICON_FALLBACK_FILE
        )

    def _stylesheet_for_theme(self, selected_text):
        if selected_text == "Dark Mode":
            return DARK_THEME_FILE
        if selected_text == "Light Mode":
            return LIGHT_THEME_FILE
        if selected_text == "System Default":
            return DARK_THEME_FILE if self.is_dark_mode() else LIGHT_THEME_FILE
        return DARK_THEME_FILE

    def _selected_days(self):
        if self.ui.Diary_radioButton.isChecked():
            return None

        raw_days = self.ui.Weekdays_lineEdit.text()
        return (
            [day.strip().capitalize() for day in raw_days.split(",") if day.strip()]
            if raw_days.strip()
            else None
        )

    def _build_alarm_from_form(self):
        return Alarm(
            time_str=self.ui.Alert_timeEdit.time().toString("HH:mm"),
            title=self.ui.Name_lineEdit.text().strip() or "Alarm Alert!",
            days=self._selected_days(),
        )

    def _reset_alarm_form(self):
        self.ui.Name_lineEdit.clear()
        self.ui.Weekdays_lineEdit.clear()
        self.ui.Diary_radioButton.setChecked(True)
        self.ui.Weekdays_lineEdit.setDisabled(True)
        self.ui.Alert_timeEdit.setTime(QTime.currentTime())

    def _persist_alarm_changes(self, reset_form=False):
        self.save_alarms()
        self.update_table_display()
        if reset_form:
            self._reset_alarm_form()


def load_stylesheet(app, filename="darkTheme_styles.qss"):
    """Safely loads and applies a QSS stylesheet or clears it if filename is None."""
    if os.path.isabs(filename):
        file_path = filename
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, filename)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print(
            f"Warning: Stylesheet could not be found at {file_path}. Using default system theme."
        )
        app.setStyleSheet("")


def qt_message_filter(msg_type, context, message):
    """Intercepts and deletes the harmless font point-size warning."""
    if "QFont::setPointSize" in message:
        return  # Drop this warning silently

    # Let all other real errors/warnings print normally
    sys.stderr.write(f"{message}\n")


if __name__ == "__main__":
    qInstallMessageHandler(qt_message_filter)  # Install the custom message filter
    if not acquire_single_instance_lock():
        sys.exit(0)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
