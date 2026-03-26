# === CONFIGURATOR ===
title: str = "Quarterly Revenue"
subtitle: str = "Actuals vs Target, 2026"
dpi: int = 150
show_target: bool = True

# === CODE ===
import matplotlib
import pandas as pd

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).parent.parent
date = "20260101"

df = pd.read_csv(BASE_DIR / "data" / f"data_{date}.csv")

fig, ax = plt.subplots(figsize=(8, 5))

x = range(len(df))
ax.bar(x, df["revenue_m"], width=0.4, label="Revenue", color="#7CA3C6", align="center")
if show_target:
    ax.plot(x, df["target_m"], marker="o", color="#e84133", linewidth=2, label="Target")

ax.set_xticks(x)
ax.set_xticklabels(df["quarter"])
ax.set_title(title)
if subtitle:
    ax.set_xlabel(subtitle, fontsize=9, color="#666")
ax.set_ylabel("CHF millions")
ax.legend()
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()

# === SAVE ===
version = 1
out = BASE_DIR / "plots" / f"plot_{date}_v{version}.png"
out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, dpi=dpi)
print(f"Saved {out}")
