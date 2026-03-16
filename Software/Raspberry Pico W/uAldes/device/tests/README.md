# On-Device Test Suite (MicroPython)

These tests run directly on the Pico device using MicroPython.

## Setup

Upload all test files to the device root:
```bash
# Using urepl
cd uAldes
./cli/urepl <device-ip> cp device/tests/run_tests.py /run_tests.py
./cli/urepl <device-ip> cp device/tests/test_ualdes.py /test_ualdes.py
./cli/urepl <device-ip> cp device/tests/test_espicoW.py /test_espicoW.py
./cli/urepl <device-ip> cp device/tests/test_simple_esp.py /test_simple_esp.py
./cli/urepl <device-ip> cp device/tests/test_integration.py /test_integration.py
```

## Running Tests

### Via urepl (remote)

```bash
# Run all tests
./cli/urepl <device-ip> exec "import run_tests; run_tests.run_all()"

# Run quick tests (ualdes only)
./cli/urepl <device-ip> exec "import run_tests; run_tests.run_quick()"

# Run hardware connectivity test
./cli/urepl <device-ip> exec "import run_tests; run_tests.run_hardware_test()"

# Run specific test module
./cli/urepl <device-ip> exec "import test_ualdes; test_ualdes.run_all_tests()"
```

### Via REPL (serial/interactive)

```python
import run_tests

# Run all tests
run_tests.run_all()

# Run quick tests (ualdes only)
run_tests.run_quick()

# Run hardware connectivity test (requires ESP8285)
run_tests.run_hardware_test()

# Run individual test module
import test_ualdes
test_ualdes.run_all_tests()
```

## Test Files

| File | Description |
|------|-------------|
| `run_tests.py` | Test runner with `run_all()`, `run_quick()`, `run_hardware_test()` |
| `test_ualdes.py` | Tests for Aldes frame encoding/decoding |
| `test_espicoW.py` | Tests for ESP8285 WiFi driver (mocked UART) |
| `test_simple_esp.py` | Tests for MQTT client |
| `test_integration.py` | Hardware integration tests (requires real ESP8285 + WiFi) |

## Test Types

### Unit Tests (no hardware required)
- `test_ualdes.py` - Pure logic tests
- `test_espicoW.py` - Mocked UART tests
- `test_simple_esp.py` - Mocked network tests

### Hardware Tests (require real hardware)
- `test_integration.py` - Full integration with ESP8285
- `run_hardware_test()` - Quick hardware connectivity check

## Output Example

```
============================================================
uAldes Test Suite
============================================================

[1/3] Running ualdes.py tests...
  [PASS] test_checksum_calculation
  [PASS] test_encode_auto_mode
  ...

[2/3] Running espicoW.py tests...
  [PASS] test_at_command
  ...

[3/3] Running simple_esp.py tests...
  [PASS] test_connect_packet
  ...

============================================================
OVERALL TEST RESULTS
============================================================
  ualdes.py: [PASS]
  espicoW.py: [PASS]
  simple_esp.py: [PASS]
============================================================
All tests PASSED!
============================================================
```
