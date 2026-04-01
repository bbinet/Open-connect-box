"""
Scheduler module for uAldes
Handles scheduled commands with persistence and NTP time sync
"""

import json

SCHEDULES_FILE = "schedules.json"

# Timezone definitions: (base_offset, dst_rule)
# dst_rule: None = no DST, "EU" = European Union rules
TIMEZONES = {
    "Europe/Paris": (1, "EU"),
    "Europe/London": (0, "EU"),
    "Europe/Berlin": (1, "EU"),
    "Europe/Madrid": (1, "EU"),
    "Europe/Rome": (1, "EU"),
    "Europe/Brussels": (1, "EU"),
    "Europe/Amsterdam": (1, "EU"),
    "Europe/Zurich": (1, "EU"),
    "Europe/Vienna": (1, "EU"),
    "Europe/Warsaw": (1, "EU"),
    "Europe/Prague": (1, "EU"),
    "Europe/Stockholm": (1, "EU"),
    "Europe/Helsinki": (2, "EU"),
    "Europe/Athens": (2, "EU"),
    "UTC": (0, None),
}


def get_eu_dst_offset(year, month, day):
    """Return DST offset (0 or 1) for European Union rules.

    EU rules:
    - Summer time starts: last Sunday of March at 2:00 -> 3:00
    - Winter time starts: last Sunday of October at 3:00 -> 2:00
    """
    def last_sunday(y, m):
        # Compute day of week for last day of month (31 for March and October)
        # Using Zeller-like formula: result 0=Sunday, 1=Monday, ..., 6=Saturday
        last_day = 31
        # Formula for day of week (0=Sunday)
        # w = (day + floor(2.6*m' - 0.2) + y' + floor(y'/4) + floor(c/4) - 2*c) mod 7
        # Simplified for March (m=3) and October (m=10)
        if m == 3:
            # March 31: using adjusted formula
            w = (31 + 2 + y + y // 4 - y // 100 + y // 400) % 7
        else:
            # October 31
            w = (31 + 6 + y + y // 4 - y // 100 + y // 400) % 7
        # w: 0=Sunday, so last Sunday = 31 - w
        return last_day - w

    march_sunday = last_sunday(year, 3)
    october_sunday = last_sunday(year, 10)

    # April to September: always summer time
    if month > 3 and month < 10:
        return 1
    # March: summer time from last Sunday onwards
    if month == 3 and day >= march_sunday:
        return 1
    # October: summer time before last Sunday
    if month == 10 and day < october_sunday:
        return 1
    # November to February: winter time
    return 0


def get_timezone_offset(tz_name, year, month, day):
    """Get total UTC offset for a timezone at a given date."""
    if tz_name not in TIMEZONES:
        # Fallback: try to parse as integer offset
        try:
            return int(tz_name)
        except:
            return 0
    base, dst_rule = TIMEZONES[tz_name]
    if dst_rule == "EU":
        return base + get_eu_dst_offset(year, month, day)
    return base


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

    def __init__(self, wifi, uart, timezone="Europe/Paris", ntp_server="pool.ntp.org", status_callback=None):
        """
        Args:
            wifi: ESP8285 instance for NTP
            uart: UART instance for sending commands
            timezone: Timezone name (e.g., "Europe/Paris") - DST handled automatically
            ntp_server: NTP server address
            status_callback: Function that returns current device status dict
        """
        self.wifi = wifi
        self.uart = uart
        self.timezone = timezone
        self.ntp_server = ntp_server
        self.status_callback = status_callback
        self.enabled = False
        self.last_check = 0
        self.current_date = None
        self.today_executions = []
        self.time_synced = False
        self._current_offset = None

    def _get_base_offset(self):
        """Get base timezone offset (without DST)."""
        if self.timezone in TIMEZONES:
            return TIMEZONES[self.timezone][0]
        try:
            return int(self.timezone)
        except:
            return 0

    def _update_timezone_offset(self):
        """Update SNTP timezone offset based on current date."""
        time_tuple = self.wifi.get_sntp_time()
        if time_tuple and time_tuple[0] >= 2020:
            new_offset = get_timezone_offset(self.timezone, time_tuple[0], time_tuple[1], time_tuple[2])
            if new_offset != self._current_offset:
                old = self._current_offset
                self._current_offset = new_offset
                self.wifi.configure_sntp(new_offset, self.ntp_server)
                if old is not None:
                    print(f"Scheduler: Timezone offset changed UTC+{old} -> UTC+{new_offset}")
                return True
        return False

    def start(self):
        """Initialize SNTP and start scheduler"""
        # First sync with base timezone to get approximate date
        base_offset = self._get_base_offset()
        if self.wifi.configure_sntp(base_offset, self.ntp_server):
            self._current_offset = base_offset
            print(f"Scheduler: SNTP configured ({self.timezone}, UTC+{base_offset})")
            self.enabled = True
            import utime
            utime.sleep(2)

            # Now update with correct DST offset based on actual date
            self._update_timezone_offset()
            utime.sleep(1)

            time_tuple = self.wifi.get_sntp_time()
            if time_tuple:
                self.time_synced = True
                print(f"Scheduler: Time synced - {time_tuple[3]:02d}:{time_tuple[4]:02d} (UTC+{self._current_offset})")
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
            base_offset = self._get_base_offset()
            self.wifi.configure_sntp(base_offset, self.ntp_server)
            self._current_offset = base_offset
            utime.sleep(2)
            self._update_timezone_offset()
            time_tuple = self.get_current_time()
            if not time_tuple or time_tuple[0] < 2020:
                print("Scheduler: SNTP resync failed")
                return
            print(f"Scheduler: Time resynced - {time_tuple[3]:02d}:{time_tuple[4]:02d} (UTC+{self._current_offset})")

        year, month, day, hour, minute, second = time_tuple
        date_key = f"{year}-{month:02d}-{day:02d}"

        # Reset at midnight
        if self.current_date != date_key:
            self.today_executions = []
            self.current_date = date_key
            # Resync SNTP at midnight and update DST offset if needed
            print("Scheduler: Midnight - resyncing SNTP...")
            self._update_timezone_offset()

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
                    elif cmd_type == "boost":
                        # Boost with optional min_temp condition
                        cmd_params = command.get("params", {})
                        min_temp = cmd_params.get("min_temp")

                        # Check temperature condition if min_temp is specified
                        if min_temp is not None and self.status_callback:
                            try:
                                status = self.status_callback()
                                t_haut = status.get("T_haut")
                                if t_haut is not None and float(t_haut) >= float(min_temp):
                                    output = {
                                        "skipped": True,
                                        "reason": f"T_haut ({t_haut}C) >= min_temp ({min_temp}C)",
                                        "T_haut": float(t_haut),
                                        "min_temp": float(min_temp)
                                    }
                                    self._record_execution(i, schedule, True, output)
                                    print(f"Scheduler: Boost skipped - T_haut ({t_haut}C) >= {min_temp}C")
                                    continue
                            except (ValueError, TypeError):
                                pass

                        # Execute boost
                        cmd_json = json.dumps({"type": "boost"})
                        frame = ualdes.frame_encode(cmd_json)
                        if frame:
                            self.uart.write(bytearray(frame))
                            output = self.status_callback() if self.status_callback else None
                            self._record_execution(i, schedule, True, output)
                            print(f"Scheduler: Executed boost")
                        else:
                            self._record_execution(i, schedule, False, None, "Failed to encode")
                    else:
                        # Other write commands
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
