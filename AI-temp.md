# bug fix

- I have identified a root cause of lack of data:

There must be some data transmitted TO the Protek 506 to trigger a return. Even random numbers like `218937` would do the trick.

- The returned data has random noises:

```
TEMP 0030 ^C
#TEMP 0030 ^C
TEMP 0030 ^C
tTEMP 0030 ^C
aTEMP 0030 ^C
TEMP 0030 ^C
QTEMP 0031 ^C
.TEMP 0030 ^C
4TEMP 0030 ^C
xTEMP 0031 ^C
aTEMP 0031 ^C
TEMP 0030 ^C
TEMP 0030 ^C
TEMP 0030 ^C
aTEMP 0031 ^C
`TEMP 0031 ^C

TEMP 0030 ^C
TEMP 0030 ^C

TEMP 0030 ^C
xTEMP 0030 ^C
4TEMP 0030 ^C
5TEMP 0030 ^C
aTEMP 0030 ^C
TEMP 0030 ^C
TEMP 0030 ^C
```

which causes:

```
Read/parse error: Malformed sign: ' '
Read/parse error: Malformed sign: '0'
Read/parse error: Malformed sign: '3'
Read/parse error: Malformed sign: '3'
Read/parse error: Malformed sign: '3'
Read/parse error: Malformed sign: '3'
Read/parse error: Malformed sign: '0'
Read/parse error: Malformed sign: '0'

```

# New feature:

With `Seahorse` library, graph dynamically the output if `--visual` passed.

Context: data format


| No. | Function | Raw frame pattern | Format | Bytes |
|---:|---|---|---|---:|
| 1 | DC V | `DC 3999V` | DC 3999 V | 11 |
| 2 | DC V | `DC 33999V` | DC 33999 V | 12 |
| 3 | DC μV | `DC 0L999` | DC 0L999 | 6 |
| 4 | AC V | `AC 33999V` | AC 33999 V | 11 |
| 5 | AC V | `AC 0L999` | AC 0L999 | 6 |
| 6 | DC mV | `DC 3999mV` | DC 3999 mV | 12 |
| 7 | DC mV | `DC 0L999mV` | DC 0L999 mV | 13 |
| 8 | AC mV | `AC 3999mV` | AC 3999 mV | 12 |
| 9 | DC mA | `DC 3999mA` | DC 3999 mA | 12 |
| 10 | DC mA | `DC 33999mA` | DC 33999 mA | 13 |
| 11 | DC mA | `DC 0L999mA` | DC 0L999 mA | 12 |
| 12 | DC mA | `DC 0L999mA` | DC 0L999 mA | 13 |
| 13 | DC mA | `DC 3999mA` | DC 3999 mA | 13 |
| 14 | AC mA | `AC 3999mA` | AC 3999 mA | 12 |
| 15 | DC 2A | `DC 3999A` | DC 3999 A | 11 |
| 16 | DC 2A | `DC 0L999A` | DC 0L999 A | 11 |
| 17 | AC 2A | `AC 3999A` | AC 3999 A | 11 |
| 18 | Resistance | `RES 3999MΩ` | RES 3999 MΩ | 15 |
| 19 | Resistance | `RES 33999MΩ` | RES 33999 MΩ | 14 |
| 20 | Resistance | `RES 0L999` | RES 0L999 | 7 |
| 21 | Continuity | `BUZZ SHORT` | BUZZ SHORT | 10 |
| 22 | Continuity | `BUZZ OPEN` | BUZZ OPEN | 9 |
| 23 | Diode | `DIODE` | DIODE | 9 |
| 24 | Diode | `DIODE OPEN` | DIODE OPEN | 9 |
| 25 | Diode | `DIODE` | DIODE | 9 |
| 26 | Logic | `LOGIC HI` | LOGIC HI | 9 |
| 27 | Logic | `LOGIC LO` | LOGIC LO | 9 |
| 28 | Logic | `LOGIC HI` | LOGIC HI | 10 |
| 29 | Frequency | `FREQ Hz` | FREQ Hz | 13 |
| 30 | Frequency | `FREQ kHz` | FREQ kHz | 13 |
| 31 | Capacitance | `CAP 0.9999µF` | CAP 0.9999 µF | 13 |
| 32 | Capacitance | `CAP 0.999µF` | CAP 0.999 µF | 12 |
| 33 | Inductance | `IND 0.999µH` | IND 0.999 µH | 12 |
| 34 | Inductance | `IND 0.999µH` | IND 0.999 µH | 12 |
| 35 | Temperature | `TEMP -0025°C` | TEMP -0025 °C | 13 |
| 36 | Temperature | `TEMP 0025°C` | TEMP 0025 °C | 14 |


# setup  `.github/copilot-instructions.md`



