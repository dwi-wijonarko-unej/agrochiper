"""
batch_runner.py — AgroCipher batch encryption client.

Usage (legacy / kompatibel):
    python batch_runner.py <folder_dataset> [api_url] [output_csv]

Usage (mode eksperimen, EXP-001):
    python batch_runner.py <folder_dataset> [api_url] [output_csv] \
        --experiment-id EXP-001 --warmup 10 --repeat 3 [--force-rerun]

API key dibaca otomatis dari GATEWAY_API_KEY di file .env root project.

Examples:
    python batch_runner.py ./dataset-daun-kopi
    python batch_runner.py ./dataset http://localhost:8080/api/v1/encrypt-image results.csv
    python batch_runner.py ./dataset --experiment-id EXP-001 --warmup 10 --repeat 3
"""

import argparse
import base64
import csv
import datetime
import hashlib
import json
import mimetypes
import os
import platform
import subprocess
import sys
import time
import uuid
import math
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_URL_DEFAULT = "http://localhost:8080/api/v1/encrypt-image"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
RETRY_COUNT = 3
RETRY_DELAY_S = 2.0
FLUSH_EVERY = 10
RESULTS_DIR_DEFAULT = Path(__file__).resolve().parent.parent / "results"
REPO_ROOT = Path(__file__).resolve().parent.parent

# Satu-satunya .env yang dicari: tepat satu level di atas folder client/
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


# ---------------------------------------------------------------------------
# .env reader — sesederhana mungkin, tidak ada manipulasi string yang rumit
# ---------------------------------------------------------------------------


def read_gateway_api_key() -> str:
    """
    Baca GATEWAY_API_KEY dari ENV_FILE baris per baris.
    Tidak melakukan strip apapun selain newline — nilai diambil apa adanya.
    """
    if not ENV_FILE.exists():
        return ""

    with open(ENV_FILE, "rb") as f:  # buka sebagai bytes untuk debug
        raw = f.read()

    # Decode, normalize line endings
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")

    for line in text.split("\n"):
        # Cari baris yang tepat dimulai dengan GATEWAY_API_KEY=
        if line.startswith("GATEWAY_API_KEY="):
            val = line[len("GATEWAY_API_KEY=") :]  # ambil semua setelah '='
            return val  # kembalikan apa adanya, tanpa strip apapun
    return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_image_files(root_folder: str) -> List[str]:
    """Rekursif scan semua subfolder dan kumpulkan path file gambar."""
    files: List[str] = []
    for dirpath, _, filenames in os.walk(root_folder):
        for name in filenames:
            if name.lower().endswith(IMAGE_EXTENSIONS):
                files.append(os.path.join(dirpath, name))
    return sorted(files)


