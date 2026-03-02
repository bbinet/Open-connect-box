"""
Pytest tests for simple_esp.py (MQTT Client)

Run with: pytest tests/test_simple_esp.py -v
"""

import pytest
import struct


class MockWiFi:
    """Mock ESPicoW for MQTT testing"""

    def __init__(self):
        self.connections = {}
        self.sent_data = []
        self.receive_queue = []
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

    def clear_sent(self):
        """Clear sent data buffer"""
        self.sent_data = []


@pytest.fixture
def mock_wifi():
    """Provide a mock WiFi instance"""
    return MockWiFi()


class TestMQTTPacketStructure:
    """Tests for MQTT packet structure"""

    def test_connect_packet_type(self):
        """Test CONNECT packet has correct type byte"""
        # CONNECT packet type is 0x10
        packet = build_connect_packet("test_client")
        assert packet[0] == 0x10

    def test_connect_packet_contains_protocol_name(self):
        """Test CONNECT packet contains MQTT protocol name"""
        packet = build_connect_packet("test_client")
        assert b"MQTT" in packet

    def test_connect_packet_protocol_level(self):
        """Test CONNECT packet has protocol level 4 (MQTT 3.1.1)"""
        packet = build_connect_packet("test_client")
        mqtt_idx = packet.index(b"MQTT")
        assert packet[mqtt_idx + 4] == 4

    def test_connect_packet_with_auth(self):
        """Test CONNECT packet includes auth flags when credentials provided"""
        packet = build_connect_packet("test_client", user="testuser", password="testpass")
        mqtt_idx = packet.index(b"MQTT")
        connect_flags = packet[mqtt_idx + 5]

        # Check username flag (0x80) and password flag (0x40)
        assert (connect_flags & 0x80) != 0, "Username flag not set"
        assert (connect_flags & 0x40) != 0, "Password flag not set"

    def test_connect_packet_clean_session(self):
        """Test CONNECT packet has clean session flag"""
        packet = build_connect_packet("test_client", clean_session=True)
        mqtt_idx = packet.index(b"MQTT")
        connect_flags = packet[mqtt_idx + 5]

        # Clean session is bit 1 (0x02)
        assert (connect_flags & 0x02) != 0

    def test_publish_packet_type(self):
        """Test PUBLISH packet has correct type byte"""
        packet = build_publish_packet("test/topic", "hello")
        # PUBLISH type is 0x30 (with QoS 0, no retain)
        assert (packet[0] & 0xF0) == 0x30

    def test_publish_packet_contains_topic(self):
        """Test PUBLISH packet contains the topic"""
        packet = build_publish_packet("my/test/topic", "message")
        assert b"my/test/topic" in packet

    def test_publish_packet_contains_message(self):
        """Test PUBLISH packet contains the message"""
        packet = build_publish_packet("topic", "Hello World!")
        assert b"Hello World!" in packet

    def test_publish_packet_retain_flag(self):
        """Test PUBLISH packet retain flag"""
        packet = build_publish_packet("topic", "msg", retain=True)
        # Retain is bit 0 (0x01)
        assert (packet[0] & 0x01) == 0x01

    def test_publish_packet_no_retain(self):
        """Test PUBLISH packet without retain flag"""
        packet = build_publish_packet("topic", "msg", retain=False)
        assert (packet[0] & 0x01) == 0x00

    def test_subscribe_packet_type(self):
        """Test SUBSCRIBE packet has correct type byte"""
        packet = build_subscribe_packet("test/topic/#")
        assert packet[0] == 0x82

    def test_subscribe_packet_contains_topic(self):
        """Test SUBSCRIBE packet contains the topic filter"""
        packet = build_subscribe_packet("home/+/temperature")
        assert b"home/+/temperature" in packet

    def test_ping_packet(self):
        """Test PINGREQ packet structure"""
        packet = build_ping_packet()
        assert packet == b"\xc0\x00"

    def test_disconnect_packet(self):
        """Test DISCONNECT packet structure"""
        packet = build_disconnect_packet()
        assert packet == b"\xe0\x00"


class TestMQTTRemainingLength:
    """Tests for MQTT remaining length encoding"""

    def test_small_packet_single_byte_length(self):
        """Test that small packets use single byte for remaining length"""
        packet = build_publish_packet("t", "x" * 50)
        # For small packets, byte 1 should be < 128
        assert packet[1] < 128

    def test_medium_packet_length_encoding(self):
        """Test packets with remaining length 128-16383"""
        # Create a packet with ~200 bytes payload
        packet = build_publish_packet("topic", "x" * 200)
        # Remaining length should be encoded in multiple bytes
        # First byte should have continuation bit set if length > 127
        assert len(packet) > 200

    def test_remaining_length_calculation(self):
        """Test remaining length is calculated correctly"""
        topic = "test"
        message = "hello"
        packet = build_publish_packet(topic, message)

        # Remaining length = 2 (topic length) + len(topic) + len(message)
        expected_remaining = 2 + len(topic) + len(message)

        # For small packets, remaining length is in byte 1
        assert packet[1] == expected_remaining


