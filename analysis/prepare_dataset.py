"""
prepare_dataset.py — Siapkan dataset eksperimen dari dataset mentah daun kopi.

- Sampling stratified N citra per kelas (reproducible dengan seed tetap).
- Downscale ke max-dim (aspect ratio dijaga), konversi RGB, simpan JPEG q=90.
- Output: <out>/<kelas>/<nama>.jpg + manifest.json (pemetaan, ukuran, checksum).

Sumber dataset mentah tidak diubah. Folder output (data/) tidak di-git.

Usage:
  python analysis/prepare_dataset.py \
      --source "data/Coffee Leaf Diseases/Coffee leaf Diseases" \
      --out data/experiment_dataset \
      --per-class 150 --max-dim 1024 --seed 42
"""

import argparse
import datetime
import json
import os
import random
from pathlib import Path

from PIL import Image

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def collect_class_files(source: Path, cls: str) -> list:
    d = source / cls
    if not d.is_dir():
        return []
    return sorted(
        p for p in d.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def process_image(src: Path, out_path: Path, max_dim: int) -> dict:
    im = Image.open(src)
    w0, h0 = im.size
    im = im.convert("RGB")
    scale = min(1.0, max_dim / max(w0, h0))
    if scale < 1.0:
        im = im.resize((max(1, round(w0 * scale)), max(1, round(h0 * scale))))
    im.save(out_path, "JPEG", quality=90)
    return {"src": str(src), "out": str(out_path), "original_w": w0,
            "original_h": h0, "new_w": im.width, "new_h": im.height}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/Coffee Leaf Diseases/Coffee leaf Diseases")
    ap.add_argument("--out", default="data/experiment_dataset")
    ap.add_argument("--per-class", type=int, default=150)
    ap.add_argument("--max-dim", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true",
                    help="Proses ulang file yang sudah ada (default: resume/skip)")
    args = ap.parse_args()

    source = Path(args.source)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    classes = sorted(
        c for c in os.listdir(source)
        if (source / c).is_dir()
    )
    print(f"Sumber        : {source}")
    print(f"Kelas ditemukan: {classes}")
    print(f"Per class      : {args.per_class}  Max-dim: {args.max_dim}  Seed: {args.seed}")

    rng = random.Random(args.seed)
    manifest = {
        "source_root": str(source),
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_class": args.per_class,
        "max_dim": args.max_dim,
        "seed": args.seed,
        "classes": {},
        "files": [],
    }
    failures = []
    total_done = 0
    total_skipped = 0

    for cls in classes:
        files = collect_class_files(source, cls)
        if len(files) < args.per_class:
            print(f"WARN: kelas '{cls}' hanya {len(files)} file (< {args.per_class}) — pakai semua.")
            sampled = files
        else:
            sampled = rng.sample(files, args.per_class)
        manifest["classes"][cls] = {"total": len(files), "sampled": len(sampled)}

        cls_out = out_root / cls
        cls_out.mkdir(parents=True, exist_ok=True)

        for src in sampled:
            out_path = cls_out / (src.stem + ".jpg")
            if out_path.exists() and not args.force:
                total_skipped += 1
                continue
            try:
                info = process_image(src, out_path, args.max_dim)
                manifest["files"].append(info)
                total_done += 1
            except Exception as e:
                failures.append({"src": str(src), "error": str(e)})
                print(f"  FAIL {src}: {e}")

        print(f"  {cls:<16} total={len(files):>5} sampled={len(sampled):>3} done={total_done}")

    manifest["failures"] = failures
    manifest_json = out_root / "manifest.json"
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\nSelesai.")
    print(f"  File baru   : {total_done}")
    print(f"  Skipped     : {total_skipped}")
    print(f"  Gagal       : {len(failures)}")
    print(f"  Manifest    : {manifest_json}")
    print("Distribusi kelas:")
    for cls, info in manifest["classes"].items():
        print(f"    {cls:<16} {info['sampled']} citra (dari {info['total']})")


if __name__ == "__main__":
    main()