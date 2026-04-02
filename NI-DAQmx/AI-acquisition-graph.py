import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import nidaqmx

# Output folder
out_dir = "../rezulto"
os.makedirs(out_dir, exist_ok=True)

# Acquisition settings
DEVICE = "Dev1"
CHANNEL = f"{DEVICE}/ai0"
FS = 100          # 100 Hz
N_SAMPLES = 100   # 100 samples = 1 second

# Acquire data
with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan(CHANNEL)
    task.timing.cfg_samp_clk_timing(rate=FS, samps_per_chan=N_SAMPLES)
    data = task.read(number_of_samples_per_channel=N_SAMPLES)

# Convert to DataFrame with time axis
data = np.array(data, dtype=float)
time_s = np.arange(N_SAMPLES) / FS

df = pd.DataFrame({
    "time_s": time_s,
    "voltage": data
})

# Save CSV
csv_path = os.path.join(out_dir, "ai0_temperature.csv")
df.to_csv(csv_path, index=False)

# Statistics
v_min = df["voltage"].min()
v_max = df["voltage"].max()
v_avg = df["voltage"].mean()

# Plot
sns.set_theme(style="whitegrid")
plt.figure(figsize=(10, 5))

sns.lineplot(data=df, x="time_s", y="voltage", label="AI0 voltage")

plt.axhline(v_min, color="red", linestyle="--", label=f"min = {v_min:.4f} V")
plt.axhline(v_avg, color="green", linestyle="--", label=f"avg = {v_avg:.4f} V")
plt.axhline(v_max, color="orange", linestyle="--", label=f"max = {v_max:.4f} V")

plt.title("AI0 Voltage vs Time")
plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.legend()
plt.tight_layout()

# Save PNG
png_path = os.path.join(out_dir, "ai0_temperature.png")
plt.savefig(png_path, dpi=300, bbox_inches="tight")
plt.close()

print(f"Saved CSV to: {csv_path}")
print(f"Saved PNG to: {png_path}")