def load_done_set(output_csv: str) -> Set[str]:
    """Kembalikan set relative_path yang sudah berhasil diproses (legacy resume)."""
    done: Set[str] = set()
    if not os.path.exists(output_csv):
        return done
    with open(output_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("error", "").strip() == "":
                done.add(row.get("relative_path", ""))
    return done


def load_experiment_done(raw_csv: Path) -> Set[str]:
    """Kembalikan set 'relative_path::run_number' yang sudah sukses (EXP resume)."""
    done: Set[str] = set()
    if not raw_csv.exists():
        return done
    with open(raw_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("success", "").strip() == "1" and not row.get("error", "").strip():
                key = f"{row.get('relative_path','')}::{row.get('run_number','')}"
                done.add(key)
    return done


def mime_for(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def send_image(api_url: str, image_path: str, api_key: str) -> Dict:
    headers = {"X-API-Key": api_key}
    with open(image_path, "rb") as f:
        resp = requests.post(
            api_url,
            files={"file": (os.path.basename(image_path), f, mime_for(image_path))},
            headers=headers,
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()


def send_image_status(api_url: str, image_path: str, api_key: str, extra_headers: Optional[Dict[str, str]] = None):
    """Kembalikan (json, status_code, error). Tanpa retry — untuk eksperimen."""
    headers = {"X-API-Key": api_key}
    if extra_headers:
        headers.update(extra_headers)
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                api_url,
                files={"file": (os.path.basename(image_path), f, mime_for(image_path))},
                headers=headers,
                timeout=60,
            )
        if resp.status_code >= 200 and resp.status_code < 300:
            return resp.json(), resp.status_code, ""
        return {}, resp.status_code, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return {}, 0, str(e)


def save_ciphertext(resp: Dict, save_dir: Path, rid: str) -> None:
    """Simpan payload mentah (bukan base64) sebagai <rid>.bin — untuk EXP-003."""
    try:
        b64 = (resp.get("result") or {}).get("cipher_base64", "")
        if not b64:
            return
        (save_dir / f"{rid}.bin").write_bytes(base64.b64decode(b64))
    except Exception:
        pass


def send_with_retry(api_url: str, image_path: str, api_key: str) -> Dict:
    last_exc: Optional[Exception] = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            return send_image(api_url, image_path, api_key)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code < 500:
                raise  # 4xx → jangan retry
            last_exc = e
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
        if attempt < RETRY_COUNT:
            print(
                f"          [retry {attempt}/{RETRY_COUNT}] tunggu {RETRY_DELAY_S}s ..."
            )
            time.sleep(RETRY_DELAY_S)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Argumen
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AgroCipher batch runner")
    p.add_argument("dataset", help="Folder dataset citra")
    p.add_argument("api_url", nargs="?", default=API_URL_DEFAULT)
    p.add_argument("output_csv", nargs="?", default="results_batch.csv")
    p.add_argument("--experiment-id", default="",
                   help="Mode eksperimen: ID unik, mis. EXP-001")
    p.add_argument("--warmup", type=int, default=0,
                   help="Jumlah warm-up request (tidak masuk analisis utama)")
    p.add_argument("--repeat", type=int, default=1,
                   help="Jumlah pengulangan per citra")
    p.add_argument("--results-dir", default=str(RESULTS_DIR_DEFAULT),
                   help="Root folder hasil eksperimen")
    p.add_argument("--resume", action="store_true",
                   help="Lewati pasangan relative_path::run_number yang sudah sukses")
    p.add_argument("--force-rerun", action="store_true",
                   help="Abaikan resume dan ulang semua")
    p.add_argument("--concurrency", type=int, default=1,
                   help="Metadata only: eksekusi tetap serial (1)")
    p.add_argument("--extra-header", action="append", default=[],
                   metavar="'Key: value'",
                   help="Header tambahan untuk setiap request (bisa diulang). "
                        "Contoh: --extra-header 'X-Experiment-Force-Method: UHC'")
    p.add_argument("--save-ciphertext-dir", default="",
                   help="Opsional: simpan payload mentah (bukan base64) ke folder "
                        "ini, bernama <request_id>.bin (untuk analisis kriptografi EXP-003)")
    p.add_argument("--save-ciphertext-limit", type=int, default=0,
                   help="Maksimum jumlah ciphertext yang disimpan per skenario "
                        "(0 = tak terbatas). Gunakan 200-300 untuk membatasi "
                        "penggunaan disk (tiap payload ~1.7MB).")
    return p.parse_args()


def parse_extra_headers(raw: List[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for item in raw:
        if ":" in item:
            k, v = item.split(":", 1)
            headers[k.strip()] = v.strip()
    return headers


# ---------------------------------------------------------------------------
# Eksperimen (EXP-001)
# ---------------------------------------------------------------------------

EXPERIMENT_FIELDNAMES = [
    "experiment_id", "request_id", "run_number", "relative_path", "filename",
    "extension", "image_width", "image_height", "size_kb",
    "entropy", "glcm_correlation", "glcm_contrast",
    "method", "decision_code", "reasoning",
    "feature_extraction_time_ms", "selector_inference_time_ms",
    "encryption_time_ms", "decryption_time_ms", "end_to_end_latency_ms",
    "cipher_entropy", "psnr", "decrypt_verified",
    "http_status", "success", "error", "timestamp_utc",
    "phase", "psnr_is_infinite",
]


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or ""
    except Exception:
        return ""


def docker_images_best_effort() -> dict:
    try:
        out = subprocess.run(
            ["docker", "compose", "images", "--format", "json"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=15,
        )
        result: Dict[str, str] = {}
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                result[row.get("Repository", "") + ":" + row.get("Tag", "")] = row.get("ContainerName", "")
            except Exception:
                pass
        return result
    except Exception:
        return {}


def dataset_file_checksum(rel_paths: List[str]) -> str:
    """SHA-256 atas daftar relative path (bukan isi citra)."""
    payload = "\n".join(sorted(rel_paths)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def collect_experiment_row(exp_id, rid, run_number, rel_path, img_path, resp, status, error, phase):
    features = (resp or {}).get("features", {}) if resp else {}
    selector = (resp or {}).get("selector", {}) if resp else {}
    result = (resp or {}).get("result", {}) if resp else {}
    success = 1 if (status and 200 <= status < 300 and not error) else 0
    return {
        "experiment_id": exp_id,
        "request_id": rid or uuid.uuid4().hex,
        "run_number": run_number,
        "relative_path": rel_path,
        "filename": os.path.basename(img_path),
        "extension": os.path.splitext(img_path)[1].lower(),
        "image_width": features.get("image_width", ""),
        "image_height": features.get("image_height", ""),
        "size_kb": features.get("size_kb", ""),
        "entropy": features.get("entropy", ""),
        "glcm_correlation": features.get("glcm_correlation", ""),
        "glcm_contrast": features.get("glcm_contrast", ""),
        "method": result.get("method", ""),
        "decision_code": selector.get("decision_code", ""),
        "reasoning": selector.get("reasoning", ""),
        "feature_extraction_time_ms": features.get("feature_extraction_time_ms", ""),
        "selector_inference_time_ms": selector.get("selector_inference_time_ms", ""),
        "encryption_time_ms": result.get("encryption_time_ms", ""),
        "decryption_time_ms": result.get("decryption_time_ms", ""),
        "end_to_end_latency_ms": (resp or {}).get("end_to_end_latency_ms", ""),
        "cipher_entropy": result.get("cipher_entropy", ""),
        "psnr": result.get("psnr", ""),
        "decrypt_verified": result.get("decrypt_verified", ""),
        "http_status": status,
        "success": success,
        "error": error,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": phase,
        "psnr_is_infinite": result.get("psnr_is_infinite", ""),
    }


def build_run_metadata(args, image_files, main_rows, exp_dir, api_key_len) -> dict:
    rel_paths = [os.path.relpath(p, args.dataset) for p in image_files]
    ok_main = sum(1 for r in main_rows if r.get("success") == 1)
    fail_main = sum(1 for r in main_rows if r.get("success") != 1)
    return {
        "experiment_id": args.experiment_id,
        "timestamp_utc": now_utc_iso(),
        "images_found": len(image_files),
        "images_valid": None,
        "requests_total_main": len(main_rows),
        "requests_success_main": ok_main,
        "requests_failed_main": fail_main,
        "gateway_url_no_credentials": args.api_url,
        "git_commit": git_commit_hash(),
        "docker_images": docker_images_best_effort(),
        "python_version": sys.version.split()[0],
        "package_versions": _package_versions(),
        "parameters": {
            "warmup": args.warmup,
            "repeat": args.repeat,
            "concurrency": args.concurrency,
            "resume": args.resume,
            "force_rerun": args.force_rerun,
        },
        "hardware_os": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "dataset_file_checksum_sha256": dataset_file_checksum(rel_paths),
        "api_key_length": api_key_len,
    }


def _package_versions() -> dict:
    out: Dict[str, str] = {}
    for name in ("requests", "urllib3"):
        try:
            import importlib.metadata as md
            out[name] = md.version(name)
        except Exception:
            out[name] = "n/a"
    return out


def run_experiment(args, api_key) -> None:
    exp_dir = Path(args.results_dir) / args.experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    raw_csv = exp_dir / "raw_batch_results.csv"
    meta_json = exp_dir / "run_metadata.json"

    extra_headers = parse_extra_headers(args.extra_header)
    save_dir = Path(args.save_ciphertext_dir) if args.save_ciphertext_dir else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
    saved_ct = 0
    # Sampel deterministik merata bila limit > 0 (hindari bias ke kelas awal
    # yang muncul pertama dalam urutan file terurut).
    ct_stride = 1
    if args.save_ciphertext_limit > 0:
        ct_stride = max(1, math.ceil(len(find_image_files(args.dataset)) * args.repeat
                                     / args.save_ciphertext_limit))
    main_idx = 0

    image_files = find_image_files(args.dataset)
    if not image_files:
        print(f"Tidak ada file gambar di '{args.dataset}'.")
        sys.exit(1)

    write_mode = "a" if (args.resume and raw_csv.exists() and not args.force_rerun) else "w"
    done = load_experiment_done(raw_csv) if args.resume and not args.force_rerun else set()

    print(f"Experiment ID : {args.experiment_id}")
    print(f"Dataset       : {args.dataset}")
    print(f"Images found  : {len(image_files)}")
    print(f"Repeat        : {args.repeat}  Warmup: {args.warmup}")
    print(f"Output dir    : {exp_dir}")
    print(f"Resume        : {args.resume} (done={len(done)})")

    main_rows: List[Dict] = []
    warmup_rows: List[Dict] = []
    fail_reasons: Dict[str, int] = {}

    with open(raw_csv, mode=write_mode, newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=EXPERIMENT_FIELDNAMES)
        if write_mode == "w":
            writer.writeheader()

        # Warm-up (tidak masuk analisis utama; dicatat dengan phase=warmup)
        warm_target = image_files[0] if image_files else None
        if args.warmup > 0 and warm_target:
            print(f"\n-- Warm-up {args.warmup}x pada {os.path.basename(warm_target)} --")
            for i in range(args.warmup):
                resp, status, err = send_image_status(args.api_url, warm_target, api_key, extra_headers)
                rid = resp.get("request_id") if resp else ""
                row = collect_experiment_row(
                    args.experiment_id, rid, 0,
                    os.path.relpath(warm_target, args.dataset),
                    warm_target, resp, status, err, "warmup",
                )
                row["request_id"] = rid or "warmup-" + uuid.uuid4().hex
                writer.writerow(row)
                warmup_rows.append(row)
                print(f"  warmup {i + 1}/{args.warmup} -> status {status}")

        # Analisis utama
        total_planned = len(image_files) * args.repeat
        n_main = 0
        for img_path in image_files:
            rel_name = os.path.relpath(img_path, args.dataset)
            for run_number in range(1, args.repeat + 1):
                key = f"{rel_name}::{run_number}"
                if key in done:
                    print(f"[skip]  {rel_name} run {run_number} (sudah sukses)")
                    continue
                resp, status, err = send_image_status(args.api_url, img_path, api_key, extra_headers)
                rid = resp.get("request_id") if resp else ""
                row = collect_experiment_row(
                    args.experiment_id, rid, run_number, rel_name, img_path,
                    resp, status, err, "main",
                )
                if save_dir and rid and not err and (
                        args.save_ciphertext_limit == 0
                        or main_idx % ct_stride == 0):
                    save_ciphertext(resp, save_dir, rid)
                    saved_ct += 1
                writer.writerow(row)
                main_rows.append(row)
                n_main += 1
                main_idx += 1
                if err:
                    fail_reasons[err[:80]] = fail_reasons.get(err[:80], 0) + 1
                    print(f"[{n_main:4d}/{total_planned}] {rel_name:<46} run {run_number} -> ERROR: {err[:80]}")
                else:
                    print(f"[{n_main:4d}/{total_planned}] {rel_name:<46} run {run_number} -> {row['method']} (status {status})")
                if n_main % FLUSH_EVERY == 0:
                    csvfile.flush()
                    os.fsync(csvfile.fileno())
        csvfile.flush()

    metadata = build_run_metadata(args, image_files, main_rows, exp_dir, len(api_key))
    # fill images_valid properly: images with at least one success in main
    succeeded_paths = {r["relative_path"] for r in main_rows if r.get("success") == 1}
    metadata["images_valid"] = len(succeeded_paths)
    metadata["images_failed"] = len(image_files) - len(succeeded_paths)
    metadata["images_failed_reasons_summary"] = fail_reasons
    metadata["warmup_requests"] = len(warmup_rows)
    metadata["warmup_success"] = sum(1 for r in warmup_rows if r.get("success") == 1)
    with open(meta_json, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 50)
    print(f"  EKSPERIMEN {args.experiment_id} SELESAI")
    print("=" * 50)
    print(f"  Citra ditemukan      : {len(image_files)}")
    print(f"  Citra valid (>=1 OK) : {metadata['images_valid']}")
    print(f"  Request utama        : {len(main_rows)} (sukses {metadata['requests_success_main']}, gagal {metadata['requests_failed_main']})")
    print(f"  Warm-up              : {len(warmup_rows)}")
    print(f"  Ciphertext disimpan  : {saved_ct}/{args.save_ciphertext_limit if args.save_ciphertext_limit else 'semua'}")
    print(f"  Raw CSV              : {raw_csv}")
    print(f"  Metadata             : {meta_json}")
    print("=" * 50)
    if metadata["requests_failed_main"] > 0:
        print("Gagal tersimpan beserta alasannya. Gunakan --resume untuk melanjutkan.")
    if metadata["images_failed"] > 0:
        print(f"Catatan: gunakan key yang valid dan .env dengan API key 64 karakter.")


# ---------------------------------------------------------------------------
# Mode legacy (kompatibel penuh)
# ---------------------------------------------------------------------------

LEGACY_FIELDNAMES = [
    "relative_path",
    "filename",
    "method",
    "decision_code",
    "reasoning",
    "encryption_time",
    "decryption_time",
    "cipher_entropy",
    "psnr",
    "entropy",
    "size_kb",
    "glcm_correlation",
    "glcm_contrast",
    "error",
]


def run_legacy(args, api_key) -> None:
    dataset_folder = args.dataset
    api_url = args.api_url
    output_csv = args.output_csv

    if not os.path.isdir(dataset_folder):
        print(f"ERROR: Folder '{dataset_folder}' tidak ditemukan.")
        sys.exit(1)

    image_files = find_image_files(dataset_folder)
    if not image_files:
        print(f"Tidak ada file gambar di '{dataset_folder}'.")
        sys.exit(1)

    done_set = load_done_set(output_csv)
    resume_mode = bool(done_set)
    pending = [
        p for p in image_files if os.path.relpath(p, dataset_folder) not in done_set
    ]

    print()
    print(f"Dataset folder  : {dataset_folder}")
    print(f"API endpoint    : {api_url}")
    print(f"Output CSV      : {output_csv}")
    print(f"Total gambar    : {len(image_files)}")
    if resume_mode:
        print(f"Sudah selesai   : {len(done_set)} (resume mode aktif)")
    print(f"Akan diproses   : {len(pending)} gambar\n")

    if not pending:
        print("Semua gambar sudah diproses. Tidak ada yang perlu diulang.")
        sys.exit(0)

    csv_mode = "a" if resume_mode else "w"
    with open(output_csv, mode=csv_mode, newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=LEGACY_FIELDNAMES)
        if not resume_mode:
            writer.writeheader()

        start_all = time.perf_counter()
        total_ok = 0
        total_err = 0
        total_all = len(pending)

        for idx, img_path in enumerate(pending, start=1):
            rel_name = os.path.relpath(img_path, dataset_folder)
            row: Dict = {k: "" for k in LEGACY_FIELDNAMES}
            row["relative_path"] = rel_name
            row["filename"] = os.path.basename(img_path)

            try:
                resp_json = send_with_retry(api_url, img_path, api_key)
                features = resp_json.get("features", {})
                selector = resp_json.get("selector", {})
                result = resp_json.get("result", {})
                row.update(
                    {
                        "method": result.get("method", ""),
                        "decision_code": selector.get("decision_code", ""),
                        "reasoning": selector.get("reasoning", ""),
                        "encryption_time": result.get("encryption_time", ""),
                        "decryption_time": result.get("decryption_time", ""),
                        "cipher_entropy": result.get("cipher_entropy", ""),
                        "psnr": result.get("psnr", ""),
                        "entropy": features.get("entropy", ""),
                        "size_kb": features.get("size_kb", ""),
                        "glcm_correlation": features.get("glcm_correlation", ""),
                        "glcm_contrast": features.get("glcm_contrast", ""),
                    }
                )
                writer.writerow(row)
                total_ok += 1
                print(f"[{idx:4d}/{total_all}] {rel_name:<50} -> {row['method']} (OK)")

            except Exception as e:
                row["error"] = str(e)
                writer.writerow(row)
                total_err += 1
                print(f"[{idx:4d}/{total_all}] {rel_name:<50} -> ERROR: {e}")

            if idx % FLUSH_EVERY == 0:
                csvfile.flush()
                os.fsync(csvfile.fileno())

        csvfile.flush()

    end_all = time.perf_counter()
    print("\n" + "=" * 45)
    print("  RINGKASAN BATCH")
    print("=" * 45)
    print(f"  Berhasil diproses  : {total_ok:>6} gambar")
    print(f"  Gagal diproses     : {total_err:>6} gambar")
    print(f"  Total waktu batch  : {end_all - start_all:>8.2f} detik")
    print(f"  Hasil tersimpan di : {output_csv}")
    print("=" * 45)
    if total_err > 0:
        print(
            f"\nTip: Jalankan ulang perintah yang sama untuk me-retry {total_err} file yang gagal."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    if args.experiment_id and (args.warmup < 0 or args.repeat < 1):
        print("ERROR: --warmup >= 0 dan --repeat >= 1 untuk mode eksperimen.")
        sys.exit(1)

    # --- Baca API key ---
    api_key = read_gateway_api_key()

    print(f".env path       : {ENV_FILE}")
    print(f".env exists     : {ENV_FILE.exists()}")
    print(f"API key len     : {len(api_key)} karakter  (harus 64)")
    print(f"API key end     : ...{api_key[-8:] if len(api_key) >= 8 else api_key}")

    if len(api_key) != 64:
        print()
        print("ERROR: Panjang API key tidak 64 karakter.")
        print(f"       Nilai yang terbaca: [{api_key}]")
        print(f"       Periksa file: {ENV_FILE}")
        sys.exit(1)

    if not os.path.isdir(args.dataset):
        print(f"ERROR: Folder '{args.dataset}' tidak ditemukan.")
        sys.exit(1)

    if args.experiment_id:
        run_experiment(args, api_key)
    else:
        run_legacy(args, api_key)


if __name__ == "__main__":
    main()