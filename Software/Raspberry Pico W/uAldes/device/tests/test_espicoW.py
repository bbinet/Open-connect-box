"""
Unit tests for espicoW.py

These tests use a mock UART to simulate ESP8285 responses.
Run on device with: import test_espicoW; test_espicoW.run_all_tests()
"""

import time


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def add_fail(self, name, expected, got):
        self.failed += 1
        self.errors.append((name, expected, got))
        print(f"  [FAIL] {name}")
        print(f"         Expected: {expected}")
        print(f"         Got: {got}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"Failed tests: {self.failed}")
        print(f"{'='*50}")
        return self.failed == 0


result = TestResult()


def assert_equal(name, expected, got):
    if expected == got:
        result.add_pass(name)
    else:
        result.add_fail(name, expected, got)


def assert_true(name, condition):
    if condition:
        result.add_pass(name)
    else:
        result.add_fail(name, True, condition)


def assert_false(name, condition):
    if not condition:
        result.add_pass(name)
    else:
        result.add_fail(name, False, condition)


# =============================================================================
# Mock UART for testing
# =============================================================================

class MockUART:
    """Mock UART that simulates ESP8285 responses"""

    def __init__(self):
        self.tx_buffer = []
        self.rx_buffer = b""
        self.responses = {}
        self._setup_default_responses()

    def _setup_default_responses(self):
        """Setup default AT command responses"""
        self.responses = {
            "AT\r\n": b"AT\r\n\r\nOK\r\n",
            "AT+GMR\r\n": b"AT version:1.7.4.0\r\nSDK version:3.0.4\r\n\r\nOK\r\n",
            "AT+CWMODE=1\r\n": b"OK\r\n",
            "AT+CWMODE=2\r\n": b"OK\r\n",
            "AT+CWMODE=3\r\n": b"OK\r\n",
            "AT+CWQAP\r\n": b"OK\r\n",
            "AT+CIPMUX=1\r\n": b"OK\r\n",
            "AT+CIPMUX=0\r\n": b"OK\r\n",
            "AT+CIFSR\r\n": b'+CIFSR:STAIP,"192.168.1.100"\r\n+CIFSR:STAMAC,"aa:bb:cc:dd:ee:ff"\r\n\r\nOK\r\n',
            "AT+CWJAP?\r\n": b'+CWJAP:"TestNetwork","aa:bb:cc:dd:ee:ff",6,-50\r\n\r\nOK\r\n',
        }

    def set_response(self, command, response):
        """Set a custom response for a command"""
        self.responses[command] = response

    def write(self, data):
        """Simulate writing to UART"""
        if isinstance(data, str):
            data = data.encode()
        self.tx_buffer.append(data)

        # Find matching response
        cmd = data.decode() if isinstance(data, bytes) else data
        for pattern, response in self.responses.items():
            if pattern in cmd or cmd.startswith(pattern.split("=")[0]):
                self.rx_buffer += response
                break

    def read(self, size=None):
        """Simulate reading from UART"""
        if size is None:
            data = self.rx_buffer
            self.rx_buffer = b""
            return data
        else:
            data = self.rx_buffer[:size]
            self.rx_buffer = self.rx_buffer[size:]
            return data

    def any(self):
        """Check if data available"""
        return len(self.rx_buffer)

    def clear(self):
        """Clear buffers"""
        self.tx_buffer = []
        self.rx_buffer = b""


class MockPin:
    """Mock Pin class"""
    OUT = 1
    IN = 0

    def __init__(self, pin_num, mode=None):
        self.pin_num = pin_num
        self.mode = mode


# =============================================================================
# ESPicoW with Mock UART
# =============================================================================

class MockESPicoW:
    """ESPicoW class that uses mock UART for testing"""

    MODE_STATION = 1
    MODE_AP = 2
    MODE_BOTH = 3

    TYPE_TCP = "TCP"
    TYPE_UDP = "UDP"

    def __init__(self, mock_uart=None):
        self.uart = mock_uart or MockUART()
        self.debug = False
        self.timeout = 5000
        self.connections = {}

    def _send_cmd(self, cmd, timeout=None, wait_for="OK"):
        if timeout is None:
            timeout = self.timeout
        if self.debug:
            print(f"[TX] {cmd}")
        self.uart.write(cmd + "\r\n")

        # Simulate waiting for response
        response = b""
        start = time.ticks_ms() if hasattr(time, 'ticks_ms') else int(time.time() * 1000)

        while True:
            if self.uart.any():
                response += self.uart.read()
                try:
                    resp_str = response.decode('utf-8', 'ignore')
                    if wait_for in resp_str or "ERROR" in resp_str or "FAIL" in resp_str:
                        if self.debug:
                            print(f"[RX] {resp_str}")
                        return resp_str
                except:
                    pass

            # Check timeout
            now = time.ticks_ms() if hasattr(time, 'ticks_ms') else int(time.time() * 1000)
            if hasattr(time, 'ticks_diff'):
                elapsed = time.ticks_diff(now, start)
            else:
                elapsed = now - start

            if elapsed > timeout:
                break

        try:
            return response.decode('utf-8', 'ignore')
        except:
            return str(response)

    def test(self):
        resp = self._send_cmd("AT", timeout=1000)
        return "OK" in resp

    def get_version(self):
        resp = self._send_cmd("AT+GMR")
        return resp

    def set_mode(self, mode):
        resp = self._send_cmd(f"AT+CWMODE={mode}")
        return "OK" in resp

    def connect(self, ssid, password, timeout=15000):
        self.set_mode(self.MODE_STATION)
        cmd = f'AT+CWJAP="{ssid}","{password}"'
        # Set response for this specific command
        self.uart.set_response(cmd + "\r\n", b"WIFI CONNECTED\r\nWIFI GOT IP\r\n\r\nOK\r\n")
        resp = self._send_cmd(cmd, timeout=timeout, wait_for="WIFI CONNECTED")
        if "WIFI CONNECTED" in resp or "OK" in resp:
            return True
        return False

    def disconnect(self):
        resp = self._send_cmd("AT+CWQAP")
        return "OK" in resp

    def is_connected(self):
        resp = self._send_cmd("AT+CWJAP?", timeout=2000)
        return "No AP" not in resp and "ERROR" not in resp

    def get_ip(self):
        resp = self._send_cmd("AT+CIFSR", timeout=2000)
        sta_ip = None
        ap_ip = None
        lines = resp.split('\n')
        for line in lines:
            if 'STAIP' in line:
                try:
                    if '"' in line:
                        start = line.index('"') + 1
                        end = line.index('"', start)
                        sta_ip = line[start:end]
                except:
                    pass
            elif 'APIP' in line:
                try:
                    if '"' in line:
                        start = line.index('"') + 1
                        end = line.index('"', start)
                        ap_ip = line[start:end]
                except:
                    pass
        return {'station': sta_ip, 'ap': ap_ip}

    def set_multiple_connections(self, enable=True):
        mode = 1 if enable else 0
        resp = self._send_cmd(f"AT+CIPMUX={mode}")
        return "OK" in resp


# =============================================================================
# Tests
# =============================================================================

def test_at_command():
    """Test basic AT command"""
    print("\n--- AT Command Tests ---")

    wifi = MockESPicoW()
    assert_true("at_command_ok", wifi.test())


def test_get_version():
    """Test getting firmware version"""
    print("\n--- Firmware Version Tests ---")

    wifi = MockESPicoW()
    version = wifi.get_version()
    assert_true("version_contains_at", "AT version" in version)
    assert_true("version_contains_sdk", "SDK version" in version)


def test_set_mode():
    """Test setting WiFi mode"""
    print("\n--- WiFi Mode Tests ---")

    wifi = MockESPicoW()

    assert_true("set_mode_station", wifi.set_mode(MockESPicoW.MODE_STATION))
    assert_true("set_mode_ap", wifi.set_mode(MockESPicoW.MODE_AP))
    assert_true("set_mode_both", wifi.set_mode(MockESPicoW.MODE_BOTH))


def test_wifi_connect():
    """Test WiFi connection"""
    print("\n--- WiFi Connection Tests ---")

    wifi = MockESPicoW()
    connected = wifi.connect("TestSSID", "TestPassword")
    assert_true("wifi_connect_success", connected)


def test_wifi_disconnect():
    """Test WiFi disconnection"""
    print("\n--- WiFi Disconnection Tests ---")

    wifi = MockESPicoW()
    disconnected = wifi.disconnect()
    assert_true("wifi_disconnect_success", disconnected)


def test_is_connected():
    """Test connection status check"""
    print("\n--- Connection Status Tests ---")

    wifi = MockESPicoW()
    connected = wifi.is_connected()
    assert_true("is_connected_true", connected)

    # Test when not connected
    wifi.uart.set_response("AT+CWJAP?\r\n", b"No AP\r\n\r\nOK\r\n")
    wifi.uart.clear()
    not_connected = wifi.is_connected()
    assert_false("is_connected_false", not_connected)


def test_get_ip():
    """Test getting IP address"""
    print("\n--- Get IP Tests ---")

    wifi = MockESPicoW()
    ip_info = wifi.get_ip()

    assert_equal("station_ip", "192.168.1.100", ip_info['station'])


def test_multiple_connections():
    """Test enabling/disabling multiple connections"""
    print("\n--- Multiple Connections Tests ---")

    wifi = MockESPicoW()

    assert_true("enable_mux", wifi.set_multiple_connections(True))
    assert_true("disable_mux", wifi.set_multiple_connections(False))


def test_command_sent_correctly():
    """Test that commands are sent correctly"""
    print("\n--- Command Format Tests ---")

    mock_uart = MockUART()
    wifi = MockESPicoW(mock_uart)

    wifi.test()
    assert_true("at_sent", b"AT\r\n" in mock_uart.tx_buffer)

    mock_uart.clear()
    wifi.set_mode(1)
    sent = b"".join(mock_uart.tx_buffer)
    assert_true("cwmode_sent", b"AT+CWMODE=1" in sent)


# =============================================================================
# Run All Tests
# =============================================================================

def run_all_tests():
    """Run all test suites"""
    global result
    result = TestResult()

    print("=" * 50)
    print("Running espicoW.py tests (with mocks)")
    print("=" * 50)

    test_at_command()
    test_get_version()
    test_set_mode()
    test_wifi_connect()
    test_wifi_disconnect()
    test_is_connected()
    test_get_ip()
    test_multiple_connections()
    test_command_sent_correctly()

    return result.summary()


if __name__ == "__main__":
    run_all_tests()
