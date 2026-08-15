"""
crypto_metrics.py — Analisis kriptografi ciphertext EXP-003 (offline).

Input:
  results/EXP-003/ciphertexts/<request_id>.bin   (payload: header + ciphertext)
  results/EXP-002-{UHC,Blo,Hyb,Ada}/raw_batch_results.csv  (request_id -> method)
  data/experiment_dataset_v2/                  (citra sumber utk NPCR/UACI)
  .env                                            (SECRET_KEY, UHC_*)

Output (results/EXP-003/):
  crypto_metrics_detail.csv    per-sampel: entropy, chi2, korelasi, ukuran
  crypto_metrics_summary.csv   agregat per metode
  npcr_uaci.csv                NPCR/UACI differential (re-encrypt offline)

Catatan ilmiah & keterbatasan (didokumentasikan di docs/CRYPTO_METRICS.md):
  - Blowfish asli memakai IV acak os.urandom(8) per request. Untuk NPCR/UACI
    differential yang menuntut panjang ciphertext identik, script ini memakai
    IV tetap (b"\\x00"*8) pada BOTH encrypt — IV bukan bagian perbandingan.
  - "Korelasi vertikal" dihitung via lag = 3*width (baris RGB raster), bukan
    korelasi spasial 2D; bukan klaim keamanan.
  - chi-square uniformity memakai critical value df=255 (alpha=0.05); tidak
    memakai p-value eksak (tanpa scipy).
"""

import argparse
import base64
import csv
import io
import json
import os
import random
import statistics
import struct
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CT_DIR = ROOT / "results" / "EXP-003" / "ciphertexts"
OUT_DIR = ROOT / "results" / "EXP-003"
DATASET_ROOT = ROOT / "data" / "experiment_dataset_v2"
CLASSES = ["Healthy", "Miner", "Phoma", "Red Spider Mite", "Rust", "Cerscospora"]

CHI2_CRIT_255 = 292.982  # chi2 df=255 alpha=0.05
BLOWFISH_IV = b"\x00" * 8  # IV tetap untuk uji differential saja


def load_env() -> dict:
    env = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ---------------------------------------------------------------------------
# Replika fungsi kriptografi encryption-service (harus identik)
# ---------------------------------------------------------------------------
def logistic_map(x0: float, banyak: int) -> np.ndarray:
    x0 = x0 % 1.0
    if x0 == 0.0:
        x0 = 0.5
    x = x0
    for _ in range(1000):
        x = 3.923 * x * (1 - x)
    barisan = np.empty(banyak, dtype=np.int32)
    for i in range(banyak):
        x = 3.923 * x * (1 - x)
        barisan[i] = int(abs(x * 1000)) % 256
    return barisan


def generate_key_matrix(n: int, x0: float, mode: str = "e"):
    banyak = int(n * (n - 1) / 2)
    barisan = logistic_map(x0, banyak + n - 1)
    msa = np.eye(n, dtype=np.int32)
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            msa[i, j] = barisan[idx]
            idx += 1
    for baris_i in range(1, n):
        msa[baris_i] = (msa[baris_i] + barisan[idx] * msa[0]) % 256
        idx += 1
    if mode == "e":
        return msa
    aug = np.zeros((n, 2 * n), dtype=np.int32)
    aug[:, :n] = msa
    aug[:, n:] = np.eye(n, dtype=np.int32)
    for baris in range(1, n):
        aug[baris] = (aug[baris] + (-aug[baris, 0]) * aug[0]) % 256
    for kolom in range(1, n):
        for baris in range(kolom):
            aug[baris] = (aug[baris] + (-aug[baris, kolom]) * aug[kolom]) % 256
    return msa, aug[:, n:]


def hill_multiply(data: np.ndarray, key_matrix: np.ndarray, n: int) -> np.ndarray:
    total_cols = len(data) // n
    result = np.empty(len(data), dtype=np.uint8)
    key_i32 = key_matrix.astype(np.int32)
    chunk = data.reshape(n, total_cols).astype(np.int32)
    out = np.dot(key_i32, chunk) % 256
    result[:] = out.astype(np.uint8).flatten()
    return result


