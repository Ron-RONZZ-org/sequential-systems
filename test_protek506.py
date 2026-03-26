import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from protek506 import Measurement, Protek506


class Protek506Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.meter = Protek506(port="COM1")

    def test_parse_frame_valid(self) -> None:
        measurement = self.meter.parse_frame("+12342VACOL   ")
        self.assertIsInstance(measurement, Measurement)
        self.assertAlmostEqual(measurement.value, 12.34)
        self.assertEqual(measurement.unit, "V")
        self.assertTrue(measurement.flags["ac"])
        self.assertTrue(measurement.flags["overload"])

    def test_parse_frame_invalid_sign(self) -> None:
        with self.assertRaises(ValueError):
            self.meter.parse_frame("*12342VXXXXXXX")

    def test_read_frame_timeout(self) -> None:
        self.meter.ser = Mock()
        self.meter.ser.read.return_value = b"+123"
        with self.assertRaises(TimeoutError):
            self.meter.read_frame()

    def test_read_frame_non_ascii(self) -> None:
        self.meter.ser = Mock()
        self.meter.ser.read.return_value = b"\xff" * 14
        with self.assertRaises(ValueError):
            self.meter.read_frame()

    def test_read_measurement_reads_and_parses(self) -> None:
        self.meter.ser = Mock()
        self.meter.ser.read.return_value = b"+01032ADC     "
        measurement = self.meter.read_measurement()
        self.assertAlmostEqual(measurement.value, 1.03)
        self.assertEqual(measurement.unit, "A")
        self.assertTrue(measurement.flags["dc"])

    def test_open_uses_required_serial_settings(self) -> None:
        serial_ctor = Mock(return_value=Mock(is_open=True))
        fake_serial = SimpleNamespace(
            Serial=serial_ctor,
            SEVENBITS=7,
            PARITY_EVEN="E",
            STOPBITS_ONE=1,
        )
        with patch("protek506.serial", fake_serial):
            self.meter.open()

        serial_ctor.assert_called_once_with(
            port="COM1",
            baudrate=2400,
            bytesize=7,
            parity="E",
            stopbits=1,
            timeout=1.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )


if __name__ == "__main__":
    unittest.main()
