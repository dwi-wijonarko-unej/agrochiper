import base64
import io
import os
import sqlite3
import struct
import time

import numpy as np
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.decrepit.ciphers.algorithms import Blowfish
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, modes
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from PIL import Image

app = FastAPI(title="Encryption Service")

# Load environment and initialize settings
load_dotenv()

DB_PATH = os.getenv("DB_PATH", "logs.db")
SECRET_KEY = os.getenv("SECRET_KEY", "kunci_rahasia_16b").encode("utf-8")
PWD1 = int(os.getenv("UHC_MATRIX_SIZE", "16"))
PWD2 = os.getenv("UHC_PASSWORD2", "7391")
EXPERIMENT_DB_PATH = os.getenv("EXPERIMENT_DB_PATH", "experiment_logs.db")

# Initialize SQLite
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS encryption_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        method TEXT,
        encryption_time REAL,
        decryption_time REAL,
        cipher_entropy REAL,
        psnr TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)
conn.commit()

# Experiment logging DB (fail-open; logging must never break encryption).
try:
    exp_conn = sqlite3.connect(EXPERIMENT_DB_PATH, check_same_thread=False)
    exp_cur = exp_conn.cursor()
    exp_cur.execute(
        """
        CREATE TABLE IF NOT EXISTS crypto_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            timestamp_utc TEXT,
            method TEXT,
            encryption_time_ms REAL,
            decryption_time_ms REAL,
            cipher_entropy REAL,
            psnr TEXT,
            psnr_is_infinite INTEGER,
            decrypt_verified INTEGER,
            encrypted_payload_size_bytes INTEGER,
            original_payload_size_bytes INTEGER,
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


def log_crypto(
    request_id: str,
    method: str,
    enc_ms: float,
    dec_ms: float,
    cipher_entropy: float,
    psnr: str,
    psnr_is_infinite: bool,
    decrypt_verified: bool,
    encrypted_size: int,
    original_size: int,
    processing_ms: float,
    status: str,
    error_message: str,
) -> None:
    """Insert one crypto-log row. Best effort only."""
    if exp_cur is None:
        return
    try:
        exp_cur.execute(
            """
            INSERT INTO crypto_logs
            (request_id, timestamp_utc, method, encryption_time_ms, decryption_time_ms,
             cipher_entropy, psnr, psnr_is_infinite, decrypt_verified,
             encrypted_payload_size_bytes, original_payload_size_bytes,
             processing_time_ms, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                method,
                enc_ms,
                dec_ms,
                cipher_entropy,
                psnr,
                1 if psnr_is_infinite else 0,
                1 if decrypt_verified else 0,
                encrypted_size,
                original_size,
                processing_ms,
                status,
                error_message,
            ),
        )
        exp_conn.commit()
    except Exception:
        pass


def logistic_map(x0: float, banyak: int) -> np.ndarray:
    x0 = x0 % 1.0
    if x0 == 0.0:
        x0 = 0.5
    x = x0
    for _ in range(1000):
        x = 3.923 * x * (1 - x)

    barisan = np.empty(banyak, dtype=np.int32)
    for i in range(banyak):
        x = 3.923 * x * (1 - x)
        barisan[i] = int(abs(x * 1000)) % 256
    return barisan


def r_ij(m: np.ndarray, i: int, j: int, r: int) -> np.ndarray:
    return m[i] + r * m[j]


def generate_key_matrix(n: int, x0: float, mode: str = "e"):
    banyak = int(n * (n - 1) / 2)
    barisan = logistic_map(x0, banyak + n - 1)
    msa = np.eye(n, dtype=np.int32)
    idx = 0

    for i in range(n):
        for j in range(i + 1, n):
            msa[i, j] = barisan[idx]
            idx += 1

    for baris_i in range(1, n):
        msa[baris_i] = r_ij(msa, baris_i, 0, barisan[idx]) % 256
        idx += 1

    if mode == "e":
        return msa

    # decryption: compute inverse
    aug = np.zeros((n, 2 * n), dtype=np.int32)
    aug[:, :n] = msa
    aug[:, n:] = np.eye(n, dtype=np.int32)

    for baris in range(1, n):
        aug[baris] = r_ij(aug, baris, 0, -aug[baris, 0]) % 256

    for kolom in range(1, n):
        for baris in range(kolom):
            aug[baris] = r_ij(aug, baris, kolom, -aug[baris, kolom]) % 256

    return msa, aug[:, n:]


