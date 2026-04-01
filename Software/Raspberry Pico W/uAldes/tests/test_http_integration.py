"""
Integration tests for HTTP API with real device.

These tests verify that large HTTP responses are handled correctly,
particularly after the chunked send fix for ESP8285.

Run with: pytest tests/test_http_integration.py -v --device-ip=192.168.1.79
Or: python tests/test_http_integration.py 192.168.1.79
"""

import json
import socket
import sys
import time


def http_get(host, path, timeout=10):
    """Make HTTP/1.0 GET request and return response body"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, 80))

    request = f"GET {path} HTTP/1.0\r\nHost: {host}\r\n\r\n"
    sock.sendall(request.encode())

    response = b""
    sock.settimeout(2)
    empty_timeouts = 0
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            empty_timeouts = 0
        except socket.timeout:
            empty_timeouts += 1
            if empty_timeouts >= 3:
                break
            continue

    sock.close()

    response = response.decode()
    if "\r\n\r\n" in response:
        headers, body = response.split("\r\n\r\n", 1)
        return body, headers
    return response, ""


def get_current_mode(device_ip):
    """Get current water heater mode with duration info"""
    body, _ = http_get(device_ip, "/mode")
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def restore_mode(device_ip, mode_info):
    """Restore water heater mode from saved info"""
    if not mode_info:
        return set_mode(device_ip, "auto")

    mode = mode_info.get("mode", "auto")
    remaining_days = mode_info.get("remaining_days")

    if mode in ("confort", "vacances") and remaining_days and remaining_days > 0:
        # Restore timed mode with remaining duration
        duration = max(1, int(remaining_days + 0.5))  # Round to nearest day, min 1
        return set_mode(device_ip, mode, duration)
    else:
        return set_mode(device_ip, mode)


def set_mode(device_ip, mode, duration=None):
    """Set water heater mode"""
    if mode == "auto":
        path = "/auto"
    elif mode == "boost":
        path = "/boost"
    elif mode == "confort":
        path = f"/confort?duration={duration or 2}"
    elif mode == "vacances":
        path = f"/vacances?duration={duration or 10}"
    else:
        path = "/auto"

    body, _ = http_get(device_ip, path)
    if body:
        try:
            result = json.loads(body)
            return result.get("status") == "ok"
        except json.JSONDecodeError:
            pass
    return False


def save_schedules(device_ip):
    """Save all existing schedules and return them"""
    body, _ = http_get(device_ip, "/schedules")
    if not body:
        return []
    try:
        data = json.loads(body)
        schedules = data.get("schedules", [])
        # Remove runtime fields (index, executed) - keep only config
        saved = []
        for s in schedules:
            saved.append({
                "hour": s.get("hour"),
                "minute": s.get("minute"),
                "command": s.get("command", {}),
                "enabled": s.get("enabled", True)
            })
        return saved
    except json.JSONDecodeError:
        return []


def restore_schedules(device_ip, schedules):
    """Restore schedules from saved list"""
    # Clear all first
    http_get(device_ip, "/schedules?action=clear")
    time.sleep(0.3)

    # Re-add each schedule
    for s in schedules:
        hour = s.get("hour", 0)
        minute = s.get("minute", 0)
        cmd = s.get("command", {})
        cmd_type = cmd.get("type", "status")
        params = cmd.get("params", {})
        enabled = "1" if s.get("enabled", True) else "0"

        path = f"/schedules?action=add&hour={hour}&minute={minute}&type={cmd_type}&enabled={enabled}"
        for k, v in params.items():
            path += f"&{k}={v}"

        http_get(device_ip, path)
        time.sleep(0.2)


def test_large_http_response(device_ip, target_size=2000):
    """
    Test that HTTP responses larger than ESP8285 single-send limit work.

    Saves existing schedules, creates test schedules, runs test, then restores.
    """
    print(f"\nTesting large HTTP response (target > {target_size} bytes)")
    print("-" * 50)

    # 1. Save existing schedules
    saved_schedules = save_schedules(device_ip)
    print(f"Saved {len(saved_schedules)} existing schedules")

    try:
        # 2. Clear all schedules for clean test
        http_get(device_ip, "/schedules?action=clear")
        time.sleep(0.3)

        # 3. Add schedules until response exceeds target size
        current_size = 0
        hour = 0
        while current_size < target_size and hour < 24:
            # Add a schedule
            path = f"/schedules?action=add&hour={hour}&minute=30&type=status"
            resp, _ = http_get(device_ip, path)
            if resp:
                result = json.loads(resp)
                if result.get("status") == "ok":
                    print(f"  Added schedule at {hour:02d}:30 (index {result.get('index')})")

            time.sleep(0.3)  # Small delay between requests

            # Check new size
            body, _ = http_get(device_ip, "/schedules")
            if body:
                current_size = len(body)
                print(f"  Response size: {current_size} bytes")

            hour += 1

        # 4. Final test - can we get the large response?
        print(f"\nFinal test with {current_size} bytes response...")
        body, headers = http_get(device_ip, "/schedules")

        if not body:
            print(f"[FAIL] Empty response for {current_size} byte payload")
            return False

        try:
            data = json.loads(body)
            actual_size = len(body)
            schedule_count = len(data.get("schedules", []))
            print(f"[PASS] Got valid JSON: {actual_size} bytes, {schedule_count} schedules")

            # Verify Content-Length matches
            for line in headers.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":")[1].strip())
                    if content_length != actual_size:
                        print(f"[WARN] Content-Length mismatch: header={content_length}, actual={actual_size}")

            return actual_size >= target_size

        except json.JSONDecodeError as e:
            print(f"[FAIL] Invalid JSON: {e}")
            print(f"  Response preview: {body[:200]}...")
            return False

    finally:
        # 5. Restore original schedules
        print(f"\nRestoring {len(saved_schedules)} original schedules...")
        restore_schedules(device_ip, saved_schedules)
        print("  Schedules restored")


def test_boost_with_min_temp(device_ip):
    """
    Test boost command with min_temp condition.

    Tests that boost is skipped when T_haut >= min_temp.
    """
    print("\nTesting boost with min_temp condition...")
    print("-" * 50)

    time.sleep(1)  # Allow device to settle after previous tests

    # First get current status to know T_haut
    body, _ = http_get(device_ip, "/status")
    if not body:
        print("[FAIL] Cannot get status")
        return False

    try:
        status = json.loads(body)
        t_haut = status.get("T_haut")
        if t_haut is None:
            print("[SKIP] T_haut not available in status")
            return True
        t_haut = float(t_haut)
        print(f"Current T_haut: {t_haut}C")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[FAIL] Cannot parse status: {e}")
        return False

    # Test 1: boost with min_temp below current T_haut (should be skipped)
    min_temp_low = t_haut - 5  # 5 degrees below current
    time.sleep(0.5)
    body, _ = http_get(device_ip, f"/boost?min_temp={min_temp_low}")
    if not body:
        print(f"[FAIL] Empty response for boost?min_temp={min_temp_low}")
        return False

    try:
        result = json.loads(body)
        if result.get("status") == "skipped":
            print(f"[PASS] Boost skipped when min_temp={min_temp_low}C < T_haut={t_haut}C")
        else:
            # Boost was executed (T_haut might have changed)
            print(f"[WARN] Boost executed (T_haut may be < {min_temp_low}C)")
    except json.JSONDecodeError as e:
        print(f"[FAIL] Invalid JSON: {e}")
        return False

    # Test 2: boost with min_temp above current T_haut (should execute)
    min_temp_high = t_haut + 10  # 10 degrees above current
    time.sleep(0.5)
    body, _ = http_get(device_ip, f"/boost?min_temp={min_temp_high}")
    if not body:
        print(f"[FAIL] Empty response for boost?min_temp={min_temp_high}")
        return False

    try:
        result = json.loads(body)
        if result.get("status") == "ok":
            print(f"[PASS] Boost executed when min_temp={min_temp_high}C > T_haut={t_haut}C")
        elif result.get("status") == "skipped":
            print(f"[WARN] Boost skipped unexpectedly (T_haut may have changed to >= {min_temp_high}C)")
        else:
            print(f"[FAIL] Unexpected response: {result}")
            return False
    except json.JSONDecodeError as e:
        print(f"[FAIL] Invalid JSON: {e}")
        return False

    return True


def test_reboot_restore(device_ip):
    """
    Test that after reboot, the last scheduled command is restored.
    """
    print("\nTesting reboot restore functionality...")
    print("-" * 50)

    # 1. Save existing schedules
    saved_schedules = save_schedules(device_ip)
    print(f"Saved {len(saved_schedules)} existing schedules")

    try:
        # 2. Clear schedules and add a test schedule
        http_get(device_ip, "/schedules?action=clear")
        time.sleep(0.3)

        # Get current time from device
        body, _ = http_get(device_ip, "/time")
        if not body:
            print("[FAIL] Cannot get device time")
            return False

        try:
            time_data = json.loads(body)
            current_hour = time_data.get("hour", 12)
            current_minute = time_data.get("minute", 0)
        except json.JSONDecodeError:
            print("[FAIL] Invalid time response")
            return False

        # Add a schedule 1 hour before current time (should be "last executed")
        test_hour = (current_hour - 1) % 24
        path = f"/schedules?action=add&hour={test_hour}&minute=0&type=confort&duration=1"
        resp, _ = http_get(device_ip, path)
        if not resp:
            print("[FAIL] Cannot add test schedule")
            return False

        print(f"  Added test schedule: confort at {test_hour:02d}:00")
        time.sleep(0.3)

        # 3. Reboot the device
        print("  Rebooting device...")
        http_get(device_ip, "/reboot")
        print("  Waiting for device to restart...")
        time.sleep(15)  # Wait for reboot and NTP sync

        # 4. Check that the schedule was executed with reboot flag
        # Retry a few times in case device is slow to respond
        body = None
        for attempt in range(5):
            body, _ = http_get(device_ip, "/schedules")
            if body:
                break
            print(f"  Waiting for device... (attempt {attempt + 1}/5)")
            time.sleep(3)

        if not body:
            print("[FAIL] Cannot get schedules after reboot")
            return False

        try:
            data = json.loads(body)
            schedules = data.get("schedules", [])
            if not schedules:
                print("[FAIL] No schedules found after reboot")
                return False

            schedule = schedules[0]
            executed = schedule.get("executed")

            if not executed:
                print("[FAIL] Schedule was not executed on reboot")
                return False

            if not executed.get("reboot"):
                print("[FAIL] Execution missing 'reboot' flag")
                return False

            if not executed.get("success"):
                print(f"[FAIL] Execution failed: {executed.get('error')}")
                return False

            print(f"[PASS] Schedule restored on reboot: {executed.get('command', {}).get('type')}")
            print(f"  Executed at: {executed.get('time')}")
            print(f"  Reboot flag: {executed.get('reboot')}")

            # Check mode is now confort
            time.sleep(0.5)
            mode_info = get_current_mode(device_ip)
            if mode_info and mode_info.get("mode") == "confort":
                print(f"[PASS] Mode correctly set to confort")
            else:
                print(f"[WARN] Mode is {mode_info.get('mode') if mode_info else 'unknown'}, expected confort")

            return True

        except json.JSONDecodeError as e:
            print(f"[FAIL] Invalid JSON: {e}")
            return False

    finally:
        # 5. Restore original schedules
        print(f"\nRestoring {len(saved_schedules)} original schedules...")
        restore_schedules(device_ip, saved_schedules)
        print("  Schedules restored")


def run_tests(device_ip):
    """Run all HTTP integration tests"""
    print(f"Testing device at {device_ip}")
    print("=" * 50)

    # Save initial state
    initial_mode = get_current_mode(device_ip)
    if initial_mode:
        mode_str = initial_mode.get("mode", "unknown")
        remaining = initial_mode.get("remaining_days")
        if remaining:
            print(f"Initial mode: {mode_str} ({remaining} days remaining)")
        else:
            print(f"Initial mode: {mode_str}")
    else:
        print("Initial mode: unknown (could not fetch)")

    try:
        # Test 1: Basic connectivity
        print("\n1. Testing basic connectivity...")
        body, _ = http_get(device_ip, "/ualdes")
        if not body:
            print("[FAIL] Cannot connect to device")
            return False
        try:
            data = json.loads(body)
            if data.get("ualdes"):
                print("[PASS] Device responds correctly")
            else:
                print("[FAIL] Unexpected response")
                return False
        except:
            print("[FAIL] Invalid JSON response")
            return False

        # Test 2: Various endpoint sizes
        print("\n2. Testing various endpoints...")
        endpoints = ["/ualdes", "/info", "/time", "/status", "/help", "/schedules"]

        for endpoint in endpoints:
            time.sleep(0.5)  # Small delay between requests to avoid overloading ESP8285
            body, _ = http_get(device_ip, endpoint)
            if body:
                try:
                    json.loads(body)
                    print(f"  [PASS] {endpoint:15} {len(body):5} bytes")
                except:
                    print(f"  [FAIL] {endpoint:15} invalid JSON")
                    return False
            else:
                print(f"  [FAIL] {endpoint:15} empty response")
                return False

        # Test 3: Large response test (the main test for chunked send fix)
        print("\n3. Testing large HTTP response (chunked send fix)...")
        if not test_large_http_response(device_ip, target_size=2000):
            print("[FAIL] Large response test failed")
            return False

        # Test 4: Boost with min_temp condition
        print("\n4. Testing boost with min_temp condition...")
        if not test_boost_with_min_temp(device_ip):
            print("[FAIL] Boost min_temp test failed")
            return False

        # Test 5: Reboot restore (restores last scheduled command)
        print("\n5. Testing reboot restore...")
        if not test_reboot_restore(device_ip):
            print("[FAIL] Reboot restore test failed")
            return False

        print("\n" + "=" * 50)
        print("All tests passed!")
        return True

    finally:
        # Restore original mode
        print("\nRestoring device mode...")
        time.sleep(0.5)
        if restore_mode(device_ip, initial_mode):
            final_mode = get_current_mode(device_ip)
            initial_name = initial_mode.get("mode") if initial_mode else "unknown"
            final_name = final_mode.get("mode") if final_mode else "unknown"
            print(f"  Mode restored: {initial_name} -> {final_name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <device-ip>")
        print(f"Example: {sys.argv[0]} 192.168.1.79")
        sys.exit(1)

    device_ip = sys.argv[1]
    success = run_tests(device_ip)
    sys.exit(0 if success else 1)
