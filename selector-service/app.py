import hashlib
import joblib
import numpy as np
import os
import sqlite3
import time
from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.tree import DecisionTreeClassifier

app = FastAPI(title="AI Selector Service")

EXPERIMENT_DB_PATH = os.getenv("EXPERIMENT_DB_PATH", "experiment_logs.db")
MODEL_VERSION = "dt-maxdepth3-seed42"
MODEL_FEATURES_USED = "entropy,size_kb,glcm_correlation,glcm_contrast"


class FeatureInput(BaseModel):
    entropy: float
    size_kb: float
    glcm_correlation: float
    glcm_contrast: float
    request_id: str = ""


model: DecisionTreeClassifier | None = None
model_version: str = MODEL_VERSION

# Shared SQLite connection for experiment logging (fail-open).
try:
    exp_conn = sqlite3.connect(EXPERIMENT_DB_PATH, check_same_thread=False)
    exp_cur = exp_conn.cursor()
    exp_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS selector_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            timestamp_utc TEXT,
            selector_method TEXT,
            decision_code INTEGER,
            reasoning TEXT,
            selector_inference_time_ms REAL,
            processing_time_ms REAL,
            model_version TEXT,
            model_features_used TEXT,
            status TEXT,
            error_message TEXT
        )
        """
    )
    exp_conn.commit()
except Exception:
    exp_conn = None
    exp_cur = None


def log_selector(
    request_id: str,
    selector_method: str,
    decision_code: int,
    reasoning: str,
    inference_ms: float,
    processing_ms: float,
    status: str,
    error_message: str,
) -> None:
    """Insert one selector-log row. Best effort only."""
    if exp_cur is None:
        return
    try:
        exp_cur.execute(
            """
            INSERT INTO selector_logs
            (request_id, timestamp_utc, selector_method, decision_code, reasoning,
             selector_inference_time_ms, processing_time_ms, model_version,
             model_features_used, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                selector_method,
                decision_code,
                reasoning,
                inference_ms,
                processing_ms,
                model_version,
                MODEL_FEATURES_USED,
                status,
                error_message,
            ),
        )
        exp_conn.commit()
    except Exception:
        pass


def compute_model_version() -> str:
    """Best-effort model fingerprint: md5 of the pkl file when present."""
    global model_version
    try:
        if os.path.exists("ai_selector_model.pkl"):
            with open("ai_selector_model.pkl", "rb") as f:
                digest = hashlib.md5(f.read()).hexdigest()
            model_version = "md5:" + digest
    except Exception:
        pass


def train_default_model() -> DecisionTreeClassifier:
    np.random.seed(42)
    X = np.random.rand(200, 4)
    X[:, 0] *= 8  # entropy 0-8
    X[:, 1] *= 500  # size 0-500 KB
    X[:, 2] = np.random.uniform(-1, 1, 200)  # correlation
    X[:, 3] *= 1  # contrast

    y: list[int] = []
    for row in X:
        if row[0] > 6.2 and row[3] > 0.2:
            y.append(2)  # Hybrid UHC-Blowfish
        elif row[0] > 4.8:
            y.append(1)  # Blowfish
        else:
            y.append(0)  # UHC

    clf = DecisionTreeClassifier(max_depth=3, random_state=42)
    clf.fit(X, y)
    return clf


@app.on_event("startup")
def startup_event():
    global model
    try:
        model = joblib.load("ai_selector_model.pkl")
    except Exception:
        model = train_default_model()
        joblib.dump(model, "ai_selector_model.pkl")
    compute_model_version()


@app.get("/health")
def health():
    return {"status": "ok", "service": "selector-service"}


@app.post("/selector/v1/predict")
def predict(inp: FeatureInput):
    global model
    started = time.perf_counter()
    request_id = inp.request_id or ""

    try:
        if model is None:
            model = train_default_model()

        infer_started = time.perf_counter()
        pred = int(
            model.predict(
                [[inp.entropy, inp.size_kb, inp.glcm_correlation, inp.glcm_contrast]]
            )[0]
        )
        infer_ms = round((time.perf_counter() - infer_started) * 1000.0, 4)

        mapping = {0: "UHC", 1: "Blowfish", 2: "Hybrid UHC-Blowfish"}
        reasons = {
            0: "Low image complexity detected.",
            1: "Moderate entropy detected.",
            2: "High entropy and contrast detected. Maximum security fallback activated.",
        }

        log_selector(
            request_id, mapping[pred], pred, reasons[pred], infer_ms,
            round((time.perf_counter() - started) * 1000.0, 4),
            "ok", "",
        )

        return {
            "decision_code": pred,
            "recommended_cipher": mapping[pred],
            "reasoning": reasons[pred],
            "request_id": request_id,
            "selector_inference_time_ms": infer_ms,
            "model_version": model_version,
            "model_features_used": MODEL_FEATURES_USED,
        }
    except Exception as e:
        log_selector(
            request_id, "", -1, "", 0.0,
            round((time.perf_counter() - started) * 1000.0, 4),
            "error", str(e),
        )
        raise