def process_blowfish(data_bytes: bytes, mode: str, env, fixed_iv: bool = False) -> bytes:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.decrepit.ciphers.algorithms import Blowfish

    key = env["SECRET_KEY"].encode("utf-8")
    if mode == "encrypt":
        iv = BLOWFISH_IV if fixed_iv else os.urandom(8)
        padder = padding.PKCS7(64).padder()
        padded = padder.update(data_bytes) + padder.finalize()
        cipher = Cipher(Blowfish(key), modes.CBC(iv), backend=default_backend())
        enc = cipher.encryptor()
        return iv + enc.update(padded) + enc.finalize()
    iv = data_bytes[:8]
    enc_data = data_bytes[8:]
    cipher = Cipher(Blowfish(key), modes.CBC(iv), backend=default_backend())
    dec = cipher.decryptor()
    padded = dec.update(enc_data) + dec.finalize()
    unpadder = padding.PKCS7(64).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def uhc_encrypt(img_bytes: bytes, n: int, x0: float) -> bytes:
    pad_len = (n - len(img_bytes) % n) % n
    img_padded = np.pad(np.frombuffer(img_bytes, dtype=np.uint8), (0, pad_len), "constant")
    enc = hill_multiply(img_padded, generate_key_matrix(n, x0, "e"), n)
    return enc.tobytes(), pad_len


def encrypt_offline(method: str, img_bytes: bytes, env, n: int, x0: float,
                    width: int, height: int, fixed_iv: bool = False) -> bytes:
    """Replika payload format encryption-service."""
    if method == "UHC":
        enc, pad_len = uhc_encrypt(img_bytes, n, x0)
        return struct.pack("II", width, height) + b"UHC" + struct.pack("I", pad_len) + enc
    if method == "Blowfish":
        enc = process_blowfish(img_bytes, "encrypt", env, fixed_iv)
        return struct.pack("II", width, height) + b"BLO" + enc
    enc1, pad_len = uhc_encrypt(img_bytes, n, x0)
    enc2 = process_blowfish(enc1, "encrypt", env, fixed_iv)
    return struct.pack("II", width, height) + b"HYB" + struct.pack("I", pad_len) + enc2


# ---------------------------------------------------------------------------
# Metrik byte
# ---------------------------------------------------------------------------
def parse_payload(payload: bytes):
    bio = io.BytesIO(payload)
    w, h = struct.unpack("II", bio.read(8))
    tag = bio.read(3)
    if tag in (b"UHC", b"HYB"):
        pad_len = struct.unpack("I", bio.read(4))[0]
    else:
        pad_len = None
    return w, h, tag, pad_len, bio.read()


def entropy_bytes(data: np.ndarray) -> float:
    hist = np.bincount(data, minlength=256).astype(np.float64)
    if hist.sum() == 0:
        return 0.0
    prob = hist / hist.sum()
    prob = prob[prob > 0]
    return float(-np.sum(prob * np.log2(prob)))


def chi2_uniform(data: np.ndarray):
    hist = np.bincount(data, minlength=256).astype(np.float64)
    exp = data.size / 256.0
    stat = float(np.sum((hist - exp) ** 2 / exp))
    return stat, stat < CHI2_CRIT_255


