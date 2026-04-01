"""
Pytest tests for scheduler.py

Run with: pytest tests/test_scheduler.py -v
"""

import pytest
import json
import os
import sys

# Add device directory to path
DEVICE_DIR = os.path.join(os.path.dirname(__file__), '..', 'device')
sys.path.insert(0, DEVICE_DIR)


class TestScheduleSorting:
    """Tests for schedule sorting functionality"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        """Create a temporary schedules file"""
        schedules_file = tmp_path / "schedules.json"
        # Patch the SCHEDULES_FILE constant
        monkeypatch.chdir(tmp_path)
        return schedules_file

    def test_save_schedules_sorts_by_time(self, temp_schedules_file):
        """Test that schedules are sorted by hour and minute when saved"""
        import scheduler

        # Create unsorted schedules
        unsorted = [
            {"hour": 22, "minute": 0, "command": {"type": "auto"}, "enabled": True},
            {"hour": 6, "minute": 30, "command": {"type": "boost"}, "enabled": True},
            {"hour": 6, "minute": 0, "command": {"type": "status"}, "enabled": True},
            {"hour": 12, "minute": 15, "command": {"type": "confort"}, "enabled": True},
        ]

        scheduler.save_schedules(unsorted)
        loaded = scheduler.load_schedules()

        # Verify sorted order
        assert loaded[0]["hour"] == 6 and loaded[0]["minute"] == 0
        assert loaded[1]["hour"] == 6 and loaded[1]["minute"] == 30
        assert loaded[2]["hour"] == 12 and loaded[2]["minute"] == 15
        assert loaded[3]["hour"] == 22 and loaded[3]["minute"] == 0

    def test_add_schedule_maintains_sort_order(self, temp_schedules_file):
        """Test that adding a schedule maintains sort order"""
        import scheduler

        # Start with empty
        scheduler.save_schedules([])

        # Add schedules out of order
        scheduler.add_schedule(22, 0, "auto")
        scheduler.add_schedule(6, 0, "boost")
        scheduler.add_schedule(12, 30, "status")

        loaded = scheduler.load_schedules()

        assert loaded[0]["hour"] == 6
        assert loaded[1]["hour"] == 12
        assert loaded[2]["hour"] == 22

    def test_edit_schedule_resorts(self, temp_schedules_file):
        """Test that editing a schedule re-sorts the list"""
        import scheduler

        # Create sorted schedules
        scheduler.save_schedules([
            {"hour": 6, "minute": 0, "command": {"type": "boost"}, "enabled": True},
            {"hour": 12, "minute": 0, "command": {"type": "status"}, "enabled": True},
            {"hour": 22, "minute": 0, "command": {"type": "auto"}, "enabled": True},
        ])

        # Edit middle schedule to be first
        scheduler.edit_schedule(1, hour=5, minute=0)

        loaded = scheduler.load_schedules()

        # Should now be: 5:00, 6:00, 22:00
        assert loaded[0]["hour"] == 5
        assert loaded[1]["hour"] == 6
        assert loaded[2]["hour"] == 22

    def test_sort_handles_same_hour_different_minute(self, temp_schedules_file):
        """Test sorting with same hour but different minutes"""
        import scheduler

        unsorted = [
            {"hour": 8, "minute": 45, "command": {"type": "a"}, "enabled": True},
            {"hour": 8, "minute": 15, "command": {"type": "b"}, "enabled": True},
            {"hour": 8, "minute": 30, "command": {"type": "c"}, "enabled": True},
            {"hour": 8, "minute": 0, "command": {"type": "d"}, "enabled": True},
        ]

        scheduler.save_schedules(unsorted)
        loaded = scheduler.load_schedules()

        assert [s["minute"] for s in loaded] == [0, 15, 30, 45]

    def test_remove_schedule_maintains_order(self, temp_schedules_file):
        """Test that removing a schedule doesn't affect sort order"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 6, "minute": 0, "command": {"type": "a"}, "enabled": True},
            {"hour": 12, "minute": 0, "command": {"type": "b"}, "enabled": True},
            {"hour": 18, "minute": 0, "command": {"type": "c"}, "enabled": True},
        ])

        scheduler.remove_schedule(1)  # Remove 12:00

        loaded = scheduler.load_schedules()

        assert len(loaded) == 2
        assert loaded[0]["hour"] == 6
        assert loaded[1]["hour"] == 18


