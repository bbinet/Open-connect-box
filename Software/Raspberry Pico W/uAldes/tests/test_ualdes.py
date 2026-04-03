"""
Pytest tests for ualdes.py

Run with: pytest tests/test_ualdes.py -v
"""

import pytest
import json


class TestChecksum:
    """Tests for checksum calculation and verification"""

    def test_checksum_calculation(self):
        """Test that checksum is calculated correctly"""
        import ualdes

        # Frame with known checksum - the function returns what the checksum SHOULD be
        # For a valid frame, aldes_checksum(data) should equal data[-1]
        data = [0xFD, 0xA0, 0x09, 0xA0, 0xFF, 0x01, 0xFF, 0xFF, 0x9F, 0x00]  # placeholder checksum
        # Calculate expected: -sum([0xFD, 0xA0, 0x09, 0xA0, 0xFF, 0x01, 0xFF, 0xFF, 0x9F]) & 0xFF
        expected = (-sum(data[:-1])) & 0xFF
        checksum = ualdes.aldes_checksum(data)
        assert checksum == expected

    def test_checksum_is_twos_complement(self):
        """Test that checksum is 2's complement of sum"""
        import ualdes

        data = [0x01, 0x02, 0x03, 0x04, 0x00]  # Last byte is placeholder
        expected = (-sum(data[:-1])) & 0xFF
        assert ualdes.aldes_checksum(data) == expected

    def test_checksum_verification_valid(self, sample_valid_frame):
        """Test checksum verification with valid frame"""
        import ualdes

        assert ualdes.aldes_checksum_test(list(sample_valid_frame)) is True

    def test_checksum_verification_invalid(self, sample_valid_frame):
        """Test checksum verification with corrupted frame"""
        import ualdes

        invalid_frame = list(sample_valid_frame)
        invalid_frame[-1] = 0x00  # Corrupt checksum
        assert ualdes.aldes_checksum_test(invalid_frame) is False

    def test_checksum_verification_single_bit_error(self, sample_valid_frame):
        """Test that single bit errors are detected"""
        import ualdes

        corrupted = list(sample_valid_frame)
        corrupted[10] ^= 0x01  # Flip one bit
        assert ualdes.aldes_checksum_test(corrupted) is False


class TestFrameEncode:
    """Tests for frame encoding"""

    def test_encode_auto_mode(self):
        """Test encoding auto mode command"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "auto"}')

        assert frame is not None
        assert len(frame) == 10
        assert frame[0] == 0xFD  # Header
        assert frame[5] == 0x01  # Auto mode code

    def test_encode_boost_mode(self):
        """Test encoding boost mode command"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "boost"}')

        assert frame is not None
        assert frame[5] == 0x02  # Boost mode code

    def test_encode_confort_default_duration(self):
        """Test encoding confort mode with default duration"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "confort"}')

        assert frame is not None
        assert frame[5] == 0x03  # Confort mode code
        assert frame[6] == 0x00
        assert frame[7] == 0x02  # Default 2 days

    def test_encode_confort_custom_duration(self):
        """Test encoding confort mode with custom duration"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "confort", "params": {"duration": 5}}')

        assert frame is not None
        assert frame[7] == 5  # 5 days

    def test_encode_vacances_default_duration(self):
        """Test encoding vacances mode with default duration"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "vacances"}')

        assert frame is not None
        assert frame[5] == 0x04  # Vacances mode code
        assert frame[7] == 0x0A  # Default 10 days

    def test_encode_vacances_custom_duration(self):
        """Test encoding vacances mode with custom duration"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "vacances", "params": {"duration": 14}}')

        assert frame is not None
        assert frame[7] == 14  # 14 days

    def test_encode_temperature(self):
        """Test encoding temperature command"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "temp", "params": {"temperature": 20.5}}')

        assert frame is not None
        assert frame[4] == 41  # 20.5 * 2 = 41

    def test_encode_temperature_integer(self):
        """Test encoding integer temperature"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "temp", "params": {"temperature": 22}}')

        assert frame is not None
        assert frame[4] == 44  # 22 * 2 = 44

    def test_encode_invalid_json(self):
        """Test encoding invalid JSON returns None"""
        import ualdes

        assert ualdes.frame_encode("not valid json") is None
        assert ualdes.frame_encode("{invalid}") is None
        assert ualdes.frame_encode("") is None

    def test_encoded_frame_has_valid_checksum(self):
        """Test that all encoded frames have valid checksums"""
        import ualdes

        commands = [
            '{"type": "auto"}',
            '{"type": "boost"}',
            '{"type": "confort", "params": {"duration": 3}}',
            '{"type": "vacances", "params": {"duration": 7}}',
            '{"type": "temp", "params": {"temperature": 22.5}}',
        ]

        for cmd in commands:
            frame = ualdes.frame_encode(cmd)
            assert frame is not None, f"Failed to encode: {cmd}"
            assert ualdes.aldes_checksum_test(frame), f"Invalid checksum for: {cmd}"

    def test_encode_unknown_type(self):
        """Test encoding unknown command type"""
        import ualdes

        # Unknown type should still return a frame (base frame with checksum)
        frame = ualdes.frame_encode('{"type": "unknown"}')
        assert frame is not None
        assert len(frame) == 10


