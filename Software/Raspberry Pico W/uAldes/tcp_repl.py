"""
TCP REPL Handler for remote mpremote access
Implements MicroPython Raw REPL protocol over TCP

This is integrated with the HTTP server - when a connection starts
with CTRL_A (0x01), it's handled as REPL instead of HTTP.

Note: MicroPython doesn't support sys.stdout reassignment, so print()
output cannot be captured. Only expression results are returned.
"""


class TcpRepl:
    """Handles Raw REPL protocol for mpremote compatibility"""

    CTRL_A = b'\x01'  # Enter raw REPL
    CTRL_B = b'\x02'  # Enter normal REPL
    CTRL_C = b'\x03'  # Interrupt
    CTRL_D = b'\x04'  # Execute (raw) / Soft reset (normal)

    def __init__(self, wifi):
        self.wifi = wifi
        # Per-connection state (link_id -> state)
        self.sessions = {}

    def _get_session(self, link_id):
        """Get or create session state for a connection"""
        if link_id not in self.sessions:
            self.sessions[link_id] = {
                'in_raw_mode': False,
                'code_buffer': ''
            }
        return self.sessions[link_id]

    def close_session(self, link_id):
        """Clean up session when connection closes"""
        if link_id in self.sessions:
            del self.sessions[link_id]

    def _send(self, link_id, data):
        """Send data to client"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.wifi.send(link_id, data)

    def _exec_code(self, code):
        """Execute code and return result

        Note: MicroPython doesn't support sys.stdout reassignment,
        so we can't capture print() output. We return eval results
        for expressions and None for statements.
        """
        result = None
        exception = None

        try:
            # Use compile + exec to handle both expressions and statements
            try:
                # Try as expression first
                result = eval(code)
            except SyntaxError:
                # Fall back to exec for statements
                exec(code)
        except Exception as e:
            exception = e

        # MicroPython can't capture stdout, so we return empty strings for stdout/stderr
        return "", "", result, exception

    def handle_data(self, link_id, data):
        """Handle incoming data from TCP client

        Returns True if connection should stay open, False to close
        """
        if isinstance(data, str):
            data = data.encode('utf-8')

        session = self._get_session(link_id)

        # Quick check for mpremote init sequence
        # mpremote sends: \r\x03 (interrupt), then \r\x01 (enter raw REPL)
        # We should only respond to CTRL_A, not CTRL_C during init
        # This avoids timing issues where KeyboardInterrupt arrives after mpremote's flush

        # CTRL_A: enter raw REPL - always respond
        if data == b'\r\x01' or data == b'\x01':
            session['in_raw_mode'] = True
            session['code_buffer'] = ''
            self._send(link_id, b"raw REPL; CTRL-B to exit\r\n>")
            return True

        # CTRL_C alone: interrupt, but don't respond if not in raw mode (mpremote init)
        # This prevents the KeyboardInterrupt from interfering with the init sequence
        if data == b'\r\x03' or data == b'\x03':
            session['code_buffer'] = ''
            if session['in_raw_mode']:
                self._send(link_id, b">")
            # In normal mode, don't send response - let mpremote proceed to CTRL_A
            return True

        for byte in data:
            char = bytes([byte])

            if char == self.CTRL_A:
                # Enter raw REPL mode
                session['in_raw_mode'] = True
                session['code_buffer'] = ''
                # Send raw REPL prompt
                self._send(link_id, b"raw REPL; CTRL-B to exit\r\n>")

            elif char == self.CTRL_B:
                # Exit raw REPL, enter normal mode
                session['in_raw_mode'] = False
                session['code_buffer'] = ''
                self._send(link_id, b"\r\nMicroPython\r\n>>> ")

            elif char == self.CTRL_C:
                # Interrupt - clear buffer
                session['code_buffer'] = ''
                if session['in_raw_mode']:
                    self._send(link_id, b">")
                else:
                    self._send(link_id, b"\r\nKeyboardInterrupt\r\n>>> ")

            elif char == self.CTRL_D:
                if session['in_raw_mode']:
                    # Execute code in raw mode
                    if session['code_buffer']:
                        stdout, stderr, result, exc = self._exec_code(session['code_buffer'])

                        # Raw REPL response format: OK<\x04>output<\x04>exception<\x04>
                        response = b"OK" + self.CTRL_D

                        # Add stdout
                        if stdout:
                            response += stdout.encode('utf-8')
                        if result is not None:
                            response += repr(result).encode('utf-8')

                        response += self.CTRL_D

                        # Add stderr/exception
                        if exc:
                            response += f"{type(exc).__name__}: {exc}".encode('utf-8')
                        if stderr:
                            response += stderr.encode('utf-8')

                        response += self.CTRL_D
                        self._send(link_id, response)
                        self._send(link_id, b">")
                    else:
                        # Empty buffer - just acknowledge and ready for next command
                        self._send(link_id, b"OK" + self.CTRL_D + self.CTRL_D + self.CTRL_D + b">")

                    session['code_buffer'] = ''
                else:
                    # Soft reset in normal mode - close connection first
                    self._send(link_id, b"\r\nsoft reboot\r\n")
                    self.close_session(link_id)
                    from machine import reset
                    reset()

            elif byte == 0x0D or byte == 0x0A:
                # CR/LF - ignore in normal mode, add to buffer in raw mode
                if session['in_raw_mode']:
                    session['code_buffer'] += chr(byte)
                # In normal mode, just ignore (or could echo)

            else:
                # Regular character - add to buffer
                session['code_buffer'] += chr(byte)

        return True  # Keep connection open for REPL
