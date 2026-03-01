#!/usr/bin/env python3
"""
Interactive test tool for STM32F411 USB-UART Bridge.

Allows manual testing by providing an interactive terminal
to send/receive data through the USB CDC interface.

Usage:
    python interactive_test.py [port]

Example:
    python interactive_test.py /dev/ttyACM0
"""

import sys
import time
import threading
import serial
import serial.tools.list_ports


class InteractiveTester:
    def __init__(self, port_name: str, baudrate: int = 115200):
        self.ser = serial.Serial(port_name, baudrate=baudrate, timeout=0.1)
        self.running = True
        self.rx_thread = None

    def start(self):
        """Start the interactive session."""
        print()
        print("=" * 60)
        print("Interactive USB-UART Bridge Tester")
        print("=" * 60)
        print(f"Port: {self.ser.port}")
        print(f"Baudrate: {self.ser.baudrate}")
        print()
        print("Commands:")
        print("  Type text and press Enter to send")
        print("  !hex <bytes>  - Send hex bytes (e.g., !hex 48454C4C4F)")
        print("  !file <path>  - Send file contents")
        print("  !clear        - Clear receive buffer")
        print("  !quit         - Exit")
        print()
        print("Received data will be displayed with [RX] prefix")
        print("-" * 60)

        # Start receive thread
        self.rx_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.rx_thread.start()

        # Main input loop
        try:
            while self.running:
                try:
                    line = input()
                    self._process_input(line)
                except EOFError:
                    break
        except KeyboardInterrupt:
            print("\nInterrupted")

        self.running = False
        self.ser.close()

    def _receive_loop(self):
        """Background thread to receive and display data."""
        buffer = b""
        last_print = time.time()

        while self.running:
            try:
                data = self.ser.read(64)
                if data:
                    buffer += data
                    # Print if we have data and haven't received more in 50ms
                    if time.time() - last_print > 0.05:
                        self._print_received(buffer)
                        buffer = b""
                    last_print = time.time()
                elif buffer and time.time() - last_print > 0.1:
                    self._print_received(buffer)
                    buffer = b""
            except serial.SerialException:
                break

    def _print_received(self, data: bytes):
        """Print received data."""
        # Try to decode as ASCII, show hex for non-printable
        try:
            text = data.decode('ascii')
            # Replace non-printable chars
            printable = ''.join(c if c.isprintable() or c in '\r\n\t' else f'\\x{ord(c):02x}'
                               for c in text)
            print(f"\r[RX] {printable}")
        except UnicodeDecodeError:
            print(f"\r[RX] (hex) {data.hex()}")
        print("> ", end="", flush=True)

    def _process_input(self, line: str):
        """Process user input."""
        line = line.strip()
        if not line:
            return

        if line.startswith("!"):
            self._process_command(line[1:])
        else:
            # Send as text
            data = line.encode('utf-8')
            self.ser.write(data)
            self.ser.flush()
            print(f"[TX] Sent {len(data)} bytes: {line}")

    def _process_command(self, cmd: str):
        """Process a command."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "quit" or command == "exit":
            self.running = False
        elif command == "hex":
            try:
                data = bytes.fromhex(args.replace(" ", ""))
                self.ser.write(data)
                self.ser.flush()
                print(f"[TX] Sent {len(data)} hex bytes: {data.hex()}")
            except ValueError as e:
                print(f"[ERROR] Invalid hex: {e}")
        elif command == "file":
            try:
                with open(args, 'rb') as f:
                    data = f.read()
                self.ser.write(data)
                self.ser.flush()
                print(f"[TX] Sent file '{args}' ({len(data)} bytes)")
            except FileNotFoundError:
                print(f"[ERROR] File not found: {args}")
            except Exception as e:
                print(f"[ERROR] {e}")
        elif command == "clear":
            self.ser.reset_input_buffer()
            print("[INFO] Input buffer cleared")
        else:
            print(f"[ERROR] Unknown command: {command}")


def find_stm32_port():
    """Find STM32 CDC port."""
    for port in serial.tools.list_ports.comports():
        if port.vid == 0x0483 and port.pid == 0x5740:
            return port.device
    return None


def main():
    if len(sys.argv) > 1:
        port_name = sys.argv[1]
    else:
        port_name = find_stm32_port()
        if not port_name:
            print("ERROR: No STM32 CDC device found.")
            print("Usage: python interactive_test.py <port>")
            print()
            print("Available ports:")
            for port in serial.tools.list_ports.comports():
                print(f"  {port.device}: {port.description}")
            return 1
        print(f"Auto-detected: {port_name}")

    try:
        tester = InteractiveTester(port_name)
        tester.start()
    except serial.SerialException as e:
        print(f"ERROR: Could not open port: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