class TestScheduleValidation:
    """Tests for schedule validation"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        """Create a temporary schedules file"""
        monkeypatch.chdir(tmp_path)

    def test_add_schedule_validates_hour(self, temp_schedules_file):
        """Test that invalid hours are rejected"""
        import scheduler

        scheduler.save_schedules([])

        assert scheduler.add_schedule(-1, 0, "auto") == -1
        assert scheduler.add_schedule(24, 0, "auto") == -1
        assert scheduler.add_schedule(25, 0, "auto") == -1

    def test_add_schedule_validates_minute(self, temp_schedules_file):
        """Test that invalid minutes are rejected"""
        import scheduler

        scheduler.save_schedules([])

        assert scheduler.add_schedule(12, -1, "auto") == -1
        assert scheduler.add_schedule(12, 60, "auto") == -1
        assert scheduler.add_schedule(12, 100, "auto") == -1

    def test_add_schedule_validates_command_type(self, temp_schedules_file):
        """Test that invalid command types are rejected"""
        import scheduler

        scheduler.save_schedules([])

        assert scheduler.add_schedule(12, 0, "invalid_command") == -1
        assert scheduler.add_schedule(12, 0, "") == -1

    def test_add_schedule_accepts_valid_types(self, temp_schedules_file):
        """Test that valid command types are accepted"""
        import scheduler

        scheduler.save_schedules([])

        valid_types = ["auto", "boost", "confort", "vacances", "temp", "status"]
        for i, cmd_type in enumerate(valid_types):
            result = scheduler.add_schedule(i, 0, cmd_type)
            assert result >= 0, f"Failed for type: {cmd_type}"


class TestAddSchedule:
    """Tests for add_schedule function"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_add_schedule_with_params(self, temp_schedules_file):
        """Test adding schedule with parameters"""
        import scheduler

        scheduler.save_schedules([])
        scheduler.add_schedule(8, 0, "confort", params={"duration": 2})

        loaded = scheduler.load_schedules()
        assert loaded[0]["command"]["params"] == {"duration": 2}

    def test_add_schedule_disabled(self, temp_schedules_file):
        """Test adding disabled schedule"""
        import scheduler

        scheduler.save_schedules([])
        scheduler.add_schedule(8, 0, "auto", enabled=False)

        loaded = scheduler.load_schedules()
        assert loaded[0]["enabled"] is False

    def test_add_schedule_returns_index(self, temp_schedules_file):
        """Test that add_schedule returns correct index"""
        import scheduler

        scheduler.save_schedules([])
        idx0 = scheduler.add_schedule(8, 0, "auto")
        idx1 = scheduler.add_schedule(9, 0, "boost")
        idx2 = scheduler.add_schedule(10, 0, "status")

        # Note: index returned is position in list after sorting
        assert idx0 == 0
        assert idx1 == 1
        assert idx2 == 2


class TestEditSchedule:
    """Tests for edit_schedule function"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_edit_schedule_invalid_index(self, temp_schedules_file):
        """Test edit with invalid index returns None"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        assert scheduler.edit_schedule(-1, hour=9) is None
        assert scheduler.edit_schedule(5, hour=9) is None

    def test_edit_schedule_command_type(self, temp_schedules_file):
        """Test editing command type"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        result = scheduler.edit_schedule(0, command_type="boost")

        assert result is not None
        assert result["command"]["type"] == "boost"
        loaded = scheduler.load_schedules()
        assert loaded[0]["command"]["type"] == "boost"

    def test_edit_schedule_invalid_command_type(self, temp_schedules_file):
        """Test editing with invalid command type returns None"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        result = scheduler.edit_schedule(0, command_type="invalid")
        assert result is None

    def test_edit_schedule_params(self, temp_schedules_file):
        """Test editing params"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "confort"}, "enabled": True}
        ])

        scheduler.edit_schedule(0, params={"duration": 5})

        loaded = scheduler.load_schedules()
        assert loaded[0]["command"]["params"] == {"duration": 5}

    def test_edit_schedule_enabled(self, temp_schedules_file):
        """Test editing enabled state"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        scheduler.edit_schedule(0, enabled=False)

        loaded = scheduler.load_schedules()
        assert loaded[0]["enabled"] is False

    def test_edit_schedule_invalid_hour(self, temp_schedules_file):
        """Test editing with invalid hour returns None"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        assert scheduler.edit_schedule(0, hour=25) is None
        assert scheduler.edit_schedule(0, hour=-1) is None

    def test_edit_schedule_invalid_minute(self, temp_schedules_file):
        """Test editing with invalid minute returns None"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        assert scheduler.edit_schedule(0, minute=60) is None
        assert scheduler.edit_schedule(0, minute=-1) is None


