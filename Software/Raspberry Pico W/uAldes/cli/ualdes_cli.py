#!/usr/bin/env python3
"""
uAldes CLI - Command line interface for uAldes HTTP API
"""

import argparse
import cmd
import json
import os
import readline
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def http_get(url, timeout=5):
    """Make HTTP/1.0 GET request (ESP8285 doesn't handle HTTP/1.1 well)"""
    # Parse URL
    if url.startswith("http://"):
        url = url[7:]

    if "/" in url:
        host_port, path = url.split("/", 1)
        path = "/" + path
    else:
        host_port = url
        path = "/"

    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 80

    # Create socket and connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))

    # Send HTTP/1.0 request
    request = f"GET {path} HTTP/1.0\r\nHost: {host}\r\n\r\n"
    sock.sendall(request.encode())

    # Receive response
    response = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break

    sock.close()

    # Parse response
    response = response.decode()
    if "\r\n\r\n" in response:
        headers, body = response.split("\r\n\r\n", 1)
        return body
    return response


def http_post(url, body, timeout=10):
    """Make HTTP/1.0 POST request"""
    if url.startswith("http://"):
        url = url[7:]

    if "/" in url:
        host_port, path = url.split("/", 1)
        path = "/" + path
    else:
        host_port = url
        path = "/"

    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 80

    if isinstance(body, str):
        body = body.encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))

    request = f"POST {path} HTTP/1.0\r\nHost: {host}\r\nContent-Length: {len(body)}\r\n\r\n"
    sock.sendall(request.encode() + body)

    response = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break

    sock.close()

    response = response.decode()
    if "\r\n\r\n" in response:
        headers, body = response.split("\r\n\r\n", 1)
        return body
    return response


# History file for persistent command history
HISTORY_FILE = os.path.expanduser("~/.ualdes_history")


