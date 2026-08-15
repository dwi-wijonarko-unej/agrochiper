"""
load_test.py — Eksperimen beban (EXP-004) untuk BAB 4.5 microservices performance.

Skenario: virtual users (VU) 1, 5, 10, 20. Tiap skenario: warmup lalu uji
durasi tetap; setiap VU mengirim request enkripsi adaptif ke gateway (X-API-Key
dari .env). Metrik per request: latency e2e, http_status, success, method.

Resource: sampel CPU% & memori container (docker stats --no-stream) diambil
pada beberapa titik selama tiap skenario.

Catatan konteks (jujur): single-node Docker Compose, uvicorn single worker,
bukan Kubernetes — klaim performa dibatasi pada purwarupa ini.

Usage:
  python3 analysis/load_test.py --images-dir data/experiment_dataset_v2 \
      --n-images 40 --vus 1,5,10,20 --duration 120 --warmup 15 \
      --out-dir results/EXP-004
"""

import argparse
import csv
import datetime
import json
import os
import random
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SERVICES = ["coffee-gateway", "coffee-feature-service", "coffee-selector-service",
            "coffee-encryption-service", "coffee-web"]


def load_api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GATEWAY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return ""


def collect_images(images_dir: Path, n: int, seed: int) -> list:
    files = sorted(images_dir.glob("*/*.jpg"))
    rng = random.Random(seed)
    return rng.sample(files, min(n, len(files)))


def docker_stats() -> dict:
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        result = {}
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) == 4:
                result[parts[0]] = {"cpu": parts[1], "mem": parts[2], "mem_pct": parts[3]}
        return result
    except Exception as e:
        return {"error": str(e)}


