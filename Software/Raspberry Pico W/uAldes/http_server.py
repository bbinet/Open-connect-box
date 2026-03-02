"""
HTTP Server for uAldes
Minimal HTTP server for ESP8285-based boards
"""

import json


def parse_request(data):
    """Parse HTTP request and extract method, path, and query params"""
    try:
        lines = data.split('\r\n')
        if not lines:
            return None, None, {}

        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) < 2:
            return None, None, {}

        method = parts[0]
        full_path = parts[1]

        # Parse path and query string
        if '?' in full_path:
            path, query_string = full_path.split('?', 1)
            params = {}
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
        else:
            path = full_path
            params = {}

        return method, path, params
    except:
        return None, None, {}


def json_response(data, status=200):
    """Create HTTP response with JSON body and CORS headers"""
    body = json.dumps(data)
    status_text = "OK" if status == 200 else "Bad Request" if status == 400 else "Not Found"
    response = f"HTTP/1.1 {status} {status_text}\r\n"
    response += "Content-Type: application/json\r\n"
    response += f"Content-Length: {len(body)}\r\n"
    response += "Access-Control-Allow-Origin: *\r\n"
    response += "Access-Control-Allow-Methods: GET, OPTIONS\r\n"
    response += "Access-Control-Allow-Headers: Content-Type\r\n"
    response += "Connection: close\r\n"
    response += "\r\n"
    response += body
    return response


# Fake data for testing
FAKE_STATUS = {
    "Soft": "1a",
    "Etat": "1",
    "Comp_C": "12.5",
    "Comp_R": "8.0",
    "T_hp": "45.5",
    "T_vmc": "21.0",
    "T_evap": "8.5",
    "T_haut": "22.0",
    "T_bas": "19.5",
    "DP": "0",
    "Ventil_flow": "125",
    "Ventil_rpm": "1200"
}


