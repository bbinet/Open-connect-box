# uAldes Test Suite (PC)

This directory contains pytest tests that can be run on a standard Python installation (not on the device).

## Setup

### With NixOS:
```bash
cd uAldes
nix-shell -p python3Packages.pytest --run "pytest tests/ -v"
```

### With venv:
```bash
cd uAldes
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r tests/requirements.txt
pytest tests/ -v
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_ualdes.py -v

# Run specific test class
pytest tests/test_ualdes.py::TestChecksum -v

# Run specific test
pytest tests/test_ualdes.py::TestChecksum::test_checksum_calculation -v

# Run with coverage report
pytest tests/ --cov=device --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and MicroPython mocks
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── test_ualdes.py       # Tests for frame encoding/decoding
├── test_esp8285.py      # Tests for ESP8285 WiFi driver
├── test_mqtt.py         # Tests for MQTT client
├── test_scheduler.py    # Tests for scheduler functions
└── test_urepl.py        # Tests for TCP REPL client
```

## Test Coverage

| File | Tests |
|------|-------|
| test_ualdes.py | Checksum, frame encode/decode, temperature BCD |
| test_esp8285.py | AT commands, WiFi connection, TCP sockets |
| test_mqtt.py | Packet structure, connect/publish/subscribe |
| test_scheduler.py | Add/edit/remove schedules, sorting, validation |
| test_urepl.py | Connection, raw REPL protocol, all commands (exec, ls, cp, sync, etc.) |

## How Mocking Works

Since the device code uses MicroPython-specific modules (`machine`, `utime`, `network`, `rp2`), the `conftest.py` file provides mock implementations that allow the tests to run on standard Python.

### Mocked Modules:
- `machine.Pin` - GPIO pin control
- `machine.UART` - Serial communication
- `utime` - Time functions (sleep, ticks_ms, etc.)
- `network.WLAN` - WiFi interface
- `rp2` - RP2040-specific functions

## On-Device Tests

For tests that run directly on the MicroPython device, see `device/tests/`:
- `device/tests/run_tests.py` - Test runner
- `device/tests/test_ualdes.py`
- `device/tests/test_esp8285.py`
- `device/tests/test_mqtt.py`
- `device/tests/test_integration.py`

Run on device with:
```python
import run_tests
run_tests.run_all()
```
