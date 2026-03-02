"""
MQTT Client for ESP8285/ESPicoW

This is a modified version of umqtt.simple that works with ESPicoW's
TCP connections instead of standard sockets.
"""

import struct
import time


class MQTTException(Exception):
    pass


class MQTTClient:
    """MQTT Client that uses ESPicoW for TCP communication"""

    def __init__(
        self,
        client_id,
        server,
        port=1883,
        user=None,
        password=None,
        keepalive=0,
        wifi=None,
        link_id=0,
    ):
        self.client_id = client_id
        self.server = server
        self.port = port
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.wifi = wifi  # ESPicoW instance
        self.link_id = link_id
        self.pid = 0
        self.cb = None
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False
        self._connected = False
        self._rx_buffer = b""

    def _write(self, data):
        """Send data over ESPicoW TCP connection"""
        if isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        return self.wifi.send(self.link_id, data)

    def _read(self, length, timeout=5000):
        """Read data from ESPicoW TCP connection"""
        start = time.ticks_ms()
        result = b""

        # First check buffer
        if len(self._rx_buffer) >= length:
            result = self._rx_buffer[:length]
            self._rx_buffer = self._rx_buffer[length:]
            return result

        while time.ticks_diff(time.ticks_ms(), start) < timeout:
            received = self.wifi.receive(timeout=100)
            for link, data in received:
                if link == self.link_id:
                    if isinstance(data, str):
                        data = data.encode('latin-1')
                    self._rx_buffer += data

            if len(self._rx_buffer) >= length:
                result = self._rx_buffer[:length]
                self._rx_buffer = self._rx_buffer[length:]
                return result

            time.sleep_ms(10)

        # Return what we have
        if self._rx_buffer:
            result = self._rx_buffer[:length]
            self._rx_buffer = self._rx_buffer[length:]
        return result

    def _read_available(self, timeout=100):
        """Read any available data"""
        received = self.wifi.receive(timeout=timeout)
        for link, data in received:
            if link == self.link_id:
                if isinstance(data, str):
                    data = data.encode('latin-1')
                self._rx_buffer += data
        return len(self._rx_buffer) > 0

    def _send_str(self, s):
        if isinstance(s, str):
            s = s.encode('utf-8')
        self._write(struct.pack("!H", len(s)))
        self._write(s)

    def _recv_len(self):
        n = 0
        sh = 0
        while True:
            b = self._read(1, timeout=2000)
            if not b:
                raise MQTTException("Connection lost")
            b = b[0]
            n |= (b & 0x7F) << sh
            if not b & 0x80:
                return n
            sh += 7

    def set_callback(self, f):
        self.cb = f

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True, timeout=None):
        # Enable multiple connections mode on ESP8285
        self.wifi.set_multiple_connections(True)
        time.sleep_ms(100)

        # Start TCP connection
        if not self.wifi.start_connection(self.link_id, "TCP", self.server, self.port):
            raise MQTTException("Failed to connect to MQTT broker")

        time.sleep_ms(200)

        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1
        if self.user:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            assert self.keepalive < 65536
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
        if self.lw_topic:
            sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            msg[6] |= self.lw_retain << 5

        i = 1
        while sz > 0x7F:
            premsg[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        premsg[i] = sz

        self._write(premsg[:i + 2])
        self._write(msg)
        self._send_str(self.client_id)
        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)
        if self.user:
            self._send_str(self.user)
            self._send_str(self.pswd)

        resp = self._read(4, timeout=5000)
        if len(resp) < 4:
            raise MQTTException("No response from broker")
        if resp[0] != 0x20 or resp[1] != 0x02:
            raise MQTTException(f"Invalid CONNACK: {resp}")
        if resp[3] != 0:
            raise MQTTException(resp[3])

        self._connected = True
        return resp[2] & 1

    def disconnect(self):
        self._write(b"\xe0\0")
        self.wifi.close(self.link_id)
        self._connected = False

    def ping(self):
        self._write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        if isinstance(topic, str):
            topic = topic.encode('utf-8')
        if isinstance(msg, str):
            msg = msg.encode('utf-8')

        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2
        assert sz < 2097152
        i = 1
        while sz > 0x7F:
            pkt[i] = (sz & 0x7F) | 0x80
            sz >>= 7
            i += 1
        pkt[i] = sz

        self._write(pkt[:i + 1])
        self._send_str(topic)
        if qos > 0:
            self.pid += 1
            pid = self.pid
            struct.pack_into("!H", pkt, 0, pid)
            self._write(pkt[:2])
        self._write(msg)

        if qos == 1:
            while True:
                op = self.wait_msg()
                if op == 0x40:
                    sz = self._read(1)
                    if sz != b"\x02":
                        continue
                    rcv_pid = self._read(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                    if pid == rcv_pid:
                        return
        elif qos == 2:
            assert 0

    def subscribe(self, topic, qos=0):
        if isinstance(topic, str):
            topic = topic.encode('utf-8')

        assert self.cb is not None, "Subscribe callback is not set"
        pkt = bytearray(b"\x82\0\0\0")
        self.pid += 1
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)
        self._write(pkt)
        self._send_str(topic)
        self._write(bytes([qos]))

        while True:
            op = self.wait_msg()
            if op == 0x90:
                resp = self._read(4)
                if len(resp) < 4:
                    raise MQTTException("Invalid SUBACK response")
                if resp[1] == pkt[2] and resp[2] == pkt[3]:
                    if resp[3] == 0x80:
                        raise MQTTException(resp[3])
                    return

    def wait_msg(self):
        res = self._read(1, timeout=5000)
        if not res:
            return None
        if res == b"\xd0":  # PINGRESP
            sz = self._read(1)
            if sz and sz[0] == 0:
                return None
            return None
        op = res[0]
        if op & 0xF0 != 0x30:
            return op
        sz = self._recv_len()
        topic_len = self._read(2)
        if len(topic_len) < 2:
            return None
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = self._read(topic_len)
        sz -= topic_len + 2
        if op & 6:
            pid = self._read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2
        msg = self._read(sz)
        if self.cb:
            self.cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self._write(pkt)
        elif op & 6 == 4:
            assert 0
        return op

    def check_msg(self):
        self._read_available(timeout=50)
        if self._rx_buffer:
            return self.wait_msg()
        return None
