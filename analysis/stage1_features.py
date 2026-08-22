#!/usr/bin/env python3
"""Tahap 1 — Ekstraksi fitur dataset eksperimen.

Sumber cepat (default): hasil ekstraksi feature-service yang terekam pada
results/EXP-001/raw_batch_results.csv (satu baris unik per citra).
Mode --recompute menghitung ulang entropi/GLCM langsung dari citra di
data/experiment_dataset_v2 memakai skimage (identik definisi feature-service:
grayscale, offset (1,0), distances=[1], angles=[0], levels=256).

Output:
  results/stages/stage1_features.csv      — satu baris per citra unik
  results/stages/stage1_class_stats.csv   — statistik deskriptif per kelas
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "results", "stages")
EXP1_CSV = os.path.join(REPO, "results", "EXP-001", "raw_batch_results.csv")
DATASET_DIR = os.path.join(REPO, "data", "experiment_dataset_v2")

FEATURES = ["entropy", "size_kb", "glcm_correlation", "glcm_contrast"]


def extract_from_exp001() -> pd.DataFrame:
    df = pd.read_csv(EXP1_CSV)
    df = df[df["phase"] != "warmup"] if "phase" in df.columns else df
    df = df.drop_duplicates(subset="relative_path", keep="first").copy()
    df = df.rename(columns={"image_width": "width", "image_height": "height"})
    df["label"] = df["relative_path"].str.split("/").str[0]
    df["file_size_bytes"] = (df["size_kb"] * 1024).round(0).astype("int64")
    cols = ["relative_path", "label", "width", "height", "size_kb",
            "file_size_bytes", "entropy", "glcm_correlation", "glcm_contrast"]
    return df[cols].sort_values("relative_path").reset_index(drop=True)


def recompute_from_images() -> pd.DataFrame:
    from PIL import Image
    from skimage.feature import graycomatrix, graycoprops

    rows = []
    files = sorted(
        os.path.join(dp, f)
        for dp, _, fs in os.walk(DATASET_DIR) for f in fs
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    for i, path in enumerate(files, 1):
        rel = os.path.relpath(path, DATASET_DIR)
        label = rel.split(os.sep)[0].replace(os.sep, "/")
        img = Image.open(path).convert("L")
        arr = np.asarray(img, dtype=np.uint8)
        glcm = graycomatrix(arr, distances=[1], angles=[0], levels=256,
                            symmetric=True, normed=True)
        rows.append({
            "relative_path": rel.replace(os.sep, "/"),
            "label": label,
            "width": img.width,
            "height": img.height,
            "size_kb": round(os.path.getsize(path) / 1024, 4),
            "file_size_bytes": os.path.getsize(path),
            "entropy": float(-np.sum(np.bincount(arr.ravel(), minlength=256)[np.bincount(arr.ravel(), minlength=256) > 0] / arr.size *
                                     np.log2(np.bincount(arr.ravel(), minlength=256)[np.bincount(arr.ravel(), minlength=256) > 0] / arr.size))),
            "glcm_correlation": float(graycoprops(glcm, "correlation")[0, 0]),
            "glcm_contrast": float(graycoprops(glcm, "contrast")[0, 0]),
        })
        if i % 100 == 0:
            print(f"  [stage1] {i}/{len(files)} gambar diproses")
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recompute", action="store_true",
                    help="hitung ulang fitur dari citra asli (lambat)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    df = recompute_from_images() if args.recompute else extract_from_exp001()
    feats = [c for c in FEATURES if c in df.columns]

    stats = (
        df.groupby("label")[feats]
        .agg(["min", "max", "mean", "std"])
        .round(6)
    )
    stats_out = stats.stack(level=0, future_stack=True).reset_index()
    stats_out.columns = ["label", "feature", "statistic"] if stats_out.shape[1] == 3 else stats_out.columns
    # normalisasi nama kolom hasil stack (pandas versi beda bisa beda urutan)
    if list(stats_out.columns) != ["label", "feature", "statistic"]:
        stats_out = stats.rename_axis(None)
        long_rows = []
        for label, sub in df.groupby("label"):
            for feat in feats:
                s = sub[feat]
                long_rows.append({
                    "label": label, "feature": feat,
                    "min": round(s.min(), 6), "max": round(s.max(), 6),
                    "mean": round(s.mean(), 6), "std": round(s.std(), 6),
                    "n": int(s.count()),
                })
        stats_out = pd.DataFrame(long_rows)

    out_csv = os.path.join(OUT_DIR, "stage1_features.csv")
    out_stats = os.path.join(OUT_DIR, "stage1_class_stats.csv")
    df.to_csv(out_csv, index=False)
    stats_out.to_csv(out_stats, index=False)

    print(f"[stage1] {len(df)} citra unik, {df['label'].nunique()} kelas")
    print(df.groupby("label").size().to_string())
    print(f"\n[stage1] mean fitur global:\n{df[feats].mean().round(4).to_string()}")
    print(f"\n[stage1] tulis: {out_csv}\n[stage1] tulis: {out_stats}")


if __name__ == "__main__":
    sys.exit(main())
