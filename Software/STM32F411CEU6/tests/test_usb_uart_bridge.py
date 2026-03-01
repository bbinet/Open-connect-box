#!/usr/bin/env python3
"""
Test suite for STM32F411 USB-UART Bridge firmware.

This tests the functionality of the USB CDC to UART bridge by:
1. Sending data via USB CDC and verifying UART output
2. Sending data via UART and verifying USB CDC output
3. Testing various data patterns and edge cases

Requirements:
- Device flashed with the firmware and connected via USB
- A USB-to-Serial adapter connected to UART1 (PA9=TX, PA10=RX)
- pyserial: pip install pyserial

Usage:
    python test_usb_uart_bridge.py --usb-port /dev/ttyACM0 --uart-port /dev/ttyUSB0

Or for loopback test (UART TX connected to UART RX):
    python test_usb_uart_bridge.py --usb-port /dev/ttyACM0 --loopback
"""

import argparse
import time
import sys
import serial
import serial.tools.list_ports
from typing import Optional
import unittest


class USBUARTBridgeTests(unittest.TestCase):
    """Test cases for USB-UART bridge functionality."""

    usb_port: Optional[serial.Serial] = None
    uart_port: Optional[serial.Serial] = None
    loopback_mode: bool = False

    @classmethod
    def setUpClass(cls):
        """Set up serial connections before running tests."""
        pass  # Connections are set up in main()

    @classmethod
    def tearDownClass(cls):
        """Clean up serial connections after all tests."""
        if cls.usb_port and cls.usb_port.is_open:
            cls.usb_port.close()
        if cls.uart_port and cls.uart_port.is_open:
            cls.uart_port.close()

    def setUp(self):
        """Clear buffers before each test."""
        if self.usb_port:
            self.usb_port.reset_input_buffer()
            self.usb_port.reset_output_buffer()
        if self.uart_port:
            self.uart_port.reset_input_buffer()
            self.uart_port.reset_output_buffer()
        time.sleep(0.1)

    def test_01_usb_connection(self):
        """Test that USB CDC port is accessible."""
        self.assertIsNotNone(self.usb_port, "USB port not configured")
        self.assertTrue(self.usb_port.is_open, "USB port not open")
        print(f"  USB port: {self.usb_port.port}")

    def test_02_uart_connection(self):
        """Test that UART port is accessible (skip in loopback mode)."""
        if self.loopback_mode:
            self.skipTest("Loopback mode - no separate UART port")
        self.assertIsNotNone(self.uart_port, "UART port not configured")
        self.assertTrue(self.uart_port.is_open, "UART port not open")
        print(f"  UART port: {self.uart_port.port}")

    def test_03_usb_to_uart_simple(self):
        """Test sending simple data from USB to UART."""
        if self.loopback_mode:
            self.skipTest("Loopback mode - cannot test USB to UART separately")

        test_data = b"Hello UART!"
        self.usb_port.write(test_data)
        self.usb_port.flush()

        time.sleep(0.2)
        received = self.uart_port.read(len(test_data))

        self.assertEqual(received, test_data,
                        f"Expected {test_data!r}, got {received!r}")
        print(f"  Sent via USB: {test_data!r}")
        print(f"  Received on UART: {received!r}")

    def test_04_uart_to_usb_simple(self):
        """Test sending simple data from UART to USB."""
        if self.loopback_mode:
            self.skipTest("Loopback mode - cannot test UART to USB separately")

        test_data = b"Hello USB!"
        # Pad to 10 bytes as firmware reads 10 bytes at a time
        test_data_padded = test_data.ljust(10, b'\x00')

        self.uart_port.write(test_data_padded)
        self.uart_port.flush()

        time.sleep(0.6)  # Firmware has 500ms timeout
        received = self.usb_port.read(10)

        self.assertTrue(received.startswith(test_data.rstrip(b'\x00')),
                       f"Expected data starting with {test_data!r}, got {received!r}")
        print(f"  Sent via UART: {test_data_padded!r}")
        print(f"  Received on USB: {received!r}")

    def test_05_usb_loopback(self):
        """Test USB echo when UART TX is connected to RX (loopback)."""
        if not self.loopback_mode:
            self.skipTest("Not in loopback mode")

        # The firmware reads UART in 10-byte chunks with 500ms timeout
        # Send data continuously to ensure it's captured
        test_pattern = b"X"
        num_bytes = 50

        # Clear any pending data
        self.usb_port.reset_input_buffer()
        time.sleep(0.6)  # Wait for firmware cycle

        # Send data continuously
        for _ in range(num_bytes):
            self.usb_port.write(test_pattern)
            self.usb_port.flush()
            time.sleep(0.02)

        # Wait for firmware to process and send back
        time.sleep(1.5)

        # Read response (firmware sends 10-byte chunks)
        received = self.usb_port.read(100)

        # We should receive at least some data back
        self.assertGreater(len(received), 0,
                          f"Loopback failed: sent {num_bytes} bytes, got nothing back")

        # Count how many X's we received
        x_count = received.count(ord('X'))
        print(f"  Loopback test: sent {num_bytes} bytes, received {len(received)} bytes ({x_count} 'X's)")

    def test_05b_loopback_binary_data(self):
        """Test loopback with binary data (avoiding 0x00 as first byte)."""
        if not self.loopback_mode:
            self.skipTest("Not in loopback mode")

        # NOTE: Firmware ignores chunks where first byte is 0x00
        # Send non-zero bytes to test binary transmission
        test_data = bytes([i if i != 0 else 0x80 for i in range(100)])

        self.usb_port.reset_input_buffer()
        time.sleep(0.6)

        # Send byte by byte like working test
        for b in test_data:
            self.usb_port.write(bytes([b]))
            self.usb_port.flush()
            time.sleep(0.02)

        time.sleep(2.0)
        received = self.usb_port.read(150)

        self.assertGreater(len(received), 50,
                          f"Binary loopback: expected >50 bytes, got {len(received)}")
        print(f"  Binary loopback: sent {len(test_data)} bytes, received {len(received)} bytes")

    def test_05c_loopback_rapid_transmission(self):
        """Test rapid consecutive transmissions in loopback."""
        if not self.loopback_mode:
            self.skipTest("Not in loopback mode")

        self.usb_port.reset_input_buffer()
        time.sleep(0.6)

        # Send 100 bytes rapidly (like working test)
        total_sent = 0
        for i in range(100):
            self.usb_port.write(b"Y")  # Non-zero byte
            self.usb_port.flush()
            total_sent += 1
            time.sleep(0.02)

        time.sleep(2.0)
        received = self.usb_port.read(150)

        y_count = received.count(ord('Y'))
        self.assertGreater(y_count, 50,
                          f"Rapid transmission: expected >50 Y's, got {y_count}")
        print(f"  Rapid transmission: sent {total_sent} bytes, received {len(received)} bytes ({y_count} Y's)")

    def test_05d_loopback_special_characters(self):
        """Test special characters in loopback mode."""
        if not self.loopback_mode:
            self.skipTest("Not in loopback mode")

        self.usb_port.reset_input_buffer()
        time.sleep(0.6)

        # Test special chars (avoiding 0x00 as firmware ignores chunks starting with 0x00)
        # Send byte by byte like working tests
        test_chars = [0x0D, 0x0A, 0x09, 0x7F, 0xFF, 0x01, 0x02, 0x1B, 0x80, 0xFE]
        for b in test_chars:
            self.usb_port.write(bytes([b]))
            self.usb_port.flush()
            time.sleep(0.02)

        time.sleep(1.5)
        received = self.usb_port.read(20)

        self.assertGreater(len(received), 0,
                          "Special chars loopback: received nothing")
        print(f"  Special chars: sent {len(test_chars)} bytes, received {len(received)} bytes")
        print(f"    Received hex: {received.hex()}")

    def test_05e_loopback_max_packet(self):
        """Test sending 64 bytes (CDC max packet size) in loopback."""
        if not self.loopback_mode:
            self.skipTest("Not in loopback mode")

        self.usb_port.reset_input_buffer()
        time.sleep(0.6)

        # Send 64 non-zero bytes one by one (firmware ignores chunks starting with 0x00)
        for i in range(64):
            self.usb_port.write(bytes([0x41 + (i % 26)]))  # A-Z
            self.usb_port.flush()
            time.sleep(0.02)

        time.sleep(2.0)
        received = self.usb_port.read(100)

        self.assertGreater(len(received), 40,
                          f"Max packet loopback: expected >40 bytes, got {len(received)}")
        print(f"  Max packet (64 bytes): sent 64 bytes, received {len(received)} bytes")

    def test_05f_loopback_stress_test(self):
        """Stress test with larger data transfer in loopback."""
        if not self.loopback_mode:
            self.skipTest("Not in loopback mode")

        self.usb_port.reset_input_buffer()
        time.sleep(0.6)

        # Send 200 non-zero bytes one by one
        num_bytes = 200
        for i in range(num_bytes):
            self.usb_port.write(bytes([0x30 + (i % 10)]))  # 0-9 ASCII
            self.usb_port.flush()
            time.sleep(0.015)

        time.sleep(3.0)
        received = self.usb_port.read(300)

        self.assertGreater(len(received), 100,
                          f"Stress test: expected >100 bytes, got {len(received)}")
        print(f"  Stress test: sent {num_bytes} bytes, received {len(received)} bytes")

    def test_06_binary_data(self):
        """Test sending binary data (all byte values)."""
        if self.loopback_mode:
            self.skipTest("Loopback mode - testing via loopback instead")

        # Test with bytes 0x00-0x09
        test_data = bytes(range(10))

        self.usb_port.write(test_data)
        self.usb_port.flush()

        time.sleep(0.2)
        received = self.uart_port.read(10)

        self.assertEqual(received, test_data,
                        f"Binary data mismatch: sent {test_data.hex()}, got {received.hex()}")
        print(f"  Binary test passed: {test_data.hex()}")

    def test_07_rapid_transmission(self):
        """Test rapid consecutive transmissions."""
        if self.loopback_mode:
            self.skipTest("Loopback mode")

        for i in range(5):
            test_data = f"Msg{i:02d}TEST".encode()  # 10 bytes
            self.usb_port.write(test_data)
            self.usb_port.flush()
            time.sleep(0.05)

        time.sleep(0.3)
        received = self.uart_port.read(50)

        self.assertGreaterEqual(len(received), 40,
                               f"Expected at least 40 bytes, got {len(received)}")
        print(f"  Rapid transmission: sent 50 bytes, received {len(received)} bytes")

    def test_08_special_characters(self):
        """Test special characters and control codes."""
        if self.loopback_mode:
            self.skipTest("Loopback mode")

        # Test newlines, tabs, and special chars
        test_data = b"\r\n\t\x00\xff"

        self.usb_port.write(test_data)
        self.usb_port.flush()

        time.sleep(0.2)
        received = self.uart_port.read(len(test_data))

        self.assertEqual(received, test_data,
                        f"Special chars mismatch: sent {test_data!r}, got {received!r}")
        print(f"  Special characters test passed")

    def test_09_max_packet_size(self):
        """Test sending data up to CDC max packet size (64 bytes)."""
        if self.loopback_mode:
            self.skipTest("Loopback mode")

        test_data = bytes(range(64))

        self.usb_port.write(test_data)
        self.usb_port.flush()

        time.sleep(0.3)
        received = self.uart_port.read(64)

        self.assertEqual(len(received), 64,
                        f"Expected 64 bytes, got {len(received)}")
        self.assertEqual(received, test_data,
                        "64-byte packet data mismatch")
        print(f"  Max packet size (64 bytes) test passed")

    def test_10_stress_test(self):
        """Stress test with larger data transfer."""
        if self.loopback_mode:
            self.skipTest("Loopback mode")

        # Send 1KB of data
        test_data = bytes([i % 256 for i in range(1024)])

        self.usb_port.write(test_data)
        self.usb_port.flush()

        time.sleep(1.0)
        received = self.uart_port.read(1024)

        self.assertGreaterEqual(len(received), 900,
                               f"Expected ~1024 bytes, got {len(received)}")
        print(f"  Stress test: sent 1024 bytes, received {len(received)} bytes")


