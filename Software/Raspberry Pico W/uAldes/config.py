# Configuration file for ualdes project
# Contains WiFi, MQTT, and HTTP settings

# Services configuration
SERVICES = {
    "mqtt_enabled": False,  # Set to True to enable MQTT
    "http_enabled": True,   # Set to True to enable HTTP API
    "http_port": 80
}

# WiFi Configuration
WIFI_NETWORKS = {
    "ssid": "REDACTED",
    "password": "REDACTED",
    "gateway": "192.168.1.1"
}

# MQTT Configuration
MQTT_CONFIG = {
    "broker": "mqtt.broker.address",
    "port": 1883,
    "client_id": "aldes",
    "user": "mqtt_username",
    "password": "mqtt_password",
    "ssl": False,
    "keepalive": 60
}

# MQTT Topics
MQTT_TOPICS = {
    "main": "aldes/",
    "command": "aldes/commands",
}

UALDES_OPTIONS = {
    "refresh_time": 60  # Time in seconds to refresh data
}

# Scheduler configuration
# Schedules are stored in schedules.json and managed via HTTP API or CLI
SCHEDULER_CONFIG = {
    "enabled": True,
    "timezone_offset": 1,  # UTC+1 for France (winter), set to 2 for summer time (CEST)
    "ntp_server": "pool.ntp.org",
}

# ITEMS_MAPPING for frame decoding
# Type definitions:
# 0: Return as is
# 1: Divide by 2
# 2: Temperature conversion (value * 0.5 - 20)
# 3: Multiply by 10
# 4: value * 2 - 1
# 5: Convert to hex (last 2 chars)
# 6: BCD temperature with 0.25C precision
ITEMS_MAPPING = {
    "Soft": {"Index": 4, "Type": 5, "Publish": True},
    "Etat": {"Index": 6, "Type": 0, "Publish": True},
    "Comp_C": {"Index": 28, "Type": 1, "Publish": True},
    "Comp_R": {"Index": 29, "Type": 1, "Publish": True},
    "T_hp": {"Index": 32, "Type": 2, "Publish": True},
    "T_vmc": {"Index": 33, "Type": 2, "Publish": True},
    "T_evap": {"Index": 34, "Type": 2, "Publish": True},
    "T_haut": {"Index": 36, "Type": 2, "Publish": True},
    "T_bas": {"Index": 37, "Type": 2, "Publish": True},
    "DP": {"Index": 38, "Type": 0, "Publish": True},
    "Ventil_flow": {"Index": 39, "Type": 4, "Publish": True},
    "Ventil_rpm": {"Index": 40, "Type": 3, "Publish": True},
}

# Hardware Configuration for RP2040 + ESP8285 clone
# This board uses ESP8285 chip for WiFi instead of the CYW43439 on genuine Pico W
# The ESP8285 communicates via UART using AT commands
HARDWARE_CONFIG = {
    # ESP8285 WiFi module UART configuration
    # Default: UART0 on pins GP0 (TX) and GP1 (RX)
    "esp_uart_id": 0,
    "esp_tx_pin": 0,
    "esp_rx_pin": 1,
    "esp_baudrate": 115200,
    "esp_debug": False,  # Set to True to see AT commands in console

    # STM32 communication UART configuration
    # Using UART1 on pins GP4 (TX) and GP5 (RX)
    "stm32_uart_id": 1,
    "stm32_tx_pin": 4,
    "stm32_rx_pin": 5,
    "stm32_baudrate": 115200,

    # LED pin - use "LED" for Pico W onboard LED, or GPIO number for external LED
    # Note: Pico clones may not have onboard LED, set to GPIO pin number (e.g., 25)
    "led_pin": 25,

    # ESP8285 sleep mode: 0 = disabled (low latency), 1 = light-sleep (power saving)
    # Disabling sleep improves ping/response times from ~1000ms to ~50ms
    "esp_sleep_mode": 0,
}
