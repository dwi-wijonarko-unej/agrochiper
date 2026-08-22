#!/usr/bin/env python3
"""Regenerasi figur publikasi dari output Tahap 1-5.

Figur lama (fig1-3, dari analysis/generate_figures.py) dipertahankan;
script ini menambahkan:
  fig4_confusion_matrix.png     (dari stage3)
  fig5_feature_importance.png   (dari stage3)
  fig6_decision_tree.png        (dari stage3)
  fig8_loadtest.png             (dari stage4)
  fig7_noise_robustness.png     (dari stage5)

Output: results/FIGURES/
"""

import os
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGES = os.path.join(REPO, "results", "stages")
FIGS = os.path.join(REPO, "results", "stages", "figures")
OUT = os.path.join(REPO, "results", "FIGURES")

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.titlesize": 10, "axes.labelsize": 9.5, "legend.fontsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6,
})

# salin figur stage3 ke direktori publikasi (penomoran urut kemunculan)
for src, dst in [
    ("stage3_decision_tree.png", "fig2_decision_tree.png"),
    ("stage3_confusion_matrix.png", "fig3_confusion_matrix.png"),
    ("stage3_feature_importance.png", "fig4_feature_importance.png"),
]:
    shutil.copyfile(os.path.join(FIGS, src), os.path.join(OUT, dst))
print("[figs] fig2-4 disalin dari stage3.")

# ------------------------- fig7: load test -------------------------------
lt = pd.read_csv(os.path.join(STAGES, "stage4_load_test_results.csv"))
fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.6))
ax = axes[0]
ax.plot(lt["vu"], lt["throughput_req_per_s"], marker="o", color="#16a34a", lw=1.6)
for _, r in lt.iterrows():
    ax.annotate(f"{r['throughput_req_per_s']:.2f}",
                (r["vu"], r["throughput_req_per_s"]),
                textcoords="offset points", xytext=(0, 7),
                ha="center", fontsize=8)
ax.set_xlabel("Concurrent virtual users")
ax.set_ylabel("Throughput (req/s)")
ax.set_xticks(lt["vu"])
ax.set_ylim(0, 5.2)

ax = axes[1]
for col, label, color in [
    ("latency_p50_ms", "p50", "#2563eb"),
    ("latency_p95_ms", "p95", "#dc2626"),
    ("latency_p99_ms", "p99", "#9333ea"),
]:
    ax.plot(lt["vu"], lt[col], marker="s", lw=1.4, label=label, color=color)
ax.set_yscale("log")
ax.set_xlabel("Concurrent virtual users")
ax.set_ylabel("End-to-end latency (ms)")
ax.set_xticks(lt["vu"])
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig8_loadtest.png"), dpi=300)
plt.close(fig)
print("[figs] fig8_loadtest.png")

# ---------------------- fig8: noise robustness ---------------------------
agg = pd.read_csv(os.path.join(STAGES, "stage5_noise_robustness_summary.csv"))
det = pd.read_csv(os.path.join(STAGES, "stage5_noise_robustness_detail.csv"))

noise_order = ["gaussian_sigma8", "gaussian_sigma16",
               "saltpepper_1pct", "saltpepper_5pct"]
noise_labels = ["Gauss\nσ=8", "Gauss\nσ=16", "S&P\n1%", "S&P\n5%"]
methods = ["UHC", "Blowfish", "Hybrid UHC-Blowfish"]
colors = {"UHC": "#2563eb", "Blowfish": "#16a34a", "Hybrid UHC-Blowfish": "#dc2626"}

fig, ax = plt.subplots(figsize=(7.6, 3.8))
width = 0.26
x = np.arange(len(noise_order))
for k, m in enumerate(methods):
    vals, fail_rates = [], []
    sub_m = agg[agg["method"] == m]
    for nz in noise_order:
        row = sub_m[sub_m["noise"] == nz]
        if len(row) and row.iloc[0]["psnr_mean_db"] != "":
            vals.append(float(row.iloc[0]["psnr_mean_db"]))
            fail_rates.append(100 * int(row.iloc[0]["decrypt_failure_n"]) / int(row.iloc[0]["n"]))
        else:
            vals.append(np.nan)
            fail_rates.append(100.0)
    bars = ax.bar(x + (k - 1) * width, vals, width, label=m, color=colors[m],
                  alpha=0.88 if m != "UHC" else 1.0)
    for xi, (v, fr) in enumerate(zip(vals, fail_rates)):
        if np.isnan(v):
            ax.text(xi + (k - 1) * width, 0.35, f"{fr:.0f}% fail",
                    rotation=90, va="bottom", ha="center", fontsize=7,
                    color=colors[m], fontweight="bold")
        else:
            ax.text(xi + (k - 1) * width, v + 0.4, f"{v:.1f}",
                    ha="center", fontsize=7.2)
ax.set_xticks(x, noise_labels)
ax.set_ylabel("PSNR recovery after corruption (dB)")
ax.set_ylim(0, max(det["psnr_db"].dropna().astype(float)) * 1.22)
ax.legend(frameon=False, ncol=3, loc="upper right")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig7_noise_robustness.png"), dpi=300)
plt.close(fig)
print("[figs] fig7_noise_robustness.png")
print("[figs] selesai ->", OUT)
