"""
MIT License

Copyright (c) 2025 Yann DOUBLET

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
# WARNING: Do not modify this code directly.
# All configuration should be done in the 'config.py' file.
# This includes MQTT settings, WiFi credentials, and topic paths.
# Make any changes to the configuration file instead of modifying this main script.

from machine import Pin, UART, reset, WDT
import utime

# Import ESP8285 WiFi driver
from esp8285 import ESP8285

import ualdes
import json
from config import WIFI_NETWORKS, UALDES_OPTIONS, HARDWARE_CONFIG, SERVICES, SCHEDULER_CONFIG

RELEASE_DATE = "16_03_2026"
VERSION = "4.5"

# Boot count - persisted to file
BOOTCOUNT_FILE = "bootcount.txt"

def load_bootcount():
    try:
        with open(BOOTCOUNT_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_bootcount(count):
    try:
        with open(BOOTCOUNT_FILE, "w") as f:
            f.write(str(count))
    except Exception as e:
        print(f"Failed to save bootcount: {e}")

boot_count = load_bootcount() + 1
save_bootcount(boot_count)
reconnection_count = 0

# Debug logging - in RAM by default to preserve flash
MAX_LOG_LINES = 100
_log_buffer = []  # In-memory log buffer (mutable, no global needed)
_debug_to_file = SERVICES.get("debug_to_file", False)


def log(message):
    """Write debug message to RAM buffer (and optionally to file)"""
    print(message)
    entry = f"[{boot_count}] {message}"

    # Store in RAM (trim old entries by modifying list in place)
    _log_buffer.append(entry)
    while len(_log_buffer) > MAX_LOG_LINES:
        _log_buffer.pop(0)

    # Optionally write to file (wears flash)
    if _debug_to_file:
        try:
            import os
            try:
                if os.stat("debug.log")[6] > 10000:
                    os.remove("debug.log")
            except:
                pass
            with open("debug.log", "a") as f:
                f.write(entry + "\n")
        except:
            pass


def get_log_buffer():
    """Get the in-memory log buffer (used by http_server)"""
    return _log_buffer


print(f"uAldes ESP8285 Version - Release Date: {RELEASE_DATE} - Version: {VERSION}")
print(f"Boot count: {boot_count}")
log(f"=== Boot {boot_count} ===")

# Initialize LED
led_pin = HARDWARE_CONFIG.get("led_pin", 25)
try:
    led = Pin(led_pin, Pin.OUT)
except:
    led = Pin(25, Pin.OUT)
led.off()

# Initialize UART to STM32
uart = UART(
    HARDWARE_CONFIG["stm32_uart_id"],
    baudrate=HARDWARE_CONFIG["stm32_baudrate"],
    tx=Pin(HARDWARE_CONFIG["stm32_tx_pin"]),
    rx=Pin(HARDWARE_CONFIG["stm32_rx_pin"])
)
print(f"STM32 UART initialized on UART{HARDWARE_CONFIG['stm32_uart_id']} (TX: GP{HARDWARE_CONFIG['stm32_tx_pin']}, RX: GP{HARDWARE_CONFIG['stm32_rx_pin']})")

# Initialize ESP8285 WiFi module
print("Initializing ESP8285 WiFi module...")
wifi = ESP8285(
    uart_id=HARDWARE_CONFIG["esp_uart_id"],
    tx_pin=HARDWARE_CONFIG["esp_tx_pin"],
    rx_pin=HARDWARE_CONFIG["esp_rx_pin"],
    baudrate=HARDWARE_CONFIG["esp_baudrate"],
    debug=HARDWARE_CONFIG.get("esp_debug", False)
)

# Test ESP8285 communication
print("Testing ESP8285 module...")
if not wifi.test():
    print("ESP8285 not responding. Attempting reset...")
    wifi.reset()
    utime.sleep(2)
    if not wifi.test():
        print("ESP8285 communication failed. Please check wiring.")
        print("Restarting in 10 seconds...")
        utime.sleep(10)
        reset()

print("ESP8285 module OK")
print(f"Firmware version: {wifi.get_version()}")

# Software variables
last_message = 0
mqtt_client = None
http_server = None
scheduler = None
last_status = {}  # Shared status for http_server and scheduler
last_status_time = 0  # Timestamp when last_status was updated

def get_last_status():
    """Get current device status (used by scheduler and http_server)"""
    return last_status

def get_last_status_time():
    """Get timestamp of last status update"""
    return last_status_time

def get_status_with_time():
    """Get current device status and its timestamp"""
    return last_status, last_status_time

# Connect to WiFi
def connect_wifi(max_attempts=10):
    """Connect to WiFi using ESP8285"""
    print(f"Connecting to WiFi: {WIFI_NETWORKS['ssid']}...")

    for attempt in range(max_attempts):
        if wifi.connect(WIFI_NETWORKS["ssid"], WIFI_NETWORKS["password"], timeout=15000):
            # Wait for IP address to be assigned
            for _ in range(5):
                utime.sleep(1)
                ip_info = wifi.get_ip()
                if ip_info.get('station'):
                    print(f"WiFi connected! IP: {ip_info['station']}")
                    led.on()
                    return True
            # Connected but no IP yet, continue anyway
            print("WiFi connected! (IP pending)")
            led.on()
            return True
        print(f"Connection attempt {attempt + 1}/{max_attempts} failed...")
        utime.sleep(2)

    return False

# Initial WiFi connection
if not connect_wifi():
    print("Failed to connect to WiFi. Restarting...")
    reset()

# Apply ESP8285 sleep mode setting
esp_sleep_mode = HARDWARE_CONFIG.get("esp_sleep_mode", 1)
if wifi.set_sleep_mode(esp_sleep_mode):
    print(f"ESP8285 sleep mode set to {esp_sleep_mode}")
else:
    print("Warning: Failed to set ESP8285 sleep mode")


# MQTT functions (only if enabled)
if SERVICES.get("mqtt_enabled", False):
    from mqtt import MQTTClient
    from config import MQTT_CONFIG, MQTT_TOPICS

    def try_reconnect_mqtt(max_attempts=5):
        """Attempt to reconnect to MQTT broker"""
        global mqtt_client
        attempts = 0
        while attempts < max_attempts:
            try:
                print("Attempting MQTT reconnection...")
                mqtt_client = connect_and_subscribe()
                print("MQTT reconnection successful")
                return True
            except Exception as e:
                print("MQTT reconnection failed:", e)
                attempts += 1
                utime.sleep(10)
        print("MQTT reconnection impossible.")
        return False

    def connect_and_subscribe():
        """Connect to MQTT broker and subscribe to command topic"""
        global mqtt_client

        mqtt_client = MQTTClient(
            MQTT_CONFIG["client_id"],
            MQTT_CONFIG["broker"],
            MQTT_CONFIG["port"],
            MQTT_CONFIG["user"],
            MQTT_CONFIG["password"],
            wifi=wifi,
            link_id=0
        )
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect(timeout=5)
        mqtt_client.subscribe(MQTT_TOPICS["command"])
        print('Connected to %s, subscribed to %s topic' % (MQTT_CONFIG["broker"], MQTT_TOPICS["command"]))
        return mqtt_client

    def mqtt_callback(topic, msg):
        """Callback for received MQTT messages"""
        print((topic, msg))
        if isinstance(topic, bytes):
            topic = topic.decode('utf-8')
        if isinstance(msg, bytes):
            msg = msg.decode('utf-8')

        if topic == MQTT_TOPICS["command"]:
            led.off()
            print('Received command: %s' % msg)
            input_cmd = ualdes.frame_encode(msg)
            print(input_cmd)
            if input_cmd is not None:
                print(uart.write(bytearray(input_cmd)))
                utime.sleep(0.5)
            led.on()

    # Connect to MQTT broker
    print("MQTT enabled, connecting...")
    if not try_reconnect_mqtt():
        print("Warning: MQTT connection failed, continuing without MQTT")
        SERVICES["mqtt_enabled"] = False


# Initialize scheduler (if enabled) - before HTTP server so it can be passed
if SCHEDULER_CONFIG.get("enabled", False):
    from scheduler import Scheduler
    scheduler = Scheduler(
        wifi=wifi,
        uart=uart,
        timezone=SCHEDULER_CONFIG.get("timezone", "Europe/Paris"),
        ntp_server=SCHEDULER_CONFIG.get("ntp_server", "pool.ntp.org"),
        status_callback=get_last_status
    )
    if scheduler.start():
        print("Scheduler started")
    else:
        print("Warning: Scheduler failed to start")
        scheduler = None

# HTTP server (only if enabled)
if SERVICES.get("http_enabled", False):
    from http_server import HttpServer

    def get_system_stats():
        return {
            "boot_count": boot_count,
            "reconnection_count": reconnection_count
        }

    repl_enabled = SERVICES.get("repl_enabled", False)
    http_server = HttpServer(wifi, uart, SERVICES.get("http_port", 80), stats_callback=get_system_stats, scheduler=scheduler, status_callback=get_status_with_time, repl_enabled=repl_enabled, log_callback=get_log_buffer)
    if http_server.start():
        ip_info = wifi.get_ip()
        print(f"HTTP API available at http://{ip_info['station']}/")
        if repl_enabled:
            print(f"TCP REPL enabled - connect with: mpremote connect socket://{ip_info['station']}:80")
    else:
        print("Warning: HTTP server failed to start")
        SERVICES["http_enabled"] = False


# Check that at least one service is enabled
if not SERVICES.get("mqtt_enabled", False) and not SERVICES.get("http_enabled", False):
    print("Warning: No services enabled (MQTT and HTTP both disabled)")

# Initialize watchdog timer (8 seconds timeout)
# The watchdog will reset the device if not fed within 8 seconds
try:
    wdt = WDT(timeout=8000)
    print("Watchdog timer enabled (8s timeout)")
except Exception as e:
    wdt = None
    print(f"Watchdog not available: {e}")

last_ping = utime.time()
last_wifi_check = utime.time()
ping_interval = 30
wifi_check_interval = 60
consecutive_ping_failures = 0
MAX_PING_FAILURES = 3  # Reset after 3 consecutive ping failures


consecutive_at_failures = 0
MAX_AT_FAILURES = 5  # Reset after 5 consecutive AT command failures


def check_and_reconnect_wifi():
    """Check WiFi connectivity and reconnect/reset if needed."""
    global consecutive_ping_failures, reconnection_count, consecutive_at_failures

    # First verify ESP8285 is responsive (AT command test)
    if not wifi.test():
        consecutive_at_failures += 1
        log(f"ESP8285 AT failed ({consecutive_at_failures}/{MAX_AT_FAILURES})")
        if consecutive_at_failures >= MAX_AT_FAILURES:
            log("ESP8285 not responding. Restarting...")
            reset()
        return  # Skip other checks this round
    else:
        if consecutive_at_failures > 0:
            log(f"ESP8285 AT OK (was {consecutive_at_failures} failures)")
        consecutive_at_failures = 0

    # Check WiFi connection status
    if not wifi.is_connected():
        log("WiFi disconnected. Attempting to reconnect...")
        led.off()
        reconnection_count += 1
        consecutive_ping_failures = 0
        if not connect_wifi(max_attempts=5):
            log("Unable to reconnect to WiFi. Restarting...")
            reset()
        if SERVICES.get("mqtt_enabled", False):
            try_reconnect_mqtt()
        if SERVICES.get("http_enabled", False) and http_server:
            http_server.start()
        return

    # Ping gateway to verify connectivity (log only, no reset)
    gateway = WIFI_NETWORKS.get("gateway", "192.168.1.1")
    ping_result = wifi.ping(gateway)
    if ping_result is None:
        consecutive_ping_failures += 1
        log(f"Ping {gateway} failed ({consecutive_ping_failures})")
    else:
        if consecutive_ping_failures > 0:
            log(f"Ping OK ({ping_result}ms) after {consecutive_ping_failures} failures")
        consecutive_ping_failures = 0


while True:
    current_time = utime.time()

    # Feed the watchdog
    if wdt:
        wdt.feed()

    # Check WiFi connection periodically
    if (current_time - last_wifi_check) > wifi_check_interval:
        last_wifi_check = current_time
        check_and_reconnect_wifi()

    try:
        # Handle MQTT if enabled
        if SERVICES.get("mqtt_enabled", False) and mqtt_client:
            mqtt_client.check_msg()

            if (current_time - last_ping) > ping_interval:
                try:
                    mqtt_client.ping()
                    print("MQTT ping sent")
                    last_ping = current_time
                except Exception as e:
                    print("MQTT ping error, attempting reconnection...")
                    try_reconnect_mqtt()

        # Handle HTTP if enabled
        if SERVICES.get("http_enabled", False) and http_server:
            http_server.check_requests()

        # Check scheduled commands
        if scheduler:
            scheduler.check()

        # Read UART data from STM32
        uart_data = uart.read()

        if (current_time - last_message) > UALDES_OPTIONS["refresh_time"]:
            if uart_data is not None:
                print("Frame received")
                print(uart_data)
                print("Size: " + str(len(uart_data)))
                try:
                    led.off()
                    decoded_data = ualdes.frame_decode(uart_data)

                    if decoded_data is not None:
                        # Update shared status (used by http_server and scheduler)
                        last_status.clear()
                        last_status.update(decoded_data)
                        last_status_time = current_time

                        # Publish to MQTT if enabled
                        if SERVICES.get("mqtt_enabled", False) and mqtt_client:
                            mqtt_client.publish(MQTT_TOPICS["main"] + "trame", bytearray(uart_data).hex(" "))
                            for topic in decoded_data:
                                mqtt_client.publish(MQTT_TOPICS["main"] + topic, str(decoded_data[topic]))
                                print(f"{MQTT_TOPICS['main']}{topic}: {decoded_data[topic]}")

                    last_message = current_time
                    utime.sleep(0.2)
                    led.on()
                except Exception as e:
                    print("Error processing data:", e)

    except Exception as e:
        led.off()
        print('General error:', e)
        utime.sleep(10)
        if SERVICES.get("mqtt_enabled", False):
            try_reconnect_mqtt()

    # Small delay to avoid tight-looping and give ESP8285 time to process
    utime.sleep_ms(50)
