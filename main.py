"""Desktop Notifier: main window and system tray app.

The GUI lets you create, edit, delete and turn alarms on or off. Closing the
window only hides it to the system tray. The actual alarm checks happen in a
separate background process (worker.py), which this window starts and stops.
"""

import sys
import os
import subprocess
import csv
import io

from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAbstractItemView,
    QStyledItemDelegate,
    QStyle,
    QPushButton,
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon, QCursor
from PyQt6.QtCore import QTime, qInstallMessageHandler, Qt, QRect, QEvent
from gui import Ui_MainWindow
from alarm_model import Alarm, DEFAULT_DAYS
from alarm_storage import load_alarms, save_alarms
from app_paths import (
    BLACK_ICON_FILE,
    BLACK_ICON_FALLBACK_FILE,
    DARK_THEME_FILE,
    LIGHT_THEME_FILE,
    STATUS_OFF_ICON_FILE,
    STATUS_ON_ICON_FILE,
    WHITE_ICON_FILE,
    WHITE_ICON_FALLBACK_FILE,
    WORKER_FILE,
    EDIT_BLACK_BUTTON_ICON_FILE,
    EDIT_WHITE_BUTTON_ICON_FILE,
)

IS_WINDOWS = os.name == "nt"
SINGLE_INSTANCE_MUTEX_NAME = "Global\\DesktopNotifier_SingleInstance_Mutex_Lock"
# Kept for the app's whole lifetime: Windows releases the mutex when the handle closes
_APP_MUTEX_HANDLE = None

if IS_WINDOWS:
    import winreg
    import ctypes


# .ico files only work on Windows, so use the .png versions elsewhere
if not IS_WINDOWS:
    BLACK_ICON_FILE = BLACK_ICON_FALLBACK_FILE
    WHITE_ICON_FILE = WHITE_ICON_FALLBACK_FILE


def acquire_single_instance_lock():
    """
    Makes sure only one copy of the app runs at a time.

    Creates a named Windows mutex. If it already exists, another instance is
    running, so a message box is shown and False is returned.
    Always returns True on other platforms.
    """
    global _APP_MUTEX_HANDLE

    if not IS_WINDOWS:
        return True

    _APP_MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(
        None, False, SINGLE_INSTANCE_MUTEX_NAME
    )
    last_error = ctypes.windll.kernel32.GetLastError()

    if last_error == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            None,
            "Desktop Notifier is already running.\n\nCheck the system tray near the clock.",
            "App Already Open",
            0x30,  # MB_ICONWARNING
        )
        return False

    return True


class StatusIconDelegate(QStyledItemDelegate):
    """
    Draws the on/off toggle in the table's Status column and flips it on click.

    The alarm's active state is stored in the cell's UserRole data.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.on_icon = QIcon(STATUS_ON_ICON_FILE)
        self.off_icon = QIcon(STATUS_OFF_ICON_FILE)

    def paint(self, painter, option, index):
        """Draws the cell background and a centred on/off toggle icon."""
        active = bool(index.data(Qt.ItemDataRole.UserRole))
        icon = self.on_icon if active else self.off_icon

        painter.save()
        painter.fillRect(option.rect, option.palette.base())
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Fixed 35x19 toggle size, centred in the cell
        icon_rect = QRect(option.rect)
        icon_rect.setWidth(35)
        icon_rect.setHeight(19)
        icon_rect.moveCenter(option.rect.center())
        icon.paint(painter, icon_rect)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Flips the alarm's active state when the Status cell is clicked."""
        if event.type() == QEvent.Type.MouseButtonRelease and index.column() == 2:
            current = bool(index.data(Qt.ItemDataRole.UserRole))
            new_state = not current
            # Updating the model emits itemChanged, which MainWindow.toggle_alarm_state
            # uses to save the new state.
            model.setData(index, new_state, Qt.ItemDataRole.UserRole)
            model.setData(
                index,
                STATUS_ON_ICON_FILE if new_state else STATUS_OFF_ICON_FILE,
                Qt.ItemDataRole.DecorationRole,
            )
            model.setData(index, "", Qt.ItemDataRole.DisplayRole)
            return True
        return super().editorEvent(event, model, option, index)


