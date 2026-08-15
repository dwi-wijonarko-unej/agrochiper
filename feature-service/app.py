import io
import os
import sqlite3
import time

import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from PIL import Image
from skimage.feature import graycomatrix, graycoprops

app = FastAPI(title="Feature Extractor Service")

EXPERIMENT_DB_PATH = os.getenv("EXPERIMENT_DB_PATH", "experiment_logs.db")

# Shared SQLite connection for experiment logging (fail-open; logging must never
# break feature extraction). Table created at startup.
try:
    exp_conn = sqlite3.connect(EXPERIMENT_DB_PATH, check_same_thread=False)
    exp_cur = exp_conn.cursor()
    exp_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            timestamp_utc TEXT,
            filename TEXT,
            file_extension TEXT,
            image_width INTEGER,
            image_height INTEGER,
            file_size_kb REAL,
            entropy REAL,
            glcm_correlation REAL,
            glcm_contrast REAL,
            feature_extraction_time_ms REAL,
            processing_time_ms REAL,
            status TEXT,
            error_message TEXT
        )
        """
    )
    exp_conn.commit()
except Exception:
    exp_conn = None
    exp_cur = None


def log_feature(
    request_id: str,
    filename: str,
    file_extension: str,
    image_width: int,
    image_height: int,
    file_size_kb: float,
    entropy: float,
    glcm_correlation: float,
    glcm_contrast: float,
    feature_extraction_time_ms: float,
    processing_time_ms: float,
    status: str,
    error_message: str,
) -> None:
    """Insert one feature-log row. Best effort only."""
    if exp_cur is None:
        return
    try:
        exp_cur.execute(
            """
            INSERT INTO feature_logs
            (request_id, timestamp_utc, filename, file_extension, image_width,
             image_height, file_size_kb, entropy, glcm_correlation, glcm_contrast,
             feature_extraction_time_ms, processing_time_ms, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                filename,
                file_extension,
                image_width,
                image_height,
                file_size_kb,
                entropy,
                glcm_correlation,
                glcm_contrast,
                feature_extraction_time_ms,
                processing_time_ms,
                status,
                error_message,
            ),
        )
        exp_conn.commit()
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "feature-service"}


@app.post("/extractor/v1/analyze")
async def analyze(file: UploadFile = File(...), request_id: str = Form("")):
    started = time.perf_counter()
    request_id = request_id or ""
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    data = await file.read()

    image_width = 0
    image_height = 0
    size_kb = 0.0
    entropy = 0.0
    contrast = 0.0
    correlation = 0.0
    feat_ms = 0.0

    try:
        feat_started = time.perf_counter()

        # Convert to grayscale
        img = Image.open(io.BytesIO(data)).convert("L")
        img_arr = np.array(img)
        image_width, image_height = img.size

        # File size in KB (approx)
        size_kb = len(data) / 1024.0

        # Entropy
        hist, _ = np.histogram(img_arr.flatten(), bins=256, range=(0, 256))
        prob = hist / hist.sum()
        prob = prob[prob > 0]
        entropy = float(-np.sum(prob * np.log2(prob)))

        # GLCM features
        img_quantized = (img_arr / 32).astype(np.uint8)
        glcm = graycomatrix(
            img_quantized,
            distances=[1],
            angles=[0],
            levels=8,
            symmetric=True,
            normed=True,
        )
        contrast = float(graycoprops(glcm, "contrast")[0, 0])
        correlation = float(graycoprops(glcm, "correlation")[0, 0])

        feat_ms = round((time.perf_counter() - feat_started) * 1000.0, 4)

        log_feature(
            request_id, filename, ext, image_width, image_height, size_kb,
            entropy, correlation, contrast, feat_ms,
            round((time.perf_counter() - started) * 1000.0, 4),
            "ok", "",
        )

        return {
            "entropy": round(entropy, 4),
            "size_kb": round(size_kb, 4),
            "glcm_correlation": round(correlation, 4),
            "glcm_contrast": round(contrast, 4),
            "request_id": request_id,
            "image_width": image_width,
            "image_height": image_height,
            "file_extension": ext,
            "feature_extraction_time_ms": feat_ms,
        }
    except Exception as e:
        log_feature(
            request_id, filename, ext, image_width, image_height, size_kb,
            entropy, correlation, contrast, feat_ms,
            round((time.perf_counter() - started) * 1000.0, 4),
            "error", str(e),
        )
        raise