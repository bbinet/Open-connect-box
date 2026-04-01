"""
HTTP Server for uAldes
Minimal HTTP server for ESP8285-based boards
"""

import json


def parse_request(data):
    """Parse HTTP request and extract method, path, query params, and body"""
    try:
        lines = data.split('\r\n')
        if not lines:
            return None, None, {}, None

        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) < 2:
            return None, None, {}, None

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

        # Extract body (after \r\n\r\n)
        body = None
        if '\r\n\r\n' in data:
            body = data.split('\r\n\r\n', 1)[1]

        return method, path, params, body
    except:
        return None, None, {}, None


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

    VERSION = "1.1"

    def __init__(self, wifi, uart, port=80, stats_callback=None, scheduler=None, status_callback=None, repl_enabled=False, log_callback=None):
        self.wifi = wifi
        self.uart = uart
        self.port = port
        self.status_callback = status_callback
        self.running = False
        self.start_time = None
        self.request_count = 0
        self.stats_callback = stats_callback
        self.scheduler = scheduler
        self.repl_enabled = repl_enabled
        self.log_callback = log_callback
        self.tcp_repl = None
        self.repl_connections = set()  # Track active REPL connections

        if repl_enabled:
            from tcp_repl import TcpRepl
            self.tcp_repl = TcpRepl(wifi)

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

    def _get_status_data(self):
        """Get status data with timestamp and staleness info"""
        import utime
        if self.status_callback:
            status, status_time = self.status_callback()
            current_time = utime.time()
            age = current_time - status_time if status_time > 0 else -1
            return status, status_time, age
        return {}, 0, -1

    def handle_request(self, link_id, data):
        """Handle incoming HTTP request"""
        import ualdes

        self.request_count += 1
        method, path, params, body = parse_request(data)

        # Handle CORS preflight
        if method == "OPTIONS":
            response = "HTTP/1.1 204 No Content\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Access-Control-Allow-Methods: GET, OPTIONS\r\n"
            response += "Access-Control-Allow-Headers: Content-Type\r\n"
            response += "Connection: close\r\n\r\n"
            self.wifi.send_response(link_id, response)
            return

        if method not in ("GET", "POST"):
            response = json_response({"error": "Method not allowed"}, 400)
            self.wifi.send_response(link_id, response)
            return

        # Check for test mode
        test_mode = params.get("test", "0") == "1"

        # Route requests
        if path == "/status":
            if test_mode:
                # Return fake data for testing
                result = dict(FAKE_STATUS)
                result["_updated_ago"] = 0
                response = json_response(result)
            else:
                status, status_time, age = self._get_status_data()
                result = dict(status) if status else {}
                if age >= 0:
                    result["_updated_ago"] = age
                    if age > 120:  # More than 2 minutes
                        result["_warning"] = f"Status is stale ({age}s old)"
                response = json_response(result)

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
            min_temp = params.get("min_temp")

            # Check temperature condition if min_temp is specified
            if min_temp is not None and not test_mode:
                try:
                    min_temp_val = float(min_temp)
                    status, _ = self.status_callback() if self.status_callback else ({}, 0)
                    t_haut = status.get("T_haut")
                    if t_haut is not None:
                        if float(t_haut) >= min_temp_val:
                            response = json_response({
                                "status": "skipped",
                                "command": "boost",
                                "reason": f"T_haut ({t_haut}C) >= min_temp ({min_temp_val}C)",
                                "T_haut": float(t_haut),
                                "min_temp": min_temp_val
                            })
                            self.wifi.send_response(link_id, response)
                            return
                except (ValueError, TypeError):
                    pass

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
            status, status_time, age = self._get_status_data()
            info = {
                "version": self.VERSION,
                "uptime": f"{uptime_hours}h {uptime_mins}m",
                "uptime_seconds": uptime_secs,
                "ip": ip_info.get("station"),
                "requests": self.request_count,
                "status_cached": bool(status),
                "status_age": age if age >= 0 else None
            }
            # Add system stats if callback provided
            if self.stats_callback:
                try:
                    stats = self.stats_callback()
                    info["boot_count"] = stats.get("boot_count", 0)
                    info["reconnection_count"] = stats.get("reconnection_count", 0)
                except:
                    pass
            response = json_response(info)

        elif path == "/ualdes":
            # Simple endpoint for device discovery
            response = json_response({"ualdes": True})

        elif path == "/" or path == "/help":
            # Build endpoints dict incrementally to reduce memory pressure
            ep = {}
            ep["/status"] = {"description": "Get sensor data"}
            ep["/auto"] = {"description": "Set auto mode"}
            ep["/boost"] = {"description": "Set boost mode", "params": {"min_temp": "only if T_haut < value"}}
            ep["/confort"] = {"description": "Set comfort mode", "params": {"duration": "days"}}
            ep["/vacances"] = {"description": "Set vacation mode", "params": {"duration": "days"}}
            ep["/temp"] = {"description": "Set temperature", "params": {"value": "celsius"}}
            ep["/info"] = {"description": "Get device info"}
            ep["/time"] = {"description": "Get device time"}
            ep["/log"] = {"description": "Get debug logs", "params": {"lines": "count"}}
            ep["/log_clear"] = {"description": "Clear debug logs"}
            ep["/reboot"] = {"description": "Reboot device"}
            ep["/schedules"] = {"description": "Manage schedules", "params": {"action": "list|add|edit|remove|clear", "hour": "0-23", "minute": "0-59", "type": "cmd", "index": "idx", "min_temp": "boost condition"}}
            response = json_response({"api": "uAldes HTTP API", "version": self.VERSION, "endpoints": ep})

        elif path == "/schedules":
            import scheduler
            action = params.get("action", "list")

            if action == "list":
                schedules = scheduler.get_schedules()  # Already sorted
                # Add index and execution info
                for i, sched in enumerate(schedules):
                    sched["index"] = i
                    if self.scheduler:
                        for rec in self.scheduler.today_executions:
                            if rec["index"] == i:
                                sched["executed"] = rec
                                break
                result = {"schedules": schedules}
                if self.scheduler and self.scheduler.current_date:
                    result["date"] = self.scheduler.current_date
                response = json_response(result)

            elif action == "add":
                try:
                    hour = int(params.get("hour", -1))
                    minute = int(params.get("minute", 0))
                    cmd_type = params.get("type", "")
                    duration = params.get("duration")
                    min_temp = params.get("min_temp")
                    cmd_params = {}
                    if duration:
                        cmd_params["duration"] = int(duration)
                    if min_temp:
                        cmd_params["min_temp"] = float(min_temp)
                    enabled = params.get("enabled", "1") == "1"

                    index = scheduler.add_schedule(hour, minute, cmd_type, cmd_params if cmd_params else None, enabled)
                    if index >= 0:
                        response = json_response({"status": "ok", "index": index})
                    else:
                        response = json_response({"error": "Invalid schedule parameters"}, 400)
                except Exception as e:
                    response = json_response({"error": str(e)}, 400)

            elif action == "edit":
                try:
                    index = int(params.get("index", -1))
                    hour = int(params["hour"]) if "hour" in params else None
                    minute = int(params["minute"]) if "minute" in params else None
                    cmd_type = params.get("type")
                    duration = params.get("duration")
                    min_temp = params.get("min_temp")
                    cmd_params = None
                    if duration or min_temp:
                        cmd_params = {}
                        if duration:
                            cmd_params["duration"] = int(duration)
                        if min_temp:
                            cmd_params["min_temp"] = float(min_temp)
                    enabled = None
                    if "enabled" in params:
                        enabled = params["enabled"] == "1"

                    result = scheduler.edit_schedule(index, hour, minute, cmd_type, cmd_params, enabled)
                    if result:
                        response = json_response({"status": "ok", "schedule": result})
                    else:
                        response = json_response({"error": "Invalid index or parameters"}, 400)
                except Exception as e:
                    response = json_response({"error": str(e)}, 400)

            elif action == "remove":
                try:
                    index = int(params.get("index", -1))
                    result = scheduler.remove_schedule(index)
                    if result:
                        response = json_response({"status": "ok", "removed": result})
                    else:
                        response = json_response({"error": "Invalid index"}, 400)
                except Exception as e:
                    response = json_response({"error": str(e)}, 400)

            elif action == "enable":
                try:
                    index = int(params.get("index", -1))
                    result = scheduler.enable_schedule(index, True)
                    if result:
                        response = json_response({"status": "ok", "schedule": result})
                    else:
                        response = json_response({"error": "Invalid index"}, 400)
                except Exception as e:
                    response = json_response({"error": str(e)}, 400)

            elif action == "disable":
                try:
                    index = int(params.get("index", -1))
                    result = scheduler.enable_schedule(index, False)
                    if result:
                        response = json_response({"status": "ok", "schedule": result})
                    else:
                        response = json_response({"error": "Invalid index"}, 400)
                except Exception as e:
                    response = json_response({"error": str(e)}, 400)

            elif action == "clear":
                scheduler.clear_schedules()
                response = json_response({"status": "ok"})

            else:
                response = json_response({"error": "Unknown action"}, 400)

        elif path == "/time":
            if self.scheduler:
                time_tuple = self.scheduler.get_current_time()
                if time_tuple:
                    response = json_response({
                        "year": time_tuple[0],
                        "month": time_tuple[1],
                        "day": time_tuple[2],
                        "hour": time_tuple[3],
                        "minute": time_tuple[4],
                        "second": time_tuple[5],
                        "formatted": f"{time_tuple[0]}-{time_tuple[1]:02d}-{time_tuple[2]:02d} {time_tuple[3]:02d}:{time_tuple[4]:02d}:{time_tuple[5]:02d}"
                    })
                else:
                    response = json_response({"error": "Time not synced"}, 400)
            else:
                response = json_response({"error": "Scheduler not enabled"}, 400)

        elif path == "/log":
            if self.log_callback:
                lines = int(params.get("lines", 50))
                all_lines = self.log_callback()
                recent = all_lines[-lines:] if len(all_lines) > lines else list(all_lines)
                response = json_response({"log": recent, "total_lines": len(all_lines)})
            else:
                response = json_response({"error": "Logging not configured"}, 404)

        elif path == "/log_clear":
            if self.log_callback:
                # Clear the buffer by removing all items
                buf = self.log_callback()
                buf.clear()
                response = json_response({"status": "ok", "message": "Log cleared"})
            else:
                response = json_response({"error": "Logging not configured"}, 404)

        elif path == "/reboot":
            response = json_response({"status": "ok", "message": "Rebooting..."})
            self.wifi.send_response(link_id, response)
            import utime
            utime.sleep(1)
            from machine import reset
            reset()
            return

        else:
            response = json_response({"error": "Not found", "see": "/help"}, 404)

        self.wifi.send_response(link_id, response)

    def check_requests(self):
        """Check for and handle incoming requests"""
        if not self.running:
            return

        incoming = self.wifi.check_incoming(timeout=500)
        for link_id, data in incoming:
            # Handle closed connections
            if data is None:
                self.cleanup_repl_connection(link_id)
                continue

            # Check if this is a REPL connection
            if link_id in self.repl_connections:
                # Existing REPL connection - handle data
                if self.tcp_repl:
                    self.tcp_repl.handle_data(link_id, data)
                continue

            # Check if this is a new REPL connection (starts with control char)
            if self.repl_enabled and self.tcp_repl:
                first_byte = ord(data[0]) if isinstance(data, str) and len(data) > 0 else (data[0] if isinstance(data, bytes) and len(data) > 0 else -1)
                # Detect REPL: any control character (< 0x20)
                # HTTP requests start with "GET", "POST", etc. (>= 0x20)
                if first_byte < 0x20:
                    self.repl_connections.add(link_id)
                    self.tcp_repl.handle_data(link_id, data)
                    continue

            # Regular HTTP request
            self.handle_request(link_id, data)

    def cleanup_repl_connection(self, link_id):
        """Clean up a closed REPL connection"""
        if link_id in self.repl_connections:
            self.repl_connections.discard(link_id)
            if self.tcp_repl:
                self.tcp_repl.close_session(link_id)