class LoadTest:
    def __init__(self, api_url, api_key, images, duration, warmup, out_dir, vu):
        self.api_url = api_url
        self.api_key = api_key
        self.images = images
        self.duration = duration
        self.warmup = warmup
        self.out_dir = out_dir
        self.vu = vu
        self.lock = threading.Lock()
        self.idx = 0
        self.rows = []
        self.start_time = None
        self.resource_samples = []

    def send_one(self):
        with self.lock:
            img = self.images[self.idx % len(self.images)]
            self.idx += 1
        t0 = time.perf_counter()
        try:
            with open(img, "rb") as f:
                r = requests.post(
                    self.api_url + "/api/v1/encrypt-image",
                    headers={"X-API-Key": self.api_key},
                    files={"file": (img.name, f, "image/jpeg")},
                    timeout=120,
                )
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            try:
                body = r.json()
                method = (body.get("result") or {}).get("method", "")
            except Exception:
                method = ""
            self.rows.append({
                "timestamp": datetime.datetime.now(
                    datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "latency_ms": latency_ms,
                "http_status": r.status_code,
                "success": int(r.status_code == 200),
                "method": method,
            })
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            self.rows.append({
                "timestamp": datetime.datetime.now(
                    datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "latency_ms": latency_ms,
                "http_status": 0,
                "success": 0,
                "method": "",
                "error": str(e)[:200],
            })

    def _resource_loop(self, stop_event):
        while not stop_event.is_set():
            sample = docker_stats()
            if "error" not in sample:
                self.resource_samples.append({
                    "ts": time.time(),
                    "services": sample,
                })
            time.sleep(20)

    def _run_window(self, workers, duration):
        """Kirim request selama duration detik dengan in-flight dibatasi
        workers*4 (hindari banjir antrian future yang membuat drain lama)."""
        with ThreadPoolExecutor(max_workers=workers) as ex:
            deadline = time.time() + duration
            pending = set()
            for _ in range(workers * 4):
                pending.add(ex.submit(self.send_one))
            while time.time() < deadline:
                done = {f for f in pending if f.done()}
                if done:
                    pending -= done
                    for _ in done:
                        pending.add(ex.submit(self.send_one))
                else:
                    time.sleep(0.01)
            for f in pending:
                f.result()

    def run(self):
        print(f"\n-- VU={self.vu} warmup={self.warmup}s test={self.duration}s --")
        self._run_window(max(1, self.vu), self.warmup)
        warmup_n = len(self.rows)
        self.rows = []

        stop_event = threading.Event()
        res_t = threading.Thread(target=self._resource_loop, args=(stop_event,), daemon=True)
        res_t.start()

        self._run_window(self.vu, self.duration)
        stop_event.set()
        elapsed = self.duration
        self.write(warmup_n, elapsed)

    def write(self, warmup_n, elapsed):
        out = self.out_dir
        out.mkdir(parents=True, exist_ok=True)
        csv_path = out / f"load_test_vu{self.vu}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["timestamp", "latency_ms",
                                              "http_status", "success", "method", "error"])
            w.writeheader()
            for r in self.rows:
                w.writerow(r)
        ok = [r for r in self.rows if r["success"] == 1]
        lat = sorted(r["latency_ms"] for r in self.rows)
        throughput = len(self.rows) / elapsed
        n = len(lat)
        def pct(p):
            return round(lat[min(n - 1, int((n - 1) * p))], 2) if n else 0.0
        summary = {
            "vu": self.vu, "duration_s": elapsed, "requests": n,
            "success": len(ok), "failed": n - len(ok),
            "error_rate_pct": round(100 * (n - len(ok)) / n, 2) if n else 0.0,
            "throughput_req_per_s": round(throughput, 3),
            "latency_mean_ms": round(statistics.mean(lat), 2) if lat else 0.0,
            "latency_median_ms": pct(0.50),
            "latency_p95_ms": pct(0.95),
            "latency_p99_ms": pct(0.99),
            "warmup_requests": warmup_n,
        }
        # agregat resource per service
        res = {}
        for s in self.resource_samples:
            for name, m in s["services"].items():
                res.setdefault(name, {"cpu": [], "mem_pct": []})
                cpu = float(m["cpu"].rstrip("%")) if "%" in m["cpu"] else 0.0
                mem_pct = float(m["mem_pct"].rstrip("%")) if "%" in m["mem_pct"] else 0.0
                res[name]["cpu"].append(cpu)
                res[name]["mem_pct"].append(mem_pct)
        res_rows = []
        for name in SERVICES:
            if name not in res:
                continue
            res_rows.append([name, round(statistics.mean(res[name]["cpu"]), 2),
                             round(statistics.mean(res[name]["mem_pct"]), 2),
                             len(res[name]["cpu"])])
        with open(out / "load_test_summary.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summary.keys()))
            write_header = (out / "load_test_summary.csv").stat().st_size == 0
            if write_header:
                w.writeheader()
            w.writerow(summary)
        res_path = out / "service_resource_usage.csv"
        with open(res_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not res_path.exists() or res_path.stat().st_size == 0:
                w.writerow(["vu", "service", "cpu_mean_pct", "mem_mean_pct", "samples"])
            for r in res_rows:
                w.writerow([self.vu] + r)
        print(f"  VU={self.vu}: requests={n} success={len(ok)} "
              f"throughput={summary['throughput_req_per_s']}/s "
              f"p50={summary['latency_median_ms']}ms p95={summary['latency_p95_ms']}ms "
              f"p99={summary['latency_p99_ms']}ms err={summary['error_rate_pct']}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-url", default="http://localhost:8080")
    ap.add_argument("--images-dir", default="data/experiment_dataset_v2")
    ap.add_argument("--n-images", type=int, default=40)
    ap.add_argument("--vus", default="1,5,10,20")
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--warmup", type=int, default=15)
    ap.add_argument("--out-dir", default="results/EXP-004")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    api_key = load_api_key()
    if not api_key:
        print("[error] GATEWAY_API_KEY tidak ditemukan di .env")
        return
    images = collect_images(ROOT / args.images_dir, args.n_images, args.seed)
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "load_test_summary.csv"
    if summary_path.exists():
        summary_path.unlink()
    res_path = out_dir / "service_resource_usage.csv"
    if res_path.exists():
        res_path.unlink()

    print(f"Images pool : {len(images)}  (dir {args.images_dir})")
    print(f"VU          : {args.vus}  duration={args.duration}s warmup={args.warmup}s")

    for vu in [int(x) for x in args.vus.split(",")]:
        lt = LoadTest(args.api_url, api_key, images, args.duration,
                      args.warmup, out_dir, vu)
        lt.run()

    meta = {
        "images_dir": args.images_dir, "n_images": len(images),
        "vus": args.vus, "duration_s": args.duration, "warmup_s": args.warmup,
        "seed": args.seed, "context": "single-node Docker Compose, uvicorn single worker",
    }
    (out_dir / "run_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")
    print("\nSelesai →", out_dir)


if __name__ == "__main__":
    main()