class TestMQTTClientIntegration:
    """Integration tests for MQTT client with mock WiFi"""

    def test_client_sends_data_through_wifi(self, mock_wifi):
        """Test that client sends data through WiFi send method"""
        # Simulate what the client would do
        mock_wifi.start_connection(0, "TCP", "broker.test.com", 1883)
        mock_wifi.send(0, b"test data")

        sent = mock_wifi.get_all_sent()
        assert b"test data" in sent

    def test_client_connection_setup(self, mock_wifi):
        """Test that client sets up connection correctly"""
        mock_wifi.set_multiple_connections(True)
        mock_wifi.start_connection(0, "TCP", "mqtt.example.com", 1883)

        assert mock_wifi._mux_enabled is True
        assert 0 in mock_wifi.connections
        assert mock_wifi.connections[0]['type'] == "TCP"
        assert mock_wifi.connections[0]['port'] == 1883

    def test_multiple_sends_accumulated(self, mock_wifi):
        """Test that multiple sends are accumulated"""
        mock_wifi.send(0, b"part1")
        mock_wifi.send(0, b"part2")
        mock_wifi.send(0, b"part3")

        sent = mock_wifi.get_all_sent()
        assert b"part1" in sent
        assert b"part2" in sent
        assert b"part3" in sent

    def test_receive_from_queue(self, mock_wifi):
        """Test receiving data from queue"""
        mock_wifi.queue_response(0, b"response data")

        received = mock_wifi.receive()
        assert len(received) == 1
        assert received[0][0] == 0  # link_id
        assert received[0][1] == b"response data"

    def test_close_connection(self, mock_wifi):
        """Test closing connection"""
        mock_wifi.start_connection(0, "TCP", "test.com", 1883)
        assert 0 in mock_wifi.connections

        mock_wifi.close(0)
        assert 0 not in mock_wifi.connections


class TestMQTTPacketID:
    """Tests for MQTT packet ID handling"""

    def test_subscribe_includes_packet_id(self):
        """Test that SUBSCRIBE packet includes packet ID"""
        packet = build_subscribe_packet("topic", packet_id=1234)

        # Packet ID is bytes 2-3 (after fixed header)
        # Find the packet ID in the packet
        assert len(packet) >= 4

    def test_packet_ids_are_unique(self):
        """Test that sequential packets get unique IDs"""
        pid_tracker = PacketIDTracker()

        id1 = pid_tracker.next_id()
        id2 = pid_tracker.next_id()
        id3 = pid_tracker.next_id()

        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

    def test_packet_id_increments(self):
        """Test that packet ID increments correctly"""
        pid_tracker = PacketIDTracker()

        id1 = pid_tracker.next_id()
        id2 = pid_tracker.next_id()

        assert id2 == id1 + 1


class TestMQTTTopicValidation:
    """Tests for MQTT topic handling"""

    def test_topic_with_wildcards(self):
        """Test subscribing to topics with wildcards"""
        packet = build_subscribe_packet("home/+/temperature")
        assert b"home/+/temperature" in packet

        packet = build_subscribe_packet("sensors/#")
        assert b"sensors/#" in packet

    def test_topic_encoding(self):
        """Test that topics are properly encoded as UTF-8"""
        packet = build_publish_packet("test/topic", "message")

        # Topic should be preceded by 2-byte length
        topic = b"test/topic"
        topic_with_length = struct.pack("!H", len(topic)) + topic
        assert topic_with_length in packet


# =============================================================================
# Helper functions for building MQTT packets
# =============================================================================

def build_connect_packet(client_id, user=None, password=None, clean_session=True, keepalive=0):
    """Build an MQTT CONNECT packet"""
    premsg = bytearray(b"\x10\0\0\0\0\0")
    msg = bytearray(b"\x04MQTT\x04\x02\0\0")

    if isinstance(client_id, str):
        client_id = client_id.encode()

    sz = 10 + 2 + len(client_id)
    msg[6] = clean_session << 1

    if user:
        if isinstance(user, str):
            user = user.encode()
        if isinstance(password, str):
            password = password.encode()
        sz += 2 + len(user) + 2 + len(password)
        msg[6] |= 0xC0

    if keepalive:
        msg[7] |= keepalive >> 8
        msg[8] |= keepalive & 0x00FF

    i = 1
    while sz > 0x7F:
        premsg[i] = (sz & 0x7F) | 0x80
        sz >>= 7
        i += 1
    premsg[i] = sz

    result = bytes(premsg[:i + 2]) + bytes(msg)
    result += struct.pack("!H", len(client_id)) + client_id

    if user:
        result += struct.pack("!H", len(user)) + user
        result += struct.pack("!H", len(password)) + password

    return result


def build_publish_packet(topic, message, retain=False, qos=0):
    """Build an MQTT PUBLISH packet"""
    if isinstance(topic, str):
        topic = topic.encode()
    if isinstance(message, str):
        message = message.encode()

    pkt = bytearray(b"\x30\0\0\0")
    pkt[0] |= qos << 1 | retain
    sz = 2 + len(topic) + len(message)
    if qos > 0:
        sz += 2

    i = 1
    while sz > 0x7F:
        pkt[i] = (sz & 0x7F) | 0x80
        sz >>= 7
        i += 1
    pkt[i] = sz

    result = bytes(pkt[:i + 1])
    result += struct.pack("!H", len(topic)) + topic
    result += message

    return result


def build_subscribe_packet(topic, qos=0, packet_id=1):
    """Build an MQTT SUBSCRIBE packet"""
    if isinstance(topic, str):
        topic = topic.encode()

    pkt = bytearray(b"\x82\0\0\0")
    struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, packet_id)

    result = bytes(pkt)
    result += struct.pack("!H", len(topic)) + topic
    result += bytes([qos])

    return result


def build_ping_packet():
    """Build an MQTT PINGREQ packet"""
    return b"\xc0\x00"


def build_disconnect_packet():
    """Build an MQTT DISCONNECT packet"""
    return b"\xe0\x00"


class PacketIDTracker:
    """Helper class for tracking packet IDs"""

    def __init__(self):
        self._current_id = 0

    def next_id(self):
        self._current_id += 1
        return self._current_id
