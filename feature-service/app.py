from fastapi import FastAPI, UploadFile, File
from PIL import Image
from skimage.feature import graycomatrix, graycoprops
import numpy as np
import io

app = FastAPI(title="Feature Extractor Service")


@app.get("/health")
def health():
    return {"status": "ok", "service": "feature-service"}


@app.post("/extractor/v1/analyze")
async def analyze(file: UploadFile = File(...)):
    data = await file.read()

    # Convert to grayscale
    img = Image.open(io.BytesIO(data)).convert("L")
    img_arr = np.array(img)

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

    return {
        "entropy": round(entropy, 4),
        "size_kb": round(size_kb, 4),
        "glcm_correlation": round(correlation, 4),
        "glcm_contrast": round(contrast, 4),
    }
