# uAldes (ESP8285 Version)

## Presentation

This project implements a gateway between UART serial communications (from an STM32 connected to an ALDES T.FLOW water heater) and an MQTT broker. Designed to run on RP2040-based boards with ESP8285 WiFi chip (Pico W clones), it allows:

- Receiving data from a UART device
- Decoding data via the `ualdes` library
- Publishing decoded data to configurable MQTT topics
- Receiving MQTT commands and transmitting them via UART

## Supported Hardware

This version is specifically designed for **Pico W clones** that use:
- **RP2040** microcontroller
- **ESP8285** WiFi chip (instead of the CYW43439 on genuine Raspberry Pi Pico W)

The ESP8285 communicates with the RP2040 via UART using AT commands.

## Features

- Configuration via `config.py` file for WiFi, MQTT, and hardware settings
- Automatic UART frame detection
- Real-time data publishing
- Bidirectional control (read/write)
- LED indicator for connection status and transmissions
- Automatic reconnection on connection loss
- Support for ESP8285-based Pico clones

## Configuration

All configuration is done in `config.py`:

```python
# WiFi Configuration
WIFI_NETWORKS = {
    "ssid": "your_ssid",
    "password": "your_password"
}

# MQTT Configuration
MQTT_CONFIG = {
    "client_id": "gateway_uart",
    "broker": "broker_address",
    "port": 1883,
    "user": "mqtt_user",
    "password": "mqtt_password"
}

# MQTT Topics
MQTT_TOPICS = {
    "main": "home/device/",
    "command": "home/device/command"
}

# UALDES options
UALDES_OPTIONS = {
    "refresh_time": 60  # Refresh time in seconds
}

# Hardware Configuration for RP2040 + ESP8285 clone
HARDWARE_CONFIG = {
    # ESP8285 WiFi module UART configuration
    "esp_uart_id": 0,
    "esp_tx_pin": 0,
    "esp_rx_pin": 1,
    "esp_baudrate": 115200,
    "esp_debug": False,  # Set to True to see AT commands

    # STM32 communication UART configuration
    "stm32_uart_id": 1,
    "stm32_tx_pin": 4,
    "stm32_rx_pin": 5,
    "stm32_baudrate": 115200,

    # LED pin (GPIO number)
    "led_pin": 25,
}
```

## Hardware Connections

### ESP8285 Module (WiFi)
Usually pre-wired on the board:
- **UART0 TX**: GPIO 0 (Pin 1)
- **UART0 RX**: GPIO 1 (Pin 2)

### STM32 Communication
- **UART1 TX**: GPIO 4 (Pin 6)
- **UART1 RX**: GPIO 5 (Pin 7)
- **Power**: USB or external 5V source

### Wiring Diagram
```
RP2040 + ESP8285 Board          STM32
┌─────────────────────┐         ┌─────────┐
│                     │         │         │
│  GP4 (UART1 TX) ────┼────────►│ RX      │
│  GP5 (UART1 RX) ◄───┼─────────│ TX      │
│  GND ───────────────┼─────────│ GND     │
│                     │         │         │
│  [ESP8285 internal] │         └─────────┘
│  GP0 ◄──► ESP TX    │
│  GP1 ◄──► ESP RX    │
└─────────────────────┘
```

## Project Structure

```
uAldes/
├── cli/                    # PC tools
│   ├── ualdes_cli.py       # CLI to interact with device
│   └── urepl.py            # Remote REPL client
├── device/                 # MicroPython code (runs on Pico)
│   ├── tests/              # On-device tests
│   ├── config.py
│   ├── main.py
│   ├── esp8285.py          # ESP8285 WiFi driver
│   ├── mqtt.py             # MQTT client
│   ├── http_server.py
│   ├── scheduler.py
│   ├── tcp_repl.py
│   └── ualdes.py
├── tests/                  # Pytest tests (runs on PC)
│   ├── conftest.py
│   └── test_*.py
└── pytest.ini
```

## Installation

1. Flash MicroPython on your RP2040 board (use standard RP2040 MicroPython, NOT Pico W version)
2. Transfer files from `device/` to the board:
   - `main.py`
   - `config.py` (create based on template above)
   - `esp8285.py` (ESP8285 WiFi driver)
   - `mqtt.py` (MQTT client)
   - `ualdes.py` (Aldes decoding library)
   - `http_server.py` (HTTP server)
   - `tcp_repl.py` (Remote REPL)
   - `scheduler.py` (Task scheduler)

## CLI Tools

### urepl.py - Remote REPL Client

TCP REPL client compatible with mpremote syntax:

```bash
# List files
./cli/urepl.py 192.168.1.79 ls

# Execute Python code
./cli/urepl.py 192.168.1.79 exec "print('hello')"

# Copy files to/from device
./cli/urepl.py 192.168.1.79 cp local.py :remote.py
./cli/urepl.py 192.168.1.79 cp :remote.py local.py

# Sync local files to device (OTA update)
./cli/urepl.py 192.168.1.79 sync device/
./cli/urepl.py 192.168.1.79 sync --force -r device/  # force + reboot

# Interactive REPL
./cli/urepl.py 192.168.1.79 repl

# Reset device
./cli/urepl.py 192.168.1.79 reset
```

### ualdes_cli.py - Device CLI

Interactive CLI for device control:

```bash
./cli/ualdes_cli.py 192.168.1.79
> status
> schedules
> auto
> help
```

## Usage

Once configured and started, the system will:
1. Initialize the ESP8285 module and test communication
2. Connect to the WiFi network
3. Establish a connection with the MQTT broker
4. Listen for UART data and publish to corresponding topics
5. Listen for MQTT commands and transmit via UART

## Testing

### PC Tests (pytest)

Run the test suite on your PC (mocks MicroPython modules):

```bash
# NixOS
nix-shell -p python3Packages.pytest --run "pytest tests/ -v"

# Or with venv
pip install -r tests/requirements.txt
pytest tests/ -v
```

### On-Device Tests

Upload test files from `device/tests/` to the Pico, then run:

```python
import run_tests
run_tests.run_all()
```

## Troubleshooting

### ESP8285 Not Responding
- Check that the ESP8285 is properly connected to UART0 (GP0/GP1)
- Verify the baudrate (usually 115200)
- Enable debug mode in config: `"esp_debug": True`

### No WiFi Connection
- Verify SSID and password
- Ensure the network is 2.4GHz (ESP8285 doesn't support 5GHz)
- Check signal strength

### MQTT Connection Issues
- Verify broker address and port
- Check credentials
- Ensure the broker accepts non-SSL connections (port 1883)

## Data Format

The system receives UART frames in binary format. Example:
```
[0x33, 0xff, 0x4c, 0x33, 0x26, 0x00, ...]
```

These data are decoded by `ualdes.py` and published to individual MQTT topics.

## Differences from Original Pico W Version

| Feature | Pico W | ESP8285 Clone |
|---------|--------|---------------|
| WiFi Chip | CYW43439 | ESP8285 |
| WiFi API | `network.WLAN` | AT Commands via UART |
| Available UARTs | 2 (both free) | 1 free (UART1) |
| HTTPS Support | Yes | No (HTTP only) |

## License

MIT License - 2025 Yann DOUBLET

## Version

Version: 3.0
Release Date: 01/03/2026

---

**Warning**: Do not modify the `main.py` file directly. All configurations should be done in `config.py`.
