"""
analyze_selector.py — Evaluasi AI Selector AgroCipher (deskriptif, bukan akurasi).

Input:
  results/EXP-001/raw_batch_results.csv            (keputusan adaptive)
  results/EXP-002-{UHC,Blo,Hyb,Ada}/raw_batch_results.csv  (baseline forced)
  analysis/models/ai_selector_model.pkl            (opsional: struktur pohon)

Output (results/analysis/):
  selector_distribution.csv    A  — distribusi & rata-rata per metode terpilih
  selector_feature_summary.csv B  — statistik fitur per metode
  method_comparison.csv             — perbandingan metode (EXP-002)
  adaptive_vs_baseline.csv      E  — skor security/performance/combined + rank
  feature_importance.csv            — feature importance DecisionTree
  decision_tree.txt                 — ekspor teks struktur pohon
  model_params.json                 — hyperparameter model

Catatan ilmiah: tidak ada ground truth label metode terbaik, sehingga script ini
TIDAK menghitung accuracy/precision/recall. Evaluasi dibatasi pada decision
behavior dan outcome eksperimen (lihat docs/SELECTOR_ANALYSIS.md).
"""

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
OUT = RESULTS / "analysis"

FEATURES = ["entropy", "glcm_correlation", "glcm_contrast", "size_kb",
            "image_width", "image_height"]


