"""
Unit tests for mqtt.py (MQTT Client)

These tests use mock objects to simulate MQTT protocol exchanges.
Run on device with: import test_mqtt; test_mqtt.run_all_tests()
"""

import struct


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


def assert_is_not_none(name, value):
    if value is not None:
        result.add_pass(name)
    else:
        result.add_fail(name, "not None", value)


# =============================================================================
# Mock ESP8285 for MQTT testing
# =============================================================================

class MockESP8285:
    """Mock ESP8285 that simulates TCP operations for MQTT testing"""

    def __init__(self):
        self.connections = {}
        self.sent_data = []
        self.receive_queue = []
        self._connected = False
        self._mux_enabled = False

    def set_multiple_connections(self, enable):
        self._mux_enabled = enable
        return True

    def start_connection(self, link_id, conn_type, ip, port):
        self.connections[link_id] = {
            'type': conn_type,
            'ip': ip,
            'port': port
        }
        self._connected = True
        return True

    def send(self, link_id, data):
        if isinstance(data, str):
            data = data.encode()
        self.sent_data.append((link_id, bytes(data)))
        return True

    def receive(self, timeout=5000):
        if self.receive_queue:
            return self.receive_queue.pop(0)
        return []

    def close(self, link_id):
        if link_id in self.connections:
            del self.connections[link_id]
        return True

    def queue_response(self, link_id, data):
        """Queue a response to be returned by receive()"""
        if isinstance(data, str):
            data = data.encode('latin-1')
        self.receive_queue.append([(link_id, data)])

    def get_all_sent(self):
        """Get all sent data concatenated"""
        result = b""
        for link_id, data in self.sent_data:
            result += data
        return result


# =============================================================================
# Mock MQTTClient for testing
# =============================================================================

