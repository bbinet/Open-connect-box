"""
Pytest configuration and fixtures for uAldes tests.

This file sets up mocks for MicroPython-specific modules so tests
can run on a standard Python installation.
"""

import sys
import os
import pytest

# Add the uAldes directory to the path
UALDES_DIR = os.path.join(os.path.dirname(__file__), '..', 'uAldes')
sys.path.insert(0, UALDES_DIR)


# =============================================================================
# Mock MicroPython modules
# =============================================================================

class MockPin:
    """Mock for machine.Pin"""
    OUT = 1
    IN = 0
    PULL_UP = 1
    PULL_DOWN = 2

    def __init__(self, pin_id, mode=None, pull=None):
        self.pin_id = pin_id
        self.mode = mode
        self.pull = pull
        self._value = 0

    def value(self, val=None):
        if val is None:
            return self._value
        self._value = val

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0

    def __repr__(self):
        return f"MockPin({self.pin_id})"


class MockUART:
    """Mock for machine.UART"""

    def __init__(self, uart_id, baudrate=115200, tx=None, rx=None, **kwargs):
        self.uart_id = uart_id
        self.baudrate = baudrate
        self.tx = tx
        self.rx = rx
        self._rx_buffer = b""
        self._tx_buffer = b""

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        self._tx_buffer += data
        return len(data)

    def read(self, size=None):
        if size is None:
            data = self._rx_buffer
            self._rx_buffer = b""
            return data if data else None
        data = self._rx_buffer[:size]
        self._rx_buffer = self._rx_buffer[size:]
        return data if data else None

    def any(self):
        return len(self._rx_buffer)

    def readline(self):
        if b'\n' in self._rx_buffer:
            idx = self._rx_buffer.index(b'\n') + 1
            line = self._rx_buffer[:idx]
            self._rx_buffer = self._rx_buffer[idx:]
            return line
        return None

    # Test helpers
    def _inject_rx(self, data):
        """Inject data into receive buffer for testing"""
        if isinstance(data, str):
            data = data.encode()
        self._rx_buffer += data

    def _get_tx(self):
        """Get transmitted data for testing"""
        return self._tx_buffer

    def _clear(self):
        """Clear buffers"""
        self._rx_buffer = b""
        self._tx_buffer = b""


class MockMachine:
    """Mock for the machine module"""
    Pin = MockPin
    UART = MockUART

    @staticmethod
    def reset():
        raise SystemExit("MockMachine.reset() called")


class MockTime:
    """Mock for utime module"""
    _current_ms = 0

    @classmethod
    def sleep(cls, seconds):
        cls._current_ms += int(seconds * 1000)

    @classmethod
    def sleep_ms(cls, ms):
        cls._current_ms += ms

    @classmethod
    def sleep_us(cls, us):
        cls._current_ms += us // 1000

    @classmethod
    def ticks_ms(cls):
        return cls._current_ms

    @classmethod
    def ticks_us(cls):
        return cls._current_ms * 1000

    @classmethod
    def ticks_diff(cls, t1, t2):
        return t1 - t2

    @classmethod
    def time(cls):
        return cls._current_ms // 1000

    @classmethod
    def _advance(cls, ms):
        """Test helper to advance time"""
        cls._current_ms += ms

    @classmethod
    def _reset(cls):
        """Test helper to reset time"""
        cls._current_ms = 0


class MockNetwork:
    """Mock for network module"""
    STA_IF = 0
    AP_IF = 1

    class WLAN:
        def __init__(self, interface):
            self.interface = interface
            self._active = False
            self._connected = False
            self._ssid = None

        def active(self, state=None):
            if state is not None:
                self._active = state
            return self._active

        def connect(self, ssid, password):
            self._ssid = ssid
            self._connected = True

        def disconnect(self):
            self._connected = False
            self._ssid = None

        def isconnected(self):
            return self._connected

        def ifconfig(self):
            return ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')


class MockRP2:
    """Mock for rp2 module"""
    @staticmethod
    def country(code):
        pass


# Install mocks before importing any uAldes modules
sys.modules['machine'] = MockMachine
sys.modules['utime'] = MockTime
sys.modules['network'] = MockNetwork
sys.modules['rp2'] = MockRP2


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture
def mock_uart():
    """Provide a fresh mock UART instance"""
    return MockUART(0)


@pytest.fixture
def mock_pin():
    """Provide a fresh mock Pin instance"""
    return MockPin(25, MockPin.OUT)


@pytest.fixture
def reset_time():
    """Reset mock time before each test"""
    MockTime._reset()
    yield MockTime
    MockTime._reset()


@pytest.fixture
def sample_valid_frame():
    """Provide a sample valid Aldes frame"""
    return bytes([
        0x33, 0xff, 0x4c, 0x33, 0x26, 0x00, 0x01, 0x01,
        0x98, 0x03, 0x00, 0x00, 0x88, 0x00, 0x00, 0x28,
        0x95, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0xff, 0x00, 0x00, 0x00, 0x00,
        0x56, 0x56, 0x56, 0x00, 0x93, 0x8b, 0xff, 0x03,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x81, 0xc7, 0x2c, 0x01, 0x00, 0x00, 0x00,
        0x00, 0xb0, 0xda, 0x38, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x32, 0x7a
    ])


@pytest.fixture
def mock_config(tmp_path, monkeypatch):
    """Create a mock config module"""
    config_content = '''
WIFI_NETWORKS = {
    "ssid": "TestNetwork",
    "password": "TestPassword"
}

MQTT_CONFIG = {
    "broker": "test.broker.com",
    "port": 1883,
    "client_id": "test_client",
    "user": "testuser",
    "password": "testpass",
    "ssl": False,
    "keepalive": 60
}

MQTT_TOPICS = {
    "main": "test/",
    "command": "test/commands",
}

UALDES_OPTIONS = {
    "refresh_time": 60
}

ITEMS_MAPPING = {
    "Soft": {"Index": 4, "Type": 5, "Publish": True},
    "Etat": {"Index": 6, "Type": 0, "Publish": True},
    "T_hp": {"Index": 32, "Type": 2, "Publish": True},
}

HARDWARE_CONFIG = {
    "esp_uart_id": 0,
    "esp_tx_pin": 0,
    "esp_rx_pin": 1,
    "esp_baudrate": 115200,
    "esp_debug": False,
    "stm32_uart_id": 1,
    "stm32_tx_pin": 4,
    "stm32_rx_pin": 5,
    "stm32_baudrate": 115200,
    "led_pin": 25,
}
'''
    # Write config to a temp file and add to path
    config_file = tmp_path / "config.py"
    config_file.write_text(config_content)
    monkeypatch.syspath_prepend(str(tmp_path))

    # Import and return the config
    import importlib
    if 'config' in sys.modules:
        del sys.modules['config']
    import config
    return config
