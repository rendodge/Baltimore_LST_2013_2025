"""Detection-limit simulation: how much of a narrow riparian corridor's cooling can Landsat / ECOSTRESS see?

1-D cross-section (perpendicular to the stream), 1 m resolution: "true" surface LST anomaly = -A inside the
forested buffer (|x| <= w, per side) and 0 outside. Sensor model: box average over the native thermal
footprint (Landsat 8 TIRS 100 m; ECOSTRESS 70 m) convolved with a Gaussian optical blur (sigma = 0.25 x
footprint), then sampled on the distributed grid (Landsat 30 m with bilinear-equivalent resampling;
ECOSTRESS 70 m), with grid phase averaged over all offsets. Measured corridor signal = mean over 0-60 m from
the channel, as in the deep-dive analysis. Attenuation = measured / true.

A = plateau cooling observed for wide buffers in 30_buffer_analysis.py (default 3.5 C); detection threshold =
1.96 x the standard error of the narrow-width class coefficients from the same models (read from
deepdive_robustness.csv, model "M2 rich controls"). Minimum detectable width = narrowest w whose expected
measured cooling exceeds the threshold.

Outputs: data/processed/streams/detection_limit.csv, figures/buffer_deepdive/detection_limit.png.
Run after 30: conda run -p .\\env python scripts\\33_detection_limit.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d, uniform_filter1d

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/streams"
FIG = ROOT / "figures/buffer_deepdive"
SENSORS = {"Landsat 8 TIRS (100 m, 30 m grid)": (100, 30), "ECOSTRESS (70 m, 70 m grid)": (70, 70)}
WIDTHS = np.arange(5, 305, 5)
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def measured(w, footprint, grid, half=1500):
    x = np.arange(-half, half + 1)
    true = np.where(np.abs(x) <= w, -1.0, 0.0)
    obs = gaussian_filter1d(uniform_filter1d(true, footprint, mode="nearest"), 0.25 * footprint)
    vals = []
    for phase in range(0, grid, 5):  # average over grid alignment
        centres = np.arange(-half + phase, half, grid)
        samp = np.interp(centres, x, obs)
        if grid != footprint:  # Landsat ST is resampled from 100 m to 30 m; interpolate back to 1 m (bilinear-like)
            samp = np.interp(x, centres, samp)
            vals.append(samp[(np.abs(x) <= 60)].mean())
        else:  # ECOSTRESS: pixels whose centres fall within 60 m of the channel
            sel = np.abs(centres) <= 60
            vals.append(samp[sel].mean() if sel.any() else np.interp(0, centres, samp))
    return -np.mean(vals)  # fraction of the true anomaly captured (true = 1 inside the corridor)


def main():
    rob = pd.read_csv(OUT / "deepdive_robustness.csv")
    m2 = rob[(rob.model == "M2 rich controls") & (rob["class"].isin(["10-30", "30-50", "50-100"]))]
    se = ((m2.ci_hi - m2.ci_lo) / (2 * 1.96)).mean()
    sel = (rob.model == "M2 rich controls") & (rob["class"] == "<10")
    # reference is >= 200 m, so the < 10 m coefficient is the (positive) warming of an unbuffered corridor
    A = abs(rob[sel].coef_C.iloc[0]) if sel.any() else 3.5
    thr = 1.96 * se
    rows = []
    for name, (fp, grid) in SENSORS.items():
        for w in WIDTHS:
            f = measured(w, fp, grid)
            rows.append({"sensor": name, "width_m": w, "fraction_captured": f, "expected_signal_C": f * A})
    t = pd.DataFrame(rows)
    mins = {n: (t[(t.sensor == n) & (t.expected_signal_C >= thr)].width_m.min()) for n in SENSORS}
    t.to_csv(OUT / "detection_limit.csv", index=False, float_format="%.4f")
    print(f"plateau cooling A = {A:.2f} C (from <10 m vs >= 200 m, M2); detection threshold 1.96 x SE = {thr:.2f} C")
    for n in SENSORS:
        s = t[t.sensor == n].set_index("width_m").fraction_captured
        print(f"{n}: captured at 10/30/50/75/100 m per side = " + ", ".join(f"{s.get(w, np.nan):.2f}" for w in (10, 30, 50, 75, 100))
              + f"; minimum detectable width ~{mins[n]} m per side")

    fig, ax = plt.subplots(figsize=(11, 7.5))
    for (n, colr) in zip(SENSORS, ("#1d3f6e", "#b2182b")):
        s = t[t.sensor == n]
        ax.plot(s.width_m, s.expected_signal_C, color=colr, lw=2.5, label=f"{n}: ≥ {mins[n]} m")
    ax.axhline(thr, color="0.4", lw=1.2, ls="--")
    ax.axhline(A, color="0.7", lw=1, ls=":")
    ax.text(300, thr + 0.05, "detection threshold (1.96 × SE)", ha="right", va="bottom", fontsize=13, color="0.35")
    ax.text(300, A + 0.05, "true cooling (wide-buffer plateau)", ha="right", va="bottom", fontsize=13, color="0.5")
    ax.set(xlim=(0, 300), ylim=(0, A * 1.15), xlabel="Forested buffer width, per side (m)",
           ylabel="Corridor cooling the sensor would record (°C)", title="Can the sensor see a narrow buffer?")
    ax.grid(color="0.9", lw=0.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(title="Minimum detectable width", fontsize=13, title_fontsize=14, frameon=False, loc="lower right")
    fig.text(0.99, 0.01, "1-D simulation: box footprint + Gaussian blur, sampled on the distributed grid; corridor = 0–60 m from channel.",
             ha="right", va="bottom", fontsize=11, color="0.45")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG / "detection_limit.png", dpi=150)


if __name__ == "__main__":
    main()
