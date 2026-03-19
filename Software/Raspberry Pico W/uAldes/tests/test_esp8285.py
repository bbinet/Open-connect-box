"""
Pytest tests for esp8285.py (ESP8285 WiFi driver)

Run with: pytest tests/test_esp8285.py -v
"""

import pytest
import time as std_time


class MockESPUart:
    """Mock UART that simulates ESP8285 AT command responses"""

    def __init__(self):
        self.tx_buffer = []
        self.rx_buffer = b""
        self.responses = {}
        self._setup_default_responses()

    def _setup_default_responses(self):
        """Setup default AT command responses"""
        self.responses = {
            "AT": b"AT\r\n\r\nOK\r\n",
            "AT+GMR": b"AT version:1.7.4.0\r\nSDK version:3.0.4\r\n\r\nOK\r\n",
            "AT+RST": b"OK\r\n\r\nready\r\n",
            "AT+CWMODE=1": b"OK\r\n",
            "AT+CWMODE=2": b"OK\r\n",
            "AT+CWMODE=3": b"OK\r\n",
            "AT+CWQAP": b"OK\r\n",
            "AT+CIPMUX=1": b"OK\r\n",
            "AT+CIPMUX=0": b"OK\r\n",
            "AT+CIFSR": b'+CIFSR:STAIP,"192.168.1.100"\r\n+CIFSR:STAMAC,"aa:bb:cc:dd:ee:ff"\r\n\r\nOK\r\n',
            "AT+CWJAP?": b'+CWJAP:"TestNetwork","aa:bb:cc:dd:ee:ff",6,-50\r\n\r\nOK\r\n',
            "AT+CWLAP": b'+CWLAP:(3,"Network1",-45,"aa:bb:cc:dd:ee:01",1)\r\n+CWLAP:(4,"Network2",-60,"aa:bb:cc:dd:ee:02",6)\r\n\r\nOK\r\n',
            "AT+CIPSTATUS": b"STATUS:3\r\n\r\nOK\r\n",
            "AT+SLEEP=0": b"OK\r\n",
            "AT+CWDHCP=1,1": b"OK\r\n",
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
        cmd_str = data.decode().strip()
        for pattern, response in self.responses.items():
            if cmd_str == pattern or cmd_str.startswith(pattern.split("=")[0] + "="):
                self.rx_buffer += response
                return len(data)

        # Default response for unknown commands
        self.rx_buffer += b"ERROR\r\n"
        return len(data)

    def read(self, size=None):
        """Simulate reading from UART"""
        if size is None:
            data = self.rx_buffer
            self.rx_buffer = b""
            return data if data else None
        data = self.rx_buffer[:size]
        self.rx_buffer = self.rx_buffer[size:]
        return data if data else None

    def any(self):
        """Check if data available"""
        return len(self.rx_buffer)

    def clear(self):
        """Clear buffers"""
        self.tx_buffer = []
        self.rx_buffer = b""

    def get_last_command(self):
        """Get the last command sent"""
        if self.tx_buffer:
            return self.tx_buffer[-1].decode().strip()
        return None


class ESP8285Testable:
    """ESP8285 class with injectable UART for testing"""

    MODE_STATION = 1
    MODE_AP = 2
    MODE_BOTH = 3
    TYPE_TCP = "TCP"
    TYPE_UDP = "UDP"

    def __init__(self, mock_uart=None):
        self.uart = mock_uart or MockESPUart()
        self.debug = False
        self.timeout = 1000  # Shorter timeout for tests
        self.connections = {}

    def _send_cmd(self, cmd, timeout=None, wait_for="OK"):
        if timeout is None:
            timeout = self.timeout
        if self.debug:
            print(f"[TX] {cmd}")

        self.uart.write(cmd + "\r\n")

        response = b""
        start = std_time.time() * 1000

        while (std_time.time() * 1000 - start) < timeout:
            if self.uart.any():
                chunk = self.uart.read()
                if chunk:
                    response += chunk
                try:
                    resp_str = response.decode('utf-8', 'ignore')
                    if wait_for in resp_str or "ERROR" in resp_str or "FAIL" in resp_str:
                        return resp_str
                except:
                    pass
            std_time.sleep(0.001)

        return response.decode('utf-8', 'ignore') if response else ""

    def test(self):
        resp = self._send_cmd("AT", timeout=1000)
        return "OK" in resp

    def get_version(self):
        return self._send_cmd("AT+GMR")

    def set_mode(self, mode):
        resp = self._send_cmd(f"AT+CWMODE={mode}")
        return "OK" in resp

    def connect(self, ssid, password, timeout=15000):
        self.set_mode(self.MODE_STATION)
        cmd = f'AT+CWJAP="{ssid}","{password}"'
        self.uart.set_response(cmd, b"WIFI CONNECTED\r\nWIFI GOT IP\r\n\r\nOK\r\n")
        resp = self._send_cmd(cmd, timeout=timeout, wait_for="WIFI CONNECTED")
        return "WIFI CONNECTED" in resp or "OK" in resp

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
        for line in resp.split('\n'):
            if 'STAIP' in line and '"' in line:
                try:
                    start = line.index('"') + 1
                    end = line.index('"', start)
                    sta_ip = line[start:end]
                except:
                    pass
            elif 'APIP' in line and '"' in line:
                try:
                    start = line.index('"') + 1
                    end = line.index('"', start)
                    ap_ip = line[start:end]
                except:
                    pass
        return {'station': sta_ip, 'ap': ap_ip}

    def scan(self):
        resp = self._send_cmd("AT+CWLAP", timeout=10000)
        networks = []
        for line in resp.split('\n'):
            if '+CWLAP:' in line:
                try:
                    start = line.index('(') + 1
                    end = line.rindex(')')
                    data = line[start:end]
                    parts = []
                    current = ""
                    in_quotes = False
                    for char in data:
                        if char == '"':
                            in_quotes = not in_quotes
                        elif char == ',' and not in_quotes:
                            parts.append(current)
                            current = ""
                        else:
                            current += char
                    parts.append(current)
                    if len(parts) >= 5:
                        networks.append({
                            'encryption': int(parts[0]),
                            'ssid': parts[1].strip('"'),
                            'rssi': int(parts[2]),
                            'mac': parts[3].strip('"'),
                            'channel': int(parts[4])
                        })
                except:
                    continue
        return networks

    def set_multiple_connections(self, enable=True):
        mode = 1 if enable else 0
        resp = self._send_cmd(f"AT+CIPMUX={mode}")
        return "OK" in resp

    def start_connection(self, link_id, conn_type, remote_ip, remote_port):
        cmd = f'AT+CIPSTART={link_id},"{conn_type}","{remote_ip}",{remote_port}'
        self.uart.set_response(cmd, b"CONNECT\r\n\r\nOK\r\n")
        resp = self._send_cmd(cmd, timeout=10000)
        if "OK" in resp or "ALREADY CONNECTED" in resp:
            self.connections[link_id] = {
                'type': conn_type,
                'ip': remote_ip,
                'port': remote_port
            }
            return True
        return False

    def close(self, link_id):
        self.uart.set_response(f"AT+CIPCLOSE={link_id}", b"CLOSED\r\n\r\nOK\r\n")
        resp = self._send_cmd(f"AT+CIPCLOSE={link_id}")
        if link_id in self.connections:
            del self.connections[link_id]
        return "OK" in resp


@pytest.fixture
def wifi():
    """Provide a testable ESP8285 instance"""
    return ESP8285Testable()


@pytest.fixture
def mock_uart():
    """Provide a mock UART instance"""
    return MockESPUart()


class TestATCommand:
    """Tests for basic AT command functionality"""

    def test_at_command_ok(self, wifi):
        """Test that AT command returns OK"""
        assert wifi.test() is True

    def test_at_command_sends_correct_data(self, wifi):
        """Test that AT command is sent correctly"""
        wifi.test()
        assert wifi.uart.get_last_command() == "AT"


class TestFirmwareVersion:
    """Tests for firmware version retrieval"""

    def test_get_version_contains_at_version(self, wifi):
        """Test that version response contains AT version"""
        version = wifi.get_version()
        assert "AT version" in version

    def test_get_version_contains_sdk_version(self, wifi):
        """Test that version response contains SDK version"""
        version = wifi.get_version()
        assert "SDK version" in version


class TestWiFiMode:
    """Tests for WiFi mode setting"""

    def test_set_station_mode(self, wifi):
        """Test setting station mode"""
        assert wifi.set_mode(ESP8285Testable.MODE_STATION) is True
        assert wifi.uart.get_last_command() == "AT+CWMODE=1"

    def test_set_ap_mode(self, wifi):
        """Test setting AP mode"""
        assert wifi.set_mode(ESP8285Testable.MODE_AP) is True
        assert wifi.uart.get_last_command() == "AT+CWMODE=2"

    def test_set_both_mode(self, wifi):
        """Test setting station+AP mode"""
        assert wifi.set_mode(ESP8285Testable.MODE_BOTH) is True
        assert wifi.uart.get_last_command() == "AT+CWMODE=3"


class TestWiFiConnection:
    """Tests for WiFi connection"""

    def test_connect_success(self, wifi):
        """Test successful WiFi connection"""
        assert wifi.connect("TestSSID", "TestPassword") is True

    def test_connect_sends_correct_command(self, wifi):
        """Test that connect sends correct AT command"""
        wifi.connect("MyNetwork", "MyPassword")
        # The last command should be the CWJAP command
        commands = [cmd.decode().strip() for cmd in wifi.uart.tx_buffer]
        assert any('AT+CWJAP="MyNetwork","MyPassword"' in cmd for cmd in commands)

    def test_disconnect_success(self, wifi):
        """Test successful WiFi disconnection"""
        assert wifi.disconnect() is True
        assert wifi.uart.get_last_command() == "AT+CWQAP"

    def test_is_connected_true(self, wifi):
        """Test is_connected returns True when connected"""
        assert wifi.is_connected() is True

    def test_is_connected_false_when_no_ap(self, wifi):
        """Test is_connected returns False when no AP"""
        wifi.uart.set_response("AT+CWJAP?", b"No AP\r\n\r\nOK\r\n")
        wifi.uart.clear()
        assert wifi.is_connected() is False


class TestIPAddress:
    """Tests for IP address retrieval"""

    def test_get_station_ip(self, wifi):
        """Test getting station IP address"""
        ip_info = wifi.get_ip()
        assert ip_info['station'] == "192.168.1.100"

    def test_get_ip_returns_dict(self, wifi):
        """Test that get_ip returns a dictionary"""
        ip_info = wifi.get_ip()
        assert isinstance(ip_info, dict)
        assert 'station' in ip_info
        assert 'ap' in ip_info


class TestNetworkScan:
    """Tests for network scanning"""

    def test_scan_returns_list(self, wifi):
        """Test that scan returns a list"""
        networks = wifi.scan()
        assert isinstance(networks, list)

    def test_scan_finds_networks(self, wifi):
        """Test that scan finds networks"""
        networks = wifi.scan()
        assert len(networks) == 2

    def test_scan_network_has_required_fields(self, wifi):
        """Test that scanned networks have required fields"""
        networks = wifi.scan()
        assert len(networks) > 0

        network = networks[0]
        assert 'ssid' in network
        assert 'rssi' in network
        assert 'channel' in network
        assert 'encryption' in network

    def test_scan_parses_ssid_correctly(self, wifi):
        """Test that SSID is parsed correctly"""
        networks = wifi.scan()
        ssids = [n['ssid'] for n in networks]
        assert "Network1" in ssids
        assert "Network2" in ssids


class TestMultipleConnections:
    """Tests for multiple connections mode"""

    def test_enable_multiple_connections(self, wifi):
        """Test enabling multiple connections"""
        assert wifi.set_multiple_connections(True) is True
        assert wifi.uart.get_last_command() == "AT+CIPMUX=1"

    def test_disable_multiple_connections(self, wifi):
        """Test disabling multiple connections"""
        assert wifi.set_multiple_connections(False) is True
        assert wifi.uart.get_last_command() == "AT+CIPMUX=0"


class TestTCPConnection:
    """Tests for TCP connection management"""

    def test_start_tcp_connection(self, wifi):
        """Test starting a TCP connection"""
        result = wifi.start_connection(0, "TCP", "192.168.1.1", 80)
        assert result is True
        assert 0 in wifi.connections

    def test_connection_stored_correctly(self, wifi):
        """Test that connection info is stored correctly"""
        wifi.start_connection(1, "TCP", "10.0.0.1", 8080)

        assert wifi.connections[1]['type'] == "TCP"
        assert wifi.connections[1]['ip'] == "10.0.0.1"
        assert wifi.connections[1]['port'] == 8080

    def test_close_connection(self, wifi):
        """Test closing a connection"""
        wifi.start_connection(0, "TCP", "192.168.1.1", 80)
        assert 0 in wifi.connections

        result = wifi.close(0)
        assert result is True
        assert 0 not in wifi.connections


class TestCommandFormat:
    """Tests for AT command formatting"""

    def test_commands_end_with_crlf(self, wifi):
        """Test that commands are sent with CRLF"""
        wifi.test()
        raw_data = wifi.uart.tx_buffer[0]
        assert raw_data.endswith(b"\r\n")

    def test_connect_command_format(self, wifi):
        """Test WiFi connect command format"""
        wifi.connect("Test SSID", "Test Pass")
        commands = b"".join(wifi.uart.tx_buffer).decode()
        assert 'AT+CWJAP="Test SSID","Test Pass"' in commands


class MockESPUartWithSend(MockESPUart):
    """Mock UART that simulates ESP8285 AT command responses including CIPSEND"""

    def __init__(self):
        super().__init__()
        self.send_data_buffer = []
        self.waiting_for_data = False
        self.expected_data_len = 0

    def write(self, data):
        """Simulate writing to UART"""
        if isinstance(data, str):
            data = data.encode()

        # If we're waiting for data after AT+CIPSEND
        if self.waiting_for_data:
            self.send_data_buffer.append(data)
            self.waiting_for_data = False
            self.rx_buffer += b"SEND OK\r\n"
            return len(data)

        self.tx_buffer.append(data)
        cmd_str = data.decode().strip()

        # Handle AT+CIPSEND command
        if cmd_str.startswith("AT+CIPSEND="):
            # Parse: AT+CIPSEND=link_id,length
            parts = cmd_str.split("=")[1].split(",")
            self.expected_data_len = int(parts[1])
            self.waiting_for_data = True
            self.rx_buffer += b"AT+CIPSEND\r\n\r\n>"
            return len(data)

        # Handle other commands
        for pattern, response in self.responses.items():
            if cmd_str == pattern or cmd_str.startswith(pattern.split("=")[0] + "="):
                self.rx_buffer += response
                return len(data)

        self.rx_buffer += b"ERROR\r\n"
        return len(data)


class ESP8285TestableWithSend(ESP8285Testable):
    """ESP8285 class with send() method for testing chunked sends"""

    CHUNK_SIZE = 1024  # Same as in real implementation

    def __init__(self, mock_uart=None):
        super().__init__(mock_uart)
        self.uart = mock_uart or MockESPUartWithSend()

    def send(self, link_id, data):
        """Send data with chunking (mirrors real implementation)"""
        if isinstance(data, str):
            data = data.encode('utf-8')

        offset = 0
        total = len(data)

        while offset < total:
            chunk = data[offset:offset + self.CHUNK_SIZE]
            chunk_len = len(chunk)

            cmd = f"AT+CIPSEND={link_id},{chunk_len}"
            resp = self._send_cmd(cmd, timeout=1000, wait_for=">")
            if ">" not in resp:
                return False

            self.uart.write(chunk)
            start = std_time.time() * 1000
            response = b""
            success = False
            while (std_time.time() * 1000 - start) < 5000:
                if self.uart.any():
                    chunk_resp = self.uart.read()
                    if chunk_resp:
                        response += chunk_resp
                    resp_str = response.decode('utf-8', 'ignore')
                    if "SEND OK" in resp_str:
                        success = True
                        break
                    if "SEND FAIL" in resp_str or "ERROR" in resp_str:
                        return False
                std_time.sleep(0.001)

            if not success:
                return False

            offset += chunk_len

        return True


@pytest.fixture
def wifi_with_send():
    """Provide a testable ESP8285 instance with send capability"""
    return ESP8285TestableWithSend()


class TestSendChunking:
    """Tests for send() with chunking for large payloads"""

    def test_send_small_data_single_chunk(self, wifi_with_send):
        """Test that small data is sent in a single chunk"""
        data = b"Hello World"  # 11 bytes, well under 1024
        result = wifi_with_send.send(0, data)
        assert result is True
        # Should have one CIPSEND command
        cipsend_cmds = [cmd for cmd in wifi_with_send.uart.tx_buffer
                        if b"AT+CIPSEND" in cmd]
        assert len(cipsend_cmds) == 1
        assert b"AT+CIPSEND=0,11" in cipsend_cmds[0]

    def test_send_exact_chunk_size(self, wifi_with_send):
        """Test sending data exactly equal to chunk size"""
        data = b"X" * 1024  # Exactly 1024 bytes
        result = wifi_with_send.send(0, data)
        assert result is True
        cipsend_cmds = [cmd for cmd in wifi_with_send.uart.tx_buffer
                        if b"AT+CIPSEND" in cmd]
        assert len(cipsend_cmds) == 1

    def test_send_large_data_multiple_chunks(self, wifi_with_send):
        """Test that large data is split into multiple chunks"""
        data = b"X" * 2500  # 2500 bytes = 3 chunks (1024 + 1024 + 452)
        result = wifi_with_send.send(0, data)
        assert result is True
        cipsend_cmds = [cmd for cmd in wifi_with_send.uart.tx_buffer
                        if b"AT+CIPSEND" in cmd]
        assert len(cipsend_cmds) == 3
        # Verify chunk sizes
        assert b"AT+CIPSEND=0,1024" in cipsend_cmds[0]
        assert b"AT+CIPSEND=0,1024" in cipsend_cmds[1]
        assert b"AT+CIPSEND=0,452" in cipsend_cmds[2]

    def test_send_data_integrity(self, wifi_with_send):
        """Test that all data chunks are sent correctly"""
        data = b"ABCD" * 500  # 2000 bytes
        result = wifi_with_send.send(0, data)
        assert result is True
        # Verify data was sent
        sent_data = b"".join(wifi_with_send.uart.send_data_buffer)
        assert sent_data == data

    def test_send_string_converted_to_bytes(self, wifi_with_send):
        """Test that string data is converted to bytes"""
        data = "Hello World"
        result = wifi_with_send.send(0, data)
        assert result is True
        assert wifi_with_send.uart.send_data_buffer[0] == b"Hello World"

    def test_send_large_json_response(self, wifi_with_send):
        """Test sending a typical large JSON response (like /schedules)"""
        # Simulate a schedules response with multiple entries
        import json
        schedules = {
            "date": "2026-03-19",
            "schedules": [
                {"index": i, "hour": i % 24, "minute": 0, "enabled": True,
                 "command": {"type": "status"},
                 "executed": {"time": f"{i:02d}:00", "success": True,
                              "output": {"T_vmc": "21.5", "T_hp": "45.0"}}}
                for i in range(20)  # 20 schedules to make it large
            ]
        }
        data = json.dumps(schedules)
        # This should be > 2KB
        assert len(data) > 2000

        result = wifi_with_send.send(0, data)
        assert result is True

        # Verify chunking happened
        cipsend_cmds = [cmd for cmd in wifi_with_send.uart.tx_buffer
                        if b"AT+CIPSEND" in cmd]
        assert len(cipsend_cmds) >= 2  # Should need multiple chunks
