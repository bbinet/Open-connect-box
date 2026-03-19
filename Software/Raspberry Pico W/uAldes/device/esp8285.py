"""
ESP8285 - WiFi library for RP2040 with ESP8285 using AT commands

This library provides WiFi connectivity for Pico W clones that use
ESP8285 chip for WiFi instead of the CYW43439 on genuine Pico W.

Based on: https://github.com/asifneon13/espicoW
License: MIT
"""

from machine import UART, Pin
import time


class ESP8285:
    """WiFi library for RP2040 with ESP8285 using AT commands"""

    MODE_STATION = 1
    MODE_AP = 2
    MODE_BOTH = 3

    TYPE_TCP = "TCP"
    TYPE_UDP = "UDP"
    TYPE_SSL = "SSL"

    def __init__(self, uart_id=0, tx_pin=0, rx_pin=1, baudrate=115200, debug=False):
        # Use larger RX buffer for handling POST data
        self.uart = UART(uart_id, baudrate=baudrate, tx=Pin(tx_pin), rx=Pin(rx_pin), rxbuf=4096)
        self.debug = debug
        self.timeout = 5000
        self.connections = {}

    def _send_cmd(self, cmd, timeout=None, wait_for="OK"):
        if timeout is None:
            timeout = self.timeout
        if self.debug:
            print(f"[TX] {cmd}")
        self.uart.write(cmd + "\r\n")
        start = time.ticks_ms()
        response = b""
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.uart.any():
                chunk = self.uart.read()
                if chunk:
                    response += chunk
                try:
                    resp_str = response.decode('utf-8', 'ignore')
                    if wait_for in resp_str or "ERROR" in resp_str or "FAIL" in resp_str:
                        if self.debug:
                            print(f"[RX] {resp_str}")
                        return resp_str
                except:
                    pass
            time.sleep_ms(10)
        try:
            resp_str = response.decode('utf-8', 'ignore')
        except:
            resp_str = str(response)
        if self.debug:
            print(f"[RX] Timeout: {resp_str}")
        return resp_str

    def reset(self):
        resp = self._send_cmd("AT+RST", timeout=3000, wait_for="ready")
        time.sleep(2)
        while self.uart.any():
            self.uart.read()
        time.sleep_ms(500)
        return self.test()

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
        time.sleep_ms(100)
        cmd = f'AT+CWJAP="{ssid}","{password}"'
        resp = self._send_cmd(cmd, timeout=timeout, wait_for="WIFI CONNECTED")
        if "WIFI CONNECTED" in resp or "OK" in resp:
            time.sleep(1)
            return True
        return False

    def disconnect(self):
        resp = self._send_cmd("AT+CWQAP")
        return "OK" in resp

    def is_connected(self):
        resp = self._send_cmd("AT+CWJAP?", timeout=2000)
        # Positive response: +CWJAP:"SSID","mac",channel,rssi
        # Negative response: "No AP", empty, timeout, or error
        return "+CWJAP:" in resp

    def get_ip(self):
        resp = self._send_cmd("AT+CIFSR", timeout=2000)
        sta_ip = None
        ap_ip = None
        lines = resp.split('\n')
        for line in lines:
            if 'STAIP' in line or 'STIP' in line:
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

    def scan(self):
        resp = self._send_cmd("AT+CWLAP", timeout=10000)
        networks = []
        lines = resp.split('\n')
        for line in lines:
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

    def create_ap(self, ssid, password, channel=1, encryption=3):
        self.set_mode(self.MODE_AP)
        time.sleep_ms(100)
        cmd = f'AT+CWSAP="{ssid}","{password}",{channel},{encryption}'
        resp = self._send_cmd(cmd, timeout=3000)
        return "OK" in resp

    def set_multiple_connections(self, enable=True):
        mode = 1 if enable else 0
        resp = self._send_cmd(f"AT+CIPMUX={mode}")
        return "OK" in resp

    def start_connection(self, link_id, conn_type, remote_ip, remote_port, local_port=0):
        if conn_type == self.TYPE_UDP and local_port > 0:
            cmd = f'AT+CIPSTART={link_id},"{conn_type}","{remote_ip}",{remote_port},{local_port}'
        else:
            cmd = f'AT+CIPSTART={link_id},"{conn_type}","{remote_ip}",{remote_port}'
        resp = self._send_cmd(cmd, timeout=10000)
        if "OK" in resp or "ALREADY CONNECTED" in resp:
            self.connections[link_id] = {
                'type': conn_type,
                'ip': remote_ip,
                'port': remote_port
            }
            return True
        return False

    def send(self, link_id, data):
        if isinstance(data, str):
            data = data.encode('utf-8')

        # ESP8285 has a limit on data size per send (typically 2048 bytes)
        # Split large data into chunks
        CHUNK_SIZE = 1024
        offset = 0
        total = len(data)

        while offset < total:
            chunk = data[offset:offset + CHUNK_SIZE]
            chunk_len = len(chunk)

            cmd = f"AT+CIPSEND={link_id},{chunk_len}"
            resp = self._send_cmd(cmd, timeout=1000, wait_for=">")
            if ">" not in resp:
                return False

            self.uart.write(chunk)
            start = time.ticks_ms()
            response = b""
            success = False
            while time.ticks_diff(time.ticks_ms(), start) < 5000:
                if self.uart.any():
                    response += self.uart.read()
                    resp_str = response.decode('utf-8', 'ignore')
                    if "SEND OK" in resp_str:
                        success = True
                        break
                    if "SEND FAIL" in resp_str or "ERROR" in resp_str:
                        return False
                time.sleep_ms(10)

            if not success:
                return False

            offset += chunk_len
            # Small delay between chunks to let ESP8285 process
            if offset < total:
                time.sleep_ms(50)

        return True

    def receive(self, timeout=5000):
        start = time.ticks_ms()
        response = b""
        received = []
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.uart.any():
                response += self.uart.read()
                try:
                    resp_str = response.decode('utf-8', 'ignore')
                    idx = 0
                    while True:
                        ipd_pos = resp_str.find('+IPD,', idx)
                        if ipd_pos == -1:
                            break
                        try:
                            comma1 = resp_str.index(',', ipd_pos)
                            comma2 = resp_str.index(',', comma1 + 1)
                            colon = resp_str.index(':', comma2)
                            link_id = int(resp_str[comma1+1:comma2])
                            length = int(resp_str[comma2+1:colon])
                            data_start = colon + 1
                            data = resp_str[data_start:data_start+length]
                            received.append((link_id, data))
                            idx = data_start + length
                        except:
                            break
                except:
                    pass
                if received:
                    return received
            time.sleep_ms(10)
        return received

    def close(self, link_id):
        resp = self._send_cmd(f"AT+CIPCLOSE={link_id}")
        if link_id in self.connections:
            del self.connections[link_id]
        return "OK" in resp

    def close_all(self):
        for link_id in list(self.connections.keys()):
            self.close(link_id)

    def http_get(self, url, timeout=10000):
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            return None
        parts = url.split('/', 1)
        host = parts[0]
        path = '/' + parts[1] if len(parts) > 1 else '/'
        self.set_multiple_connections(False)
        time.sleep_ms(100)
        cmd = f'AT+CIPSTART="TCP","{host}",80'
        resp = self._send_cmd(cmd, timeout=10000)
        if "OK" not in resp and "ALREADY CONNECTED" not in resp:
            return None
        request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        length = len(request)
        cmd = f"AT+CIPSEND={length}"
        resp = self._send_cmd(cmd, timeout=1000, wait_for=">")
        if ">" not in resp:
            return None
        self.uart.write(request)
        start = time.ticks_ms()
        response = b""
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.uart.any():
                response += self.uart.read()
            resp_str = response.decode('utf-8', 'ignore')
            if "CLOSED" in resp_str:
                break
            time.sleep_ms(10)
        resp_str = response.decode('utf-8', 'ignore')
        if '\r\n\r\n' in resp_str:
            return resp_str.split('\r\n\r\n', 1)[1]
        return resp_str

    def ping(self, host):
        resp = self._send_cmd(f'AT+PING="{host}"', timeout=5000)
        if self.debug:
            print(f"PING {host} response: {repr(resp)}")
        if '+' in resp:
            try:
                lines = resp.split('\n')
                for line in lines:
                    if line.strip().startswith('+'):
                        num_str = line.strip()[1:].split()[0]
                        return int(num_str)
            except:
                pass
        return None

    def get_connection_status(self):
        resp = self._send_cmd("AT+CIPSTATUS")
        statuses = []
        lines = resp.split('\n')
        for line in lines:
            if '+CIPSTATUS:' in line:
                try:
                    start = line.index(':') + 1
                    parts = []
                    current = ""
                    in_quotes = False
                    for char in line[start:]:
                        if char == '"':
                            in_quotes = not in_quotes
                        elif char == ',' and not in_quotes:
                            parts.append(current)
                            current = ""
                        else:
                            current += char
                    parts.append(current)
                    if len(parts) >= 6:
                        statuses.append({
                            'link_id': int(parts[0]),
                            'type': parts[1].strip('"'),
                            'remote_ip': parts[2].strip('"'),
                            'remote_port': int(parts[3]),
                            'local_port': int(parts[4]),
                            'tetype': int(parts[5])
                        })
                except:
                    continue
        return statuses

    def set_sleep_mode(self, mode):
        resp = self._send_cmd(f"AT+SLEEP={mode}")
        return "OK" in resp

    def enable_dhcp(self, mode, enable=True):
        en = 1 if enable else 0
        resp = self._send_cmd(f"AT+CWDHCP={mode},{en}")
        return "OK" in resp

    def start_server(self, port=80):
        """Start TCP server on specified port"""
        self.set_multiple_connections(True)
        time.sleep_ms(100)
        resp = self._send_cmd(f"AT+CIPSERVER=1,{port}", timeout=3000)
        return "OK" in resp

    def stop_server(self):
        """Stop TCP server"""
        resp = self._send_cmd("AT+CIPSERVER=0", timeout=2000)
        return "OK" in resp

    def check_incoming(self, timeout=300):
        """Check for incoming data from clients
        Returns list of (link_id, data) tuples or empty list
        Special data values: None means connection closed
        """
        start = time.ticks_ms()
        response = b""
        received = []

        # First check if there's any data available
        if not self.uart.any():
            return received

        # Small delay to let more data arrive
        time.sleep_ms(20)

        # Read initial data
        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self.uart.any():
                response += self.uart.read()
            # Check if we have +IPD header
            if b'+IPD,' in response:
                try:
                    resp_str = response.decode('utf-8', 'ignore')
                    ipd_pos = resp_str.find('+IPD,')
                    comma1 = resp_str.index(',', ipd_pos)
                    comma2 = resp_str.index(',', comma1 + 1)
                    colon = resp_str.index(':', comma2)
                    expected_len = int(resp_str[comma2+1:colon])
                    data_start = colon + 1
                    # Wait until we have all expected data
                    if len(resp_str) >= data_start + expected_len:
                        break
                except:
                    pass
            time.sleep_ms(10)

        # Final read to catch any remaining data
        time.sleep_ms(50)
        while self.uart.any():
            response += self.uart.read()
            time.sleep_ms(10)

        if not response:
            return received

        try:
            resp_str = response.decode('utf-8', 'ignore')

            # Parse closed connections (e.g., "0,CLOSED" or "1,CLOSED")
            for line in resp_str.split('\r\n'):
                if ',CLOSED' in line:
                    try:
                        link_id = int(line.split(',')[0])
                        received.append((link_id, None))  # None means closed
                    except:
                        pass

            # Parse incoming data
            idx = 0
            while True:
                ipd_pos = resp_str.find('+IPD,', idx)
                if ipd_pos == -1:
                    break
                try:
                    comma1 = resp_str.index(',', ipd_pos)
                    comma2 = resp_str.index(',', comma1 + 1)
                    colon = resp_str.index(':', comma2)
                    link_id = int(resp_str[comma1+1:comma2])
                    length = int(resp_str[comma2+1:colon])
                    data_start = colon + 1
                    data = resp_str[data_start:data_start+length]
                    received.append((link_id, data))
                    idx = data_start + length
                except:
                    break
        except:
            pass

        return received

    def send_response(self, link_id, data):
        """Send response to client and close connection"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        result = self.send(link_id, data)
        time.sleep_ms(100)  # Wait for data to be sent
        self.close(link_id)
        time.sleep_ms(50)   # Wait for close to complete
        # Clear any pending data in UART buffer
        while self.uart.any():
            self.uart.read()
        return result

    def clear_buffer(self):
        """Clear UART receive buffer"""
        while self.uart.any():
            self.uart.read()

    def configure_sntp(self, timezone_offset=0, server="pool.ntp.org"):
        """Configure SNTP time synchronization

        Args:
            timezone_offset: Hours offset from UTC (e.g., 1 for CET, 2 for CEST)
            server: NTP server address

        Returns:
            True if configuration successful
        """
        # AT+CIPSNTPCFG=<enable>,<timezone>,<server>
        cmd = f'AT+CIPSNTPCFG=1,{timezone_offset},"{server}"'
        resp = self._send_cmd(cmd, timeout=3000)
        return "OK" in resp

    def get_sntp_time(self):
        """Get current time from SNTP

        Returns:
            Tuple (year, month, day, hour, minute, second) or None if failed
        """
        resp = self._send_cmd("AT+CIPSNTPTIME?", timeout=3000)
        # Response format: +CIPSNTPTIME:Thu Jan 01 00:00:00 1970
        # Or newer format: +CIPSNTPTIME:Mon Mar 13 21:30:00 2026
        if "+CIPSNTPTIME:" in resp:
            try:
                # Extract time string after +CIPSNTPTIME:
                time_str = resp.split("+CIPSNTPTIME:")[1].split("\r")[0].strip()
                # Parse: "Mon Mar 13 21:30:00 2026"
                parts = time_str.split()
                if len(parts) >= 5:
                    months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                              "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
                    month = months.get(parts[1], 1)
                    day = int(parts[2])
                    time_parts = parts[3].split(":")
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2])
                    year = int(parts[4])
                    return (year, month, day, hour, minute, second)
            except Exception as e:
                if self.debug:
                    print(f"SNTP parse error: {e}")
        return None