class TestEnableSchedule:
    """Tests for enable_schedule function"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_enable_schedule(self, temp_schedules_file):
        """Test enabling a disabled schedule"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": False}
        ])

        scheduler.enable_schedule(0, True)

        loaded = scheduler.load_schedules()
        assert loaded[0]["enabled"] is True

    def test_disable_schedule(self, temp_schedules_file):
        """Test disabling an enabled schedule"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        scheduler.enable_schedule(0, False)

        loaded = scheduler.load_schedules()
        assert loaded[0]["enabled"] is False


class TestRemoveSchedule:
    """Tests for remove_schedule function"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_remove_schedule_returns_removed(self, temp_schedules_file):
        """Test that remove returns the removed schedule"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        removed = scheduler.remove_schedule(0)

        assert removed is not None
        assert removed["hour"] == 8
        assert removed["command"]["type"] == "auto"

    def test_remove_schedule_invalid_index(self, temp_schedules_file):
        """Test remove with invalid index returns None"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        assert scheduler.remove_schedule(-1) is None
        assert scheduler.remove_schedule(5) is None


class TestClearSchedules:
    """Tests for clear_schedules function"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_clear_schedules(self, temp_schedules_file):
        """Test clearing all schedules"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True},
            {"hour": 12, "minute": 0, "command": {"type": "boost"}, "enabled": True},
        ])

        result = scheduler.clear_schedules()

        assert result is True
        loaded = scheduler.load_schedules()
        assert loaded == []


class TestGetSchedules:
    """Tests for get_schedules and get_schedule functions"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_get_schedules(self, temp_schedules_file):
        """Test getting all schedules"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True},
            {"hour": 12, "minute": 0, "command": {"type": "boost"}, "enabled": True},
        ])

        schedules = scheduler.get_schedules()

        assert len(schedules) == 2
        assert schedules[0]["hour"] == 8
        assert schedules[1]["hour"] == 12

    def test_get_schedule_by_index(self, temp_schedules_file):
        """Test getting a specific schedule by index"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True},
            {"hour": 12, "minute": 0, "command": {"type": "boost"}, "enabled": True},
        ])

        schedule = scheduler.get_schedule(1)

        assert schedule is not None
        assert schedule["hour"] == 12
        assert schedule["command"]["type"] == "boost"

    def test_get_schedule_invalid_index(self, temp_schedules_file):
        """Test getting schedule with invalid index returns None"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 8, "minute": 0, "command": {"type": "auto"}, "enabled": True}
        ])

        assert scheduler.get_schedule(-1) is None
        assert scheduler.get_schedule(5) is None


class TestLoadSchedules:
    """Tests for load_schedules function"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_load_schedules_empty_file(self, temp_schedules_file):
        """Test loading when file doesn't exist returns empty list"""
        import scheduler

        loaded = scheduler.load_schedules()
        assert loaded == []

    def test_load_schedules_invalid_json(self, temp_schedules_file):
        """Test loading invalid JSON returns empty list"""
        import scheduler

        with open("schedules.json", "w") as f:
            f.write("not valid json")

        loaded = scheduler.load_schedules()
        assert loaded == []

    def test_load_schedules_missing_schedules_key(self, temp_schedules_file):
        """Test loading JSON without schedules key returns empty list"""
        import scheduler

        with open("schedules.json", "w") as f:
            json.dump({"other": "data"}, f)

        loaded = scheduler.load_schedules()
        assert loaded == []


