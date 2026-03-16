"""
Integration tests for uAldes with real hardware

These tests require:
- ESP8285 module connected and working
- Valid WiFi credentials in config.py
- (Optional) MQTT broker accessible

Run on device with: import test_integration; test_integration.run_all_tests()
"""

import time


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def add_pass(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def add_fail(self, name, reason=""):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  [FAIL] {name}")
        if reason:
            print(f"         Reason: {reason}")

    def add_skip(self, name, reason=""):
        self.skipped += 1
        print(f"  [SKIP] {name}")
        if reason:
            print(f"         Reason: {reason}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*50}")
        print(f"Results: {self.passed} passed, {self.failed} failed, {self.skipped} skipped")
        print(f"{'='*50}")
        return self.failed == 0


result = TestResult()


# =============================================================================
# Configuration Loading Test
# =============================================================================

def test_config_loading():
    """Test that configuration loads correctly"""
    print("\n--- Configuration Loading Tests ---")

    try:
        from config import WIFI_NETWORKS, MQTT_CONFIG, HARDWARE_CONFIG
        result.add_pass("config_import")
    except ImportError as e:
        result.add_fail("config_import", str(e))
        return False

    # Check required WiFi fields
    if "ssid" in WIFI_NETWORKS and "password" in WIFI_NETWORKS:
        result.add_pass("wifi_config_fields")
    else:
        result.add_fail("wifi_config_fields", "Missing ssid or password")

    # Check required MQTT fields
    required_mqtt = ["broker", "port", "client_id"]
    if all(f in MQTT_CONFIG for f in required_mqtt):
        result.add_pass("mqtt_config_fields")
    else:
        result.add_fail("mqtt_config_fields", f"Missing fields: {required_mqtt}")

    # Check hardware config
    required_hw = ["esp_uart_id", "esp_tx_pin", "esp_rx_pin", "stm32_uart_id"]
    if all(f in HARDWARE_CONFIG for f in required_hw):
        result.add_pass("hardware_config_fields")
    else:
        result.add_fail("hardware_config_fields", f"Missing fields: {required_hw}")

    return True


# =============================================================================
# ESP8285 Hardware Tests
# =============================================================================

def test_esp8285_communication():
    """Test ESP8285 basic communication"""
    print("\n--- ESP8285 Communication Tests ---")

    try:
        from config import HARDWARE_CONFIG
        from espicoW import ESPicoW
    except ImportError as e:
        result.add_skip("esp8285_communication", f"Import error: {e}")
        return None

    try:
        wifi = ESPicoW(
            uart_id=HARDWARE_CONFIG['esp_uart_id'],
            tx_pin=HARDWARE_CONFIG['esp_tx_pin'],
            rx_pin=HARDWARE_CONFIG['esp_rx_pin'],
            baudrate=HARDWARE_CONFIG['esp_baudrate'],
            debug=False
        )

        # Test AT command
        if wifi.test():
            result.add_pass("esp8285_at_response")
        else:
            result.add_fail("esp8285_at_response", "No response to AT command")
            return None

        # Test firmware version
        version = wifi.get_version()
        if "AT version" in version or "OK" in version:
            result.add_pass("esp8285_version")
        else:
            result.add_fail("esp8285_version", "Could not get version")

        return wifi

    except Exception as e:
        result.add_fail("esp8285_init", str(e))
        return None


def test_wifi_scan(wifi):
    """Test WiFi network scanning"""
    print("\n--- WiFi Scan Tests ---")

    if wifi is None:
        result.add_skip("wifi_scan", "ESP8285 not initialized")
        return

    try:
        networks = wifi.scan()
        if isinstance(networks, list):
            result.add_pass("wifi_scan_returns_list")
            if len(networks) > 0:
                result.add_pass(f"wifi_scan_found_{len(networks)}_networks")
            else:
                result.add_skip("wifi_scan_networks", "No networks found (may be normal)")
        else:
            result.add_fail("wifi_scan_returns_list", f"Got {type(networks)}")
    except Exception as e:
        result.add_fail("wifi_scan", str(e))


def test_wifi_connection(wifi):
    """Test WiFi connection"""
    print("\n--- WiFi Connection Tests ---")

    if wifi is None:
        result.add_skip("wifi_connection", "ESP8285 not initialized")
        return False

    try:
        from config import WIFI_NETWORKS

        # Check if using placeholder credentials
        if WIFI_NETWORKS["ssid"] == "your_wifi_ssid":
            result.add_skip("wifi_connection", "Using placeholder credentials")
            return False

        print(f"  Connecting to: {WIFI_NETWORKS['ssid']}...")
        connected = wifi.connect(
            WIFI_NETWORKS["ssid"],
            WIFI_NETWORKS["password"],
            timeout=20000
        )

        if connected:
            result.add_pass("wifi_connect")

            # Check IP
            ip_info = wifi.get_ip()
            if ip_info.get('station'):
                result.add_pass(f"wifi_got_ip_{ip_info['station']}")
            else:
                result.add_fail("wifi_got_ip", "No IP assigned")

            return True
        else:
            result.add_fail("wifi_connect", "Connection failed")
            return False

    except Exception as e:
        result.add_fail("wifi_connection", str(e))
        return False


# =============================================================================
# MQTT Tests
# =============================================================================

def test_mqtt_connection(wifi):
    """Test MQTT broker connection"""
    print("\n--- MQTT Connection Tests ---")

    if wifi is None:
        result.add_skip("mqtt_connection", "WiFi not available")
        return

    if not wifi.is_connected():
        result.add_skip("mqtt_connection", "WiFi not connected")
        return

    try:
        from config import MQTT_CONFIG
        from simple_esp import MQTTClient

        # Check placeholder
        if MQTT_CONFIG["broker"] == "mqtt.broker.address":
            result.add_skip("mqtt_connection", "Using placeholder broker address")
            return

        print(f"  Connecting to MQTT: {MQTT_CONFIG['broker']}:{MQTT_CONFIG['port']}...")

        client = MQTTClient(
            MQTT_CONFIG["client_id"],
            MQTT_CONFIG["broker"],
            MQTT_CONFIG["port"],
            MQTT_CONFIG.get("user"),
            MQTT_CONFIG.get("password"),
            wifi=wifi,
            link_id=0
        )

        client.set_callback(lambda t, m: print(f"  Received: {t} -> {m}"))
        client.connect(timeout=10)
        result.add_pass("mqtt_connect")

        # Test publish
        test_topic = "test/ualdes/ping"
        test_msg = "integration_test"
        client.publish(test_topic, test_msg)
        result.add_pass("mqtt_publish")

        # Disconnect
        client.disconnect()
        result.add_pass("mqtt_disconnect")

    except Exception as e:
        result.add_fail("mqtt_connection", str(e))


# =============================================================================
# STM32 UART Test
# =============================================================================

def test_stm32_uart():
    """Test STM32 UART configuration"""
    print("\n--- STM32 UART Tests ---")

    try:
        from machine import UART, Pin
        from config import HARDWARE_CONFIG

        uart = UART(
            HARDWARE_CONFIG["stm32_uart_id"],
            baudrate=HARDWARE_CONFIG["stm32_baudrate"],
            tx=Pin(HARDWARE_CONFIG["stm32_tx_pin"]),
            rx=Pin(HARDWARE_CONFIG["stm32_rx_pin"])
        )
        result.add_pass("stm32_uart_init")

        # Check if any data is available (may or may not have STM32 connected)
        data = uart.read()
        if data:
            result.add_pass(f"stm32_uart_data_received_{len(data)}_bytes")
        else:
            result.add_skip("stm32_uart_data", "No data (STM32 may not be connected)")

    except Exception as e:
        result.add_fail("stm32_uart", str(e))


# =============================================================================
# Full Integration Test
# =============================================================================

def test_ualdes_decode_integration():
    """Test ualdes frame decoding with sample data"""
    print("\n--- uAldes Decode Integration Tests ---")

    try:
        import ualdes

        # Sample frame from documentation
        sample_frame = [
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
        ]

        decoded = ualdes.frame_decode(sample_frame)

        if decoded is not None:
            result.add_pass("ualdes_decode_success")
            print(f"  Decoded {len(decoded)} fields:")
            for key, value in decoded.items():
                print(f"    {key}: {value}")
        else:
            result.add_fail("ualdes_decode", "Decode returned None")

    except Exception as e:
        result.add_fail("ualdes_decode_integration", str(e))


def test_ualdes_encode_integration():
    """Test ualdes frame encoding"""
    print("\n--- uAldes Encode Integration Tests ---")

    try:
        import ualdes

        commands = [
            ('{"type": "auto"}', "auto"),
            ('{"type": "boost"}', "boost"),
            ('{"type": "temp", "params": {"temperature": 22}}', "temp"),
        ]

        for cmd, name in commands:
            frame = ualdes.frame_encode(cmd)
            if frame and len(frame) == 10:
                # Verify checksum
                if ualdes.aldes_checksum_test(frame):
                    result.add_pass(f"ualdes_encode_{name}")
                else:
                    result.add_fail(f"ualdes_encode_{name}", "Invalid checksum")
            else:
                result.add_fail(f"ualdes_encode_{name}", "Invalid frame length")

    except Exception as e:
        result.add_fail("ualdes_encode_integration", str(e))


# =============================================================================
# Run All Tests
# =============================================================================

def run_all_tests():
    """Run all integration tests"""
    global result
    result = TestResult()

    print("=" * 60)
    print("uAldes Integration Tests")
    print("=" * 60)
    print("NOTE: These tests require actual hardware!")
    print("=" * 60)

    # Configuration
    if not test_config_loading():
        print("\nCannot continue without valid configuration.")
        return result.summary()

    # ESP8285 tests
    wifi = test_esp8285_communication()

    # WiFi scan
    test_wifi_scan(wifi)

    # WiFi connection
    wifi_connected = test_wifi_connection(wifi)

    # MQTT tests (only if WiFi connected)
    if wifi_connected:
        test_mqtt_connection(wifi)

    # STM32 UART
    test_stm32_uart()

    # uAldes library integration
    test_ualdes_decode_integration()
    test_ualdes_encode_integration()

    # Cleanup
    if wifi:
        try:
            wifi.disconnect()
        except:
            pass

    return result.summary()


if __name__ == "__main__":
    run_all_tests()
