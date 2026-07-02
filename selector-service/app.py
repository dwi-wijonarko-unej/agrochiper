import joblib
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.tree import DecisionTreeClassifier

app = FastAPI(title="AI Selector Service")


class FeatureInput(BaseModel):
    entropy: float
    size_kb: float
    glcm_correlation: float
    glcm_contrast: float


model: DecisionTreeClassifier | None = None


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "selector-service"}


@app.post("/selector/v1/predict")
def predict(inp: FeatureInput):
    global model
    if model is None:
        model = train_default_model()

    pred = int(
        model.predict(
            [[inp.entropy, inp.size_kb, inp.glcm_correlation, inp.glcm_contrast]]
        )[0]
    )
    mapping = {0: "UHC", 1: "Blowfish", 2: "Hybrid UHC-Blowfish"}
    reasons = {
        0: "Low image complexity detected.",
        1: "Moderate entropy detected.",
        2: "High entropy and contrast detected. Maximum security fallback activated.",
    }
    return {
        "decision_code": pred,
        "recommended_cipher": mapping[pred],
        "reasoning": reasons[pred],
    }