def hill_multiply(data: np.ndarray, key_matrix: np.ndarray, n: int) -> np.ndarray:
    total_cols = len(data) // n
    result = np.empty(len(data), dtype=np.uint8)
    key_i32 = key_matrix.astype(np.int32)

    chunk = data.reshape(n, total_cols).astype(np.int32)
    out = np.dot(key_i32, chunk) % 256
    result[:] = out.astype(np.uint8).flatten()
    return result


def process_blowfish(data_bytes: bytes, mode: str = "encrypt") -> bytes:
    iv = os.urandom(8)

    if mode == "encrypt":
        padder = padding.PKCS7(64).padder()
        padded_data = padder.update(data_bytes) + padder.finalize()
        cipher = Cipher(Blowfish(SECRET_KEY), modes.CBC(iv), backend=default_backend())
        enc_dec = cipher.encryptor()
        final_data = enc_dec.update(padded_data) + enc_dec.finalize()
        return iv + final_data

    # decrypt
    iv = data_bytes[:8]
    enc_data = data_bytes[8:]
    cipher = Cipher(Blowfish(SECRET_KEY), modes.CBC(iv), backend=default_backend())
    enc_dec = cipher.decryptor()
    padded_data = enc_dec.update(enc_data) + enc_dec.finalize()
    unpadder = padding.PKCS7(64).unpadder()
    return unpadder.update(padded_data) + unpadder.finalize()


@app.get("/health")
def health():
    return {"status": "ok", "service": "encryption-service"}


@app.get("/encryption/v1/logs")
def get_logs():
    cur.execute(
        """
        SELECT id, filename, method, encryption_time, decryption_time, cipher_entropy, psnr, created_at
        FROM encryption_logs
        ORDER BY id DESC LIMIT 100
        """
    )
    rows = cur.fetchall()
    logs = []
    for r in rows:
        logs.append(
            {
                "id": r[0],
                "filename": r[1],
                "method": r[2],
                "encryption_time": r[3],
                "decryption_time": r[4],
                "cipher_entropy": r[5],
                "psnr": r[6],
                "created_at": r[7],
            }
        )
    return {"status": "success", "data": logs}