class TestTemperatureBCD:
    """Tests for BCD temperature decoding"""

    def test_decode_18_5_degrees(self):
        """Test decoding 18.5 degrees (from docstring example)"""
        import ualdes

        # 0x62 = 0110 0010
        # Bits 0-1: 10 = 2 -> 0.5°C
        # Bits 2-7: 0x18 (BCD) = 18°C
        assert ualdes.decode_temperature_bcd(0x62) == 18.5

    def test_decode_zero_degrees(self):
        """Test decoding 0.0 degrees"""
        import ualdes

        assert ualdes.decode_temperature_bcd(0x00) == 0.0

    def test_decode_quarter_degrees(self):
        """Test decoding 0.25 degree increments"""
        import ualdes

        assert ualdes.decode_temperature_bcd(0x00) == 0.0   # 0.00
        assert ualdes.decode_temperature_bcd(0x01) == 0.25  # 0.25
        assert ualdes.decode_temperature_bcd(0x02) == 0.50  # 0.50
        assert ualdes.decode_temperature_bcd(0x03) == 0.75  # 0.75

    def test_decode_one_degree(self):
        """Test decoding 1.0 degree"""
        import ualdes

        # 1 in BCD shifted left by 2 = 0x04
        assert ualdes.decode_temperature_bcd(0x04) == 1.0

    def test_decode_ten_degrees(self):
        """Test decoding 10.0 degrees"""
        import ualdes

        # 10 in BCD = 0x10, shifted left by 2 = 0x40
        assert ualdes.decode_temperature_bcd(0x40) == 10.0


class TestDecodeValue:
    """Tests for value decoding with different types"""

    def test_type_0_passthrough(self):
        """Type 0: Return value as is"""
        import ualdes

        assert ualdes.decode_value(42, 0) == "42"
        assert ualdes.decode_value(0, 0) == "0"
        assert ualdes.decode_value(255, 0) == "255"

    def test_type_1_divide_by_two(self):
        """Type 1: Divide by 2"""
        import ualdes

        assert ualdes.decode_value(42, 1) == "21.0"
        assert ualdes.decode_value(10, 1) == "5.0"
        assert ualdes.decode_value(0, 1) == "0.0"

    def test_type_2_temperature_conversion(self):
        """Type 2: Temperature conversion (value * 0.5 - 20)"""
        import ualdes

        assert ualdes.decode_value(40, 2) == "0.0"   # 40 * 0.5 - 20 = 0
        assert ualdes.decode_value(80, 2) == "20.0"  # 80 * 0.5 - 20 = 20
        assert ualdes.decode_value(42, 2) == "1.0"   # 42 * 0.5 - 20 = 1

    def test_type_3_multiply_by_ten(self):
        """Type 3: Multiply by 10"""
        import ualdes

        assert ualdes.decode_value(42, 3) == "420"
        assert ualdes.decode_value(0, 3) == "0"

    def test_type_4_times_two_minus_one(self):
        """Type 4: value * 2 - 1"""
        import ualdes

        assert ualdes.decode_value(42, 4) == "83"  # 42 * 2 - 1 = 83
        assert ualdes.decode_value(1, 4) == "1"    # 1 * 2 - 1 = 1

    def test_type_5_hex_conversion(self):
        """Type 5: Convert to hex (last 2 chars)"""
        import ualdes

        assert ualdes.decode_value(42, 5) == "2a"   # hex(42) = 0x2a
        assert ualdes.decode_value(255, 5) == "ff"  # hex(255) = 0xff
        assert ualdes.decode_value(16, 5) == "10"   # hex(16) = 0x10

    def test_type_6_bcd_temperature(self):
        """Type 6: BCD temperature decoding"""
        import ualdes

        assert ualdes.decode_value(0x62, 6) == "18.5"

    def test_unknown_type_passthrough(self):
        """Unknown types should return value as is"""
        import ualdes

        assert ualdes.decode_value(42, 99) == "42"
        assert ualdes.decode_value(42, -1) == "42"


