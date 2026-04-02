import nidaqmx
import numpy as np

with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
    task.timing.cfg_samp_clk_timing(rate=1000, samps_per_chan=1000)

    data = task.read(number_of_samples_per_channel=1000)
    data = np.array(data)

print(data[:10])
