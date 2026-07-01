"""
batch_runner.py — AgroCipher batch encryption client.

Usage:
    python batch_runner.py <folder_dataset> [api_url] [output_csv]

API key dibaca otomatis dari GATEWAY_API_KEY di file .env root project.

Examples:
    python batch_runner.py ./dataset-daun-kopi
    python batch_runner.py ./dataset http://localhost:8080/api/v1/encrypt-image results.csv
"""

import csv
import mimetypes
import os
import sys
import time
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
    """Kembalikan set relative_path yang sudah berhasil diproses (resume)."""
    done: Set[str] = set()
    if not os.path.exists(output_csv):
        return done
    with open(output_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("error", "").strip() == "":
                done.add(row.get("relative_path", ""))
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
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    dataset_folder = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) >= 3 else API_URL_DEFAULT
    output_csv = sys.argv[3] if len(sys.argv) >= 4 else "results_batch.csv"

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

    fieldnames = [
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

    csv_mode = "a" if resume_mode else "w"
    with open(output_csv, mode=csv_mode, newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not resume_mode:
            writer.writeheader()

        start_all = time.perf_counter()
        total_ok = 0
        total_err = 0
        total_all = len(pending)

        for idx, img_path in enumerate(pending, start=1):
            rel_name = os.path.relpath(img_path, dataset_folder)
            row: Dict = {k: "" for k in fieldnames}
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


if __name__ == "__main__":
    main()
