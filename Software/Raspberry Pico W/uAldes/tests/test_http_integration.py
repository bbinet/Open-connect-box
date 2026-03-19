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


def test_large_http_response(device_ip, target_size=2000):
    """
    Test that HTTP responses larger than ESP8285 single-send limit work.

    Creates temporary schedules to generate a response > target_size bytes,
    then cleans up.
    """
    print(f"\nTesting large HTTP response (target > {target_size} bytes)")
    print("-" * 50)

    # 1. Get initial schedules and their count
    body, _ = http_get(device_ip, "/schedules")
    if not body:
        print("[FAIL] Cannot get initial schedules")
        return False

    initial_data = json.loads(body)
    initial_count = len(initial_data.get("schedules", []))
    initial_size = len(body)
    print(f"Initial: {initial_count} schedules, {initial_size} bytes")

    # 2. Add schedules until response exceeds target size
    added_indices = []
    current_size = initial_size

    try:
        hour = 0
        while current_size < target_size and hour < 24:
            # Add a schedule
            path = f"/schedules?action=add&hour={hour}&minute=30&type=status"
            resp, _ = http_get(device_ip, path)
            if resp:
                result = json.loads(resp)
                if result.get("status") == "ok":
                    added_indices.append(result.get("index"))
                    print(f"  Added schedule at {hour:02d}:30 (index {result.get('index')})")

            time.sleep(0.3)  # Small delay between requests

            # Check new size
            body, _ = http_get(device_ip, "/schedules")
            if body:
                current_size = len(body)
                print(f"  Response size: {current_size} bytes")

            hour += 1

        # 3. Final test - can we get the large response?
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
        # 4. Cleanup - remove added schedules (in reverse order since indices shift)
        print("\nCleaning up added schedules...")
        # Re-fetch to get current indices
        body, _ = http_get(device_ip, "/schedules")
        if body:
            data = json.loads(body)
            current_count = len(data.get("schedules", []))
            # Remove from the end to avoid index shifting issues
            for i in range(current_count - 1, initial_count - 1, -1):
                path = f"/schedules?action=remove&index={i}"
                http_get(device_ip, path)
                time.sleep(0.2)
            print(f"  Removed {current_count - initial_count} schedules")


def run_tests(device_ip):
    """Run all HTTP integration tests"""
    print(f"Testing device at {device_ip}")
    print("=" * 50)

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

    print("\n" + "=" * 50)
    print("All tests passed!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <device-ip>")
        print(f"Example: {sys.argv[0]} 192.168.1.79")
        sys.exit(1)

    device_ip = sys.argv[1]
    success = run_tests(device_ip)
    sys.exit(0 if success else 1)
