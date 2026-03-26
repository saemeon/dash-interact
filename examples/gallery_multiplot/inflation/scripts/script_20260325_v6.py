# === CONFIGURATOR ===
title: str = "CPI Inflation"
show_core: bool = True
smoothing: int = 1
color_cpi: str = "#7CA3C6"

# === CODE ===
import matplotlib
import pandas as pd

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).parent.parent
date = "20260101"

df = pd.read_csv(BASE_DIR / "data" / f"data_{date}.csv", parse_dates=["month"])

fig, ax = plt.subplots(figsize=(8, 5))

cpi = df["cpi"]
if smoothing > 1:
    cpi = cpi.rolling(smoothing, min_periods=1).mean()

ax.plot(df["month"], cpi, linewidth=2, label="CPI", color=color_cpi)

if show_core:
    core = df["core_cpi"]
    if smoothing > 1:
        core = core.rolling(smoothing, min_periods=1).mean()
    ax.plot(
        df["month"],
        core,
        linewidth=2,
        label="Core CPI",
        color="#e84133",
        linestyle="--",
    )

ax.set_title(title)
ax.set_ylabel("Index (base=100)")
ax.legend()
ax.grid(alpha=0.3)
fig.autofmt_xdate()
plt.tight_layout()

# === SAVE ===
date = "20260325"
version = 6
date = "20260325"
version = 5
date = "20260325"
version = 4
date = "20260325"
version = 1
version = 1
out = BASE_DIR / "plots" / f"plot_{date}_v{version}.png"
out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, dpi=150)
print(f"Saved {out}")