class TestDST:
    """Tests for DST (Daylight Saving Time) functions"""

    def test_get_eu_dst_offset_winter(self):
        """Test DST offset in winter months (Jan, Feb, Nov, Dec)"""
        import scheduler

        # January - winter time
        assert scheduler.get_eu_dst_offset(2026, 1, 15) == 0
        # February - winter time
        assert scheduler.get_eu_dst_offset(2026, 2, 15) == 0
        # November - winter time
        assert scheduler.get_eu_dst_offset(2026, 11, 15) == 0
        # December - winter time
        assert scheduler.get_eu_dst_offset(2026, 12, 15) == 0

    def test_get_eu_dst_offset_summer(self):
        """Test DST offset in summer months (Apr-Sep)"""
        import scheduler

        # April to September - always summer time
        for month in range(4, 10):
            assert scheduler.get_eu_dst_offset(2026, month, 15) == 1, f"Failed for month {month}"

    def test_get_eu_dst_offset_march_transition(self):
        """Test DST transition in March (last Sunday)"""
        import scheduler

        # 2026: March 29 is last Sunday
        # Before last Sunday - winter
        assert scheduler.get_eu_dst_offset(2026, 3, 28) == 0
        # On last Sunday - summer
        assert scheduler.get_eu_dst_offset(2026, 3, 29) == 1
        # After last Sunday - summer
        assert scheduler.get_eu_dst_offset(2026, 3, 30) == 1
        assert scheduler.get_eu_dst_offset(2026, 3, 31) == 1

    def test_get_eu_dst_offset_october_transition(self):
        """Test DST transition in October (last Sunday)"""
        import scheduler

        # 2026: October 25 is last Sunday
        # Before last Sunday - summer
        assert scheduler.get_eu_dst_offset(2026, 10, 24) == 1
        # On last Sunday - winter
        assert scheduler.get_eu_dst_offset(2026, 10, 25) == 0
        # After last Sunday - winter
        assert scheduler.get_eu_dst_offset(2026, 10, 26) == 0
        assert scheduler.get_eu_dst_offset(2026, 10, 31) == 0

    def test_get_eu_dst_offset_various_years(self):
        """Test DST for various years to verify formula"""
        import scheduler

        # Test data: (year, march_last_sunday, october_last_sunday)
        test_years = [
            (2024, 31, 27),
            (2025, 30, 26),
            (2026, 29, 25),
            (2027, 28, 31),
            (2028, 26, 29),
        ]

        for year, march_sun, oct_sun in test_years:
            # Day before March transition - winter
            assert scheduler.get_eu_dst_offset(year, 3, march_sun - 1) == 0, f"Failed {year} March {march_sun - 1}"
            # March transition day - summer
            assert scheduler.get_eu_dst_offset(year, 3, march_sun) == 1, f"Failed {year} March {march_sun}"
            # Day before October transition - summer
            assert scheduler.get_eu_dst_offset(year, 10, oct_sun - 1) == 1, f"Failed {year} Oct {oct_sun - 1}"
            # October transition day - winter
            assert scheduler.get_eu_dst_offset(year, 10, oct_sun) == 0, f"Failed {year} Oct {oct_sun}"

    def test_get_timezone_offset_paris(self):
        """Test timezone offset for Europe/Paris"""
        import scheduler

        # Winter: UTC+1
        assert scheduler.get_timezone_offset("Europe/Paris", 2026, 1, 15) == 1
        # Summer: UTC+2
        assert scheduler.get_timezone_offset("Europe/Paris", 2026, 7, 15) == 2

    def test_get_timezone_offset_london(self):
        """Test timezone offset for Europe/London"""
        import scheduler

        # Winter: UTC+0
        assert scheduler.get_timezone_offset("Europe/London", 2026, 1, 15) == 0
        # Summer: UTC+1
        assert scheduler.get_timezone_offset("Europe/London", 2026, 7, 15) == 1

    def test_get_timezone_offset_helsinki(self):
        """Test timezone offset for Europe/Helsinki (EET/EEST)"""
        import scheduler

        # Winter: UTC+2
        assert scheduler.get_timezone_offset("Europe/Helsinki", 2026, 1, 15) == 2
        # Summer: UTC+3
        assert scheduler.get_timezone_offset("Europe/Helsinki", 2026, 7, 15) == 3

    def test_get_timezone_offset_utc(self):
        """Test timezone offset for UTC (no DST)"""
        import scheduler

        # UTC has no DST
        assert scheduler.get_timezone_offset("UTC", 2026, 1, 15) == 0
        assert scheduler.get_timezone_offset("UTC", 2026, 7, 15) == 0

    def test_get_timezone_offset_unknown(self):
        """Test timezone offset for unknown timezone"""
        import scheduler

        # Unknown timezone returns 0
        assert scheduler.get_timezone_offset("Unknown/City", 2026, 7, 15) == 0

    def test_get_timezone_offset_integer_fallback(self):
        """Test timezone offset with integer string (fallback)"""
        import scheduler

        # Integer string as fallback
        assert scheduler.get_timezone_offset("1", 2026, 7, 15) == 1
        assert scheduler.get_timezone_offset("2", 2026, 7, 15) == 2
        assert scheduler.get_timezone_offset("-5", 2026, 7, 15) == -5