class MainWindow(QMainWindow):
    """The main app window: alarm list, create/edit form, settings and tray icon."""

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

    # --- Setup ---

    def _setup_ui(self):
        """Builds the widgets generated from UI/menu.ui (see gui.py)."""
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

    def _apply_default_theme(self):
        """Starts the app with the dark stylesheet."""
        load_stylesheet(QApplication.instance(), DARK_THEME_FILE)

    def _apply_window_icon(self):
        """Sets the window icon to the variant that matches the Windows theme."""
        icon_to_use = self._current_icon_path()
        if not os.path.exists(icon_to_use):
            print(f"[Icon Missing] Not found at: {icon_to_use}.")
            return

        self.setWindowIcon(QIcon(icon_to_use))

    def _setup_table(self):
        """Creates the alarm table: Time, Alarm Name and a Status toggle column."""
        self.table_model = QStandardItemModel(0, 3, self)
        self.table_model.setHorizontalHeaderLabels(["Time", "Alarm Name", "Status"])
        self.ui.Alert_tableView.setModel(self.table_model)
        self.ui.Alert_tableView.setItemDelegateForColumn(
            2, StatusIconDelegate(self.ui.Alert_tableView)
        )
        # Read-only table where clicking selects a whole row, one at a time
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
        """Sets the form's starting values and adds the Edit button to the sidebar."""
        # None while creating a new alarm; the alarm's id while editing one
        self.editing_alarm_id = None

        self.ui.Alert_timeEdit.setTime(QTime.currentTime())
        self.ui.Diary_radioButton.setChecked(True)
        self.ui.Weekdays_lineEdit.setDisabled(True)
        self.ui.Theme_comboBox.setCurrentText("Dark Mode")

        # The Edit button isn't in menu.ui, so it is created here and placed
        # just above the Delete button
        self.Edit_pushButton = QPushButton("Edit Alarm")
        self.Edit_pushButton.setObjectName("Edit_pushButton")
        self._update_edit_button_icon("System Default")
        self.Edit_pushButton.setMinimumSize(0, 44)
        self.Edit_pushButton.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ui.sidebarLayout.insertWidget(
            self.ui.sidebarLayout.indexOf(self.ui.Delete_pushButton),
            self.Edit_pushButton,
        )

    def _connect_signals(self):
        """Connects buttons, inputs and the table to their handlers."""
        self.ui.Create_pushButton.clicked.connect(self.handle_save_clicked)
        self.ui.Delete_pushButton.clicked.connect(self.delete_alarm)
        self.Edit_pushButton.clicked.connect(self.handle_edit_alarm)
        self.ui.Diary_radioButton.toggled.connect(self.toggle_days_input)
        self.ui.Theme_comboBox.currentTextChanged.connect(self.on_theme_changed)
        self.table_model.itemChanged.connect(self.toggle_alarm_state)

    def _setup_navigation(self):
        """Makes the menu bar switch between the alarms page (0) and settings page (1)."""
        self.ui.actionAlarms_Dashboard.triggered.connect(
            lambda: self.ui.mainStackedWidget.setCurrentIndex(0)
        )
        self.ui.actionPreferences_Settings.triggered.connect(
            lambda: self.ui.mainStackedWidget.setCurrentIndex(1)
        )

    # --- Theme ---

    def is_dark_mode(self):
        """
        Returns True if Windows is using a dark taskbar (SystemUsesLightTheme == 0).

        Always returns True on other platforms.
        """
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
        self._update_edit_button_icon(selected_text)

    def _update_edit_button_icon(self, theme):
        """Updates the Edit button icon dynamically based on the current theme."""
        if theme == "Dark Mode":
            icon_path = EDIT_WHITE_BUTTON_ICON_FILE
        if theme == "Light Mode":
            icon_path = EDIT_BLACK_BUTTON_ICON_FILE
        if theme == "System Default":
            icon_path = (
                EDIT_WHITE_BUTTON_ICON_FILE
                if self.is_dark_mode()
                else EDIT_BLACK_BUTTON_ICON_FILE
            )

        if icon_path and os.path.exists(icon_path):
            self.Edit_pushButton.setIcon(QIcon(icon_path))

    # --- System tray ---

    def init_system_tray(self):
        """Creates the hidden tray icon and its right-click menu."""
        self.tray_icon = QSystemTrayIcon(self)

        icon_to_use = self._current_icon_path()

        # Load your custom app icon
        if os.path.exists(icon_to_use):
            self.tray_icon.setIcon(QIcon(icon_to_use))
        else:
            # Fallback to a standard system icon if yours is missing
            print(f"[Icon Missing] Not found at: {icon_to_use}.")
            self.tray_icon.setIcon(
                self.style().standardIcon(
                    self.style().StandardPixmap.SP_MessageBoxInformation
                )
            )

        # Create a right-click context menu for the hidden icon
        tray_menu = QMenu()

        show_action = tray_menu.addAction("Open Notifier Menu")
        show_action.triggered.connect(self.showNormal)  # Brings window back
        # Also reset the form's time to now, so a new alarm starts from the current time
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

        self.tray_icon.hide()  # Remove the icon from the system tray
        QApplication.quit()  # Shut down the entire PyQt app

    # --- Alarm list ---

    def toggle_days_input(self, checked):
        """Disables and clears the weekdays field while "Diary?" (every day) is checked."""
        self.ui.Weekdays_lineEdit.setDisabled(checked)
        if checked:
            self.ui.Weekdays_lineEdit.clear()

    def toggle_alarm_state(self, item):
        """Saves an alarm's new on/off state after its Status toggle is clicked."""
        if item.column() != 2:
            return

        # Table rows are in the same order as self.alarms
        row = item.row()

        if 0 <= row < len(self.alarms):
            is_checked = bool(item.data(Qt.ItemDataRole.UserRole))
            self.alarms[row].is_active = is_checked

            self.save_alarms()

    def load_alarms(self):
        """Loads the saved alarms from disk and shows them in the table."""
        self.alarms = load_alarms()
        self.update_table_display()

    def save_alarms(self):
        """Writes self.alarms to disk, logging (not raising) any error."""
        try:
            save_alarms(self.alarms)
        except Exception as error:
            print(f"Storage error: {error}")

    def update_table_display(self):
        """Rebuilds every table row from self.alarms."""
        self.table_model.setRowCount(0)
        for alarm in self.alarms:
            status_item = QStandardItem("")
            status_item.setEditable(False)
            # Alarms saved before the on/off feature existed have no is_active
            is_active = getattr(alarm, "is_active", True)
            status_item.setData(is_active, Qt.ItemDataRole.UserRole)
            status_item.setData(
                STATUS_ON_ICON_FILE if is_active else STATUS_OFF_ICON_FILE,
                Qt.ItemDataRole.DecorationRole,
            )

            self.table_model.appendRow(
                [QStandardItem(alarm.time_str), QStandardItem(alarm.title), status_item]
            )

    # Before changing the list, the methods below reload it from disk so they
    # don't overwrite what the worker saved (e.g. last_triggered_date).
    # If the file can't be read, the in-memory list is used instead.

    def add_alarm(self):
        """Creates a new alarm from the form and saves it."""
        self.alarms = load_alarms(self.alarms)

        self.alarms.append(self._build_alarm_from_form())
        self._persist_alarm_changes(reset_form=True)

    def delete_alarm(self):
        """Deletes the alarm selected in the table."""
        selected_indexes = self.ui.Alert_tableView.selectionModel().selectedRows()
        if selected_indexes:
            self.alarms = load_alarms(self.alarms)

            del self.alarms[selected_indexes[0].row()]
            self._persist_alarm_changes()

    def update_alarm(self):
        """Saves the form's values over the alarm being edited and leaves edit mode."""
        self.alarms = load_alarms(self.alarms)
        for alarm in self.alarms:
            if getattr(alarm, "id", None) == self.editing_alarm_id:
                alarm.time_str = self.ui.Alert_timeEdit.time().toString("HH:mm")
                alarm.title = self.ui.Name_lineEdit.text().strip() or "Alarm Alert!"
                alarm.days = (
                    DEFAULT_DAYS
                    if self._selected_days() is None
                    else self._selected_days()
                )
                # Let the edited alarm fire again today, even if it already went off
                alarm.last_triggered_date = None
                break

        self._persist_alarm_changes(reset_form=True)
        self.editing_alarm_id = None

    def handle_save_clicked(self):
        """Handles the Create/Update button: updates in edit mode, otherwise creates."""
        if self.editing_alarm_id is not None:
            # STATE A: We are in 'Edit Mode' -> Update existing
            self.update_alarm()
        else:
            # STATE B: We are in 'Create Mode' -> Add a new one
            self.add_alarm()

    def handle_edit_alarm(self):
        """
        Handles the Edit button.

        Loads the selected alarm into the form and switches to edit mode.
        If already in edit mode, the button reads "Cancel Edit" and leaves it instead.
        """

        if self.editing_alarm_id is not None:
            self._reset_alarm_form()
            return

        selected_indexes = self.ui.Alert_tableView.selectionModel().selectedRows()
        if not selected_indexes:
            return

        self.alarms = load_alarms(self.alarms)
        row = selected_indexes[0].row()
        if row < 0 or row >= len(self.alarms):
            return

        alarm = self.alarms[row]
        self._populate_form_from_alarm(alarm)
        self.editing_alarm_id = alarm.id

        self.ui.Title_label.setText("Edit Alarm")
        self.ui.Create_pushButton.setText("Update Alarm")
        self.Edit_pushButton.setText("Cancel Edit")

    def _populate_form_from_alarm(self, alarm):
        """Fills the form with an existing alarm's name, time and days."""
        self.ui.Name_lineEdit.setText(alarm.title)
        self.ui.Alert_timeEdit.setTime(QTime.fromString(alarm.time_str, "HH:mm"))

        is_everyday = set(alarm.days) == set(DEFAULT_DAYS)
        if is_everyday:
            self.ui.Diary_radioButton.setChecked(True)
            self.ui.Weekdays_lineEdit.clear()
            self.ui.Weekdays_lineEdit.setDisabled(True)
        else:
            self.ui.Diary_radioButton.setChecked(False)
            days_str = ", ".join(alarm.days)
            self.ui.Weekdays_lineEdit.setText(days_str)
            self.ui.Weekdays_lineEdit.setDisabled(False)

    # --- Background worker ---

    def start_worker(self):
        """Starts worker.py as a hidden background process."""
        if os.path.exists(WORKER_FILE):
            # Make sure only one worker ever runs
            self._terminate_stale_workers()
            self.worker_process = subprocess.Popen(
                [sys.executable, WORKER_FILE, "--background"],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            print(f"[GUI] Spawned worker process at: {WORKER_FILE}")
        else:
            print(f"[GUI ERROR] Could not find worker.py at target path: {WORKER_FILE}")

    def _terminate_stale_workers(self):
        """
        Kills worker processes left over from earlier runs (Windows only).

        A worker can outlive the GUI, for example if the GUI crashes. PowerShell
        lists every process started with "worker.py ... --background", and each
        one is force-closed with taskkill.
        """
        if not IS_WINDOWS:
            return

        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.CommandLine -like '*worker.py*' -and $_.CommandLine -like '*--background*' } | "
                    "Select-Object ProcessId,CommandLine | "
                    "ConvertTo-Csv -NoTypeInformation",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception as error:
            print(f"[GUI] Could not scan for stale workers: {error}")
            return

        reader = csv.DictReader(io.StringIO(result.stdout))
        for row in reader:
            try:
                pid = int(row["ProcessId"])
            except (KeyError, TypeError, ValueError):
                continue

            if pid == os.getpid():
                continue

            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                print(f"[GUI] Terminated stale worker PID {pid}.")
            except Exception as error:
                print(f"[GUI] Could not terminate stale worker PID {pid}: {error}")

    # --- Helpers ---

    def _current_icon_path(self):
        """
        Returns the app icon that contrasts with the taskbar.

        White for dark mode, black for light mode, falling back to the .png
        version if the .ico file is missing.
        """
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
        """Maps a theme name from the combobox to its stylesheet file."""
        if selected_text == "Dark Mode":
            return DARK_THEME_FILE
        if selected_text == "Light Mode":
            return LIGHT_THEME_FILE
        if selected_text == "System Default":
            return DARK_THEME_FILE if self.is_dark_mode() else LIGHT_THEME_FILE
        return DARK_THEME_FILE

    def _selected_days(self):
        """
        Returns the days typed in the form as a list.

        Returns None (meaning every day) if "Diary?" is checked or the field is empty.
        """
        if self.ui.Diary_radioButton.isChecked():
            return None

        raw_days = self.ui.Weekdays_lineEdit.text()
        # "monday, friday" -> ["Monday", "Friday"]
        return (
            [day.strip().capitalize() for day in raw_days.split(",") if day.strip()]
            if raw_days.strip()
            else None
        )

    def _build_alarm_from_form(self):
        """Creates a new Alarm from the form's current values."""
        return Alarm(
            time_str=self.ui.Alert_timeEdit.time().toString("HH:mm"),
            title=self.ui.Name_lineEdit.text().strip() or "Alarm Alert!",
            days=self._selected_days(),
        )

    def _reset_alarm_form(self):
        """Clears the form and switches it back to "New Alarm" mode."""
        self.ui.Name_lineEdit.clear()
        self.ui.Weekdays_lineEdit.clear()
        self.ui.Diary_radioButton.setChecked(True)
        self.ui.Weekdays_lineEdit.setDisabled(True)
        self.ui.Alert_timeEdit.setTime(QTime.currentTime())
        self.ui.Title_label.setText("New Alarm")
        self.ui.Create_pushButton.setText("Create New Alarm")
        self.Edit_pushButton.setText("Edit Alarm")
        self.editing_alarm_id = None

    def _persist_alarm_changes(self, reset_form=False):
        """Saves the alarms, refreshes the table and optionally resets the form."""
        self.save_alarms()
        self.update_table_display()
        if reset_form:
            self._reset_alarm_form()


def load_stylesheet(app, filename="darkTheme_styles.qss"):
    """
    Safely loads and applies a QSS stylesheet to the whole app.

    Relative paths are resolved from this script's folder. If the file can't be
    found, the stylesheet is cleared and the default system look is used.
    """
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
    """Hides Qt's harmless font point-size warning and prints every other Qt message."""
    if "QFont::setPointSize" in message:
        return  # Drop this warning silently

    # Let all other real errors/warnings print normally
    sys.stderr.write(f"{message}\n")


if __name__ == "__main__":
    qInstallMessageHandler(qt_message_filter)  # Install the custom message filter
    # Exit if another copy is already running (the user was already warned)
    if not acquire_single_instance_lock():
        sys.exit(0)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
