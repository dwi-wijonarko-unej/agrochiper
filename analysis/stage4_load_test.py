#!/usr/bin/env python3
"""Tahap 4 — Rekomputasi hasil load test microservices (EXP-004).

Menghitung ulang throughput, latensi (mean/p50/p95/p99), dan error rate
dari request log mentah load_test_vu{1,5,10,20}.csv (jendela pengukuran =
120 detik setelah warm-up), lalu menggabungkan sampling CPU/memori per
kontainer dari service_resource_usage.csv.

Output:
  results/stages/stage4_load_test_results.csv
"""

import os

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "results", "stages")
EXP4 = os.path.join(REPO, "results", "EXP-004")
DURATION_S = 120


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    summary = pd.read_csv(os.path.join(EXP4, "load_test_summary.csv"))
    res = pd.read_csv(os.path.join(EXP4, "service_resource_usage.csv"))

    rows = []
    for _, srow in summary.iterrows():
        vu = int(srow["vu"])
        raw = pd.read_csv(os.path.join(EXP4, f"load_test_vu{vu}.csv"))
        # buang baris warm-up (warmup_requests tercatat di summary)
        raw = raw.iloc[int(srow["warmup_requests"]):]
        lat = raw["latency_ms"].to_numpy()
        n = len(lat)
        ok = int(raw["success"].sum())
        cpu = res[res["vu"] == vu].set_index("service")
        rows.append({
            "vu": vu,
            "duration_s": DURATION_S,
            "requests": n,
            "success": ok,
            "failed": n - ok,
            "error_rate_pct": round(100 * (n - ok) / n, 2),
            "throughput_req_per_s": round(n / DURATION_S, 2),
            "latency_mean_ms": round(float(np.mean(lat)), 2),
            "latency_p50_ms": round(float(np.percentile(lat, 50)), 2),
            "latency_p95_ms": round(float(np.percentile(lat, 95)), 2),
            "latency_p99_ms": round(float(np.percentile(lat, 99)), 2),
            "cpu_encryption_mean_pct": round(cpu.loc["coffee-encryption-service", "cpu_mean_pct"], 2),
            "cpu_gateway_mean_pct": round(cpu.loc["coffee-gateway", "cpu_mean_pct"], 2),
            "cpu_feature_mean_pct": round(cpu.loc["coffee-feature-service", "cpu_mean_pct"], 2),
            "cpu_selector_mean_pct": round(cpu.loc["coffee-selector-service", "cpu_mean_pct"], 2),
            "mem_encryption_mean_pct": round(cpu.loc["coffee-encryption-service", "mem_mean_pct"], 2),
        })

    out = pd.DataFrame(rows)
    f_out = os.path.join(OUT_DIR, "stage4_load_test_results.csv")
    out.to_csv(f_out, index=False)

    print("[stage4] rekomputasi vs summary asli:")
    for _, s in summary.iterrows():
        r = out[out["vu"] == s["vu"]].iloc[0]
        d_thr = abs(r["throughput_req_per_s"] - s["throughput_req_per_s"])
        d_p95 = abs(r["latency_p95_ms"] - s["latency_p95_ms"])
        flag = "OK" if d_thr < 0.05 and d_p95 < 5 else "DEVIASI"
        print(f"  VU={s['vu']}: thr {r['throughput_req_per_s']} vs "
              f"{s['throughput_req_per_s']} | p95 {r['latency_p95_ms']} vs "
              f"{s['latency_p95_ms']} -> {flag}")
    print(f"\n[stage4] tulis: {f_out}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
