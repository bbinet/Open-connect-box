"""
Scheduler module for uAldes
Handles scheduled commands with persistence and NTP time sync
"""

import json

SCHEDULES_FILE = "schedules.json"


def load_schedules():
    """Load schedules from file"""
    try:
        with open(SCHEDULES_FILE, "r") as f:
            data = json.load(f)
            return data.get("schedules", [])
    except:
        return []


def save_schedules(schedules):
    """Save schedules to file (sorted by time)"""
    try:
        # Sort schedules by hour, then minute
        schedules.sort(key=lambda s: (s.get("hour", 0), s.get("minute", 0)))
        with open(SCHEDULES_FILE, "w") as f:
            json.dump({"schedules": schedules}, f)
        return True
    except Exception as e:
        print(f"Failed to save schedules: {e}")
        return False


def add_schedule(hour, minute, command_type, params=None, enabled=True):
    """Add a new schedule

    Args:
        hour: 0-23
        minute: 0-59
        command_type: "auto", "boost", "confort", "vacances", "temp", "status"
        params: dict with command parameters (e.g., {"duration": 2})
        enabled: whether the schedule is active

    Returns:
        The new schedule index or -1 if invalid
    """
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return -1

    valid_types = ["auto", "boost", "confort", "vacances", "temp", "status"]
    if command_type not in valid_types:
        return -1

    schedule = {
        "hour": hour,
        "minute": minute,
        "command": {"type": command_type},
        "enabled": enabled
    }

    if params:
        schedule["command"]["params"] = params

    schedules = load_schedules()
    schedules.append(schedule)
    save_schedules(schedules)

    return len(schedules) - 1


def edit_schedule(index, hour=None, minute=None, command_type=None, params=None, enabled=None):
    """Edit an existing schedule"""
    schedules = load_schedules()
    if not (0 <= index < len(schedules)):
        return None

    schedule = schedules[index]

    if hour is not None:
        if not (0 <= hour <= 23):
            return None
        schedule["hour"] = hour

    if minute is not None:
        if not (0 <= minute <= 59):
            return None
        schedule["minute"] = minute

    if command_type is not None:
        valid_types = ["auto", "boost", "confort", "vacances", "temp", "status"]
        if command_type not in valid_types:
            return None
        schedule["command"]["type"] = command_type

    if params is not None:
        schedule["command"]["params"] = params

    if enabled is not None:
        schedule["enabled"] = enabled

    schedules[index] = schedule
    save_schedules(schedules)
    return schedule


def enable_schedule(index, enabled=True):
    """Enable or disable a schedule"""
    return edit_schedule(index, enabled=enabled)


def remove_schedule(index):
    """Remove schedule by index"""
    schedules = load_schedules()
    if 0 <= index < len(schedules):
        removed = schedules.pop(index)
        save_schedules(schedules)
        return removed
    return None


def clear_schedules():
    """Remove all schedules"""
    save_schedules([])
    return True


def get_schedules():
    """Get all schedules"""
    return load_schedules()


def get_schedule(index):
    """Get a specific schedule by index"""
    schedules = load_schedules()
    if 0 <= index < len(schedules):
        return schedules[index]
    return None


