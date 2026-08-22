#!/usr/bin/env python3
"""Tahap 5 — Pengujian keamanan (security testing).

Bagian A: agregasi metrik byte ciphertext dari EXP-003 yang sudah ada
          (entropi payload, korelasi byte, chi-square, ekspansi, NPCR/UACI).
Bagian B: ketahanan noise pada ciphertext — dekripsi OFFLINE payload tersimpan
          dengan mereplikasi persis kripto encryption-service (Hill mod-256 +
          Blowfish CBC/PKCS7), lalu mengukur PSNR pemulihan setelah body
          ciphertext dirusak noise Gaussian (sigma 8/16) dan salt&pepper
          (densitas 1%/5%). Header payload tidak dirusak agar payload tetap
          dapat diparsing.
Bagian C: estimasi keyspace teoretis per skema.

Output (results/stages/):
  stage5_security_test_results.csv     — ringkasan per metode (A + rata-rata B)
  stage5_noise_robustness_detail.csv   — per citra × per skenario noise (B)
  stage5_keyspace.csv                  — estimasi keyspace (C)
"""

import math
import os
import struct
import sys

import numpy as np
import pandas as pd
from PIL import Image
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.decrepit.ciphers.algorithms import Blowfish
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, modes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "results", "stages")
EXP3 = os.path.join(REPO, "results", "EXP-003")
DATASET_DIR = os.path.join(REPO, "data", "experiment_dataset_v2")

N_SAMPLES = 10          # payload per metode untuk uji noise
NOISE_PARAMS = [
    ("gaussian_sigma8", dict(kind="gauss", sigma=8)),
    ("gaussian_sigma16", dict(kind="gauss", sigma=16)),
    ("saltpepper_1pct", dict(kind="sp", density=0.01)),
    ("saltpepper_5pct", dict(kind="sp", density=0.05)),
]
SEED = 42


def read_env_file() -> dict:
    env = {}
    with open(os.path.join(REPO, ".env")) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load_env(env: dict):
    secret_key = env["SECRET_KEY"].encode("utf-8")
    pwd1 = int(env.get("UHC_MATRIX_SIZE", "16"))
    pwd2 = env.get("UHC_PASSWORD2", "7391")
    return secret_key, pwd1, pwd2


# ---------------------------------------------------------------------------
# Replikasi kripto encryption-service/app.py (harus identik bit-per-bit)
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
        aug[baris] = (aug[baris] - aug[baris, 0] * aug[0]) % 256
    for kolom in range(1, n):
        for baris in range(kolom):
            aug[baris] = (aug[baris] - aug[baris, kolom] * aug[kolom]) % 256
    return msa, aug[:, n:]


def hill_multiply(data: np.ndarray, key_matrix: np.ndarray, n: int) -> np.ndarray:
    total_cols = len(data) // n
    result = np.empty(len(data), dtype=np.uint8)
    chunk = data.reshape(n, total_cols).astype(np.int32)
    out = (key_matrix.astype(np.int32) @ chunk) % 256
    result[:] = out.astype(np.uint8).flatten()
    return result


def blowfish_decrypt(data_bytes: bytes, secret_key: bytes) -> bytes:
    iv, enc = data_bytes[:8], data_bytes[8:]
    cipher = Cipher(Blowfish(secret_key), modes.CBC(iv), backend=default_backend())
    dec = cipher.decryptor()
    padded = dec.update(enc) + dec.finalize()
    unpadder = padding.PKCS7(64).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def parse_and_decrypt(payload: bytes, n_uhc: int, x0: float,
                      secret_key: bytes) -> tuple[int, int, bytes]:
    bio = memoryview(payload)
    w, h = struct.unpack("II", bio[:8])
    tag = bytes(bio[8:11])
    off = 11
    if tag == b"BLO":
        final = blowfish_decrypt(bytes(bio[off:]), secret_key)
    else:
        pad_len = struct.unpack("I", bio[off:off + 4])[0]
        off += 4
        body = bytes(bio[off:])
        _, inv = generate_key_matrix(n_uhc, x0, "d")
        if tag == b"UHC":
            dec_padded = hill_multiply(
                np.frombuffer(body, dtype=np.uint8), inv, n_uhc)
        else:  # HYB
            dec_blw = blowfish_decrypt(body, secret_key)
            dec_padded = hill_multiply(
                np.frombuffer(dec_blw, dtype=np.uint8), inv, n_uhc)
        final = dec_padded[: len(dec_padded) - pad_len].tobytes()
    return w, h, final