def get_local_ip():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def check_port_open(ip, port=80, timeout=3.0):
    """Quick check if port is open using socket"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_ualdes(ip, timeout=3):
    """Check if IP is a uAldes device"""
    try:
        response = http_get(f"http://{ip}/ualdes", timeout=timeout)
        data = json.loads(response)
        if data.get("ualdes") == True:
            return ip
    except Exception:
        pass
    return None


def discover_devices():
    """Scan local network for uAldes device (only one can exist)"""
    local_ip = get_local_ip()
    if not local_ip:
        print("Error: Could not determine local IP address")
        return []

    # Get network prefix (e.g., 192.168.1.)
    prefix = ".".join(local_ip.split(".")[:-1]) + "."
    print(f"Scanning network {prefix}0/24 ...")

    found_device = None
    stop_scan = False
    ips_to_scan = [f"{prefix}{i}" for i in range(1, 255)]

    def check_and_verify(ip):
        """Check port and verify uAldes API if open"""
        nonlocal stop_scan
        if stop_scan:
            return None
        if check_port_open(ip):
            if stop_scan:
                return None
            print(f"  Port 80 open: {ip}")
            result = check_ualdes(ip, timeout=5)
            if result:
                return result
        return None

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_and_verify, ip): ip for ip in ips_to_scan}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    found_device = result
                    stop_scan = True
                    print(f"  -> Found uAldes: {result}")
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break
            except Exception:
                pass

    return [found_device] if found_device else []


# Human-readable labels for status fields
FIELD_LABELS = {
    "Etat": "State",
    "Soft": "Firmware version",
    "T_vmc": "VMC temperature",
    "T_hp": "HP temperature",
    "T_evap": "Evaporator temp",
    "T_haut": "High temperature",
    "T_bas": "Low temperature",
    "Comp_C": "Compressor C",
    "Comp_R": "Compressor R",
    "DP": "Delta pressure",
    "Ventil_flow": "Ventilation flow",
    "Ventil_rpm": "Fan speed",
}

FIELD_UNITS = {
    "T_vmc": "C",
    "T_hp": "C",
    "T_evap": "C",
    "T_haut": "C",
    "T_bas": "C",
    "Ventil_rpm": "RPM",
}


def visual_len(s):
    """Calculate visual length of string (accounting for wide chars)"""
    # Count characters, accented chars count as 1
    return len(s)


def pad_right(s, width):
    """Pad string to width, accounting for accented characters"""
    visual = len(s)
    return s + " " * (width - visual)


def pad_left(s, width):
    """Pad string to width on the left"""
    visual = len(s)
    return " " * (width - visual) + s


def format_status(data):
    """Format status data for human-readable output"""
    if not data:
        return "No data available"

    lines = []
    lines.append("+-------------------------------------+")
    lines.append("|           ALDES STATUS              |")
    lines.append("+-------------------------------------+")

    # Check for staleness warning
    warning = data.get("_warning")
    updated_ago = data.get("_updated_ago")

    if warning:
        lines.append(f"| ⚠️  {warning:<32} |")
        lines.append("+-------------------------------------+")
    elif updated_ago is not None and updated_ago >= 0:
        age_str = f"Updated {updated_ago}s ago"
        lines.append(f"| {age_str:^35} |")
        lines.append("+-------------------------------------+")

    for key in sorted(data.keys()):
        # Skip metadata fields
        if key.startswith("_"):
            continue
        value = data[key]
        label = FIELD_LABELS.get(key, key)
        unit = FIELD_UNITS.get(key, "")
        if unit:
            value_str = f"{value} {unit}"
        else:
            value_str = str(value)
        # Fixed width: 37 chars inside, label 20, value 15
        line = f"| {label:<20} {value_str:>14} |"
        lines.append(line)

    lines.append("+-------------------------------------+")
    return "\n".join(lines)


INFO_LABELS = {
    "version": "Version",
    "ip": "IP Address",
    "uptime": "Uptime",
    "uptime_seconds": "Uptime (seconds)",
    "requests": "Requests",
    "status_cached": "Status cached",
    "status_age": "Status age (s)",
    "boot_count": "Boot count",
    "reconnection_count": "Reconnections",
}


def format_info(data):
    """Format device info for human-readable output"""
    if not data:
        return "No data available"

    lines = []
    lines.append("+-------------------------------------+")
    lines.append("|           DEVICE INFO               |")
    lines.append("+-------------------------------------+")

    for key in sorted(data.keys()):
        value = data[key]
        label = INFO_LABELS.get(key, key)
        line = f"| {label:<18} {str(value):>16} |"
        lines.append(line)

    lines.append("+-------------------------------------+")
    return "\n".join(lines)


def format_time(data):
    """Format time data"""
    W = 37  # Same width as status/info
    lines = []
    lines.append("+" + "-" * W + "+")
    lines.append(f"| {'DEVICE TIME':^{W-2}} |")
    lines.append("+" + "-" * W + "+")
    lines.append(f"| {data.get('formatted', 'unknown'):^{W-2}} |")
    lines.append("+" + "-" * W + "+")
    return "\n".join(lines)


def format_log(data):
    """Format log data"""
    W = 60
    logs = data.get("log", [])
    total = data.get("total_lines", len(logs))
    lines = []
    lines.append("+" + "-" * W + "+")
    lines.append(f"| {'DEBUG LOG':^{W-2}} |")
    lines.append(f"| {f'Showing {len(logs)}/{total} lines':^{W-2}} |")
    lines.append("+" + "-" * W + "+")
    for log in logs:
        if log.strip():
            text = log[:W-2]  # Truncate if too long
            lines.append(f"| {text:<{W-2}} |")
    lines.append("+" + "-" * W + "+")
    return "\n".join(lines)


def format_schedules(data):
    """Format schedules data"""
    W = 60
    schedules = data.get("schedules", [])
    date = data.get("date", "unknown")
    lines = []
    lines.append("+" + "-" * W + "+")
    lines.append(f"| {'SCHEDULES':^{W-2}} |")
    lines.append(f"| {'Date: ' + str(date):^{W-2}} |")
    lines.append("+" + "-" * W + "+")
    if not schedules:
        lines.append(f"| {'No schedules configured':^{W-2}} |")
    for sched in schedules:
        idx = sched.get("index", "?")
        hour = sched.get("hour", 0)
        minute = sched.get("minute", 0)
        cmd = sched.get("command", {})
        cmd_type = cmd.get("type", "?")
        params = cmd.get("params", {})
        enabled = "+" if sched.get("enabled", True) else "-"
        executed = sched.get("executed")
        param_str = ""
        if params:
            param_str = " " + " ".join(f"{k}={v}" for k, v in params.items())
        exec_str = ""
        if executed:
            exec_time = executed.get("time", "?")
            exec_status = "OK" if executed.get("success") else "FAIL"
            exec_str = f" [{exec_time}: {exec_status}]"
        text = f"{idx}: [{enabled}] {hour:02d}:{minute:02d} -> {cmd_type}{param_str}{exec_str}"
        lines.append(f"| {text:<{W-2}} |")
        # Show output if present
        if executed:
            exec_output = executed.get("output")
            if exec_output and isinstance(exec_output, dict):
                for k, v in exec_output.items():
                    out_text = f"    {k}: {v}"[:W-2]
                    lines.append(f"| {out_text:<{W-2}} |")
    lines.append("+" + "-" * W + "+")
    return "\n".join(lines)


def format_files(data):
    """Format file list"""
    files = data.get("files", [])
    lines = []
    lines.append("+-------------------------------------+")
    lines.append("|          FILES ON DEVICE            |")
    lines.append("+-------------------------------------+")
    for f in files:
        name = f.get("name", "?")
        size = f.get("size", "?")
        lines.append(f"| {name:<26} {size:>8} |")
    lines.append("+-------------------------------------+")
    return "\n".join(lines)


def format_help_api(data):
    """Format API help"""
    # Border is 50 dashes = 52 total, interior is 48 chars
    endpoints = data.get("endpoints", {})
    lines = []
    lines.append("+--------------------------------------------------+")
    lines.append("|                API DOCUMENTATION                 |")
    title = data.get('api', 'uAldes API') + ' v' + data.get('version', '?')
    lines.append(f"| {title:^48} |")
    lines.append("+--------------------------------------------------+")
    for ep, info in sorted(endpoints.items()):
        desc = info.get("description", "")[:33]
        lines.append(f"| {ep:<14}{desc:<34} |")
        params = info.get("params", {})
        if params:
            for k, v in params.items():
                pstr = f"{k}={v}"[:46]
                lines.append(f"|   {pstr:<46} |")
    lines.append("+--------------------------------------------------+")
    return "\n".join(lines)


def format_response(data):
    """Format command response for human-readable output"""
    if not data:
        return "No response"

    if "error" in data:
        return f"Error: {data['error']}"

    # Special formatting for info endpoint
    if "uptime" in data and "version" in data and "ip" in data:
        return format_info(data)

    # Time endpoint
    if "formatted" in data and "hour" in data and "minute" in data:
        return format_time(data)

    # Log endpoint
    if "log" in data and "total_lines" in data:
        return format_log(data)

    # Schedules endpoint
    if "schedules" in data:
        return format_schedules(data)

    # Files list endpoint
    if "files" in data:
        return format_files(data)

    # API help endpoint
    if "endpoints" in data and "api" in data:
        return format_help_api(data)

    # Command success responses
    if "status" in data and data["status"] == "ok":
        cmd = data.get("command", "")
        msg = data.get("message", "")
        test = " (test)" if data.get("test") else ""

        if cmd == "auto":
            return f"OK: Auto mode enabled{test}"
        elif cmd == "boost":
            return f"OK: Boost mode enabled{test}"
        elif cmd == "confort":
            duration = data.get("duration", "?")
            return f"OK: Comfort mode enabled for {duration} days{test}"
        elif cmd == "vacances":
            duration = data.get("duration", "?")
            return f"OK: Vacation mode enabled for {duration} days{test}"
        elif cmd == "temp":
            temp = data.get("temperature", "?")
            return f"OK: Temperature set to {temp}C{test}"
        elif msg:
            return f"OK: {msg}"
        else:
            return "OK"

    # Handle skipped commands (e.g., boost with min_temp condition not met)
    if "status" in data and data["status"] == "skipped":
        cmd = data.get("command", "")
        reason = data.get("reason", "condition not met")
        return f"SKIPPED: {cmd} - {reason}"

    return json.dumps(data, indent=2)


# Default API structure (used when device is unreachable)
DEFAULT_API = {
    "api": "uAldes HTTP API",
    "version": "1.0",
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
            "params": {"min_temp": "only run if T_haut < value (optional)"},
            "example": "curl 'http://{ip}/boost?min_temp=22'"
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
        },
        "/schedules": {
            "description": "Manage scheduled commands",
            "params": {"action": "list|add|edit|remove", "hour": "0-23", "minute": "0-59", "type": "command type", "min_temp": "boost condition"},
            "example": "curl 'http://{ip}/schedules?action=add&hour=5&minute=0&type=boost&min_temp=42'"
        }
    },
    "test_mode": "Add --test to any command to get fake data without sending commands"
}


class UAldesCLI(cmd.Cmd):
    """Interactive CLI for uAldes HTTP API"""

    intro = "uAldes CLI - Type 'help' for available commands, 'quit' to exit"
    prompt = "ualdes> "

    def __init__(self, host, json_output=False):
        super().__init__()
        self.host = host
        self.base_url = f"http://{host}"
        self.api_doc = None
        self.endpoints = {}
        self.connected = False
        self.json_output = json_output
        self._load_api_doc()
        self._register_commands()
        self._setup_readline()

    def _setup_readline(self):
        """Setup readline with history and completion"""
        readline.set_completer_delims(' \t\n')
        readline.parse_and_bind('tab: complete')
        # Load history
        try:
            if os.path.exists(HISTORY_FILE):
                readline.read_history_file(HISTORY_FILE)
        except Exception:
            pass

    def _save_history(self):
        """Save command history"""
        try:
            readline.write_history_file(HISTORY_FILE)
        except Exception:
            pass

    def _load_api_doc(self):
        """Load API documentation from /help endpoint"""
        try:
            response = http_get(f"{self.base_url}/help", timeout=5)
            self.api_doc = json.loads(response)
            self.endpoints = self.api_doc.get("endpoints", {})
            self.connected = True
            print(f"Connected to {self.host}")
            print(f"API: {self.api_doc.get('api', 'unknown')} v{self.api_doc.get('version', '?')}")
        except Exception as e:
            print(f"Warning: Cannot connect to {self.host}: {e}")
            print("Using default API structure. Use 'reconnect' when device is available.")
            self.api_doc = DEFAULT_API
            self.endpoints = DEFAULT_API["endpoints"]
            self.connected = False

    def _get_command_names(self):
        """Get command names from endpoints"""
        return [ep.lstrip('/') for ep in self.endpoints.keys()]

    def _register_commands(self):
        """Dynamically register do_ and complete_ methods for each endpoint"""
        for endpoint, info in self.endpoints.items():
            cmd_name = endpoint.lstrip('/')
            params = info.get("params", {})
            description = info.get("description", "")
            example = info.get("example", "").replace("{ip}", self.host)

            # Build docstring
            doc_parts = [description]
            if params:
                doc_parts.append(f"Params: {', '.join(f'{k}={v}' for k, v in params.items())}")
            if example:
                doc_parts.append(f"Example: {example}")
            doc_parts.append("Add --test for test mode")
            docstring = "\n".join(doc_parts)

            # Create do_ method
            def make_do_method(ep, param_info, doc):
                is_status_endpoint = (ep == "/status")
                def do_method(self, arg):
                    params = {}
                    args = arg.split()
                    for a in args:
                        if a == "--test":
                            params["test"] = "1"
                        elif "=" in a:
                            k, v = a.split("=", 1)
                            params[k] = v
                        else:
                            # Auto-assign to first param if available
                            if param_info:
                                first_param = list(param_info.keys())[0]
                                if first_param not in params:
                                    params[first_param] = a
                    self._request(ep, params if params else None, is_status=is_status_endpoint)
                do_method.__doc__ = doc
                return do_method

            setattr(UAldesCLI, f"do_{cmd_name}", make_do_method(endpoint, params, docstring))

            # Create complete_ method
            def make_complete_method(param_info):
                def complete_method(self, text, line, begidx, endidx):
                    options = ["--test"]
                    for param_name in param_info.keys():
                        options.append(f"{param_name}=")
                    return [s for s in options if s.startswith(text)]
                return complete_method

            setattr(UAldesCLI, f"complete_{cmd_name}", make_complete_method(params))

    def _request(self, endpoint, params=None, is_status=False, retries=2, silent=False):
        """Make HTTP request to API with retry logic"""
        url = f"{self.base_url}{endpoint}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

        for attempt in range(retries + 1):
            try:
                response = http_get(url, timeout=5)
                data = json.loads(response)
                if not silent:
                    if self.json_output:
                        print(json.dumps(data, indent=2))
                    elif is_status:
                        print(format_status(data))
                    else:
                        print(format_response(data))
                time.sleep(0.3)  # Small delay after successful request
                return data
            except Exception as e:
                if attempt < retries:
                    time.sleep(0.5)  # Wait before retry
                    continue
                if self.json_output:
                    print(json.dumps({"error": str(e)}))
                elif "timed out" in str(e).lower():
                    print("Error: Connection timeout. Is the device reachable?")
                elif "connection" in str(e).lower():
                    print("Error: Connection interrupted. Try again.")
                else:
                    print(f"Error: {e}")
                return None
            except json.JSONDecodeError:
                if self.json_output:
                    print(json.dumps({"error": "Invalid JSON response"}))
                else:
                    print("Error: Invalid JSON response")
                return None
        return None

    def do_help_api(self, arg):
        """Show full API documentation from device"""
        if self.api_doc:
            print(format_help_api(self.api_doc))
        else:
            print("API documentation not available.")

    def do_reconnect(self, arg):
        """Reconnect to the device and reload API"""
        self._load_api_doc()
        self._register_commands()
        if self.connected:
            print(f"Available commands: {', '.join(self._get_command_names())}")

    def do_raw(self, arg):
        """Make raw request. Usage: raw <endpoint> [param=value ...]"""
        args = arg.split()
        if not args:
            print("Usage: raw <endpoint> [param=value ...]")
            return
        endpoint = args[0] if args[0].startswith("/") else f"/{args[0]}"
        params = {}
        for a in args[1:]:
            if "=" in a:
                k, v = a.split("=", 1)
                params[k] = v
        self._request(endpoint, params if params else None)

    def do_curl(self, arg):
        """Show curl command for endpoint. Usage: curl <command> [params]"""
        if not arg:
            print("Usage: curl <command> [param=value ...]")
            return
        args = arg.split()
        endpoint = args[0] if args[0].startswith("/") else f"/{args[0]}"
        params = []
        for a in args[1:]:
            if "=" in a:
                params.append(a)
        url = f"{self.base_url}{endpoint}"
        if params:
            url += "?" + "&".join(params)
        print(f"curl '{url}'")

    def complete_curl(self, text, line, begidx, endidx):
        return [s for s in self._get_command_names() if s.startswith(text)]

    def complete_raw(self, text, line, begidx, endidx):
        return [s for s in self._get_command_names() if s.startswith(text)]

    def do_quit(self, arg):
        """Exit the CLI"""
        self._save_history()
        print("Goodbye!")
        return True

    def do_exit(self, arg):
        """Exit the CLI"""
        return self.do_quit(arg)

    def do_EOF(self, arg):
        """Exit on Ctrl+D"""
        print()
        return self.do_quit(arg)


def main():
    parser = argparse.ArgumentParser(description="uAldes CLI - Control your Aldes ventilation system")
    parser.add_argument("host", nargs="?", help="Device IP address (e.g., 192.168.1.79)")
    parser.add_argument("-c", "--command", help="Execute single command and exit")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    parser.add_argument("--discover", action="store_true", help="Scan network to find uAldes devices")

    args = parser.parse_args()

    # Discovery mode
    if args.discover:
        devices = discover_devices()
        if devices:
            print(f"\nFound {len(devices)} device(s):")
            for d in devices:
                print(f"  - {d}")
            if len(devices) == 1:
                print(f"\nUse: {sys.argv[0]} {devices[0]}")
        else:
            print("No uAldes devices found on the network")
        sys.exit(0)

    # Auto-discover if no host provided
    if not args.host:
        print("No host specified, scanning network...")
        devices = discover_devices()
        if len(devices) == 1:
            args.host = devices[0]
            print(f"Using discovered device: {args.host}\n")
        elif len(devices) > 1:
            print(f"\nMultiple devices found. Please specify one:")
            for d in devices:
                print(f"  {sys.argv[0]} {d}")
            sys.exit(1)
        else:
            print("No devices found. Please specify IP address:")
            print(f"  {sys.argv[0]} <IP_ADDRESS>")
            sys.exit(1)

    cli = UAldesCLI(args.host, json_output=args.json)

    if args.command:
        cli.onecmd(args.command)
    else:
        try:
            cli.cmdloop()
        except KeyboardInterrupt:
            cli._save_history()
            print("\nGoodbye!")


if __name__ == "__main__":
    main()
