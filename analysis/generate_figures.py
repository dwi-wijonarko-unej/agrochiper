#!/usr/bin/env python3
"""Generate publication-quality figures for the AgroCipher manuscript.

Figures:
  fig1_selector_scatter.png   entropy vs GLCM contrast colored by selector decision
  fig2_method_performance.png encryption/decryption/e2e latency bars + cipher entropy line
  fig3_ciphertext_quality.png multi-panel (entropy, adjacent corr, NPCR, UACI)

Inputs (repo-relative):
  results/EXP-001/raw_batch_results.csv
  results/analysis/method_comparison.csv
  results/EXP-003/crypto_metrics_summary.csv
  results/EXP-003/npcr_uaci.csv
  data/experiment_dataset_v2/**/*.jpg   (baseline byte metrics)

Output: results/FIGURES/
"""

import csv
import os
import random
import glob

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "results", "FIGURES")
os.makedirs(OUT, exist_ok=True)

DPI = 300
METHODS = ["UHC", "Blowfish", "Hybrid UHC-Blowfish", "Adaptive"]
COLORS = {"UHC": "#2563eb", "Blowfish": "#16a34a",
          "Hybrid UHC-Blowfish": "#dc2626", "Adaptive": "#9333ea",
          "none": "#6b7280"}
SHORT = {"UHC": "UHC", "Blowfish": "Blowfish",
         "Hybrid UHC-Blowfish": "Hybrid", "Adaptive": "Adaptive"}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9.5,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
})


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def dedupe_by(rows, key):
    seen, out = set(), []
    for r in rows:
        k = r[key]
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


# ----------------------------------------------------------------------------
# Figure 1: entropy vs GLCM contrast, colored by selector decision
# ----------------------------------------------------------------------------
def fig1_selector_scatter():
    rows = read_csv(os.path.join(REPO, "results", "EXP-001", "raw_batch_results.csv"))
    rows = dedupe_by(rows, "relative_path")
    ent = np.array([float(r["entropy"]) for r in rows])
    con = np.array([float(r["glcm_contrast"]) for r in rows])
    method = np.array([r["method"] for r in rows])

    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    order = ["UHC", "Blowfish", "Hybrid UHC-Blowfish"]
    for m in order:
        sel = method == m
        label = SHORT[m]
        ax.scatter(ent[sel], con[sel], s=16, alpha=0.55, edgecolors="none",
                   c=COLORS[m], label=f"{label} (n={sel.sum()})", rasterized=True)

    ax.axvline(4.78, color="#444444", ls="--", lw=1.0, alpha=0.8)
    ax.text(4.80, 0.92, "entropy = 4.78", fontsize=7.5, color="#444444", rotation=90,
            va="top", ha="right")
    ax.set_xlabel("Image entropy (bit/byte)")
    ax.set_ylabel("GLCM contrast")
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlim(1.0, 8.0)
    ax.legend(loc="upper left", frameon=False, scatterpoints=1, handletextpad=0.2)
    ax.set_title("Selector decision vs image features (n = 2834)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_selector_scatter.png"), dpi=DPI)
    plt.close(fig)
    print("fig1_selector_scatter.png")


# ----------------------------------------------------------------------------
# Figure 2: method performance — bars (time) + line (cipher entropy)
# ----------------------------------------------------------------------------
def fig2_method_performance():
    rows = read_csv(os.path.join(REPO, "results", "analysis", "method_comparison.csv"))
    rows = [r for r in rows if r["method"] in METHODS]
    order = ["UHC", "Blowfish", "Hybrid UHC-Blowfish", "Adaptive"]
    names = [SHORT[m] for m in order]
    x = np.arange(len(order))
    w = 0.26
    enc = [float(next(r["encryption_time_mean_ms"] for r in rows if r["method"] == m)) for m in order]
    dec = [float(next(r["decryption_time_mean_ms"] for r in rows if r["method"] == m)) for m in order]
    e2e = [float(next(r["end_to_end_latency_mean_ms"] for r in rows if r["method"] == m)) for m in order]
    ce = [float(next(r["cipher_entropy_mean"] for r in rows if r["method"] == m)) for m in order]
    cols = [COLORS[m] for m in order]

    fig, ax1 = plt.subplots(figsize=(6.8, 4.2))
    b1 = ax1.bar(x - w, enc, w * 0.98, label="Encryption", color="#94a3b8")
    b2 = ax1.bar(x, dec, w * 0.98, label="Decryption", color="#64748b")
    b3 = ax1.bar(x + w, e2e, w * 0.98, label="End-to-end latency", color="#334155")
    ax1.set_ylabel("Time (ms)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(names)
    ax1.set_ylim(0, max(e2e) * 1.12)
    ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
    for bars in (b1, b2, b3):
        for b in bars:
            ax1.annotate(f"{b.get_height():.0f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                         ha="center", va="bottom", fontsize=6.8)

    ax2 = ax1.twinx()
    ax2.plot(x, ce, "-o", color=COLORS["Adaptive"], lw=1.8, ms=5, label="Cipher entropy")
    ax2.set_ylabel("Ciphertext entropy (bit/byte)")
    ax2.set_ylim(7.4, 8.05)
    ax2.grid(False)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="lower right", frameon=False, ncol=1)
    ax1.set_title("Encryption performance and ciphertext entropy (EXP-002)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_method_performance.png"), dpi=DPI)
    plt.close(fig)
    print("fig2_method_performance.png")


