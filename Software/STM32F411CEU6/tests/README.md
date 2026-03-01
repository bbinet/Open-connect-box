# USB-UART Bridge Test Suite

This directory contains tests for the STM32F411 USB-UART bridge firmware.

## Requirements

```bash
pip install -r requirements.txt
```

Or on NixOS:
```bash
nix-shell -p python3 python3Packages.pyserial
```

## Hardware Setup

### Option 1: Full Test (USB + UART)

Connect:
1. STM32F411 Black Pill to PC via USB (creates /dev/ttyACM0)
2. USB-to-Serial adapter to PC (creates /dev/ttyUSB0)
3. Wire connections:
   - STM32 PA9 (UART1 TX) → USB-Serial RX
   - STM32 PA10 (UART1 RX) → USB-Serial TX
   - GND → GND

```
  PC                    STM32F411              USB-Serial Adapter
  ├─ USB ────────────── USB (CDC) ──┐
  │                                 │
  │                     PA9 (TX) ───┼──────────── RX
  │                     PA10 (RX) ──┼──────────── TX
  └─ USB ───────────────────────────┴──────────── USB
```

### Option 2: Loopback Test (USB only)

Connect STM32 UART TX to RX for loopback:
- STM32 PA9 (TX) → STM32 PA10 (RX)

This allows testing with just the USB connection.

## Running Tests

### 1. Quick Connection Test

Verify the device is detected and accessible:

```bash
python test_connection.py
```

Expected output:
```
STM32F411 USB-UART Bridge Connection Test
============================================================

Scanning for STM32 CDC device...

  /dev/ttyACM0:
    Description: STM32 Virtual ComPort
    VID:PID: 0483:5740 <-- STM32 Virtual ComPort FOUND!
    ...

[OK] Connection test PASSED
```

### 2. Full Test Suite

With USB-Serial adapter connected:
```bash
python test_usb_uart_bridge.py --usb-port /dev/ttyACM0 --uart-port /dev/ttyUSB0
```

Or auto-detect USB port:
```bash
python test_usb_uart_bridge.py --uart-port /dev/ttyUSB0
```

### 3. Loopback Test

With UART TX→RX loopback wire:
```bash
python test_usb_uart_bridge.py --loopback
```

### 4. Interactive Testing

For manual testing and debugging:
```bash
python interactive_test.py /dev/ttyACM0
```

Commands in interactive mode:
- Type text + Enter: Send text
- `!hex 48454C4C4F`: Send hex bytes (HELLO)
- `!clear`: Clear receive buffer
- `!quit`: Exit

## Test Cases

| Test | Description |
|------|-------------|
| test_01_usb_connection | Verify USB CDC port is accessible |
| test_02_uart_connection | Verify UART port is accessible |
| test_03_usb_to_uart_simple | Send "Hello UART!" via USB, verify on UART |
| test_04_uart_to_usb_simple | Send data via UART, verify on USB |
| test_05_usb_loopback | Loopback test (UART TX→RX) |
| test_06_binary_data | Test binary/non-printable bytes |
| test_07_rapid_transmission | Test rapid consecutive sends |
| test_08_special_characters | Test \\r\\n\\t\\x00\\xff |
| test_09_max_packet_size | Test 64-byte CDC packet |
| test_10_stress_test | Send 1KB of data |

## Troubleshooting

### Device not found
```bash
# Check USB devices
lsusb | grep 0483

# Check dmesg for errors
dmesg | tail -20

# List serial ports
python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

### Permission denied
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in

# Or use udev rule:
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="5740", MODE="0666"' | sudo tee /etc/udev/rules.d/99-stm32.rules
sudo udevadm control --reload-rules
```

### Data corruption
- Check baud rate matches (115200)
- Verify wiring (TX→RX, not TX→TX)
- Try shorter cables
- Check ground connection

## Expected Behavior

The firmware acts as a USB-to-UART bridge:
- **USB → UART**: Data received on USB CDC is transmitted on UART1
- **UART → USB**: Data received on UART1 (10 bytes, 500ms timeout) is sent to USB
- **LED (PC13)**: Toggles on activity
