"""
batch_runner.py — AgroCipher batch encryption client.

Usage:
    python batch_runner.py <folder_dataset> [api_url] [output_csv]

API key dibaca otomatis dari file .env di folder project (GATEWAY_API_KEY).
Bisa juga di-override dengan env var: AGROCIPHER_API_KEY=mykey python batch_runner.py ./dataset

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
RETRY_COUNT = 3  # max attempts per image
RETRY_DELAY_S = 2.0  # seconds to wait between retries
FLUSH_EVERY = 10  # flush CSV to disk every N rows


# ---------------------------------------------------------------------------
# .env reader
# ---------------------------------------------------------------------------


def load_env_file() -> tuple:
    """
    Cari dan baca file .env, kembalikan (path_yang_dibaca, dict_nilai).
    Kandidat dicek berurutan, file pertama yang ada yang dipakai.
    Nilai inline komentar (# ...) diabaikan.
    """
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / ".env",  # root project  (client/../.env)
        script_dir / ".env",  # folder client
        Path("/opt/research/agrochiper/.env"),  # path absolut VPS
        Path.home() / "agrochiper" / ".env",  # ~/agrochiper/.env
    ]

    for env_path in candidates:
        if not env_path.exists():
            continue
        result: Dict[str, str] = {}
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                # Hapus trailing newline/whitespace dulu
                line = line.rstrip("\r\n")
                # Hapus inline komentar (# ...) — tapi hanya di luar tanda kutip
                if " #" in line:
                    line = line[: line.index(" #")]
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                # Hapus kutip pembungkus jika ada
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                result[key] = val
        return env_path, result

    return None, {}


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


def load_done_set(output_csv: str, rel_path_col: str = "relative_path") -> Set[str]:
    """
    Baca CSV yang sudah ada dan kembalikan set relative_path yang sudah
    berhasil diproses (kolom error kosong). Digunakan untuk fitur resume.
    """
    done: Set[str] = set()
    if not os.path.exists(output_csv):
        return done
    with open(output_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("error", "").strip() == "":
                done.add(row.get(rel_path_col, ""))
    return done


def mime_for(path: str) -> str:
    """Deteksi MIME type yang benar berdasarkan ekstensi file."""
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def send_image(api_url: str, image_path: str, api_key: str) -> Dict:
    """Kirim satu gambar ke API gateway dengan API Key auth."""
    headers = {"X-API-Key": api_key}
    mime = mime_for(image_path)
    with open(image_path, "rb") as f:
        files = {"file": (os.path.basename(image_path), f, mime)}
        resp = requests.post(api_url, files=files, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def send_with_retry(
    api_url: str,
    image_path: str,
    api_key: str,
    retries: int = RETRY_COUNT,
    delay: float = RETRY_DELAY_S,
) -> Dict:
    """
    Coba kirim gambar hingga `retries` kali.
    Langsung gagal pada 4xx (misal 401) — retry tidak akan membantu.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            return send_image(api_url, image_path, api_key)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code < 500:
                raise  # 4xx → jangan retry
            last_exc = e
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e

        if attempt < retries:
            print(f"          [retry {attempt}/{retries}] tunggu {delay}s ...")
            time.sleep(delay)

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
    # Prioritas 1: env var shell (AGROCIPHER_API_KEY)
    api_key = os.environ.get("AGROCIPHER_API_KEY", "").strip()
    key_src = "env var AGROCIPHER_API_KEY"

    # Prioritas 2: GATEWAY_API_KEY dari file .env
    if not api_key:
        env_path, env_vars = load_env_file()
        api_key = env_vars.get("GATEWAY_API_KEY", "").strip()
        key_src = str(env_path) if env_path else "tidak ditemukan"

    if not api_key:
        print("ERROR: API key tidak ditemukan.")
        print("  Pastikan file .env di root project memiliki baris:")
        print("    GATEWAY_API_KEY=<kunci-anda>")
        sys.exit(1)

    # Tampilkan panjang kunci dan 8 karakter terakhir untuk verifikasi
    print(f"API key source  : {key_src}")
    print(
        f"API key (len={len(api_key)}): {'*' * max(0, len(api_key) - 8)}{api_key[-8:]}"
    )

    if len(api_key) != 64:
        print(
            f"WARNING: Panjang kunci {len(api_key)} karakter, seharusnya 64. Periksa file .env!"
        )

    if not os.path.isdir(dataset_folder):
        print(f"ERROR: Folder '{dataset_folder}' tidak ditemukan.")
        sys.exit(1)

    image_files = find_image_files(dataset_folder)
    if not image_files:
        print(f"Tidak ada file gambar (.jpg/.jpeg/.png) di '{dataset_folder}'.")
        sys.exit(1)

    # --- Resume: lewati file yang sudah berhasil ---
    done_set = load_done_set(output_csv)
    resume_mode = bool(done_set)
    pending = [
        p for p in image_files if os.path.relpath(p, dataset_folder) not in done_set
    ]

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
            row: Dict = {
                "relative_path": rel_name,
                "filename": os.path.basename(img_path),
                "error": "",
                "method": "",
                "decision_code": "",
                "reasoning": "",
                "encryption_time": "",
                "decryption_time": "",
                "cipher_entropy": "",
                "psnr": "",
                "entropy": "",
                "size_kb": "",
                "glcm_correlation": "",
                "glcm_contrast": "",
            }

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