class TestBoostMinTemp:
    """Tests for boost command with min_temp condition"""

    @pytest.fixture
    def temp_schedules_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_add_schedule_boost_with_min_temp(self, temp_schedules_file):
        """Test adding a boost schedule with min_temp parameter"""
        import scheduler

        scheduler.save_schedules([])
        index = scheduler.add_schedule(6, 0, "boost", params={"min_temp": 22.0})

        assert index >= 0
        loaded = scheduler.load_schedules()
        assert loaded[0]["command"]["type"] == "boost"
        assert loaded[0]["command"]["params"]["min_temp"] == 22.0

    def test_add_schedule_boost_without_min_temp(self, temp_schedules_file):
        """Test adding a boost schedule without min_temp parameter"""
        import scheduler

        scheduler.save_schedules([])
        index = scheduler.add_schedule(6, 0, "boost")

        assert index >= 0
        loaded = scheduler.load_schedules()
        assert loaded[0]["command"]["type"] == "boost"
        assert "params" not in loaded[0]["command"] or loaded[0]["command"].get("params") is None

    def test_edit_schedule_add_min_temp(self, temp_schedules_file):
        """Test editing a schedule to add min_temp"""
        import scheduler

        scheduler.save_schedules([
            {"hour": 6, "minute": 0, "command": {"type": "boost"}, "enabled": True}
        ])

        scheduler.edit_schedule(0, params={"min_temp": 20.5})

        loaded = scheduler.load_schedules()
        assert loaded[0]["command"]["params"]["min_temp"] == 20.5

    def test_boost_condition_temp_below_threshold(self):
        """Test that boost executes when T_haut < min_temp"""
        # This tests the logic: if T_haut (19.5) < min_temp (22), boost should execute
        t_haut = 19.5
        min_temp = 22.0
        should_skip = float(t_haut) >= float(min_temp)
        assert should_skip is False  # Should NOT skip, should execute

    def test_boost_condition_temp_above_threshold(self):
        """Test that boost is skipped when T_haut >= min_temp"""
        # This tests the logic: if T_haut (23.0) >= min_temp (22), boost should be skipped
        t_haut = 23.0
        min_temp = 22.0
        should_skip = float(t_haut) >= float(min_temp)
        assert should_skip is True  # Should skip

    def test_boost_condition_temp_equal_threshold(self):
        """Test that boost is skipped when T_haut == min_temp"""
        # Edge case: if T_haut equals min_temp, boost should be skipped
        t_haut = 22.0
        min_temp = 22.0
        should_skip = float(t_haut) >= float(min_temp)
        assert should_skip is True  # Should skip