class TestFrameDecode:
    """Tests for frame decoding"""

    def test_decode_valid_frame(self, sample_valid_frame, mock_config):
        """Test decoding a valid frame"""
        import ualdes

        decoded = ualdes.frame_decode(list(sample_valid_frame))

        assert decoded is not None
        assert isinstance(decoded, dict)

    def test_decode_valid_frame_has_expected_keys(self, sample_valid_frame, mock_config):
        """Test that decoded frame has expected keys from ITEMS_MAPPING"""
        import ualdes

        decoded = ualdes.frame_decode(list(sample_valid_frame))

        assert decoded is not None
        # Check for keys defined in mock_config ITEMS_MAPPING
        assert "Etat" in decoded

    def test_decode_invalid_checksum_returns_none(self, sample_valid_frame):
        """Test that invalid checksum returns None"""
        import ualdes

        invalid_frame = list(sample_valid_frame)
        invalid_frame[-1] = 0x00  # Corrupt checksum

        decoded = ualdes.frame_decode(invalid_frame)
        assert decoded is None

    def test_decode_empty_frame(self):
        """Test decoding empty frame"""
        import ualdes

        decoded = ualdes.frame_decode([])
        assert decoded is None

    def test_decode_short_frame(self):
        """Test decoding frame that's too short"""
        import ualdes

        # Frame too short for checksum test
        decoded = ualdes.frame_decode([0x33, 0xff])
        assert decoded is None


class TestRoundTrip:
    """Tests for encode/decode round trips"""

    def test_encoded_frames_maintain_structure(self):
        """Test that encoded frames maintain expected structure"""
        import ualdes

        frame = ualdes.frame_encode('{"type": "auto"}')

        assert frame[0] == 0xFD  # Start byte
        assert frame[1] == 0xA0
        assert frame[2] == 0x09
        assert frame[3] == 0xA0
        assert frame[8] == 0x9F  # End marker
        assert len(frame) == 10

    def test_multiple_encodes_are_deterministic(self):
        """Test that encoding the same command gives same result"""
        import ualdes

        cmd = '{"type": "temp", "params": {"temperature": 21.5}}'

        frame1 = ualdes.frame_encode(cmd)
        frame2 = ualdes.frame_encode(cmd)

        assert frame1 == frame2


class TestModeTracking:
    """Tests for mode tracking in frame_encode"""

    def test_auto_mode_tracked(self, reset_time):
        """Test that auto mode is tracked"""
        import ualdes

        ualdes.frame_encode('{"type": "auto"}')
        info = ualdes.get_mode_info()

        assert info["mode"] == "auto"
        assert "set_ago" in info

    def test_boost_mode_tracked(self, reset_time):
        """Test that boost mode is tracked"""
        import ualdes

        ualdes.frame_encode('{"type": "boost"}')
        info = ualdes.get_mode_info()

        assert info["mode"] == "boost"

    def test_confort_mode_tracked_with_duration(self, reset_time):
        """Test that confort mode is tracked with duration"""
        import ualdes

        ualdes.frame_encode('{"type": "confort", "params": {"duration": 3}}')
        info = ualdes.get_mode_info()

        assert info["mode"] == "confort"
        assert info["duration"] == 3
        assert "remaining_seconds" in info
        assert "remaining_days" in info

    def test_vacances_mode_tracked_with_duration(self, reset_time):
        """Test that vacances mode is tracked with duration"""
        import ualdes

        ualdes.frame_encode('{"type": "vacances", "params": {"duration": 7}}')
        info = ualdes.get_mode_info()

        assert info["mode"] == "vacances"
        assert info["duration"] == 7

    def test_temp_command_does_not_change_mode(self, reset_time):
        """Test that temp command doesn't change mode tracking"""
        import ualdes

        # Set initial mode
        ualdes.frame_encode('{"type": "confort", "params": {"duration": 2}}')
        # Send temp command
        ualdes.frame_encode('{"type": "temp", "params": {"temperature": 22}}')

        info = ualdes.get_mode_info()
        assert info["mode"] == "confort"

    def test_remaining_time_decreases(self, reset_time):
        """Test that remaining time decreases over time"""
        import ualdes

        reset_time._reset()
        ualdes.frame_encode('{"type": "confort", "params": {"duration": 1}}')

        info1 = ualdes.get_mode_info()
        remaining1 = info1["remaining_seconds"]

        # Advance time by 1 hour
        reset_time._advance(3600 * 1000)

        info2 = ualdes.get_mode_info()
        remaining2 = info2["remaining_seconds"]

        assert remaining2 < remaining1
        assert remaining1 - remaining2 == 3600

    def test_mode_expired_flag(self, reset_time):
        """Test that expired flag is set when duration passes"""
        import ualdes

        reset_time._reset()
        ualdes.frame_encode('{"type": "confort", "params": {"duration": 1}}')

        # Advance time past 1 day
        reset_time._advance(25 * 3600 * 1000)

        info = ualdes.get_mode_info()
        assert info.get("expired") is True
        assert info["remaining_seconds"] == 0
