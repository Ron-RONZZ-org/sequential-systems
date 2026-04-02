import time
import nidaqmx
from nidaqmx.constants import LineGrouping

DEVICE = "Dev1"
# LINES = [f"{DEVICE}/port0/line{i}" for i in range(8)]
DELAY_S = 0.5

with nidaqmx.Task() as task:
    task.do_channels.add_do_chan(
        f"{DEVICE}/port0/line0:7",
        line_grouping=LineGrouping.CHAN_PER_LINE
    )
    pattern = [False] * 8
    while True:
        for i in range(8):
            # Turn only one LED on at a time
            pattern[i-1]= False
            pattern[i] = True
            task.write(pattern)
            time.sleep(DELAY_S)