@app.post("/encryption/v1/process")
async def process(
    file: UploadFile = File(...),
    cipher_mode: str = Form(...),
    request_id: str = Form(""),
):
    started = time.perf_counter()
    request_id = request_id or ""

    try:
        data = await file.read()

        img = Image.open(io.BytesIO(data)).convert("RGB")
        img_arr = np.array(img)
        width, height = img.size
        img_bytes = img.tobytes()
        original_size = len(img_bytes)

        n_uhc = PWD1
        x0_uhc = float("0." + PWD2 + "1")

        # Encryption
        start_enc = time.perf_counter()

        if cipher_mode == "UHC":
            key_mat = generate_key_matrix(n_uhc, x0_uhc, "e")
            pad_len = (n_uhc - len(img_bytes) % n_uhc) % n_uhc
            img_padded = np.pad(
                np.frombuffer(img_bytes, dtype=np.uint8),
                (0, pad_len),
                "constant",
            )
            enc_bytes = hill_multiply(img_padded, key_mat, n_uhc).tobytes()
            payload = (
                struct.pack("II", width, height)
                + b"UHC"
                + struct.pack("I", pad_len)
                + enc_bytes
            )
        elif cipher_mode == "Blowfish":
            enc_bytes = process_blowfish(img_bytes, "encrypt")
            payload = struct.pack("II", width, height) + b"BLO" + enc_bytes
        else:  # Hybrid
            key_mat = generate_key_matrix(n_uhc, x0_uhc, "e")
            pad_len = (n_uhc - len(img_bytes) % n_uhc) % n_uhc
            img_padded = np.pad(
                np.frombuffer(img_bytes, dtype=np.uint8),
                (0, pad_len),
                "constant",
            )
            uhc_enc = hill_multiply(img_padded, key_mat, n_uhc)
            blw_enc = process_blowfish(uhc_enc.tobytes(), "encrypt")
            payload = (
                struct.pack("II", width, height)
                + b"HYB"
                + struct.pack("I", pad_len)
                + blw_enc
            )

        end_enc = time.perf_counter()
        encrypted_size = len(payload)

        # Decryption + verify
        start_dec = time.perf_counter()

        bio = io.BytesIO(payload)
        r_w, r_h = struct.unpack("II", bio.read(8))
        method_tag = bio.read(3)

        if method_tag == b"UHC":
            pad_len = struct.unpack("I", bio.read(4))[0]
            enc_data = bio.read()
            _, inv_mat = generate_key_matrix(n_uhc, x0_uhc, "d")
            dec_padded = hill_multiply(
                np.frombuffer(enc_data, dtype=np.uint8), inv_mat, n_uhc
            )
            final_bytes = dec_padded[: len(dec_padded) - pad_len].tobytes()
        elif method_tag == b"BLO":
            final_bytes = process_blowfish(bio.read(), "decrypt")
        else:  # HYB
            pad_len = struct.unpack("I", bio.read(4))[0]
            dec_blw = process_blowfish(bio.read(), "decrypt")
            _, inv_mat = generate_key_matrix(n_uhc, x0_uhc, "d")
            dec_padded = hill_multiply(
                np.frombuffer(dec_blw, dtype=np.uint8), inv_mat, n_uhc
            )
            final_bytes = dec_padded[: len(dec_padded) - pad_len].tobytes()

        end_dec = time.perf_counter()

        final_img_arr = np.frombuffer(final_bytes, dtype=np.uint8).reshape(r_h, r_w, 3)

        mse = np.mean((img_arr.astype(float) - final_img_arr.astype(float)) ** 2)
        psnr = "∞" if mse == 0 else str(round(20 * np.log10(255.0 / np.sqrt(mse)), 2))
        psnr_is_infinite = bool(mse == 0)
        decrypt_verified = bool(mse == 0)

        cipher_bytes = np.frombuffer(payload, dtype=np.uint8)
        hist_c, _ = np.histogram(cipher_bytes, bins=256, range=(0, 256))
        prob_c = hist_c / hist_c.sum()
        prob_c = prob_c[prob_c > 0]
        cipher_entropy = float(-np.sum(prob_c * np.log2(prob_c)))

        enc_time = round(end_enc - start_enc, 4)
        dec_time = round(end_dec - start_dec, 4)
        enc_ms = round((end_enc - start_enc) * 1000.0, 4)
        dec_ms = round((end_dec - start_dec) * 1000.0, 4)
        cipher_ent = float(cipher_entropy)

        # Log to SQLite (production table — unchanged contract)
        cur.execute(
            """
            INSERT INTO encryption_logs
            (filename, method, encryption_time, decryption_time, cipher_entropy, psnr)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file.filename, cipher_mode, enc_time, dec_time, cipher_ent, psnr),
        )
        conn.commit()

        # Experiment log (fail-open)
        log_crypto(
            request_id, cipher_mode, enc_ms, dec_ms, cipher_ent, psnr,
            psnr_is_infinite, decrypt_verified, encrypted_size, original_size,
            round((time.perf_counter() - started) * 1000.0, 4),
            "ok", "",
        )

        return {
            "method": cipher_mode,
            "encryption_time": enc_time,
            "decryption_time": dec_time,
            "cipher_entropy": cipher_ent,
            "psnr": psnr,
            "output_filename": file.filename + ".dat",
            "cipher_base64": base64.b64encode(payload).decode("utf-8"),
            "request_id": request_id,
            "encryption_time_ms": enc_ms,
            "decryption_time_ms": dec_ms,
            "psnr_is_infinite": psnr_is_infinite,
            "decrypt_verified": decrypt_verified,
            "encrypted_payload_size_bytes": encrypted_size,
            "original_payload_size_bytes": original_size,
        }
    except Exception as e:
        log_crypto(
            request_id, cipher_mode, 0.0, 0.0, 0.0, "", False, False, 0, 0,
            round((time.perf_counter() - started) * 1000.0, 4),
            "error", str(e),
        )
        raise