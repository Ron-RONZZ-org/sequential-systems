from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None


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
        self.ser = serial.Serial(
            port=self.port,
            baudrate=2400,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

    def close(self) -> None:
        if self.ser is not None and getattr(self.ser, "is_open", False):
            self.ser.close()

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


if __name__ == "__main__":
    meter = Protek506(port="/dev/ttyUSB0", timeout=1.0)
    try:
        meter.open()
        meter.run_forever()
    except KeyboardInterrupt:
        print("Stopping Protek 506 reader")
    finally:
        meter.close()
