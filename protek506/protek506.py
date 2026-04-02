from __future__ import annotations

import argparse
import re
import time
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
    value: float | None
    unit: str
    flags: MeasurementFlags
    raw_frame: str
    mode: str


class Protek506:
    FRAME_LENGTH = 14
    DEFAULT_TRIGGER = "218937\n"

    def __init__(
        self,
        port: str,
        timeout: float = 1.0,
        trigger: str = DEFAULT_TRIGGER,
        trigger_interval: float = 1.0,
    ) -> None:
        self.port = port
        self.timeout = timeout
        self.trigger = trigger
        self.trigger_interval = trigger_interval
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

    def trigger_read(self) -> None:
        if self.ser is None:
            raise RuntimeError("Serial port is not open")
        self.ser.write(self.trigger.encode("ascii"))
        if hasattr(self.ser, "flush"):
            self.ser.flush()

    def _read_response_line(self) -> str:
        if self.ser is None:
            raise RuntimeError("Serial port is not open")

        raw = b""
        if hasattr(self.ser, "readline"):
            raw = self.ser.readline()
        if not raw:
            raw = self.ser.read(64)
        if not raw:
            raise TimeoutError("Timeout/incomplete frame: expected response bytes, got 0")

        try:
            return raw.decode("ascii", errors="replace")
        except UnicodeDecodeError as exc:  # pragma: no cover
            raise ValueError("Received non-ASCII frame") from exc

    @staticmethod
    def _sanitize_line(text: str) -> str:
        primary = text.replace("\x00", " ").splitlines()[0] if text else ""
        collapsed = " ".join(primary.split())
        match = re.search(
            r"(DC|AC|RES|BUZZ|DIODE|LOGIC|FREQ|CAP|IND|TEMP)\b[^\r\n]*",
            collapsed,
        )
        if match:
            return match.group(0).strip(" |")

        legacy_match = re.search(r"([+-]\d{4}\d[A-Za-z ].*)", collapsed)
        if legacy_match:
            return legacy_match.group(1).strip()

        return collapsed.strip()

    def read_frame(self, emit_trigger: bool = True) -> str:
        if emit_trigger:
            self.trigger_read()
            if self.trigger_interval > 0:
                time.sleep(self.trigger_interval)
        line = self._read_response_line()
        clean = self._sanitize_line(line)
        if not clean:
            raise ValueError(f"Empty/invalid response after sanitization: {line!r}")
        return clean

    @staticmethod
    def _parse_textual_value(token: str) -> float | None:
        upper = token.upper()
        if "OL" in upper or "0L" in upper:
            return None
        numeric = re.search(r"[-+]?\d+(?:\.\d+)?", token)
        if not numeric:
            return None
        return float(numeric.group(0))

    def parse_frame(self, frame: str) -> Measurement:
        text = frame.rstrip("\r\n")

        if len(text) >= self.FRAME_LENGTH and text[0] in {"+", "-"} and text[1:6].isdigit():
            sign = text[0]
            digits = text[1:5]
            decimal_indicator = text[5]
            unit = text[6]
            flag_segment = text[7:self.FRAME_LENGTH]

            decimal_places = int(decimal_indicator)
            magnitude = int(digits) / (10**decimal_places)
            value = magnitude if sign == "+" else -magnitude
            flags = {
                "overload": "OL" in text,
                "ac": "AC" in text,
                "dc": "DC" in text,
                "raw_flags": flag_segment.strip(),
            }
            return Measurement(value=value, unit=unit, flags=flags, raw_frame=text, mode="legacy")

        parts = text.split(maxsplit=1)
        if not parts:
            raise ValueError("Malformed frame: empty")
        mode = parts[0]
        payload = parts[1] if len(parts) > 1 else ""

        known_modes = {"DC", "AC", "RES", "BUZZ", "DIODE", "LOGIC", "FREQ", "CAP", "IND", "TEMP"}
        if mode not in known_modes:
            raise ValueError(f"Malformed mode prefix: {mode!r}")

        payload_upper = payload.upper()
        value = None if ("OL" in payload_upper or "0L" in payload_upper) else self._parse_textual_value(payload)
        unit = ""
        unit_match = re.search(r"(mV|mA|kHz|Hz|MΩ|Ω|µF|µH|°C|V|A)\b", payload)
        if unit_match:
            unit = unit_match.group(1)

        flags = {
            "overload": ("OL" in payload_upper or "0L" in payload_upper),
            "ac": mode == "AC",
            "dc": mode == "DC",
            "raw_flags": payload,
        }
        return Measurement(value=value, unit=unit, flags=flags, raw_frame=text, mode=mode)

    def read_measurement(self) -> Measurement:
        frame = self.read_frame()
        return self.parse_frame(frame)

    def _create_visualizer(self):
        try:
            import matplotlib.pyplot as plt  # type: ignore
            import seaborn as sns  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "seaborn and matplotlib are required for --visual. Install with: pip install seaborn matplotlib"
            ) from exc

        sns.set_theme(style="darkgrid")
        plt.ion()
        fig, ax = plt.subplots()
        interactive_backend = "agg" not in plt.get_backend().lower()
        ax.set_title("Protek 506 Live Measurements")
        ax.set_xlabel("Sample")
        ax.set_ylabel("Value")
        xs: list[int] = []
        ys: list[float] = []

        class _SeabornVisualizer:
            def __init__(self) -> None:
                self.interactive_backend = interactive_backend

            def add_point(self, _ts: float, value: float) -> None:
                xs.append(len(xs))
                ys.append(value)
                ax.clear()
                sns.lineplot(x=xs, y=ys, ax=ax)
                ax.set_title("Protek 506 Live Measurements")
                ax.set_xlabel("Sample")
                ax.set_ylabel("Value")
                fig.canvas.draw_idle()
                if interactive_backend:
                    plt.pause(0.001)

            def save(self, path: str) -> None:
                fig.savefig(path, bbox_inches="tight")

        return _SeabornVisualizer()

    def run_forever(self, visual: bool = False, save_plot: str | None = None) -> None:
        visualizer = self._create_visualizer() if visual else None
        if visualizer is not None and not visualizer.interactive_backend:
            print(
                "Visual backend is non-interactive; live window is unavailable. "
                "Use --save-plot <path> to save snapshots."
            )
        while True:
            try:
                measurement = self.read_measurement()
                value_text = "n/a" if measurement.value is None else f"{measurement.value:.6g}"
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
                    f"Mode: {measurement.mode} Value: {value_text} {measurement.unit} "
                    f"(flags: {flags_text})"
                )
                if visualizer is not None and measurement.value is not None:
                    visualizer.add_point(time.time(), measurement.value)
                    if save_plot:
                        visualizer.save(save_plot)
            except (TimeoutError, ValueError) as exc:
                print(f"Read/parse error: {exc}")

    def diagnose(self) -> None:
        print("=== Protek 506 diagnostic mode ===")
        print(f"Target serial config: {self.serial_config_summary()}")
        print(f"Trigger payload: {self.trigger!r}")
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

            self.trigger_read()
            if self.trigger_interval > 0:
                time.sleep(self.trigger_interval)
            raw = b""
            if hasattr(self.ser, "readline"):
                raw = self.ser.readline()
            if not raw:
                raw = self.ser.read(64)

            hex_bytes = raw.hex(" ")
            print(f"Probe read: {len(raw)} byte(s)")
            print(f"Probe hex: {hex_bytes if hex_bytes else '<empty>'}")
            if raw:
                print(f"Probe ascii: {raw.decode('ascii', errors='replace')!r}")
            clean = self._sanitize_line(raw.decode("ascii", errors="replace"))
            print(f"Probe sanitized: {clean!r}")

            if clean:
                try:
                    measurement = self.parse_frame(clean)
                    value_text = "n/a" if measurement.value is None else f"{measurement.value:.6g}"
                    print(
                        "Probe parse: "
                        f"mode={measurement.mode} value={value_text} unit={measurement.unit or '-'}"
                    )
                except ValueError as exc:
                    print(f"Probe parse: failed ({exc})")
            else:
                print("Probe parse: skipped (no parsable content)")
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
        "--trigger",
        default=Protek506.DEFAULT_TRIGGER.rstrip("\n"),
        help="ASCII trigger payload written before each read.",
    )
    parser.add_argument(
        "--trigger-interval",
        type=float,
        default=1.0,
        help="Seconds between trigger write and read (continuous polling cadence).",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run one-shot serial diagnostics and exit.",
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help="Graph numeric values dynamically using seaborn/matplotlib.",
    )
    parser.add_argument(
        "--save-plot",
        help="Save graph snapshots to this PNG path while running (useful in headless mode).",
    )
    args = parser.parse_args()

    meter = Protek506(
        port=args.port,
        timeout=args.timeout,
        trigger=f"{args.trigger}\n",
        trigger_interval=args.trigger_interval,
    )
    try:
        if args.diagnose:
            meter.diagnose()
        else:
            meter.open()
            meter.run_forever(visual=args.visual, save_plot=args.save_plot)
    except KeyboardInterrupt:
        print("Stopping Protek 506 reader")
    finally:
        meter.close()
