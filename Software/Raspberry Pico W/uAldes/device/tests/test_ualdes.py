"""
Unit tests for ualdes.py

Run on device with: import test_ualdes; test_ualdes.run_all_tests()
"""

import ualdes


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def add_fail(self, name, expected, got):
        self.failed += 1
        self.errors.append((name, expected, got))
        print(f"  [FAIL] {name}")
        print(f"         Expected: {expected}")
        print(f"         Got: {got}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"Failed tests: {self.failed}")
        print(f"{'='*50}")
        return self.failed == 0


result = TestResult()


def assert_equal(name, expected, got):
    if expected == got:
        result.add_pass(name)
    else:
        result.add_fail(name, expected, got)


def assert_true(name, condition):
    if condition:
        result.add_pass(name)
    else:
        result.add_fail(name, True, condition)


def assert_false(name, condition):
    if not condition:
        result.add_pass(name)
    else:
        result.add_fail(name, False, condition)


def assert_is_none(name, value):
    if value is None:
        result.add_pass(name)
    else:
        result.add_fail(name, None, value)


def assert_is_not_none(name, value):
    if value is not None:
        result.add_pass(name)
    else:
        result.add_fail(name, "not None", value)


# =============================================================================
# Checksum Tests
# =============================================================================

def test_checksum_calculation():
    """Test checksum calculation"""
    print("\n--- Checksum Calculation Tests ---")

    # Test data with known checksum (checksum = -sum(data[:-1]) & 0xFF = 0x1D)
    data = [0xFD, 0xA0, 0x09, 0xA0, 0xFF, 0x01, 0xFF, 0xFF, 0x9F, 0x1D]
    checksum = ualdes.aldes_checksum(data)
    assert_equal("checksum_known_data", 0x1D, checksum)

    # Test auto command checksum
    auto_frame = [0xFD, 0xA0, 0x09, 0xA0, 0xFF, 0x01, 0xFF, 0xFF, 0x9F, 0x00]
    expected_checksum = -sum(auto_frame[:-1]) & 0xFF
    auto_frame[-1] = expected_checksum
    assert_equal("checksum_auto_frame", expected_checksum, ualdes.aldes_checksum(auto_frame))


def test_checksum_verification():
    """Test checksum verification"""
    print("\n--- Checksum Verification Tests ---")

    # Valid frame
    valid_data = [0x33, 0xff, 0x4c, 0x33, 0x26, 0x00, 0x01, 0x01, 0x98, 0x03,
                  0x00, 0x00, 0x88, 0x00, 0x00, 0x28, 0x95, 0x03, 0x00, 0x00,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0x00, 0x00,
                  0x00, 0x00, 0x56, 0x56, 0x56, 0x00, 0x93, 0x8b, 0xff, 0x03,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x81,
                  0xc7, 0x2c, 0x01, 0x00, 0x00, 0x00, 0x00, 0xb0, 0xda, 0x38,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00, 0x00,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x32, 0x7a]
    assert_true("checksum_valid_frame", ualdes.aldes_checksum_test(valid_data))

    # Invalid frame (corrupted checksum)
    invalid_data = valid_data.copy()
    invalid_data[-1] = 0x00  # Wrong checksum
    assert_false("checksum_invalid_frame", ualdes.aldes_checksum_test(invalid_data))


# =============================================================================
# Frame Encoding Tests
# =============================================================================

def test_frame_encode_auto():
    """Test encoding auto mode command"""
    print("\n--- Frame Encoding Tests (Auto) ---")

    command = '{"type": "auto"}'
    frame = ualdes.frame_encode(command)

    assert_is_not_none("auto_frame_not_none", frame)
    assert_equal("auto_frame_length", 10, len(frame))
    assert_equal("auto_frame_header", 0xFD, frame[0])
    assert_equal("auto_frame_cmd_byte", 0x01, frame[5])


def test_frame_encode_boost():
    """Test encoding boost mode command"""
    print("\n--- Frame Encoding Tests (Boost) ---")

    command = '{"type": "boost"}'
    frame = ualdes.frame_encode(command)

    assert_is_not_none("boost_frame_not_none", frame)
    assert_equal("boost_frame_cmd_byte", 0x02, frame[5])


def test_frame_encode_confort():
    """Test encoding confort mode command"""
    print("\n--- Frame Encoding Tests (Confort) ---")

    # Default duration
    command = '{"type": "confort"}'
    frame = ualdes.frame_encode(command)

    assert_is_not_none("confort_frame_not_none", frame)
    assert_equal("confort_frame_cmd_byte", 0x03, frame[5])
    assert_equal("confort_frame_param1", 0x00, frame[6])
    assert_equal("confort_frame_default_duration", 0x02, frame[7])

    # Custom duration
    command = '{"type": "confort", "params": {"duration": 5}}'
    frame = ualdes.frame_encode(command)
    assert_equal("confort_frame_custom_duration", 5, frame[7])


def test_frame_encode_vacances():
    """Test encoding vacances mode command"""
    print("\n--- Frame Encoding Tests (Vacances) ---")

    # Default duration
    command = '{"type": "vacances"}'
    frame = ualdes.frame_encode(command)

    assert_is_not_none("vacances_frame_not_none", frame)
    assert_equal("vacances_frame_cmd_byte", 0x04, frame[5])
    assert_equal("vacances_frame_default_duration", 0x0A, frame[7])

    # Custom duration
    command = '{"type": "vacances", "params": {"duration": 14}}'
    frame = ualdes.frame_encode(command)
    assert_equal("vacances_frame_custom_duration", 14, frame[7])


def test_frame_encode_temp():
    """Test encoding temperature command"""
    print("\n--- Frame Encoding Tests (Temperature) ---")

    command = '{"type": "temp", "params": {"temperature": 20.5}}'
    frame = ualdes.frame_encode(command)

    assert_is_not_none("temp_frame_not_none", frame)
    # 20.5 * 2 = 41
    assert_equal("temp_frame_value", 41, frame[4])


def test_frame_encode_invalid():
    """Test encoding invalid commands"""
    print("\n--- Frame Encoding Tests (Invalid) ---")

    # Invalid JSON
    frame = ualdes.frame_encode("not json")
    assert_is_none("invalid_json_returns_none", frame)

    # Empty string
    frame = ualdes.frame_encode("")
    assert_is_none("empty_string_returns_none", frame)


# =============================================================================
# Temperature Decoding Tests
# =============================================================================

def test_decode_temperature_bcd():
    """Test BCD temperature decoding"""
    print("\n--- Temperature BCD Decoding Tests ---")

    # Test case from docstring: 0x62 should give 18.5
    # Bits 0-1: 0b10 = 2 -> 2 x 0.25 = 0.5C
    # Bits 2-7: 0x62 >> 2 = 0x18 -> BCD 18 = 18C
    temp = ualdes.decode_temperature_bcd(0x62)
    assert_equal("bcd_temp_0x62", 18.5, temp)

    # Test 0x00 = 0.0C
    temp = ualdes.decode_temperature_bcd(0x00)
    assert_equal("bcd_temp_0x00", 0.0, temp)

    # Test 0x01 = 0.25C (decimal only)
    temp = ualdes.decode_temperature_bcd(0x01)
    assert_equal("bcd_temp_0x01", 0.25, temp)

    # Test 0x04 = 1.0C (1 in BCD, no decimal)
    temp = ualdes.decode_temperature_bcd(0x04)
    assert_equal("bcd_temp_0x04", 1.0, temp)


def test_decode_value():
    """Test value decoding with different types"""
    print("\n--- Value Decoding Tests ---")

    # Type 0: Return as is
    assert_equal("decode_type0", "42", ualdes.decode_value(42, 0))

    # Type 1: Divide by 2
    assert_equal("decode_type1", "21.0", ualdes.decode_value(42, 1))

    # Type 2: Temperature conversion (value * 0.5 - 20)
    assert_equal("decode_type2", "1.0", ualdes.decode_value(42, 2))  # 42 * 0.5 - 20 = 1

    # Type 3: Multiply by 10
    assert_equal("decode_type3", "420", ualdes.decode_value(42, 3))

    # Type 4: value * 2 - 1
    assert_equal("decode_type4", "83", ualdes.decode_value(42, 4))  # 42 * 2 - 1 = 83

    # Type 5: Hex conversion (last 2 chars)
    assert_equal("decode_type5", "2a", ualdes.decode_value(42, 5))  # hex(42) = 0x2a


# =============================================================================
# Frame Decoding Tests
# =============================================================================

def test_frame_decode_valid():
    """Test decoding a valid frame"""
    print("\n--- Frame Decoding Tests (Valid) ---")

    # Example valid frame
    valid_data = [0x33, 0xff, 0x4c, 0x33, 0x26, 0x00, 0x01, 0x01, 0x98, 0x03,
                  0x00, 0x00, 0x88, 0x00, 0x00, 0x28, 0x95, 0x03, 0x00, 0x00,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0x00, 0x00,
                  0x00, 0x00, 0x56, 0x56, 0x56, 0x00, 0x93, 0x8b, 0xff, 0x03,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x81,
                  0xc7, 0x2c, 0x01, 0x00, 0x00, 0x00, 0x00, 0xb0, 0xda, 0x38,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00, 0x00,
                  0x00, 0x00, 0x00, 0x00, 0x00, 0x32, 0x7a]

    decoded = ualdes.frame_decode(valid_data)
    assert_is_not_none("valid_frame_decoded", decoded)
    assert_true("decoded_has_etat", "Etat" in decoded)


def test_frame_decode_invalid():
    """Test decoding an invalid frame"""
    print("\n--- Frame Decoding Tests (Invalid) ---")

    # Frame with bad checksum
    invalid_data = [0x33, 0xff, 0x4c, 0x33, 0x26, 0x00, 0x01, 0x01, 0x00]  # Wrong checksum

    decoded = ualdes.frame_decode(invalid_data)
    assert_is_none("invalid_frame_returns_none", decoded)


# =============================================================================
# Checksum Integrity Tests
# =============================================================================

def test_encoded_frame_checksum():
    """Test that encoded frames have valid checksums"""
    print("\n--- Encoded Frame Checksum Integrity ---")

    commands = [
        '{"type": "auto"}',
        '{"type": "boost"}',
        '{"type": "confort", "params": {"duration": 3}}',
        '{"type": "vacances", "params": {"duration": 7}}',
        '{"type": "temp", "params": {"temperature": 22.5}}',
    ]

    for cmd in commands:
        frame = ualdes.frame_encode(cmd)
        if frame:
            is_valid = ualdes.aldes_checksum_test(frame)
            assert_true(f"checksum_valid_{cmd[:20]}", is_valid)


# =============================================================================
# Run All Tests
# =============================================================================

def run_all_tests():
    """Run all test suites"""
    global result
    result = TestResult()

    print("=" * 50)
    print("Running ualdes.py tests")
    print("=" * 50)

    test_checksum_calculation()
    test_checksum_verification()
    test_frame_encode_auto()
    test_frame_encode_boost()
    test_frame_encode_confort()
    test_frame_encode_vacances()
    test_frame_encode_temp()
    test_frame_encode_invalid()
    test_decode_temperature_bcd()
    test_decode_value()
    test_frame_decode_valid()
    test_frame_decode_invalid()
    test_encoded_frame_checksum()

    return result.summary()


if __name__ == "__main__":
    run_all_tests()
