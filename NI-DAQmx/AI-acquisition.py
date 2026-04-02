import nidaqmx
import numpy as np
import pandas as pd

with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan("Dev1/ai2")
    task.timing.cfg_samp_clk_timing(rate=1000, samps_per_chan=1000)

    data = task.read(number_of_samples_per_channel=1000)
    data = np.array(data)

df = pd.DataFrame(data, columns=["voltage"])
df.to_csv("../rezulto/voltage-data.csv", index=False)
print("Saved to ../rezulto/voltage-data.csv")
