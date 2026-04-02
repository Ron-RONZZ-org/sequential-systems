# Copilot Instructions

- Preserve Protek 506 serial configuration exactly as user-verified:
  - baudrate `1200`
  - bytesize `7`
  - parity `none`
  - stopbits `2`
- Always deassert modem control lines (`DTR` and `RTS`) after open and before close.
- Device is request/response: write a trigger payload continuously (polling cadence) before each read.
- Responses can contain leading serial noise bytes; sanitize input and parse from known mode tokens (`DC`, `AC`, `RES`, `BUZZ`, `DIODE`, `LOGIC`, `FREQ`, `CAP`, `IND`, `TEMP`).
- Keep diagnostics explicit and operator-friendly; never silently hide serial errors.
- `--visual` uses `seaborn` + `matplotlib` (not Seahorse).
