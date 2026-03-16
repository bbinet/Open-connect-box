"""
Test Runner for uAldes Project

Runs all unit tests for the project components.

Usage on device:
    import run_tests
    run_tests.run_all()

Or run individual test modules:
    import test_ualdes
    test_ualdes.run_all_tests()
"""

import gc


def run_all():
    """Run all test suites"""
    print("=" * 60)
    print("uAldes Test Suite")
    print("=" * 60)

    results = []

    # Run ualdes tests
    print("\n[1/3] Running ualdes.py tests...")
    gc.collect()
    try:
        import test_ualdes
        passed = test_ualdes.run_all_tests()
        results.append(("ualdes.py", passed))
    except Exception as e:
        print(f"Error running ualdes tests: {e}")
        results.append(("ualdes.py", False))

    # Run espicoW tests
    print("\n[2/3] Running espicoW.py tests...")
    gc.collect()
    try:
        import test_espicoW
        passed = test_espicoW.run_all_tests()
        results.append(("espicoW.py", passed))
    except Exception as e:
        print(f"Error running espicoW tests: {e}")
        results.append(("espicoW.py", False))

    # Run simple_esp tests
    print("\n[3/3] Running simple_esp.py tests...")
    gc.collect()
    try:
        import test_simple_esp
        passed = test_simple_esp.run_all_tests()
        results.append(("simple_esp.py", passed))
    except Exception as e:
        print(f"Error running simple_esp tests: {e}")
        results.append(("simple_esp.py", False))

    # Summary
    print("\n" + "=" * 60)
    print("OVERALL TEST RESULTS")
    print("=" * 60)

    all_passed = True
    for module, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {module}: [{status}]")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("All tests PASSED!")
    else:
        print("Some tests FAILED!")
    print("=" * 60)

    return all_passed


def run_quick():
    """Run only the ualdes tests (fastest)"""
    print("Running quick tests (ualdes only)...")
    gc.collect()
    import test_ualdes
    return test_ualdes.run_all_tests()


def run_hardware_test():
    """
    Run hardware connectivity tests.
    This requires actual hardware (ESP8285 module connected).
    """
    print("=" * 60)
    print("Hardware Connectivity Test")
    print("=" * 60)

    try:
        from config import HARDWARE_CONFIG
    except ImportError:
        print("ERROR: config.py not found")
        return False

    print(f"\nTesting ESP8285 on UART{HARDWARE_CONFIG['esp_uart_id']}")
    print(f"  TX: GP{HARDWARE_CONFIG['esp_tx_pin']}")
    print(f"  RX: GP{HARDWARE_CONFIG['esp_rx_pin']}")
    print(f"  Baudrate: {HARDWARE_CONFIG['esp_baudrate']}")

    try:
        from espicoW import ESPicoW

        wifi = ESPicoW(
            uart_id=HARDWARE_CONFIG['esp_uart_id'],
            tx_pin=HARDWARE_CONFIG['esp_tx_pin'],
            rx_pin=HARDWARE_CONFIG['esp_rx_pin'],
            baudrate=HARDWARE_CONFIG['esp_baudrate'],
            debug=True
        )

        print("\n[1] Testing AT command...")
        if wifi.test():
            print("    [PASS] ESP8285 responding to AT command")
        else:
            print("    [FAIL] ESP8285 not responding")
            return False

        print("\n[2] Getting firmware version...")
        version = wifi.get_version()
        if "AT version" in version:
            print("    [PASS] Got firmware version")
            for line in version.split('\n'):
                if line.strip():
                    print(f"    {line.strip()}")
        else:
            print("    [WARN] Could not get version info")

        print("\n[3] Scanning for WiFi networks...")
        networks = wifi.scan()
        if networks:
            print(f"    [PASS] Found {len(networks)} networks:")
            for net in networks[:5]:  # Show first 5
                print(f"      - {net['ssid']} (RSSI: {net['rssi']})")
        else:
            print("    [WARN] No networks found (may be normal)")

        print("\n" + "=" * 60)
        print("Hardware test completed successfully!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n[ERROR] Hardware test failed: {e}")
        return False


if __name__ == "__main__":
    run_all()
