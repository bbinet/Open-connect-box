#!/usr/bin/env python3
"""
Quick connection test for STM32F411 USB-UART Bridge.

This script performs a simple connectivity check:
1. Detects the STM32 CDC device
2. Opens the port and checks basic communication
3. Displays device info

Usage:
    python test_connection.py
"""

import sys
import time
import serial
import serial.tools.list_ports


def find_stm32_device():
    """Find STM32 Virtual ComPort device."""
    ports = serial.tools.list_ports.comports()

    print("Scanning for STM32 CDC device...")
    print()

    stm32_port = None
    for port in ports:
        vid = port.vid or 0
        pid = port.pid or 0

        status = ""
        if vid == 0x0483 and pid == 0x5740:
            status = " <-- STM32 Virtual ComPort FOUND!"
            stm32_port = port

        print(f"  {port.device}:")
        print(f"    Description: {port.description}")
        print(f"    VID:PID: {vid:04X}:{pid:04X}{status}")
        print(f"    Manufacturer: {port.manufacturer or 'N/A'}")
        print(f"    Serial: {port.serial_number or 'N/A'}")
        print()

    return stm32_port


def test_connection(port_name: str, baudrate: int = 115200):
    """Test basic connection to the device."""
    print(f"Testing connection to {port_name} at {baudrate} baud...")

    try:
        ser = serial.Serial(port_name, baudrate=baudrate, timeout=1.0)
        print(f"  [OK] Port opened successfully")

        # Check port settings
        print(f"  Port settings:")
        print(f"    Baudrate: {ser.baudrate}")
        print(f"    Bytesize: {ser.bytesize}")
        print(f"    Parity: {ser.parity}")
        print(f"    Stopbits: {ser.stopbits}")
        print(f"    RTS/CTS: {ser.rtscts}")
        print(f"    DSR/DTR: {ser.dsrdtr}")

        # Try to read any pending data
        ser.reset_input_buffer()
        time.sleep(0.1)

        pending = ser.in_waiting
        if pending > 0:
            data = ser.read(pending)
            print(f"  Pending data: {data!r}")
        else:
            print(f"  No pending data (normal)")

        # Send a test byte and see if we get echo (in loopback)
        print()
        print("  Sending test data (0x55)...")
        ser.write(b'\x55')
        ser.flush()
        time.sleep(0.1)

        response = ser.read(1)
        if response:
            print(f"  Received: {response.hex()} (loopback may be connected)")
        else:
            print(f"  No immediate echo (normal if no loopback)")

        ser.close()
        print()
        print("[OK] Connection test PASSED")
        return True

    except serial.SerialException as e:
        print(f"  [ERROR] {e}")
        return False


def main():
    print("=" * 60)
    print("STM32F411 USB-UART Bridge Connection Test")
    print("=" * 60)
    print()

    # Find device
    stm32 = find_stm32_device()

    if not stm32:
        print("ERROR: No STM32 Virtual ComPort device found!")
        print()
        print("Troubleshooting:")
        print("  1. Check USB cable connection")
        print("  2. Verify device is powered on")
        print("  3. Ensure firmware is flashed correctly")
        print("  4. Check dmesg for USB errors: dmesg | tail -20")
        return 1

    print("-" * 60)
    print()

    # Test connection
    if test_connection(stm32.device):
        print()
        print("Device is ready for use!")
        print(f"Port: {stm32.device}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