def pearson_lag(data: np.ndarray, lag: int):
    if len(data) <= lag:
        return None
    a = data[:-lag].astype(np.float64)
    b = data[lag:].astype(np.float64)
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=300)
    ap.add_argument("--npcr-images", type=int, default=10)
    args = ap.parse_args()

    env = load_env()
    for k in ("SECRET_KEY", "UHC_MATRIX_SIZE", "UHC_PASSWORD2"):
        if k not in env:
            print(f"[error] {k} tidak ada di .env")
            return
    n_uhc = int(env["UHC_MATRIX_SIZE"])
    x0_uhc = float("0." + env["UHC_PASSWORD2"] + "1")

    # request_id -> (method, relative_path, width, height)
    rmap = {}
    for tag in ("UHC", "Blo", "Hyb", "Ada"):
        m = {"UHC": "UHC", "Blo": "Blowfish", "Hyb": "Hybrid UHC-Blowfish"}.get(tag, "Adaptive")
        path = ROOT / "results" / f"EXP-002-{tag}" / "raw_batch_results.csv"
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("phase") != "main" or not r.get("request_id"):
                    continue
                rmap[r["request_id"]] = (
                    r["method"], r["relative_path"],
                    int(r["image_width"]), int(r["image_height"]))

    files = sorted(CT_DIR.glob("*.bin"))
    print(f"ciphertext tersedia: {len(files)}")

    by_method = {"UHC": [], "Blowfish": [], "Hybrid UHC-Blowfish": []}
    unmatched = 0
    for fp in files:
        info = rmap.get(fp.stem)
        if not info:
            unmatched += 1
            continue
        by_method[info[0]].append((fp, info))

    if unmatched:
        print(f"  [warn] {unmatched} ciphertext tanpa mapping request_id")

    rng = random.Random(42)
    detail_rows = []
    summaries = []
    for method, entries in by_method.items():
        sample = rng.sample(entries, min(args.sample, len(entries)))
        ents, chi2s, cors_h, cors_r, sizes, cip_sizes, exp_rat = [], [], [], [], [], [], []
        for fp, (_, rel, w, h) in sample:
            payload = fp.read_bytes()
            p_w, p_h, tag, pad_len, cipher = parse_payload(payload)
            pbytes = np.frombuffer(payload, dtype=np.uint8)
            cbytes = np.frombuffer(cipher, dtype=np.uint8)
            ent = entropy_bytes(pbytes)
            ent_c = entropy_bytes(cbytes)
            chi2, passed = chi2_uniform(pbytes)
            corr_h = pearson_lag(pbytes, 1)
            corr_r = pearson_lag(pbytes, 3 * p_w)
            ents.append(ent); chi2s.append(chi2)
            if corr_h is not None:
                cors_h.append(corr_h)
            if corr_r is not None:
                cors_r.append(corr_r)
            # ukuran referensi: re-encrypt offline citra sumber
            img_path = DATASET_ROOT / rel
            if img_path.exists():
                img = Image.open(img_path).convert("RGB")
                orig = len(img.tobytes())
                sizes.append(orig)
                cip_sizes.append(len(payload))
                exp_rat.append(len(payload) / orig if orig else 0.0)
            detail_rows.append([
                fp.stem, method, rel, p_w, p_h,
                round(ent, 6), round(ent_c, 6),
                round(chi2, 2), int(passed), round(chi2 / CHI2_CRIT_255, 4),
                round(corr_h, 6) if corr_h is not None else "",
                round(corr_r, 6) if corr_r is not None else "",
                len(payload),
            ])
        pass_rate = (round(100 * sum(1 for c in chi2s if c < CHI2_CRIT_255) / len(chi2s), 2)
                     if chi2s else "")
        summaries.append([
            method, len(sample),
            _stat_mean(ents), _stat_mean(cors_h), _stat_mean(cors_r),
            round(statistics.mean(chi2s), 2) if chi2s else "",
            pass_rate,
            _stat_mean(sizes), _stat_mean(cip_sizes), _stat_mean(exp_rat),
        ])

    detail_h = ["request_id", "method", "relative_path", "width", "height",
                "payload_entropy", "cipher_entropy", "chi2_stat",
                "chi2_uniform_passed", "chi2_over_crit",
                "corr_adjacent_bytes", "corr_row_gap", "payload_size_bytes"]
    _write(OUT_DIR / "crypto_metrics_detail.csv", detail_h, detail_rows)
    _write(OUT_DIR / "crypto_metrics_summary.csv",
           ["method", "samples", "mean_payload_entropy", "mean_corr_adjacent",
            "mean_corr_row_gap", "mean_chi2_stat", "uniform_pass_rate_pct",
            "mean_original_size_bytes", "mean_payload_size_bytes",
            "mean_expansion_ratio"],
           summaries)

    # ------------------------------------------------------------------
    # NPCR / UACI differential (re-encrypt offline, Blowfish IV tetap)
    # ------------------------------------------------------------------
    k = args.npcr_images
    classes = CLASSES
    pool = []
    for cls in classes:
        d = DATASET_ROOT / cls
        imgs = sorted(p.name for p in d.glob("*.jpg"))[: (k + len(classes) - 1) // len(classes)]
        pool.extend(str(d / i) for i in imgs)
    pool = pool[:k]

    npcr_rows = []
    npcr_raw, uaci_raw = [], []
    for img_path in pool:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        orig = np.frombuffer(img.tobytes(), dtype=np.uint8).copy()
        variant = orig.copy()
        variant[0] ^= 1  # flip 1 byte: channel R pixel (0,0)
        raw_diff = (orig != variant).sum()
        npcr_raw.append(100.0 * raw_diff / orig.size)
        uaci_raw.append(100.0 * float(np.mean(np.abs(orig - variant) / 255.0)))

        for method in ("UHC", "Blowfish", "Hybrid UHC-Blowfish"):
            c1 = np.frombuffer(encrypt_offline(method, orig.tobytes(), env, n_uhc, x0_uhc, w, h, True), dtype=np.uint8)
            c2 = np.frombuffer(encrypt_offline(method, variant.tobytes(), env, n_uhc, x0_uhc, w, h, True), dtype=np.uint8)
            n_min = min(len(c1), len(c2))
            diff = (c1[:n_min] != c2[:n_min]).sum()
            npcr = 100.0 * diff / n_min
            uaci = 100.0 * float(np.mean(np.abs(c1[:n_min].astype(int) - c2[:n_min].astype(int)) / 255.0))
            npcr_rows.append([Path(img_path).parent.name + "/" + Path(img_path).name,
                              method, round(npcr, 4), round(uaci, 4)])

    npcr_h = ["relative_path", "method", "npcr_pct", "uaci_pct"]
    npcr_rows.append(["RAW_IMAGE_BASELINE", "none", round(statistics.mean(npcr_raw), 6),
                      round(statistics.mean(uaci_raw), 6)])
    _write(OUT_DIR / "npcr_uaci.csv", npcr_h, npcr_rows)

    agg_npcr = {}
    for r in npcr_rows:
        if r[1] == "none":
            continue
        agg_npcr.setdefault(r[1], ([], []))[0].append(r[2])
        agg_npcr.setdefault(r[1], ([], []))[1].append(r[3])
    print("\nNPCR/UACI (mean atas %d citra):" % k)
    for m in ("UHC", "Blowfish", "Hybrid UHC-Blowfish"):
        if m in agg_npcr:
            print(f"  {m:22s} NPCR={statistics.mean(agg_npcr[m][0]):.3f}%  UACI={statistics.mean(agg_npcr[m][1]):.3f}%")
    print(f"  {'RAW baseline':22s} NPCR={statistics.mean(npcr_raw):.5f}%  UACI={statistics.mean(uaci_raw):.4f}%")

    (OUT_DIR / "crypto_metrics.json").write_text(
        json.dumps({
            "chi2_crit_255_alpha005": CHI2_CRIT_255,
            "blowfish_iv_note": "IV tetap b'\\x00'*8 hanya untuk uji differential offline; "
                                "runtime service memakai os.urandom(8)",
            "npcr_uaci_notes": "1-byte flip (pixel(0,0) ch R); plaintext vs variant, "
                               "mode enkripsi sama, panjang identik",
            "baseline_npcr_mean": statistics.mean(npcr_raw),
            "baseline_uaci_mean": statistics.mean(uaci_raw),
        }, indent=2, default=str), encoding="utf-8")

    print("\nSelesai →", OUT_DIR)


def _stat_mean(v):
    return round(statistics.mean(v), 6) if v else ""


def _write(path: Path, headers: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  wrote {path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()