# ----------------------------------------------------------------------------
# Figure 3: multi-panel ciphertext quality
# ----------------------------------------------------------------------------
def fig3_ciphertext_quality():
    metrics = read_csv(os.path.join(REPO, "results", "EXP-003", "crypto_metrics_summary.csv"))
    npcr = read_csv(os.path.join(REPO, "results", "EXP-003", "npcr_uaci.csv"))

    def metric(method):
        r = next(r for r in metrics if r["method"] == method)
        return float(r["mean_payload_entropy"]), float(r["mean_corr_adjacent"])

    # Baseline (no encryption) byte metrics from raw image bytes
    rng = random.Random(42)
    imgs = sorted(glob.glob(os.path.join(REPO, "data", "experiment_dataset_v2", "*", "*.jpg")))
    sample = rng.sample(imgs, min(40, len(imgs)))
    ent_base, corr_base = [], []
    for p in sample:
        with open(p, "rb") as f:
            b = np.frombuffer(f.read(), dtype=np.uint8)
        if b.size == 0:
            continue
        counts = np.bincount(b.astype(np.int64), minlength=256).astype(np.float64)
        pv = counts / counts.sum()
        ent_base.append(-np.sum(pv[pv > 0] * np.log2(pv[pv > 0])))
        corr_base.append(float(np.corrcoef(b[:-1], b[1:])[0, 1]))
    ent_baseline = float(np.mean(ent_base))
    corr_baseline = float(np.mean(corr_base))

    def npcr_uaci(method):
        sub = [r for r in npcr if r["method"] == method]
        n = [float(r["npcr_pct"]) for r in sub]
        u = [float(r["uaci_pct"]) for r in sub]
        return float(np.mean(n)), float(np.mean(u))

    cats = ["UHC", "Blowfish", "Hybrid", "Baseline"]
    ent = [metric("UHC")[0], metric("Blowfish")[0], metric("Hybrid UHC-Blowfish")[0], ent_baseline]
    corr = [metric("UHC")[1], metric("Blowfish")[1], metric("Hybrid UHC-Blowfish")[1], corr_baseline]
    npv = [npcr_uaci("UHC")[0], npcr_uaci("Blowfish")[0], npcr_uaci("Hybrid UHC-Blowfish")[0], npcr_uaci("none")[0]]
    uav = [npcr_uaci("UHC")[1], npcr_uaci("Blowfish")[1], npcr_uaci("Hybrid UHC-Blowfish")[1], npcr_uaci("none")[1]]
    cols = [COLORS["UHC"], COLORS["Blowfish"], COLORS["Hybrid UHC-Blowfish"], COLORS["none"]]

    fig, axes = plt.subplots(2, 2, figsize=(7.6, 5.6))

    ax = axes[0, 0]
    bars = ax.bar(cats, ent, 0.55, color=cols)
    for b in bars:
        ax.annotate(f"{b.get_height():.4f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=7)
    ax.set_ylim(7.3, 8.1)
    ax.set_ylabel("Entropy (bit/byte)")
    ax.axhline(8.0, color="#444444", ls=":", lw=1.0)
    ax.set_title("(a) Ciphertext entropy")

    ax = axes[0, 1]
    bars = ax.bar(cats, corr, 0.55, color=cols)
    for b in bars:
        ax.annotate(f"{b.get_height():.4f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=7)
    ax.set_ylim(-0.05, max(corr) * 1.25)
    ax.set_ylabel("Correlation coefficient")
    ax.set_title("(b) Adjacent-byte correlation")

    ax = axes[1, 0]
    bars = ax.bar(cats, npv, 0.55, color=cols)
    for b in bars:
        ax.annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=7)
    ax.set_ylim(0, 115)
    ax.set_ylabel("NPCR (%)")
    ax.set_title("(c) NPCR (1-byte flip)")

    ax = axes[1, 1]
    bars = ax.bar(cats, uav, 0.55, color=cols)
    for b in bars:
        ax.annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                    ha="center", va="bottom", fontsize=7)
    ax.set_ylim(0, 40)
    ax.set_ylabel("UACI (%)")
    ax.set_title("(d) UACI (1-byte flip)")

    fig.suptitle("Ciphertext quality indicators (EXP-003, n = 300 payloads / 10 images)",
                 fontsize=10, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(os.path.join(OUT, "fig3_ciphertext_quality.png"), dpi=DPI)
    plt.close(fig)
    print("fig3_ciphertext_quality.png")


if __name__ == "__main__":
    fig1_selector_scatter()
    fig2_method_performance()
    fig3_ciphertext_quality()
    print("All figures written to", OUT)