class Scheduler:
    """Scheduler that checks and executes commands at specified times"""

    def __init__(self, wifi, uart, timezone_offset=1, ntp_server="pool.ntp.org", status_callback=None):
        """
        Args:
            wifi: ESP8285 instance for NTP
            uart: UART instance for sending commands
            timezone_offset: Hours from UTC (1 for CET, 2 for CEST)
            ntp_server: NTP server address
            status_callback: Function that returns current device status dict
        """
        self.wifi = wifi
        self.uart = uart
        self.timezone_offset = timezone_offset
        self.ntp_server = ntp_server
        self.status_callback = status_callback
        self.enabled = False
        self.last_check = 0
        self.current_date = None
        self.today_executions = []
        self.time_synced = False

    def start(self):
        """Initialize SNTP and start scheduler"""
        if self.wifi.configure_sntp(self.timezone_offset, self.ntp_server):
            print(f"Scheduler: SNTP configured (UTC+{self.timezone_offset})")
            self.enabled = True
            import utime
            utime.sleep(2)
            time_tuple = self.wifi.get_sntp_time()
            if time_tuple:
                self.time_synced = True
                print(f"Scheduler: Time synced - {time_tuple[3]:02d}:{time_tuple[4]:02d}")
            return True
        print("Scheduler: Failed to configure SNTP")
        return False

    def get_current_time(self):
        """Get current time as tuple (year, month, day, hour, minute, second)"""
        return self.wifi.get_sntp_time()

    def get_today_executions(self):
        """Get list of executions for today"""
        return {
            "date": self.current_date,
            "executions": self.today_executions
        }

    def _record_execution(self, index, schedule, success, output=None, error=None):
        """Record an execution attempt"""
        time_tuple = self.get_current_time()
        time_str = f"{time_tuple[3]:02d}:{time_tuple[4]:02d}:{time_tuple[5]:02d}" if time_tuple else "unknown"

        record = {
            "index": index,
            "time": time_str,
            "command": schedule.get("command", {}),
            "success": success,
            "output": output
        }
        if error:
            record["error"] = str(error)

        self.today_executions.append(record)

    def _already_executed_today(self, index):
        """Check if schedule was already successfully executed today"""
        for record in self.today_executions:
            if record["index"] == index and record["success"]:
                return True
        return False

    def check(self):
        """Check and execute due schedules. Call periodically from main loop."""
        import utime
        import ualdes

        if not self.enabled:
            return

        current_ticks = utime.time()
        if (current_ticks - self.last_check) < 30:
            return
        self.last_check = current_ticks

        time_tuple = self.get_current_time()
        if not time_tuple or time_tuple[0] < 2020:
            # Time not synced or invalid, try to resync
            print("Scheduler: Time invalid, resyncing SNTP...")
            self.wifi.configure_sntp(self.timezone_offset, self.ntp_server)
            utime.sleep(2)
            time_tuple = self.get_current_time()
            if not time_tuple or time_tuple[0] < 2020:
                print("Scheduler: SNTP resync failed")
                return
            print(f"Scheduler: Time resynced - {time_tuple[3]:02d}:{time_tuple[4]:02d}")

        year, month, day, hour, minute, second = time_tuple
        date_key = f"{year}-{month:02d}-{day:02d}"

        # Reset at midnight
        if self.current_date != date_key:
            self.today_executions = []
            self.current_date = date_key
            # Resync SNTP at midnight
            print("Scheduler: Midnight - resyncing SNTP...")
            self.wifi.configure_sntp(self.timezone_offset, self.ntp_server)

        schedules = get_schedules()
        for i, schedule in enumerate(schedules):
            if not schedule.get("enabled", True):
                continue

            sched_hour = schedule.get("hour", -1)
            sched_minute = schedule.get("minute", -1)
            command = schedule.get("command", {})
            cmd_type = command.get("type", "")

            if self._already_executed_today(i):
                continue

            if hour == sched_hour and minute == sched_minute:
                print(f"Scheduler: Running schedule {i} at {hour:02d}:{minute:02d}")
                try:
                    if cmd_type == "status":
                        # Read-only: get current status
                        if self.status_callback:
                            output = self.status_callback()
                            self._record_execution(i, schedule, True, output)
                            print(f"Scheduler: Status recorded")
                        else:
                            self._record_execution(i, schedule, False, None, "No status callback")
                    else:
                        # Write command
                        cmd_json = json.dumps(command)
                        frame = ualdes.frame_encode(cmd_json)
                        if frame:
                            self.uart.write(bytearray(frame))
                            # Get status after command
                            output = self.status_callback() if self.status_callback else None
                            self._record_execution(i, schedule, True, output)
                            print(f"Scheduler: Executed {cmd_type}")
                        else:
                            self._record_execution(i, schedule, False, None, "Failed to encode")
                except Exception as e:
                    print(f"Scheduler: Error - {e}")
                    self._record_execution(i, schedule, False, None, e)
