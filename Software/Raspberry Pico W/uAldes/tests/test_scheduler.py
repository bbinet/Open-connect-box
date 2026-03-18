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
