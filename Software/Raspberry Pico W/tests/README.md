# uAldes Test Suite

This directory contains pytest tests that can be run on a standard Python installation (not on the device).

## Setup

1. Create a virtual environment (recommended):
   ```bash
   cd "Software/Raspberry Pico W"
   python -m venv venv
   source venv/bin/activate  # On Linux/Mac
   # or: venv\Scripts\activate  # On Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r tests/requirements.txt
   ```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run with verbose output:
```bash
pytest -v
```

### Run specific test file:
```bash
pytest tests/test_ualdes.py -v
pytest tests/test_espicoW.py -v
pytest tests/test_simple_esp.py -v
```

### Run specific test class:
```bash
pytest tests/test_ualdes.py::TestChecksum -v
```

### Run specific test:
```bash
pytest tests/test_ualdes.py::TestChecksum::test_checksum_calculation -v
```

### Run with coverage report:
```bash
pytest --cov=uAldes --cov-report=html
```

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and MicroPython mocks
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── test_ualdes.py      # Tests for frame encoding/decoding
├── test_espicoW.py     # Tests for ESP8285 WiFi driver
└── test_simple_esp.py  # Tests for MQTT client
```

## How Mocking Works

Since the uAldes code uses MicroPython-specific modules (`machine`, `utime`, `network`, `rp2`), the `conftest.py` file provides mock implementations that allow the tests to run on standard Python.

### Mocked Modules:
- `machine.Pin` - GPIO pin control
- `machine.UART` - Serial communication
- `utime` - Time functions (sleep, ticks_ms, etc.)
- `network.WLAN` - WiFi interface
- `rp2` - RP2040-specific functions

## On-Device Tests

For tests that run directly on the MicroPython device, see the test files in `uAldes/`:
- `uAldes/test_ualdes.py`
- `uAldes/test_espicoW.py`
- `uAldes/test_simple_esp.py`
- `uAldes/test_integration.py`
- `uAldes/run_tests.py`

These can be run on the device with:
```python
import run_tests
run_tests.run_all()
```
