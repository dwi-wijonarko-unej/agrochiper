"""
prepare_mixed_dataset.py — Gabungkan SEMUA sumber dataset daun kopi menjadi
dataset eksperimen ternormalisasi (6 kelas) untuk rerun Fase 0–5.

Sumber (5):
  OLD      data/Coffee Leaf Diseases/Coffee leaf Diseases
  COF      data/coffee___healthy|rust|red_spider_mite
  DRIVE    data/drive-download-20240530T171920Z-001
  ETHTEST  data/ethiopian cofee leaf dataset/test
  ETHAUG   data/ethiopian cofee leaf dataset/train aug

Normalisasi kelas:
  Healthy | Rust | Miner | Phoma | Red Spider Mite | Cerscospora

Strategi sampling:
  - Cap PER_CLASS citra per kelas; distribusi round-robin antar sumber
    (sumber dikocok dulu, seed tetap) supaya tidak didominasi ETHAUG
    (10.800 duplikat dekat augmentasi).
  - Downscale max-dim 1024, RGB, JPEG q90. Output: <out>/<Kelas>/<TAG>__<nama>.

Usage:
  python analysis/prepare_mixed_dataset.py --out data/experiment_dataset_v2 \
      --per-class 500 --max-dim 1024 --seed 42
"""

import argparse
import datetime
import json
import random
from collections import defaultdict
from pathlib import Path

from PIL import Image

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")

SOURCES = [
    ("OLD", Path("data/Coffee Leaf Diseases/Coffee leaf Diseases")),
    ("COF", Path("data")),
    ("DRIVE", Path("data/drive-download-20240530T171920Z-001")),
    ("ETHTEST", Path("data/ethiopian cofee leaf dataset/test")),
    ("ETHAUG", Path("data/ethiopian cofee leaf dataset/train aug")),
]

CLASS_MAP = {
    "Healthy": "Healthy", "healthy": "Healthy",
    "Rust": "Rust", "rust": "Rust", "Leaf rust": "Rust",
    "Red Spider Mite": "Red Spider Mite",
    "red_spider_mite": "Red Spider Mite",
    "Phoma": "Phoma",
    "Cerscospora": "Cerscospora",
    "Miner": "Miner",
}


def discover(root: Path, tag: str) -> list:
    """Kembalikan list (normal_class, filepath) di bawah root."""
    found = []
    if not root.is_dir():
        return found
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if tag == "COF" and not child.name.startswith("coffee___"):
            continue  # di data/ hanya folder coffee___* milik sumber COF
        cls_name = child.name
        if tag == "COF":
            cls_name = cls_name.replace("coffee___", "")
        norm = CLASS_MAP.get(cls_name)
        if norm is None:
            print(f"  [warn] kelas tak dikenal di {tag}: '{cls_name}' — dilewati")
            continue
        files = sorted(
            p for p in child.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
        for f in files:
            found.append((norm, f))
    return found


def process_image(src: Path, out_path: Path, max_dim: int) -> dict:
    im = Image.open(src)
    w0, h0 = im.size
    im = im.convert("RGB")
    scale = min(1.0, max_dim / max(w0, h0))
    if scale < 1.0:
        im = im.resize((max(1, round(w0 * scale)), max(1, round(h0 * scale))))
    im.save(out_path, "JPEG", quality=90)
    return {"original_w": w0, "original_h": h0,
            "new_w": im.width, "new_h": im.height}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/experiment_dataset_v2")
    ap.add_argument("--per-class", type=int, default=500)
    ap.add_argument("--max-dim", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    out_root = root / args.out
    out_root.mkdir(parents=True, exist_ok=True)

    # kumpulkan semua (class -> [(tag, src)])
    by_class = defaultdict(list)
    for tag, sroot in SOURCES:
        found = discover(root / sroot if not sroot.is_absolute() else sroot, tag)
        for norm, f in found:
            by_class[norm].append((tag, f))

    rng = random.Random(args.seed)
    manifest = {
        "source_roots": {tag: str(sroot) for tag, sroot in SOURCES},
        "created_at_utc": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "per_class": args.per_class,
        "max_dim": args.max_dim,
        "seed": args.seed,
        "sampling": "round-robin antar sumber per kelas (kocok per sumber, seed tetap)",
        "classes": {},
        "files": [],
    }
    failures = []
    total_done = 0
    total_skipped = 0

    for cls in sorted(by_class):
        pool = by_class[cls]
        per_src = defaultdict(list)
        for tag, f in pool:
            per_src[tag].append(f)
        for tag in per_src:
            rng.shuffle(per_src[tag])

        sampled = []
        src_used = defaultdict(int)
        idx = {tag: 0 for tag in per_src}
        # round-robin antar sumber sampai cap (sumber habis -> lanjut yg tersisa)
        while len(sampled) < args.per_class:
            progressed = False
            for tag in sorted(per_src):
                if len(sampled) >= args.per_class:
                    break
                if idx[tag] < len(per_src[tag]):
                    sampled.append((tag, per_src[tag][idx[tag]]))
                    src_used[tag] += 1
                    idx[tag] += 1
                    progressed = True
            if not progressed:
                break

        manifest["classes"][cls] = {
            "total": len(pool),
            "sampled": len(sampled),
            "per_source_total": {tag: len(v) for tag, v in per_src.items()},
            "per_source_sampled": dict(src_used),
        }

        cls_out = out_root / cls
        cls_out.mkdir(parents=True, exist_ok=True)
        n_done = 0
        for tag, src in sampled:
            out_path = cls_out / f"{tag}__{src.stem}.jpg"
            if out_path.exists() and not args.force:
                total_skipped += 1
                continue
            try:
                info = process_image(src, out_path, args.max_dim)
                manifest["files"].append({
                    "src": str(src), "source": tag, "out": str(out_path),
                    **info,
                })
                total_done += 1
                n_done += 1
            except Exception as e:
                failures.append({"src": str(src), "error": str(e)})
                print(f"  FAIL {src}: {e}")
        print(f"  {cls:<16} total={len(pool):>5} sampled={len(sampled):>3} "
              f"done={n_done}")

    manifest["failures"] = failures
    manifest_json = out_root / "manifest.json"
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\nSelesai.")
    print(f"  File baru : {total_done}")
    print(f"  Skipped   : {total_skipped}")
    print(f"  Gagal     : {len(failures)}")
    print(f"  Manifest  : {manifest_json}")
    print("Distribusi:")
    for cls, info in manifest["classes"].items():
        print(f"    {cls:<16} {info['sampled']} citra "
              f"(dari {info['total']})  {info['per_source_sampled']}")


if __name__ == "__main__":
    main()