def read_rows(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(row, key, cast=float, default=None):
    try:
        return cast(row.get(key))
    except (TypeError, ValueError):
        return default


def per_image_mode(rows):
    """Map image -> metode dengan frekuensi tertinggi antar run."""
    votes = defaultdict(Counter)
    for r in rows:
        if r.get("phase") == "main" and r.get("method"):
            votes[r["relative_path"]][r["method"]] += 1
    return {img: c.most_common(1)[0][0] for img, c in votes.items()}


def write_csv(path: Path, headers: list, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)
    print(f"  wrote {path.relative_to(RESULTS.parent)} ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# A. selector_distribution.csv
# ---------------------------------------------------------------------------
def selector_distribution(ada_rows, rows_main) -> list:
    image_mode = per_image_mode(rows_main)
    by_img_method = defaultdict(list)  # method -> list of (image, row)
    by_img_feat = {}  # image -> feature dict
    for r in rows_main:
        if r.get("phase") != "main":
            continue
        by_img_feat.setdefault(r["relative_path"], r)
    for img in image_mode:
        m = image_mode[img]
        r = by_img_feat.get(img)
        if r:
            by_img_method[m].append((img, r))

    # N pada distribusi pakai citra unik (mode decision)
    total_imgs = len(image_mode)
    method_order = ["UHC", "Blowfish", "Hybrid UHC-Blowfish"]
    out = []
    headers = ["method", "total_images", "percentage",
               "mean_entropy", "mean_glcm_correlation", "mean_glcm_contrast",
               "mean_size_kb", "mean_encryption_time_ms",
               "mean_cipher_entropy", "mean_end_to_end_latency_ms",
               "total_requests"]
    for m in method_order:
        if m not in by_img_method:
            continue
        pairs = by_img_method[m]
        imgs = [i for i, _ in pairs]
        req_rows = [r for r in rows_main
                    if r.get("phase") == "main" and r.get("method") == m]
        enc_times = [fnum(r, "encryption_time_ms", float, 0) or 0 for r in req_rows]
        cipher_ents = [fnum(r, "cipher_entropy", float, 0) or 0 for r in req_rows]
        latencies = [fnum(r, "end_to_end_latency_ms", float, 0) or 0 for r in req_rows]
        e = [fnum(r, "entropy", float, 0) or 0 for _, r in pairs]
        c = [fnum(r, "glcm_correlation", float, 0) or 0 for _, r in pairs]
        ct = [fnum(r, "glcm_contrast", float, 0) or 0 for _, r in pairs]
        sk = [fnum(r, "size_kb", float, 0) or 0 for _, r in pairs]
        out.append([
            m, len(imgs), round(100 * len(imgs) / total_imgs, 2),
            _mean(e), _mean(c), _mean(ct), _mean(sk),
            _mean(enc_times), _mean(cipher_ents), _mean(latencies),
            len(req_rows),
        ])
    write_csv(OUT / "selector_distribution.csv", headers, out)
    return out


def _mean(v):
    return round(statistics.mean(v), 4) if v else ""


# ---------------------------------------------------------------------------
# B. selector_feature_summary.csv
# ---------------------------------------------------------------------------
def selector_feature_summary(rows_main) -> None:
    # dedupe fitur per citra
    per_img = {}
    for r in rows_main:
        if r.get("phase") == "main":
            per_img.setdefault(r["relative_path"], r)
    image_mode = per_image_mode(rows_main)

    headers = ["method", "feature_name", "mean", "std", "median", "min", "max", "q1", "q3"]
    rows = []
    methods = ["UHC", "Blowfish", "Hybrid UHC-Blowfish"]
    for m in methods:
        vals = defaultdict(list)
        for img, r in per_img.items():
            if image_mode.get(img) != m:
                continue
            for feat in FEATURES:
                v = fnum(r, feat, float, None)
                if v is not None:
                    vals[feat].append(v)
        for feat in FEATURES:
            v = vals.get(feat, [])
            if not v:
                continue
            v = sorted(v)
            n = len(v)
            q1 = _pct(v, 0.25)
            q3 = _pct(v, 0.75)
            rows.append([m, feat, round(statistics.mean(v), 4),
                         round(statistics.pstdev(v), 4),
                         _median(v), round(min(v), 4), round(max(v), 4),
                         q1, q3])
    write_csv(OUT / "selector_feature_summary.csv", headers, rows)


def _pct(sorted_v, q):
    if not sorted_v:
        return ""
    k = (len(sorted_v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_v) - 1)
    return round(sorted_v[lo] + (sorted_v[hi] - sorted_v[lo]) * (k - lo), 4)


def _median(sorted_v):
    return _pct(sorted_v, 0.5)


# ---------------------------------------------------------------------------
# method_comparison.csv (EXP-002)
# ---------------------------------------------------------------------------
def _enc_size_map():
    """request_id -> (original_size, encrypted_size) dari export DB enkripsi."""
    path = RESULTS / "exported" / "experiment_encryption.csv"
    if not path.exists():
        return {}
    m = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            o = fnum(r, "original_payload_size_bytes", int, None)
            e = fnum(r, "encrypted_payload_size_bytes", int, None)
            if r.get("request_id") and o is not None and e is not None:
                m.setdefault(r["request_id"], (o, e))
    return m


def method_comparison(exp_dirs) -> None:
    sizes = _enc_size_map()
    headers = [
        "method", "total_requests", "success_rate_pct",
        "encryption_time_mean_ms", "encryption_time_std_ms",
        "decryption_time_mean_ms", "decryption_time_std_ms",
        "end_to_end_latency_mean_ms", "end_to_end_latency_p95_ms",
        "cipher_entropy_mean", "cipher_entropy_std",
        "psnr_mean", "psnr_min",
        "decrypt_verified_rate_pct",
        "original_size_mean_bytes", "encrypted_size_mean_bytes",
        "payload_expansion_ratio_mean",
        "psnr_infinite_rate_pct",
    ]
    rows = []
    methods = ["UHC", "Blowfish", "Hybrid UHC-Blowfish", "Adaptive"]
    for m in methods:
        tag = {"UHC": "UHC", "Blowfish": "Blo", "Hybrid UHC-Blowfish": "Hyb",
               "Adaptive": "Ada"}[m]
        path = RESULTS / f"EXP-002-{tag}" / "raw_batch_results.csv"
        main = [r for r in read_rows(path) if r.get("phase") == "main"]
        if not main:
            print(f"  [warn] {path.name} kosong — dilewati")
            continue
        enc = [fnum(r, "encryption_time_ms", float, 0) or 0 for r in main]
        dec = [fnum(r, "decryption_time_ms", float, 0) or 0 for r in main]
        lat = [fnum(r, "end_to_end_latency_ms", float, 0) or 0 for r in main]
        ent = [fnum(r, "cipher_entropy", float, 0) or 0 for r in main]
        sz = [sizes.get(r["request_id"], (0, 0)) for r in main]
        orig = [o for o, _ in sz]
        enct = [e for _, e in sz]
        ok = [r for r in main if fnum(r, "success", int, 0) == 1]
        verified = sum(1 for r in main
                       if str(r.get("decrypt_verified", "")).lower() == "true"
                       or str(r.get("decrypt_verified", "")) == "1")
        inf = sum(1 for r in main
                  if r.get("psnr") == "∞"
                  or str(r.get("psnr_is_infinite", "")).lower() == "true")
        lat_sorted = sorted(lat)
        p95 = _pct(lat_sorted, 0.95)
        expansion = [e / o if o else 0 for e, o in zip(enct, orig)]
        rows.append([
            m, len(main),
            round(100 * len(ok) / len(main), 2),
            round(statistics.mean(enc), 4), round(statistics.pstdev(enc), 4),
            round(statistics.mean(dec), 4), round(statistics.pstdev(dec), 4),
            round(statistics.mean(lat), 4), p95,
            round(statistics.mean(ent), 4), round(statistics.pstdev(ent), 4),
            "∞ (lossless)", "∞",
            round(100 * verified / len(main), 2),
            round(statistics.mean(orig), 2), round(statistics.mean(enct), 2),
            round(statistics.mean(expansion), 4),
            round(100 * inf / len(main), 2),
        ])
    write_csv(OUT / "method_comparison.csv", headers, rows)


# ---------------------------------------------------------------------------
# E. adaptive_vs_baseline.csv
# ---------------------------------------------------------------------------
def adaptive_vs_baseline(method_rows_meta) -> None:
    """Skor keamanan/performa ternormalisasi min-max; rumus di dokumentasi."""
    entries = {}  # method -> {enc_mean, lat_mean, ent_mean}
    # reuse method_comparison rows
    for tag, m in [("UHC", "UHC"), ("Blo", "Blowfish"), ("Hyb", "Hybrid UHC-Blowfish"), ("Ada", "Adaptive")]:
        path = RESULTS / f"EXP-002-{tag}" / "raw_batch_results.csv"
        main = [r for r in read_rows(path) if r.get("phase") == "main"]
        if not main:
            entries[m] = None
            continue
        enc = statistics.mean([fnum(r, "encryption_time_ms", float, 0) or 0 for r in main])
        lat = statistics.mean([fnum(r, "end_to_end_latency_ms", float, 0) or 0 for r in main])
        ent = statistics.mean([fnum(r, "cipher_entropy", float, 0) or 0 for r in main])
        entries[m] = {"enc": enc, "lat": lat, "ent": ent}

    avail = {m: v for m, v in entries.items() if v is not None}
    if not avail:
        print("  [warn] tidak ada data EXP-002 untuk adaptive_vs_baseline")
        return
    ent_min = min(v["ent"] for v in avail.values())
    ent_max = max(v["ent"] for v in avail.values())
    cost_min = min(v["enc"] + v["lat"] for v in avail.values())
    cost_max = max(v["enc"] + v["lat"] for v in avail.values())

    rows = []
    for m, v in avail.items():
        security = (v["ent"] - ent_min) / (ent_max - ent_min) if ent_max > ent_min else 1.0
        cost = v["enc"] + v["lat"]
        perf = (cost_max - cost) / (cost_max - cost_min) if cost_max > cost_min else 1.0
        combined = 0.5 * security + 0.5 * perf
        rows.append([m, round(100 * security, 2), round(100 * perf, 2),
                     round(100 * combined, 2), 0])
    rows.sort(key=lambda r: r[3], reverse=True)
    for i, r in enumerate(rows):
        r[4] = i + 1
    write_csv(OUT / "adaptive_vs_baseline.csv",
              ["method", "security_score", "performance_score", "combined_score", "rank"],
              rows)


# ---------------------------------------------------------------------------
# Struktur DecisionTree (deskriptif — bukan akurasi)
# ---------------------------------------------------------------------------
def tree_export() -> None:
    try:
        import joblib
        from sklearn.tree import export_text
    except Exception as e:
        print(f"  [warn] sklearn/joblib tidak tersedia: {e}")
        return
    model_path = Path(__file__).resolve().parent / "models" / "ai_selector_model.pkl"
    if not model_path.exists():
        print("  [warn] model pkl tidak ditemukan — lewati ekspor pohon")
        return
    clf = joblib.load(model_path)
    names = ["entropy", "size_kb", "glcm_correlation", "glcm_contrast"]
    text = export_text(clf, feature_names=names,
                       class_names=["UHC", "Blowfish", "Hybrid UHC-Blowfish"])
    (OUT / "decision_tree.txt").write_text(text, encoding="utf-8")
    fi = clf.feature_importances_
    write_csv(OUT / "feature_importance.csv", ["feature", "importance"],
              [[n, round(float(v), 6)] for n, v in zip(names, fi)])
    (OUT / "model_params.json").write_text(
        json.dumps(clf.get_params(), indent=2, default=str), encoding="utf-8")
    print("  wrote decision_tree.txt, feature_importance.csv, model_params.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp1", default=str(RESULTS / "EXP-001" / "raw_batch_results.csv"))
    args = ap.parse_args()

    exp1 = read_rows(Path(args.exp1))
    exp1_main = [r for r in exp1 if r.get("phase") == "main"]
    if not exp1_main:
        print("EXP-001 kosong.")
        return

    print("== A. selector_distribution ==")
    selector_distribution(exp1, exp1_main)
    print("== B. selector_feature_summary ==")
    selector_feature_summary(exp1_main)
    print("== method_comparison (EXP-002) ==")
    method_comparison([RESULTS])
    print("== E. adaptive_vs_baseline ==")
    adaptive_vs_baseline(None)
    print("== Tree DecisionTree ==")
    tree_export()
    print("\nSelesai →", OUT)


if __name__ == "__main__":
    main()