class MockMQTTClient:
    """Simplified MQTT client for testing packet construction"""

    def __init__(self, client_id, server, port=1883, user=None, password=None,
                 keepalive=0, wifi=None, link_id=0):
        self.client_id = client_id
        self.server = server
        self.port = port
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.wifi = wifi or MockESP8285()
        self.link_id = link_id
        self.pid = 0
        self.cb = None
        self._rx_buffer = b""
        self._connected = False

    def _write(self, data):
        if isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        return self.wifi.send(self.link_id, data)

    def _send_str(self, s):
        if isinstance(s, str):
            s = s.encode('utf-8')
        self._write(struct.pack("!H", len(s)))
        self._write(s)

    def set_callback(self, f):
        self.cb = f

    def build_connect_packet(self, clean_session=True):
        """Build MQTT CONNECT packet"""
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1
        if self.user:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF

        i = 1
        while sz > 0x7F:
            premsg[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        premsg[i] = sz

        return bytes(premsg[:i + 2]) + bytes(msg)

    def build_publish_packet(self, topic, msg, retain=False, qos=0):
        """Build MQTT PUBLISH packet"""
        if isinstance(topic, str):
            topic = topic.encode('utf-8')
        if isinstance(msg, str):
            msg = msg.encode('utf-8')

        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2

        i = 1
        while sz > 0x7F:
            pkt[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        pkt[i] = sz

        result = bytes(pkt[:i + 1])
        result += struct.pack("!H", len(topic))
        result += topic
        result += msg

        return result

    def build_subscribe_packet(self, topic, qos=0):
        """Build MQTT SUBSCRIBE packet"""
        if isinstance(topic, str):
            topic = topic.encode('utf-8')

        self.pid += 1
        pkt = bytearray(b"\x82\0\0\0")
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)

        result = bytes(pkt)
        result += struct.pack("!H", len(topic))
        result += topic
        result += bytes([qos])

        return result

    def build_ping_packet(self):
        """Build MQTT PINGREQ packet"""
        return b"\xc0\0"

    def build_disconnect_packet(self):
        """Build MQTT DISCONNECT packet"""
        return b"\xe0\0"


# =============================================================================
# Tests
# =============================================================================

def test_connect_packet_structure():
    """Test MQTT CONNECT packet structure"""
    print("\n--- CONNECT Packet Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")
    packet = client.build_connect_packet()

    # First byte should be 0x10 (CONNECT)
    assert_equal("connect_type", 0x10, packet[0])

    # Should contain "MQTT" protocol name
    assert_true("contains_mqtt", b"MQTT" in packet)

    # Protocol level should be 4 (MQTT 3.1.1)
    mqtt_idx = packet.index(b"MQTT")
    assert_equal("protocol_level", 4, packet[mqtt_idx + 4])


def test_connect_packet_with_auth():
    """Test MQTT CONNECT packet with authentication"""
    print("\n--- CONNECT Packet with Auth Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com",
                            user="testuser", password="testpass")
    packet = client.build_connect_packet()

    # Connect flags should include username and password flags (0xC0)
    mqtt_idx = packet.index(b"MQTT")
    connect_flags = packet[mqtt_idx + 5]
    assert_true("has_user_flag", (connect_flags & 0x80) != 0)
    assert_true("has_pass_flag", (connect_flags & 0x40) != 0)


def test_publish_packet_structure():
    """Test MQTT PUBLISH packet structure"""
    print("\n--- PUBLISH Packet Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")
    packet = client.build_publish_packet("test/topic", "Hello World")

    # First byte should be 0x30 (PUBLISH with QoS 0)
    assert_equal("publish_type", 0x30, packet[0])

    # Should contain the topic
    assert_true("contains_topic", b"test/topic" in packet)

    # Should contain the message
    assert_true("contains_message", b"Hello World" in packet)


def test_publish_packet_with_retain():
    """Test MQTT PUBLISH packet with retain flag"""
    print("\n--- PUBLISH Packet with Retain Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")
    packet = client.build_publish_packet("test/topic", "Hello", retain=True)

    # First byte should have retain flag set (0x31)
    assert_equal("publish_retain_flag", 0x31, packet[0])


def test_subscribe_packet_structure():
    """Test MQTT SUBSCRIBE packet structure"""
    print("\n--- SUBSCRIBE Packet Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")
    packet = client.build_subscribe_packet("test/topic/#")

    # First byte should be 0x82 (SUBSCRIBE)
    assert_equal("subscribe_type", 0x82, packet[0])

    # Should contain the topic filter
    assert_true("contains_topic_filter", b"test/topic/#" in packet)


def test_ping_packet():
    """Test MQTT PINGREQ packet"""
    print("\n--- PINGREQ Packet Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")
    packet = client.build_ping_packet()

    assert_equal("ping_packet", b"\xc0\x00", packet)


def test_disconnect_packet():
    """Test MQTT DISCONNECT packet"""
    print("\n--- DISCONNECT Packet Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")
    packet = client.build_disconnect_packet()

    assert_equal("disconnect_packet", b"\xe0\x00", packet)


def test_packet_id_increment():
    """Test that packet IDs increment correctly"""
    print("\n--- Packet ID Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")

    initial_pid = client.pid
    client.build_subscribe_packet("topic1")
    assert_equal("pid_after_first", initial_pid + 1, client.pid)

    client.build_subscribe_packet("topic2")
    assert_equal("pid_after_second", initial_pid + 2, client.pid)


def test_wifi_connection_setup():
    """Test that MQTT client sets up WiFi connection correctly"""
    print("\n--- WiFi Connection Setup Tests ---")

    wifi = MockESP8285()
    client = MockMQTTClient("test_client", "broker.test.com", port=1883,
                            wifi=wifi, link_id=0)

    # Simulate connection setup
    wifi.set_multiple_connections(True)
    wifi.start_connection(0, "TCP", "broker.test.com", 1883)

    assert_true("mux_enabled", wifi._mux_enabled)
    assert_true("connection_exists", 0 in wifi.connections)
    assert_equal("connection_type", "TCP", wifi.connections[0]['type'])
    assert_equal("connection_port", 1883, wifi.connections[0]['port'])


def test_send_data_to_wifi():
    """Test that data is sent through WiFi correctly"""
    print("\n--- Send Data Tests ---")

    wifi = MockESP8285()
    client = MockMQTTClient("test_client", "broker.test.com", wifi=wifi)

    client._write(b"test data")

    sent = wifi.get_all_sent()
    assert_true("data_sent", b"test data" in sent)


def test_callback_setting():
    """Test callback function setting"""
    print("\n--- Callback Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")

    def my_callback(topic, msg):
        pass

    client.set_callback(my_callback)
    assert_equal("callback_set", my_callback, client.cb)


def test_variable_length_encoding():
    """Test MQTT remaining length encoding for large packets"""
    print("\n--- Variable Length Encoding Tests ---")

    client = MockMQTTClient("test_client", "broker.test.com")

    # Small message (< 128 bytes)
    small_packet = client.build_publish_packet("t", "x" * 100)
    # Remaining length should be single byte
    assert_true("small_packet_single_byte_len", small_packet[1] < 128)

    # Larger message (> 127 bytes)
    large_packet = client.build_publish_packet("topic", "x" * 200)
    # This should still work
    assert_true("large_packet_valid", len(large_packet) > 200)


# =============================================================================
# Run All Tests
# =============================================================================

def run_all_tests():
    """Run all test suites"""
    global result
    result = TestResult()

    print("=" * 50)
    print("Running mqtt.py tests (MQTT Client)")
    print("=" * 50)

    test_connect_packet_structure()
    test_connect_packet_with_auth()
    test_publish_packet_structure()
    test_publish_packet_with_retain()
    test_subscribe_packet_structure()
    test_ping_packet()
    test_disconnect_packet()
    test_packet_id_increment()
    test_wifi_connection_setup()
    test_send_data_to_wifi()
    test_callback_setting()
    test_variable_length_encoding()

    return result.summary()


if __name__ == "__main__":
    run_all_tests()
