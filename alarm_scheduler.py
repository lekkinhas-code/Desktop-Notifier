"""Checks the alarms once a minute, inside the app's own process.

The scheduler only decides which alarms are due. The main window reacts to
alarm_triggered by showing the notification, playing the sound and saving.
Because the window owns the one and only alarm list, nothing else ever
writes the alarms file at the same time.
"""

from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal


class AlarmScheduler(QObject):
    """Emits alarm_triggered for each alarm that is due, checking at the start of every minute."""

    # Emitted with the Alarm object that should go off now
    alarm_triggered = pyqtSignal(object)

    def __init__(self, get_alarms, parent=None):
        """
        :param get_alarms: Function returning the current list of Alarm objects.
            A function (not the list itself) so the scheduler always sees the
            latest list, even if the window replaces it.
        :param parent: Qt parent, so the scheduler is cleaned up with it
        """
        super().__init__(parent)
        self._get_alarms = get_alarms

        # A single-shot timer, restarted after every check, so each check can
        # be aimed at the start of the next minute (like the old worker's sleep)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.check_alarms)

    def start(self):
        """Checks right away, then at the start of every minute."""
        self.check_alarms()

    def stop(self):
        """Stops checking alarms."""
        self._timer.stop()

    def check_alarms(self):
        """Emits alarm_triggered for every alarm due now, then schedules the next check."""
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")

        try:
            for alarm in self._get_alarms():
                if alarm.should_trigger(now=now):
                    print(f"[Scheduler] Triggering alarm: {alarm.title}")
                    # Mark it as triggered for today so it doesn't fire again this minute
                    alarm.last_triggered_date = current_date
                    self.alarm_triggered.emit(alarm)
        except Exception as error:
            # One broken alarm must never stop the checks for good
            print(f"[Scheduler] Error checking alarms: {error}")
        finally:
            self._schedule_next_check()

    def _schedule_next_check(self):
        """Starts the timer so the next check happens just after the next minute begins."""
        now = datetime.now()
        # Milliseconds left in the current minute
        ms_to_next_minute = 60_000 - (now.second * 1000 + now.microsecond // 1000)

        # A tiny safety buffer (100 ms) ensures we actually cross the minute threshold
        # instead of waking up at 11:59:59.999 due to tiny system clock roundings.
        self._timer.start(ms_to_next_minute + 100)
