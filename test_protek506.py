from contextlib import redirect_stdout
import io
from types import SimpleNamespace
import unittest
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
        serial_handle = Mock(is_open=True)
        serial_ctor = Mock(return_value=serial_handle)
        fake_serial = SimpleNamespace(
            Serial=serial_ctor,
            SEVENBITS=7,
            PARITY_NONE="N",
            STOPBITS_TWO=2,
        )
        with patch("protek506.serial", fake_serial):
            self.meter.open()

        serial_ctor.assert_called_once_with(
            port="COM1",
            baudrate=1200,
            bytesize=7,
            parity="N",
            stopbits=2,
            timeout=1.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        serial_handle.setDTR.assert_called_with(False)
        serial_handle.setRTS.assert_called_with(False)

    def test_serial_config_summary(self) -> None:
        meter = Protek506(port="/dev/ttyUSB9", timeout=2.5)
        self.assertEqual(
            meter.serial_config_summary(),
            "port=/dev/ttyUSB9, baudrate=1200, bytesize=7, parity=N, stopbits=2, timeout=2.5, dtr=low, rts=low",
        )

    def test_close_deasserts_modem_lines_before_close(self) -> None:
        serial_handle = Mock(is_open=True)
        self.meter.ser = serial_handle
        self.meter.close()
        serial_handle.setDTR.assert_called_with(False)
        serial_handle.setRTS.assert_called_with(False)
        serial_handle.close.assert_called_once()

    def test_diagnose_prints_probe_for_incomplete_frame(self) -> None:
        fake_serial_handle = Mock(is_open=True)
        fake_serial_handle.read.return_value = b""
        serial_ctor = Mock(return_value=fake_serial_handle)
        fake_port = SimpleNamespace(device="/dev/ttyUSB0")
        fake_serial = SimpleNamespace(
            Serial=serial_ctor,
            SEVENBITS=7,
            PARITY_NONE="N",
            STOPBITS_TWO=2,
            VERSION="3.5",
        )
        fake_list_ports = SimpleNamespace(comports=Mock(return_value=[fake_port]))

        out = io.StringIO()
        with patch("protek506.serial", fake_serial), patch(
            "protek506.serial_list_ports", fake_list_ports
        ):
            with redirect_stdout(out):
                self.meter.diagnose()

        text = out.getvalue()
        self.assertIn("=== Protek 506 diagnostic mode ===", text)
        self.assertIn("pyserial version: 3.5", text)
        self.assertIn("  - /dev/ttyUSB0", text)
        self.assertIn("Probe read: 0 byte(s)", text)
        self.assertIn("Probe parse: skipped (incomplete frame, need 14 bytes)", text)

    def test_diagnose_parses_full_frame(self) -> None:
        fake_serial_handle = Mock(is_open=True)
        fake_serial_handle.read.return_value = b"+01032ADC     "
        serial_ctor = Mock(return_value=fake_serial_handle)
        fake_serial = SimpleNamespace(
            Serial=serial_ctor,
            SEVENBITS=7,
            PARITY_NONE="N",
            STOPBITS_TWO=2,
            VERSION="3.5",
        )
        fake_list_ports = SimpleNamespace(comports=Mock(return_value=[]))

        out = io.StringIO()
        with patch("protek506.serial", fake_serial), patch(
            "protek506.serial_list_ports", fake_list_ports
        ):
            with redirect_stdout(out):
                self.meter.diagnose()

        text = out.getvalue()
        self.assertIn("Probe read: 14 byte(s)", text)
        self.assertIn("Probe parse: value=1.03 unit=A", text)


if __name__ == "__main__":
    unittest.main()