class HttpServer:
    """Simple HTTP server for uAldes commands"""

    VERSION = "1.0"

    def __init__(self, wifi, uart, port=80):
        self.wifi = wifi
        self.uart = uart
        self.port = port
        self.last_status = {}
        self.running = False
        self.start_time = None
        self.request_count = 0

    def start(self):
        """Start the HTTP server"""
        import utime
        if self.wifi.start_server(self.port):
            self.running = True
            self.start_time = utime.time()
            print(f"HTTP server started on port {self.port}")
            return True
        print("Failed to start HTTP server")
        return False

    def stop(self):
        """Stop the HTTP server"""
        self.wifi.stop_server()
        self.running = False

    def update_status(self, status):
        """Update the cached status data"""
        if status:
            self.last_status = status

    def handle_request(self, link_id, data):
        """Handle incoming HTTP request"""
        import ualdes

        self.request_count += 1
        method, path, params = parse_request(data)

        # Handle CORS preflight
        if method == "OPTIONS":
            response = "HTTP/1.1 204 No Content\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Access-Control-Allow-Methods: GET, OPTIONS\r\n"
            response += "Access-Control-Allow-Headers: Content-Type\r\n"
            response += "Connection: close\r\n\r\n"
            self.wifi.send_response(link_id, response)
            return

        if method != "GET":
            response = json_response({"error": "Method not allowed"}, 400)
            self.wifi.send_response(link_id, response)
            return

        # Check for test mode
        test_mode = params.get("test", "0") == "1"

        # Route requests
        if path == "/status":
            if test_mode:
                response = json_response(FAKE_STATUS)
            else:
                response = json_response(self.last_status)

        elif path == "/auto":
            if test_mode:
                response = json_response({"status": "ok", "command": "auto", "test": True})
            else:
                cmd = json.dumps({"type": "auto"})
                frame = ualdes.frame_encode(cmd)
                if frame:
                    self.uart.write(bytearray(frame))
                    response = json_response({"status": "ok", "command": "auto"})
                else:
                    response = json_response({"error": "Failed to encode command"}, 400)

        elif path == "/boost":
            if test_mode:
                response = json_response({"status": "ok", "command": "boost", "test": True})
            else:
                cmd = json.dumps({"type": "boost"})
                frame = ualdes.frame_encode(cmd)
                if frame:
                    self.uart.write(bytearray(frame))
                    response = json_response({"status": "ok", "command": "boost"})
                else:
                    response = json_response({"error": "Failed to encode command"}, 400)

        elif path == "/confort":
            duration = int(params.get("duration", 2))
            if test_mode:
                response = json_response({"status": "ok", "command": "confort", "duration": duration, "test": True})
            else:
                cmd = json.dumps({"type": "confort", "params": {"duration": duration}})
                frame = ualdes.frame_encode(cmd)
                if frame:
                    self.uart.write(bytearray(frame))
                    response = json_response({"status": "ok", "command": "confort", "duration": duration})
                else:
                    response = json_response({"error": "Failed to encode command"}, 400)

        elif path == "/vacances":
            duration = int(params.get("duration", 10))
            if test_mode:
                response = json_response({"status": "ok", "command": "vacances", "duration": duration, "test": True})
            else:
                cmd = json.dumps({"type": "vacances", "params": {"duration": duration}})
                frame = ualdes.frame_encode(cmd)
                if frame:
                    self.uart.write(bytearray(frame))
                    response = json_response({"status": "ok", "command": "vacances", "duration": duration})
                else:
                    response = json_response({"error": "Failed to encode command"}, 400)

        elif path == "/temp":
            try:
                temp = float(params.get("value", 20))
                if test_mode:
                    response = json_response({"status": "ok", "command": "temp", "temperature": temp, "test": True})
                else:
                    cmd = json.dumps({"type": "temp", "params": {"temperature": temp}})
                    frame = ualdes.frame_encode(cmd)
                    if frame:
                        self.uart.write(bytearray(frame))
                        response = json_response({"status": "ok", "command": "temp", "temperature": temp})
                    else:
                        response = json_response({"error": "Failed to encode command"}, 400)
            except ValueError:
                response = json_response({"error": "Invalid temperature value"}, 400)

        elif path == "/info":
            import utime
            uptime_secs = utime.time() - self.start_time if self.start_time else 0
            uptime_mins = uptime_secs // 60
            uptime_hours = uptime_mins // 60
            uptime_mins = uptime_mins % 60
            ip_info = self.wifi.get_ip()
            info = {
                "version": self.VERSION,
                "uptime": f"{uptime_hours}h {uptime_mins}m",
                "uptime_seconds": uptime_secs,
                "ip": ip_info.get("station"),
                "requests": self.request_count,
                "status_cached": bool(self.last_status)
            }
            response = json_response(info)

        elif path == "/ualdes":
            # Simple endpoint for device discovery
            response = json_response({"ualdes": True})

        elif path == "/" or path == "/help":
            doc = {
                "api": "uAldes HTTP API",
                "version": self.VERSION,
                "endpoints": {
                    "/status": {
                        "description": "Get current sensor data",
                        "example": "curl http://{ip}/status"
                    },
                    "/auto": {
                        "description": "Set automatic mode",
                        "example": "curl http://{ip}/auto"
                    },
                    "/boost": {
                        "description": "Set boost mode",
                        "example": "curl http://{ip}/boost"
                    },
                    "/confort": {
                        "description": "Set comfort mode for N days",
                        "params": {"duration": "number of days (default: 2)"},
                        "example": "curl 'http://{ip}/confort?duration=3'"
                    },
                    "/vacances": {
                        "description": "Set vacation mode for N days",
                        "params": {"duration": "number of days (default: 10)"},
                        "example": "curl 'http://{ip}/vacances?duration=14'"
                    },
                    "/temp": {
                        "description": "Set target temperature",
                        "params": {"value": "temperature in Celsius"},
                        "example": "curl 'http://{ip}/temp?value=21.5'"
                    },
                    "/info": {
                        "description": "Get device info (version, uptime, IP)",
                        "example": "curl http://{ip}/info"
                    }
                },
                "test_mode": "Add ?test=1 to any endpoint to get fake data without sending commands"
            }
            response = json_response(doc)

        else:
            response = json_response({"error": "Not found", "see": "/help"}, 404)

        self.wifi.send_response(link_id, response)

    def check_requests(self):
        """Check for and handle incoming requests"""
        if not self.running:
            return

        incoming = self.wifi.check_incoming(timeout=50)
        for link_id, data in incoming:
            self.handle_request(link_id, data)
