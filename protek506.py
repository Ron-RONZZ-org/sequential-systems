from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import TypedDict

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None

try:
    from serial.tools import list_ports as serial_list_ports
except ImportError:  # pragma: no cover
    serial_list_ports = None


class MeasurementFlags(TypedDict):
    overload: bool
    ac: bool
    dc: bool
    raw_flags: str


@dataclass
class Measurement:
    value: float
    unit: str
    flags: MeasurementFlags
    raw_frame: str


class Protek506:
    FRAME_LENGTH = 14

    def __init__(self, port: str, timeout: float = 1.0) -> None:
        self.port = port
        self.timeout = timeout
        self.ser = None

    def open(self) -> None:
        if serial is None:
            raise RuntimeError("pyserial is required. Install it with: pip install pyserial")
        self.ser = serial.Serial(  # Configuration from Protek 506 serial protocol.
            port=self.port,
            baudrate=1200,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            timeout=self.timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        # Some USB-serial adapters latch up if modem-control lines are left asserted.
        # Keep both lines low to match the `stty`/`cat` behavior.
        if hasattr(self.ser, "setDTR"):
            self.ser.setDTR(False)
        if hasattr(self.ser, "setRTS"):
            self.ser.setRTS(False)

    def close(self) -> None:
        if self.ser is not None and getattr(self.ser, "is_open", False):
            if hasattr(self.ser, "setDTR"):
                self.ser.setDTR(False)
            if hasattr(self.ser, "setRTS"):
                self.ser.setRTS(False)
            self.ser.close()

    def serial_config_summary(self) -> str:
        return (
            f"port={self.port}, baudrate=1200, bytesize=7, parity=N, "
            f"stopbits=2, timeout={self.timeout}, dtr=low, rts=low"
        )

    def read_frame(self) -> str:
        if self.ser is None:
            raise RuntimeError("Serial port is not open")

        raw = self.ser.read(self.FRAME_LENGTH)
        if len(raw) != self.FRAME_LENGTH:
            raise TimeoutError(
                f"Timeout/incomplete frame: expected {self.FRAME_LENGTH} bytes, got {len(raw)}"
            )
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("Received non-ASCII frame") from exc

    def parse_frame(self, frame: str) -> Measurement:
        """Parse 14-byte Protek506 frame; unit is the single mode character in byte 7."""
        if len(frame) != self.FRAME_LENGTH:
            raise ValueError(f"Malformed frame length: {len(frame)}")

        sign = frame[0]
        digits = frame[1:5]
        decimal_indicator = frame[5]
        unit = frame[6]
        flag_segment = frame[7:]

        if sign not in {"+", "-"}:
            raise ValueError(f"Malformed sign: {sign!r}")
        if not digits.isdigit():
            raise ValueError(f"Malformed digits: {digits!r}")
        if not decimal_indicator.isdigit():
            raise ValueError(f"Malformed decimal indicator: {decimal_indicator!r}")

        decimal_places = int(decimal_indicator)
        magnitude = int(digits) / (10 ** decimal_places)
        value = magnitude if sign == "+" else -magnitude

        flags = {
            "overload": "OL" in frame,
            "ac": "AC" in frame,
            "dc": "DC" in frame,
            "raw_flags": flag_segment.strip(),
        }
        return Measurement(value=value, unit=unit, flags=flags, raw_frame=frame)

    def read_measurement(self) -> Measurement:
        frame = self.read_frame()
        return self.parse_frame(frame)

    def run_forever(self) -> None:
        while True:
            try:
                measurement = self.read_measurement()
                parts = []
                if measurement.flags["overload"]:
                    parts.append("OL")
                if measurement.flags["ac"]:
                    parts.append("AC")
                if measurement.flags["dc"]:
                    parts.append("DC")
                raw_flags = measurement.flags["raw_flags"]
                if raw_flags:
                    parts.append(raw_flags)
                flags_text = ", ".join(parts) if parts else "none"
                print(
                    f"Value: {measurement.value:.6g} {measurement.unit} "
                    f"(flags: {flags_text})"
                )
            except (TimeoutError, ValueError) as exc:
                print(f"Read/parse error: {exc}")

    def diagnose(self) -> None:
        print("=== Protek 506 diagnostic mode ===")
        print(f"Target serial config: {self.serial_config_summary()}")
        if serial is None:
            raise RuntimeError("pyserial is required. Install it with: pip install pyserial")

        version = getattr(serial, "VERSION", "unknown")
        print(f"pyserial version: {version}")

        print("Available ports:")
        try:
            if serial_list_ports is not None:
                ports = serial_list_ports.comports()
            elif hasattr(serial, "tools") and hasattr(serial.tools, "list_ports"):
                ports = serial.tools.list_ports.comports()
            else:
                raise RuntimeError("serial.tools.list_ports is unavailable")
        except Exception as exc:
            print(f"  <failed to enumerate ports: {exc}>")
            ports = []
        if not ports:
            print("  <none>")
        for port_info in ports:
            print(f"  - {port_info.device}")

        try:
            self.open()
            print("Open result: success")
            if self.ser is None:
                print("Probe: serial handle missing after open")
                return

            raw = self.ser.read(self.FRAME_LENGTH)
            hex_bytes = raw.hex(" ")
            print(f"Probe read: {len(raw)} byte(s)")
            print(f"Probe hex: {hex_bytes if hex_bytes else '<empty>'}")

            if raw:
                try:
                    ascii_text = raw.decode("ascii")
                    print(f"Probe ascii: {ascii_text!r}")
                except UnicodeDecodeError:
                    print("Probe ascii: <non-ascii bytes>")

            if len(raw) == self.FRAME_LENGTH:
                try:
                    measurement = self.parse_frame(raw.decode("ascii"))
                    print(
                        "Probe parse: "
                        f"value={measurement.value:.6g} unit={measurement.unit} "
                        f"flags={measurement.flags['raw_flags'] or 'none'}"
                    )
                except (UnicodeDecodeError, ValueError) as exc:
                    print(f"Probe parse: failed ({exc})")
            else:
                print(
                    "Probe parse: skipped (incomplete frame, "
                    f"need {self.FRAME_LENGTH} bytes)"
                )
        except Exception as exc:
            print(f"Open/read failure: {exc}")
        finally:
            self.close()
            print("Serial port closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read measurements from a Protek 506 multimeter.")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial device path.")
    parser.add_argument("--timeout", type=float, default=1.0, help="Serial read timeout in seconds.")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run one-shot serial diagnostics and exit.",
    )
    args = parser.parse_args()

    meter = Protek506(port=args.port, timeout=args.timeout)
    try:
        if args.diagnose:
            meter.diagnose()
        else:
            meter.open()
            meter.run_forever()
    except KeyboardInterrupt:
        print("Stopping Protek 506 reader")
    finally:
        meter.close()
