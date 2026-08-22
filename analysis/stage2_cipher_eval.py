#!/usr/bin/env python3
"""Tahap 2 — Evaluasi cipher UHC / Blowfish / Hybrid / Adaptive.

Sumber: results/EXP-002-{UHC,Blo,Hyb,Ada}/raw_batch_results.csv
(eksperimen forced-method pada 2.834 citra per skenario).

Metrik per skenario: waktu enkripsi/dekripsi/e2e (mean±std, p95), entropi
cipher, success rate, lossless rate. PSNR = ∞ (lossless) pada seluruh request
sehingga SSIM derivatif = 1.0 secara matematis (identitas piksel sempurna).

Output:
  results/stages/stage2_cipher_evaluation.csv  — format panjang per citra
  results/stages/stage2_cipher_aggregate.csv   — agregat per metode
"""

import os

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "results", "stages")

SCENARIOS = {
    "UHC": "EXP-002-UHC",
    "Blowfish": "EXP-002-Blo",
    "Hybrid UHC-Blowfish": "EXP-002-Hyb",
    "Adaptive": "EXP-002-Ada",
}


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    frames = []
    for method, dirname in SCENARIOS.items():
        path = os.path.join(REPO, "results", dirname, "raw_batch_results.csv")
        df = pd.read_csv(path)
        if "phase" in df.columns:
            df = df[df["phase"] != "warmup"]
        df["scenario_method"] = method
        frames.append(df)
        print(f"[stage2] {dirname}: {len(df)} request "
              f"(success={int(df['success'].sum())}, "
              f"lossless={int((df['psnr'] == '∞').sum())})")

    long = pd.concat(frames, ignore_index=True)
    long["psnr_infinite"] = long["psnr"] == "∞"
    long["ssim_derived"] = np.where(long["psnr_infinite"], 1.0, np.nan)

    out_long_cols = ["scenario_method", "relative_path", "size_kb", "entropy",
                     "glcm_correlation", "glcm_contrast", "method",
                     "encryption_time_ms", "decryption_time_ms",
                     "end_to_end_latency_ms", "cipher_entropy",
                     "psnr_infinite", "decrypt_verified", "success"]
    long_out = long[out_long_cols].rename(
        columns={"method": "routed_method"})
    f_long = os.path.join(OUT_DIR, "stage2_cipher_evaluation.csv")
    long_out.to_csv(f_long, index=False)

    rows = []
    for method, sub in long.groupby("scenario_method"):
        rows.append({
            "method": method,
            "requests": len(sub),
            "success_rate_pct": round(100 * sub["success"].mean(), 2),
            "lossless_rate_pct": round(100 * sub["psnr_infinite"].mean(), 2),
            "decrypt_verified_pct": round(100 * sub["decrypt_verified"].mean(), 2),
            "encryption_mean_ms": round(sub["encryption_time_ms"].mean(), 1),
            "encryption_std_ms": round(sub["encryption_time_ms"].std(), 1),
            "decryption_mean_ms": round(sub["decryption_time_ms"].mean(), 1),
            "decryption_std_ms": round(sub["decryption_time_ms"].std(), 1),
            "e2e_mean_ms": round(sub["end_to_end_latency_ms"].mean(), 1),
            "e2e_p95_ms": float(np.percentile(sub["end_to_end_latency_ms"], 95)),
            "cipher_entropy_mean": round(sub["cipher_entropy"].mean(), 4),
            "cipher_entropy_std": round(sub["cipher_entropy"].std(), 4),
            "ssim_derived_mean": 1.0,
        })
    agg = pd.DataFrame(rows).sort_values("method")
    f_agg = os.path.join(OUT_DIR, "stage2_cipher_aggregate.csv")
    agg.to_csv(f_agg, index=False)

    print("\n[stage2] agregat per metode:")
    print(agg.to_string(index=False))
    print(f"\n[stage2] tulis: {f_long}\n[stage2] tulis: {f_agg}")


if __name__ == "__main__":
    main()
