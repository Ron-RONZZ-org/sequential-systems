from contextlib import redirect_stdout
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from protek506 import Measurement, Protek506


class Protek506Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.meter = Protek506(port="COM1")

    def test_parse_frame_legacy_valid(self) -> None:
        measurement = self.meter.parse_frame("+12342VACOL   ")
        self.assertIsInstance(measurement, Measurement)
        self.assertAlmostEqual(measurement.value or 0.0, 12.34)
        self.assertEqual(measurement.unit, "V")
        self.assertTrue(measurement.flags["ac"])
        self.assertTrue(measurement.flags["overload"])
        self.assertEqual(measurement.mode, "legacy")

    def test_parse_frame_textual_temp_with_noise(self) -> None:
        cleaned = self.meter._sanitize_line("xTEMP 0031 ^C")
        self.assertEqual(cleaned, "TEMP 0031 ^C")
        measurement = self.meter.parse_frame(cleaned)
        self.assertEqual(measurement.mode, "TEMP")
        self.assertAlmostEqual(measurement.value or 0.0, 31.0)

    def test_sanitize_line_uses_first_frame_from_multiframe_chunk(self) -> None:
        raw = "TEMP 0031 ^C\rTEMP 0032 ^C\r\n"
        cleaned = self.meter._sanitize_line(raw)
        self.assertEqual(cleaned, "TEMP 0031 ^C")

    def test_parse_frame_textual_overload(self) -> None:
        measurement = self.meter.parse_frame("DC 0L999mA")
        self.assertEqual(measurement.mode, "DC")
        self.assertIsNone(measurement.value)
        self.assertTrue(measurement.flags["overload"])

    def test_read_frame_triggers_then_reads_line(self) -> None:
        ser = Mock()
        ser.readline.return_value = b"tTEMP 0030 ^C\n"
        self.meter.ser = ser
        with patch("protek506.time.sleep") as sleep_mock:
            frame = self.meter.read_frame()
        self.assertEqual(frame, "TEMP 0030 ^C")
        ser.write.assert_called_once_with(b"218937\n")
        ser.flush.assert_called_once()
        sleep_mock.assert_called_once_with(1.0)

    def test_read_frame_timeout(self) -> None:
        self.meter.ser = Mock()
        self.meter.ser.readline.return_value = b""
        self.meter.ser.read.return_value = b""
        with self.assertRaises(TimeoutError):
            self.meter.read_frame()

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
        fake_serial_handle.readline.return_value = b""
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
        self.assertIn("Trigger payload: '218937\\n'", text)
        self.assertIn("pyserial version: 3.5", text)
        self.assertIn("  - /dev/ttyUSB0", text)
        self.assertIn("Probe read: 0 byte(s)", text)

    def test_visual_mode_missing_seaborn_raises(self) -> None:
        with patch("builtins.__import__", side_effect=ImportError):
            with self.assertRaises(RuntimeError):
                self.meter._create_visualizer()

    def test_run_forever_warns_on_non_interactive_visual_backend(self) -> None:
        visualizer = Mock()
        visualizer.interactive_backend = False
        visualizer.add_point = Mock()
        visualizer.save = Mock()
        measurement = Measurement(
            value=30.0,
            unit="",
            flags={"overload": False, "ac": False, "dc": False, "raw_flags": "0030 ^C"},
            raw_frame="TEMP 0030 ^C",
            mode="TEMP",
        )
        with patch.object(self.meter, "_create_visualizer", return_value=visualizer), patch.object(
            self.meter, "read_measurement", side_effect=[measurement, KeyboardInterrupt]
        ), patch("builtins.print") as print_mock:
            with self.assertRaises(KeyboardInterrupt):
                self.meter.run_forever(visual=True, save_plot="plot.png")
        visualizer.add_point.assert_called_once()
        visualizer.save.assert_called_once_with("plot.png")
        warning_calls = [args[0] for args, _ in print_mock.call_args_list]
        self.assertTrue(any("non-interactive" in call for call in warning_calls))

    def test_read_frame_can_skip_trigger_when_already_emitted(self) -> None:
        ser = Mock()
        ser.readline.return_value = b"TEMP 0030 ^C\n"
        self.meter.ser = ser
        frame = self.meter.read_frame(emit_trigger=False)
        self.assertEqual(frame, "TEMP 0030 ^C")
        ser.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