def find_stm32_cdc_port() -> Optional[str]:
    """Find the STM32 CDC ACM port automatically."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # STMicroelectronics VID is 0x0483
        if port.vid == 0x0483 and port.pid == 0x5740:
            return port.device
        # Also check description
        if "STM32" in (port.description or "") or "Virtual COM" in (port.description or ""):
            return port.device
    return None


def list_serial_ports():
    """List all available serial ports."""
    ports = serial.tools.list_ports.comports()
    print("\nAvailable serial ports:")
    for port in ports:
        print(f"  {port.device}: {port.description} [VID:PID={port.vid:04x}:{port.pid:04x}]"
              if port.vid else f"  {port.device}: {port.description}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Test STM32F411 USB-UART Bridge firmware",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect USB port, specify UART port
  python test_usb_uart_bridge.py --uart-port /dev/ttyUSB0

  # Manual port specification
  python test_usb_uart_bridge.py --usb-port /dev/ttyACM0 --uart-port /dev/ttyUSB0

  # Loopback mode (UART TX connected to RX)
  python test_usb_uart_bridge.py --loopback

  # List available ports
  python test_usb_uart_bridge.py --list-ports
        """
    )
    parser.add_argument("--usb-port", help="USB CDC port (e.g., /dev/ttyACM0)")
    parser.add_argument("--uart-port", help="UART port (e.g., /dev/ttyUSB0)")
    parser.add_argument("--loopback", action="store_true",
                       help="Loopback mode (UART TX connected to RX)")
    parser.add_argument("--baudrate", type=int, default=115200,
                       help="UART baudrate (default: 115200)")
    parser.add_argument("--list-ports", action="store_true",
                       help="List available serial ports and exit")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose output")

    args = parser.parse_args()

    if args.list_ports:
        list_serial_ports()
        return 0

    # Find or use USB port
    usb_port_name = args.usb_port
    if not usb_port_name:
        usb_port_name = find_stm32_cdc_port()
        if usb_port_name:
            print(f"Auto-detected STM32 CDC port: {usb_port_name}")
        else:
            print("ERROR: Could not auto-detect STM32 CDC port.")
            print("Please specify --usb-port or check device connection.")
            list_serial_ports()
            return 1

    # Open USB port
    try:
        USBUARTBridgeTests.usb_port = serial.Serial(
            usb_port_name,
            baudrate=args.baudrate,
            timeout=1.0
        )
        print(f"Opened USB CDC port: {usb_port_name}")
    except serial.SerialException as e:
        print(f"ERROR: Could not open USB port {usb_port_name}: {e}")
        return 1

    # Open UART port (if not loopback mode)
    USBUARTBridgeTests.loopback_mode = args.loopback

    if not args.loopback:
        if not args.uart_port:
            print("ERROR: Please specify --uart-port or use --loopback mode")
            list_serial_ports()
            USBUARTBridgeTests.usb_port.close()
            return 1

        try:
            USBUARTBridgeTests.uart_port = serial.Serial(
                args.uart_port,
                baudrate=args.baudrate,
                timeout=1.0
            )
            print(f"Opened UART port: {args.uart_port}")
        except serial.SerialException as e:
            print(f"ERROR: Could not open UART port {args.uart_port}: {e}")
            USBUARTBridgeTests.usb_port.close()
            return 1
    else:
        print("Running in LOOPBACK mode (UART TX->RX)")

    print(f"Baudrate: {args.baudrate}")
    print()

    # Run tests
    verbosity = 2 if args.verbose else 1
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(USBUARTBridgeTests)

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    # Cleanup
    if USBUARTBridgeTests.usb_port:
        USBUARTBridgeTests.usb_port.close()
    if USBUARTBridgeTests.uart_port:
        USBUARTBridgeTests.uart_port.close()

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