# ---------------------------------------------------------------------------
# Korupsi & metrik
# ---------------------------------------------------------------------------
def corrupt_body(payload: bytes, params: dict, rng: np.random.Generator) -> bytes:
    head = 11 if payload[8:11] == b"BLO" else 15
    body = np.frombuffer(payload[head:], dtype=np.uint8).copy()
    if params["kind"] == "gauss":
        noise = np.round(rng.normal(0, params["sigma"], body.shape))
        body = ((body.astype(np.int16) + noise.astype(np.int16)) % 256).astype(np.uint8)
    else:
        mask = rng.random(body.shape) < params["density"]
        half = mask.size
        salts = rng.random(body.shape) < 0.5
        body[mask & salts] = 255
        body[mask & ~salts] = 0
    return payload[:head] + body.tobytes()


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return math.inf if mse == 0 else 20 * math.log10(255.0 / math.sqrt(mse))


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---------------- Bagian A: agregasi metrik EXP-003 --------------------
    summary = pd.read_csv(os.path.join(EXP3, "crypto_metrics_summary.csv"))
    npcr = pd.read_csv(os.path.join(EXP3, "npcr_uaci.csv"))
    npcr_mean = npcr.groupby("method")[["npcr_pct", "uaci_pct"]].mean().round(4)

    detail = pd.read_csv(os.path.join(EXP3, "crypto_metrics_detail.csv"))

    # Baseline tanpa enkripsi: flip 1 kanal piksel (0,0) sebanyak +1
    base_rows = []
    for _, r in detail.drop_duplicates("relative_path").iterrows():
        w, h = int(r["width"]), int(r["height"])
        changed_px = 1
        base_rows.append({
            "npcr_pct": 100.0 * changed_px / (w * h),
            "uaci_pct": 100.0 * 1 / (255 * w * h * 3),
        })
    baseline = pd.DataFrame(base_rows).mean().round(6)

    sec_rows = []
    for _, r in summary.iterrows():
        m = r["method"]
        sec_rows.append({
            "scheme": m,
            "payload_entropy_bits": round(r["mean_payload_entropy"], 4),
            "adjacent_byte_corr": round(r["mean_corr_adjacent"], 6),
            "row_gap_byte_corr": round(r["mean_corr_row_gap"], 6),
            "chi2_stat_mean": round(r["mean_chi2_stat"], 1),
            "chi2_uniform_pass_pct": round(r["uniform_pass_rate_pct"], 2),
            "payload_expansion_ratio": round(r["mean_expansion_ratio"], 6),
            "npcr_pct": round(npcr_mean.loc[m, "npcr_pct"], 4) if m in npcr_mean.index else None,
            "uaci_pct": round(npcr_mean.loc[m, "uaci_pct"], 4) if m in npcr_mean.index else None,
        })
    sec_rows.append({
        "scheme": "baseline_no_encryption",
        "payload_entropy_bits": "",
        "adjacent_byte_corr": "", "row_gap_byte_corr": "",
        "chi2_stat_mean": "", "chi2_uniform_pass_pct": "",
        "payload_expansion_ratio": 1.0,
        "npcr_pct": round(float(baseline["npcr_pct"]), 6),
        "uaci_pct": round(float(baseline["uaci_pct"]), 6),
    })
    f_sec = os.path.join(OUT_DIR, "stage5_security_test_results.csv")
    pd.DataFrame(sec_rows).to_csv(f_sec, index=False)
    print("[stage5/A] ringkasan metrik ciphertext + NPCR/UACI ditulis.")

    # ---------------- Bagian B: ketahanan noise ciphertext -----------------
    env = read_env_file()
    secret_key, n_uhc, pwd2 = load_env(env)
    x0 = float("0." + pwd2 + "1")
    ct_dir = os.path.join(EXP3, "ciphertexts")

    samples = []
    for method in ["UHC", "Blowfish", "Hybrid UHC-Blowfish"]:
        sub = detail[detail["method"] == method].drop_duplicates("relative_path")
        sub = sub.iloc[:: max(1, len(sub) // (N_SAMPLES * 10))][:N_SAMPLES * 3]
        picked = 0
        for _, r in sub.iterrows():
            rel = r["relative_path"]
            ct_path = os.path.join(ct_dir, f"{r['request_id']}.bin")
            orig_path = os.path.join(DATASET_DIR, rel)
            if not (os.path.exists(ct_path) and os.path.exists(orig_path)):
                continue
            samples.append({"method": method, "relative_path": rel,
                            "ct_path": ct_path, "orig_path": orig_path})
            picked += 1
            if picked >= N_SAMPLES:
                break
        print(f"[stage5/B] sampel {method}: {picked} payload")

    rng_master = np.random.default_rng(SEED)
    detail_rows, agg_rows = [], []
    for s in samples:
        with open(s["ct_path"], "rb") as fh:
            payload = fh.read()
        original = Image.open(s["orig_path"]).convert("RGB")
        orig_arr = np.asarray(original)
        try:
            w, h, clean = parse_and_decrypt(payload, n_uhc, x0, secret_key)
            clean_ok = (clean == original.tobytes())
        except Exception:
            w, h, clean_ok = None, None, False
        if not clean_ok:
            print(f"[stage5/B][WARN] clean-decrypt gagal: {s['relative_path']}")
            continue

        for label, params in NOISE_PARAMS:
            rng = np.random.default_rng(abs(hash((s['relative_path'], label))) % (2**32))
            corrupted = corrupt_body(payload, params, rng)
            try:
                _, _, rec = parse_and_decrypt(corrupted, n_uhc, x0, secret_key)
                rec_arr = np.frombuffer(rec, dtype=np.uint8)[: w * h * 3].reshape(h, w, 3)
                val = psnr(rec_arr, orig_arr)
                ok = True
            except Exception:
                val, ok = np.nan, False
            detail_rows.append({
                "method": s["method"], "relative_path": s["relative_path"],
                "noise": label, "decrypt_ok": ok,
                "psnr_db": (round(val, 2) if np.isfinite(val) else ("inf" if ok else "")),
            })

    det = pd.DataFrame(detail_rows)
    f_det = os.path.join(OUT_DIR, "stage5_noise_robustness_detail.csv")
    det.to_csv(f_det, index=False)

    for (m, noise), sub in det.groupby(["method", "noise"]):
        vals = pd.to_numeric(sub["psnr_db"], errors="coerce").dropna()
        agg_rows.append({
            "method": m, "noise": noise, "n": len(sub),
            "decrypt_failure_n": int((~sub["decrypt_ok"]).sum()),
            "psnr_mean_db": round(vals.mean(), 2) if len(vals) else "",
            "psnr_min_db": round(vals.min(), 2) if len(vals) else "",
            "psnr_max_db": round(vals.max(), 2) if len(vals) else "",
        })
    agg = pd.DataFrame(agg_rows)
    f_agg = os.path.join(OUT_DIR, "stage5_noise_robustness_summary.csv")
    agg.to_csv(f_agg, index=False)
    print("\n[stage5/B] PSNR pemulihan setelah noise:")
    print(agg.to_string(index=False))

    # ---------------- Bagian C: estimasi keyspace --------------------------
    uhc_free = n_uhc * (n_uhc - 1) // 2
    uhc_diag_units = n_uhc  # diagonal harus genap-salinan unit (ganjil) mod 256 -> 128 pilihan
    uhc_bits = uhc_free * 8 + uhc_diag_units * 7
    bf_bits = min(len(secret_key) * 8, 448)
    ks_rows = [
        {"scheme": "UHC",
         "keyspace_bits": uhc_bits,
         "note": (f"Matriks segitiga-atas {n_uhc}x{n_uhc} mod 256: "
                  f"{uhc_free} entri bebas (8 bit) + {uhc_diag_units} diagonal unit "
                  f"(7 bit). Catatan: kunci efektif dibatasi ruang seed "
                  f"logistic-map dari UHC_PASSWORD2.")},
        {"scheme": "Blowfish",
         "keyspace_bits": bf_bits,
         "note": f"Kunci terkonfigurasi {len(secret_key)} byte (maks 448 bit)."},
        {"scheme": "Hybrid UHC-Blowfish",
         "keyspace_bits": uhc_bits + bf_bits,
         "note": "Produk ruang kunci independen UHC dan Blowfish."},
    ]
    f_ks = os.path.join(OUT_DIR, "stage5_keyspace.csv")
    pd.DataFrame(ks_rows).to_csv(f_ks, index=False)
    print("\n[stage5/C] estimasi keyspace:")
    print(pd.DataFrame(ks_rows)[["scheme", "keyspace_bits"]].to_string(index=False))

    print(f"\n[stage5] tulis: {f_sec}\n[stage5] tulis: {f_det}\n"
          f"[stage5] tulis: {f_agg}\n[stage5] tulis: {f_ks}")


if __name__ == "__main__":
    sys.exit(main())
