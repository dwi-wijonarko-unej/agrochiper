# A Decision Tree-Based Adaptive AI Selector for Hybrid Encryption Algorithm Selection on Coffee Disease Images in Edge-Cloud Architecture

**First Author**¹, **Second Author**¹, **Third Author**²

¹ Faculty of Computer Science, Universitas Jember, Jember, Indonesia
² Faculty of Agriculture, Universitas Jember, Jember, Indonesia

**Corresponding Author**: First Author, email@unej.ac.id

---

## Abstract

The growing adoption of agro-IoT and computer vision for coffee disease monitoring has increased the need to secure crop images during transmission from edge devices to cloud services. Most existing studies apply a single, static encryption algorithm to all images, ignoring the fact that image characteristics such as entropy and texture differ widely across disease classes. This study presents a Decision Tree-based adaptive AI Selector that chooses among Unimodular Hill Cipher (UHC), Blowfish, and a Hybrid UHC-Blowfish scheme based on image features, orchestrated through a microservices architecture. An experimental dataset of 2,834 coffee leaf disease images (six classes, five public sources) was processed through a prototype comprising a Go gateway, three FastAPI services (feature extraction, AI selection, and encryption), and a batch experiment client. All 12,670 primary requests completed successfully with 100% lossless recovery (PSNR = ∞, decrypt-verified). The deployed selector distributed decisions as UHC 20.57%, Blowfish 72.41%, and Hybrid 7.02%; a Decision Tree refit on the actual image features reproduced this routing policy with perfect test consistency (accuracy 1.00 at depth 2), driven primarily by image entropy (importance 0.70) and GLCM contrast (0.30). Blowfish and Hybrid achieved near-ideal ciphertext quality (entropy ≈ 7.9999 bit/byte, NPCR ≈ 99.61%, UACI ≈ 33.47%), whereas UHC exhibited weak one-byte diffusion (NPCR ≈ 0.001%), empirically justifying the hybrid design. Ciphertext-corruption tests further exposed a security–robustness asymmetry: CBC-based modes are catastrophically sensitive to ciphertext noise (100% decryption failure under additive Gaussian corruption), while UHC always decrypts with localized degradation (up to 17.5 dB PSNR under sparse corruption). A load test (1–20 virtual users, warm-up excluded) identified the encryption service as the throughput bottleneck (≈3.2–4.1 requests/s, 0% error). The results demonstrate a feasible image-feature-aware cipher-selection workflow in a service-oriented edge-cloud architecture, while the selector must be interpreted as a rule-derived prototype rather than a trained classifier.

**Keywords**: agro-IoT; image encryption; microservices; decision tree; UHC; Blowfish; hybrid encryption; coffee disease.

---

## 1. Introduction

Coffee is one of Indonesia's most important agricultural commodities. Indonesia is the world's fourth-largest coffee producer, and the East Java region, particularly Jember, contributes approximately 70% of the country's Arabica-Robusta varieties. Coffee plantations are threatened by serious diseases, most notably leaf rust (*Hemileia vastatrix*) and anthracnose, which cause economic losses estimated at up to IDR 25 trillion per year. These threats have driven the adoption of Internet of Things (IoT) devices and computer vision for early disease detection, where leaf images captured by farmer smartphones or field sensors are transmitted to cloud services for automated analysis.

However, transmitting disease images over public networks introduces a cybersecurity problem. Visual agricultural data can be intercepted, manipulated, or reused by unauthorized parties during transmission and storage. Protecting these images through encryption is therefore necessary, yet conventional encryption approaches present several limitations. Classical Hill Cipher, despite its simple matrix-based formulation, is vulnerable to known-plaintext attacks and linear cryptanalysis when the key design is weak. Blowfish, a 16-round Feistel block cipher, offers good performance and has been used in practical applications, but applying it as a fixed, single-algorithm solution does not account for the structural diversity of visual data and raises concerns about key management under high image volume. Hybrid schemes that combine UHC for pixel rearrangement and Blowfish for block substitution address these weaknesses by adding a diffusion layer on top of a scrambling layer, but they add computational cost.

A key observation is that not all images exhibit the same characteristics. Image entropy, file size, and texture properties such as GLCM correlation and contrast vary substantially across disease classes and acquisition conditions. A static, one-size-fits-all cipher selection is therefore suboptimal: images with low entropy may not benefit from expensive hybrid processing, while high-entropy, high-contrast images require stronger diffusion. This condition motivates an *adaptive* mechanism that selects the encryption algorithm based on the image itself.

From a software-architecture perspective, microservices have become the dominant pattern for IoT systems because they provide modularity, service separation, and extensibility compared with monolithic designs. In the domain of security-critical image processing, separating feature extraction, decision making, and encryption into dedicated services allows each component to be developed, scaled, and tested independently. Recent work on adaptive scheduling and mimic defense in containerized systems further supports the idea of intelligent, data-informed orchestration. Nevertheless, the combination of an AI-driven *cipher-type* selector (as opposed to parameter or key tuning) with hybrid image encryption in a microservices architecture for agricultural IoT remains underexplored.

The research gap addressed in this manuscript is the limited integration of three elements: (1) image-feature-driven selection among multiple cipher *types*, (2) hybrid UHC-Blowfish encryption applied to coffee disease images, and (3) a service-oriented, containerized orchestration model for agro-IoT edge-cloud environments. The main contributions of this work are:

1. An adaptive encryption workflow in which a Decision Tree selects UHC, Blowfish, or Hybrid UHC-Blowfish using image entropy, file size, GLCM correlation, and GLCM contrast as decision inputs;
2. A containerized microservices prototype separating gateway, feature extraction, AI selection, and encryption into interoperable services;
3. A reproducible experimental evaluation covering feature profiles, selector behavior, policy-distillation audit, encryption performance, ciphertext quality, ciphertext-corruption robustness, key-space estimation, and service-level load behavior on a mixed coffee disease dataset.

The remainder of this paper follows the IMRAD structure: Section 2 describes the dataset, system architecture, and experimental methodology; Section 3 presents the results; Section 4 discusses the findings, trade-offs, and limitations; Section 5 concludes the paper and outlines future work.

## 2. Materials and Methods

### 2.1. System Overview

The prototype, named AgroCipher, implements an adaptive image-encryption pipeline as a set of containerized microservices orchestrated with Docker Compose. The processing flow is:

```
client (multipart image)
  -> gateway (Go; orchestrator + API-key auth)
      -> feature-service (FastAPI): entropy, size_kb, GLCM correlation/contrast
      -> selector-service (FastAPI): DecisionTree -> UHC(0)/Blowfish(1)/Hybrid(2)
      -> encryption-service (FastAPI): encrypt + decrypt-verify + SQLite logging
  -> JSON response (features, selector decision, result)
```

Four services compose the system:

- **Gateway** (Go 1.22, standard library only): the sole public entry point. It authenticates clients with a 64-character API key, forwards images to the feature service, routes features to the selector, invokes the chosen encryption mode, and returns a unified JSON response. It also proxies `GET /api/v1/logs` for analytics.
- **Feature-service** (Python/FastAPI): extracts Shannon entropy, file size, and GLCM-based correlation and contrast from the uploaded image.
- **Selector-service** (Python/FastAPI): runs a scikit-learn Decision Tree that maps the four features to one of three classes — UHC (0), Blowfish (1), or Hybrid UHC-Blowfish (2) — together with a rule-based fallback.
- **Encryption-service** (Python/FastAPI): executes UHC, Blowfish, or Hybrid UHC-Blowfish encryption, performs decrypt-verification, computes PSNR, and logs the request to SQLite (`/data/logs.db`).

### 2.2. Dataset and Preprocessing

The experimental dataset was assembled from five public and community sources and normalized into six disease/health classes: Healthy, Rust, Miner, Phoma, Red Spider Mite, and Cerscospora. To ensure class balance and source diversity, a deterministic round-robin sampling procedure (seed 42) selected at most 500 images per class, producing **2,834 images** in total (Table 1). All images were downscaled to a maximum dimension of 1,024 pixels and re-encoded as RGB JPEG (quality 90); the source-to-class mapping was recorded in a manifest for reproducibility.

**Table 1.** Composition of the mixed experimental dataset (v2).

| Class | Count | Source composition (OLD/COF/DRIVE/ETHTEST/ETHAUG) |
| --- | --- | --- |
| Healthy | 500 | OLD 100, COF 100, DRIVE 100, ETHTEST 100, ETHAUG 100 |
| Rust | 500 | OLD 100, COF 100, DRIVE 100, ETHTEST 100, ETHAUG 100 |
| Miner | 500 | OLD 250, DRIVE 250 |
| Phoma | 500 | OLD 125, DRIVE 125, ETHTEST 125, ETHAUG 125 |
| Red Spider Mite | 334 | OLD 167, COF 167 |
| Cerscospora | 500 | ETHTEST 250, ETHAUG 250 |
| **Total** | **2,834** | — |

For each image, four features were extracted: Shannon entropy (bit/byte), file size (KB), GLCM correlation, and GLCM contrast. The GLCM was computed with a fixed offset (1, 0) on the grayscale image. Across the corpus, mean feature values were: entropy 6.106, size 86.25 KB, GLCM correlation 0.978, and GLCM contrast 0.107 (stage-1 regeneration over 2,834 unique images).

### 2.3. Encryption Schemes

Three encryption schemes were implemented and evaluated:

- **UHC (Unimodular Hill Cipher)**: a matrix-based cipher whose key matrix has determinant ±1, applied in GF(256) arithmetic. Encryption and decryption use an identical matrix size and password-seeded key derived from the environment (`UHC_MATRIX_SIZE`, `UHC_PASSWORD2`); the matrix inverse is recomputed on each call. UHC performs pixel/value rearrangement within blocks of size *n*.
- **Blowfish**: a 16-round Feistel block cipher used in CBC mode with random IV (cryptography library, pinned `cryptography==43.0.1` because Blowfish was moved to `hazmat.decrepit`). PKCS7 padding with 64-bit block size.
- **Hybrid UHC-Blowfish**: UHC applied first for rearrangement followed by Blowfish for block substitution. Payloads carry an explicit header (`width`, `height`, cipher tag `UHC`/`BLO`/`HYB`, padding length) enabling correct decrypt-verification.

The encryption service accepts `cipher_mode` values `UHC` and `Blowfish`; any other value defaults to **Hybrid**. PSNR is reported as a string, where `"∞"` indicates lossless recovery.

### 2.4. AI Selector (Decision Tree)

The selector-service implements a scikit-learn `DecisionTreeClassifier` (gini criterion, `max_depth=3`, `random_state=42`). On startup the service attempts to load `ai_selector_model.pkl`; if absent, it trains a default model (`train_default_model()`) on a synthetic rule-derived dataset generated with a fixed seed and serializes it. The tree maps `[entropy, size_kb, glcm_correlation, glcm_contrast]` to `{0: UHC, 1: Blowfish, 2: Hybrid}`.

It is important to note that the selector is a **rule-derived placeholder, not a classifier trained on ground-truth optimal-method labels**: no per-image "best cipher" ground truth exists, so classification accuracy against empirical optima is not reported and no accuracy claim of that kind is made. The decision labels were derived from threshold logic, and the tree simply exposes this logic in interpretable form.

To audit this policy, we additionally refit a Decision Tree directly on the actual per-image features of the 2,834-image corpus using the routing decisions as labels ("policy distillation"). The pipeline used an 80:20 stratified train–test split (`random_state=42`) and `GridSearchCV` (5-fold stratified CV) over `max_depth ∈ {2,…,5}` and `min_samples_split ∈ {2, 5, 10}`, reporting accuracy, macro precision/recall/F1, confusion matrix, and Gini importances. Because the labels encode the routing rule itself, these metrics quantify how faithfully an interpretable tree can *reproduce the deployment policy*, not detection accuracy against an external optimum.

### 2.5. Experimental Protocol

Four experiment series were executed (Table 2):

- **EXP-001 (selector behavior)**: the full 2,834-image dataset was submitted three times per image (repeat 3, warm-up 10), producing 8,502 primary requests, to characterize feature profiles and selector decisions.
- **EXP-002 (method baselines)**: forced-method baselines were obtained by running each image once per method — UHC, Blowfish, Hybrid, and Adaptive (repeat 1, warm-up 5) — i.e., 2,834 requests per scenario, to compare encryption performance under identical inputs.
- **EXP-003 (ciphertext analysis)**: ciphertext payloads were collected for cryptographic analysis. A deterministic, evenly strided sample of 300 payloads per method was retained (1,136 total) to bound storage while covering all classes. The batch runner saves payloads with `--save-ciphertext-limit 300`.
- **EXP-004 (load test)**: the complete stack was exercised with 1, 5, 10, and 20 virtual users for 120 seconds each (warm-up 10 s) to measure throughput, latency, and per-service CPU/memory. All reported statistics refer to the clean measurement window only (warm-up requests excluded).

**Table 2.** Experiment series.

| ID | Purpose | Configuration | Primary requests |
| --- | --- | --- | --- |
| EXP-001 | Selector behavior | repeat 3, warm-up 10 | 8,502 (0 failed) |
| EXP-002 | Forced-method baselines | repeat 1, warm-up 5 | 2,834 × 4 (0 failed) |
| EXP-003 | Ciphertext cryptographic analysis | deterministic stride sample, 300/method | 1,136 payloads |
| EXP-004 | Microservices load test | VU 1/5/10/20, 120 s window after warm-up | 388–496 per scenario |

All experiments ran on a single node (3.7 GB RAM) with the gateway requiring the API key; the experiment mode was enabled only for forced-method scenarios and disabled during analysis.

### 2.6. Offline Analysis Pipeline

All post-processing was regenerated as five deterministic stage scripts (Python 3.11 inside a pinned container; NumPy, pandas, scikit-learn, scikit-image, Pillow, python-cryptography; all seeds fixed at 42):

1. **Stage 1 — features.csv**: one row per unique image (label, dimensions, size, entropy, GLCM correlation/contrast) derived from the feature-service outputs recorded in EXP-001, plus per-class descriptive statistics;
2. **Stage 2 — cipher_evaluation**: per-request long-format table and per-method aggregates from the four EXP-002 scenarios (encryption/decryption/end-to-end times, cipher entropy, success and lossless rates);
3. **Stage 3 — selector distillation**: the Decision Tree audit described in §2.4, exporting evaluation metrics, confusion matrix, feature importances, tree rules, predictions, and the trained model artifact;
4. **Stage 4 — load-test recomputation**: throughput and latency percentiles recomputed from raw request logs over the clean measurement window, merged with container CPU/memory samples;
5. **Stage 5 — security tests**: aggregation of EXP-003 byte metrics and NPCR/UACI results, a new ciphertext-corruption robustness test, and theoretical key-space estimates.

For the corruption test (§3.4.4), payloads from EXP-003 were decrypted *offline* by re-implementing the exact production cryptography (Hill multiplication mod 256 over blocks of *n* = 16 with logistic-map seeded matrices; Blowfish CBC with PKCS7(64) and per-payload IV). A clean-decrypt sanity check confirmed byte-exact recovery of every sampled original before any corruption was applied.

## 3. Results

### 3.1. Feature Profile

Table 3 reports the mean image entropy per class, computed from EXP-001 on unique images. The dataset spans a wide entropy range, providing sufficient feature variation to exercise the adaptive decision mechanism.

**Table 3.** Mean image entropy per class.

| Class | Mean entropy (bit/byte) |
| --- | --- |
| Red Spider Mite | 7.5692 |
| Healthy | 6.4230 |
| Rust | 6.1331 |
| Cerscospora | 6.0164 |
| Phoma | 5.7387 |
| Miner | 5.2429 |

### 3.2. AI Selector Behavior and Policy-Distillation Audit

Across the 2,834 unique images, the selector distributed its decisions as shown in Table 4. Low-entropy images (mean 3.25) were routed to UHC, mid-entropy images (mean 6.76) to Blowfish, and the highest-entropy, high-contrast images (mean 7.68, contrast 0.64) to Hybrid UHC-Blowfish.

**Table 4.** Distribution of AI Selector decisions and mean feature values (EXP-001, unique images).

| Method | Images | % | Mean entropy | Mean GLCM corr. | Mean GLCM contrast | Mean size (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 583 | 20.57 | 3.2522 | 0.985 | 0.0395 | 46.94 |
| Blowfish | 2,052 | 72.41 | 6.7642 | 0.984 | 0.0740 | 84.35 |
| Hybrid UHC-Blowfish | 199 | 7.02 | 7.6831 | 0.897 | 0.6443 | 220.94 |

**Policy-distillation audit.** Refitting a Decision Tree on the actual image features against these routing labels recovered the policy essentially exactly: cross-validated accuracy 0.9987 selected `max_depth=2, min_samples_split=2`, and the held-out test set (n = 567) yielded accuracy, macro precision, recall, and F1 of **1.000**, with a perfectly diagonal confusion matrix (Table 5). The extracted rules,

```
entropy <= 4.7771                          -> UHC
entropy >  4.7771
  └─ glcm_contrast <= 0.2281               -> Blowfish
     └─ glcm_contrast >  0.2281            -> Hybrid UHC-Blowfish
```

match the deployed routing logic (the service-side placeholder additionally applies a secondary entropy split at ≈6.24, which the depth-2 refit renders redundant on this corpus). Feature importance in the refit tree concentrates on **entropy (0.701)** and **GLCM contrast (0.299)**, with file size and GLCM correlation contributing nothing (Figure 4); the same two-feature dominance appears in the deployed placeholder tree (importance 0.869 / 0.131). These results confirm that an interpretable two-feature, depth-2 Decision Tree is sufficient to express the adaptive routing policy end-to-end.

**Table 5.** Policy-distillation evaluation (Decision Tree refit vs routing labels; stratified 80:20, seed 42).

| Item | Value |
| --- | --- |
| Train / test images | 2,267 / 567 |
| Selected hyperparameters | gini, `max_depth=2`, `min_samples_split=2` |
| CV accuracy (5-fold) | 0.9987 |
| Test accuracy | 1.000 |
| Test macro precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Confusion matrix (UHC / Blowfish / Hybrid) | 117/117, 410/410, 40/40 correct |
| Feature importance | entropy 0.701, GLCM contrast 0.299, size 0, GLCM corr. 0 |

Because the labels encode the routing rule itself, these scores demonstrate *policy fidelity*, not accuracy against empirical cipher optimality (see §4.4).

**Figure 1.** Selector decision vs image features (entropy vs GLCM contrast) for 2,834 images, colored by chosen method (`results/FIGURES/fig1_selector_scatter.png`).

**Figure 2.** Extracted decision tree from the policy-distillation refit (`results/FIGURES/fig2_decision_tree.png`).

**Figure 3.** Confusion matrix of the distilled tree on the held-out test set (`results/FIGURES/fig3_confusion_matrix.png`).

**Figure 4.** Feature importance of the distilled Decision Tree (`results/FIGURES/fig4_feature_importance.png`).

### 3.3. Encryption Performance

Table 6 compares encryption/decryption time, end-to-end latency, and ciphertext entropy across methods (EXP-002; 2,834 requests per method; 100% success and 100% lossless in every scenario).

**Table 6.** Encryption and decryption performance per method (EXP-002).

| Method | Encrypt (ms) | Decrypt (ms) | E2E mean (ms) | E2E p95 (ms) | Cipher entropy | Lossless |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 77.6 | 70.6 | 325.7 | 491 | 7.7376 | 100% |
| Blowfish | 21.4 | 21.1 | 216.1 | 314 | 7.9999 | 100% |
| Hybrid UHC-Blowfish | 89.6 | 88.2 | 352.2 | 552 | 7.9999 | 100% |
| Adaptive | 36.5 | 38.2 | 254.8 | 412 | 7.7394 | 100% |

Blowfish is the fastest method (21.4 ms) and achieves the highest ciphertext entropy (7.9999); Hybrid UHC-Blowfish is the slowest (89.6 ms) because it applies two layers of transformation. Adaptive routing (36.5 ms) sits between Blowfish and Hybrid, because 20.57% of images are routed to UHC. The ciphertext entropy of Adaptive and UHC (≈7.74) is lower than that of Blowfish/Hybrid (7.9999), reflecting UHC's weaker diffusion (Section 3.4). Given pixel-perfect recovery (PSNR = ∞ on every request), SSIM is identically 1.0 by construction for all methods.

Figure 5 visualizes the performance comparison.

**Figure 5.** Encryption/decryption/end-to-end time (bars) and ciphertext entropy (line) per method (`results/FIGURES/fig5_method_performance.png`).

### 3.4. Ciphertext Quality and Security Indicators

#### 3.4.1. Ciphertext byte metrics (EXP-003)

Table 7 reports byte-level metrics computed offline on 300 payloads per method.

**Table 7.** Ciphertext byte-level metrics (EXP-003, n = 300 per method).

| Method | Payload entropy | Adjacent-byte corr. | Row-gap corr. | χ² statistic | Uniform pass (α=0.05) | Expansion |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 7.5459 | 0.1192 | 0.1280 | 12,079,299 | 20.67% | 1.000009 |
| Blowfish | 7.9999 | 0.00004 | 0.00004 | 253.5 | 94.33% | 1.000015 |
| Hybrid UHC-Blowfish | 7.9999 | −0.00001 | 0.00000 | 256.6 | 93.33% | 1.000017 |

Blowfish and Hybrid achieve near-maximum entropy (≈8 bit/byte), near-zero byte correlation, and an approximately uniform histogram (93–94% chi-square pass rate against a uniform distribution; critical value χ²(255)@0.05 ≈ 292.98). UHC shows lower entropy (7.55), non-negligible byte correlation (≈0.12), and a chi-square statistic in the tens of millions with only a 20.7% pass rate, indicating weak diffusion on the diverse dataset. Payload expansion is negligible (≈1.0000×) for all methods.

#### 3.4.2. Differential analysis (NPCR/UACI)

A one-byte flip at pixel (0,0) (red channel) was applied and both versions were re-encrypted offline with the same mode and key (Blowfish used a fixed, documented IV so both ciphertexts have identical length). Table 8 reports the mean NPCR/UACI over 10 images per method plus a raw baseline without encryption (baseline recomputed analytically per standard definitions: NPCR counts pixels differing in any channel; UACI averages absolute channel differences normalized by 255).

**Table 8.** NPCR/UACI differential test (mean over 10 images).

| Method | NPCR mean (%) | UACI mean (%) |
| --- | --- | --- |
| UHC | 0.0009 | 0.0004 |
| Blowfish | 99.6075 | 33.4700 |
| Hybrid UHC-Blowfish | 99.6057 | 33.4668 |
| Baseline (no encryption) | 0.00017 | ≈0 |

Blowfish and Hybrid approach the ideal values (NPCR ≈ 99.61%, UACI ≈ 33.47%). UHC is almost insensitive to a one-byte change (NPCR ≈ 0.001%) because the Hill cipher processes blocks of size *n* = 16, producing weak one-byte avalanche. This finding is the main empirical justification for the Hybrid UHC-Blowfish architecture: the Blowfish layer corrects the diffusion weakness of UHC.

**Figure 6.** Multi-panel ciphertext quality comparison (entropy, adjacent-byte correlation, NPCR, UACI) across UHC, Blowfish, Hybrid, and raw baseline (`results/FIGURES/fig6_ciphertext_quality.png`).

#### 3.4.3. Decryption fidelity

All 12,670 primary requests (EXP-001 + EXP-002) returned `decrypt_verified = True` and PSNR = ∞, giving a **lossless recovery rate of 100%**. As stated in the methodology, PSNR proves fidelity, not security.

#### 3.4.4. Ciphertext-corruption robustness (new)

Real edge-cloud links corrupt bits. We therefore damaged the encrypted body (header left intact for parseability) of 10 payloads per method with four corruption models — additive Gaussian noise (σ = 8 and 16, applied mod 256 to every body byte) and salt-and-pepper substitutions (density 1% and 5%) — then attempted offline decryption and measured recovery PSNR against the original (Table 9, Figure 7).

**Table 9.** Recovery after ciphertext corruption (n = 10 payloads per cell; PSNR in dB over successful decryptions).

| Method | Gauss σ=8 | Gauss σ=16 | S&P 1% | S&P 5% |
| --- | --- | --- | --- | --- |
| UHC | 6.60 (0% fail) | 6.60 (0% fail) | **17.51 (0% fail)** | 11.32 (0% fail) |
| Blowfish | **100% fail** | **100% fail** | 18.14 (10% fail) | 11.86 (40% fail) |
| Hybrid UHC-Blowfish | **100% fail** | **100% fail** | 10.51 (10% fail) | 7.81 (40% fail) |

Two complementary behaviors emerge. First, CBC-based modes (Blowfish, Hybrid) exhibit catastrophic error propagation: dense Gaussian corruption garbles the final CBC block, breaks PKCS7 unpadding, and makes decryption *fail outright* in 100% of cases; even sparse salt-and-pepper damage causes outright failure in 10–40% of payloads, and when decryption succeeds its output is heavily degraded (Hybrid worst, since inverse-Hill spreads residual garbage across neighboring pixels). Second, UHC degrades gracefully: having no padding step it always produces an image, and its per-column block structure localizes damage — under sparse corruption it preserves structurally usable output (17.51 dB at 1% density) with zero outright failures. Under dense corruption all methods converge to unusable output (≈6–7 dB). This asymmetry quantifies the cost side of the diffusion-vs-error-propagation trade-off that motivates pairing the hybrid scheme with channel coding and integrity protection on noisy links.

#### 3.4.5. Key-space estimates

Table 10 summarizes theoretical key spaces. The UHC construction yields a large structural family (unit-diagonal triangular structure mod 256), but the *effective* secret is bounded by the logistic-map seed derived from `UHC_PASSWORD2`, whose entropy is far below the structural bound; Blowfish runs with the configured deployment key (144-bit effective here, below the 448-bit maximum); the Hybrid scheme multiplies the independent spaces.

**Table 10.** Key-space estimates per scheme.

| Scheme | Keyspace (bits) | Note |
| --- | --- | --- |
| UHC | 1,072 (structural) | Effective entropy limited by password-seeded logistic map |
| Blowfish | 144 (configured key) | Algorithm supports up to 448 bits |
| Hybrid UHC-Blowfish | 1,216 (structural product) | Product of independent UHC and Blowfish spaces |

### 3.5. Microservices Load Behavior (EXP-004)

Table 11 reports load-test results with 1, 5, 10, and 20 virtual users, recomputed over the clean 120-second measurement window (warm-up requests excluded).

**Table 11.** Load-test performance (EXP-004, clean window).

| VU | Requests | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | Error rate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 388 | 3.23 | 253 | 400 | 509 | 0% |
| 5 | 485 | 4.04 | 1,030 | 1,612 | 1,861 | 0% |
| 10 | 461 | 3.84 | 2,323 | 3,346 | 3,799 | 0% |
| 20 | 496 | 4.13 | 3,934 | 6,104 | 7,482 | 0% |

Throughput saturates at ≈3.2–4.1 requests/s once concurrency exceeds a single client, while latency grows almost linearly with the number of virtual users. Per-service CPU sampling shows the encryption service as the bottleneck (54.3–66.3%), followed by the gateway (16.5–19.3%) and feature service (9.0–12.6%), with the selector near idle (1.1–1.7%). No request failed even at VU = 20, indicating graceful degradation under load.

**Figure 8.** Load-test behavior: throughput saturation (left) and latency percentiles (right, log scale) vs concurrent virtual users (`results/FIGURES/fig8_loadtest.png`).

## 4. Discussion

### 4.1. Feature-Driven Cipher Selection

The experimental results confirm that image entropy and GLCM contrast are the dominant drivers of cipher selection. In the deployed placeholder tree their importances are 0.869 and 0.131 respectively; in the policy-distillation refit on real features they are 0.701 and 0.299, and the refit reproduces the routing decisions with 100% test consistency at depth 2 — evidence that the adaptive behavior is fully expressible from just two interpretable features on this corpus. This is consistent with the underlying rule logic: low-entropy images (mostly uniform backgrounds such as Miner) are routed to the lightweight UHC, while high-entropy, high-contrast images (e.g., Cerscospora with severe spotting) are routed to Hybrid to obtain the strongest diffusion. The interpretability of the Decision Tree — a primary reason for its selection over more opaque models — makes this routing logic directly auditable by system operators, which is valuable in an agricultural deployment context where explainability matters.

### 4.2. Trade-Offs Among Methods

Three findings deserve emphasis. First, **Hybrid UHC-Blowfish provides the best ciphertext quality** (entropy 7.9999, NPCR 99.61%, UACI 33.47%) but at the highest cost (89.6 ms encryption, 352 ms end-to-end). Second, **UHC alone is fast but cryptographically weak** on this dataset: its ciphertext entropy (7.55) is far below the 8 bit/byte ideal, byte correlation is ≈0.12, and its one-byte avalanche (NPCR ≈ 0.001%) is almost nonexistent. Third, **adaptive routing trades a small amount of diffusion quality for speed**: because 20.57% of images are routed to UHC, the aggregate ciphertext entropy of the adaptive scenario (7.7394) is lower than the Blowfish/Hybrid 7.9999, while its mean end-to-end latency (254.8 ms) is faster than Hybrid (352.2 ms) and comparable to Blowfish (216.1 ms).

The corruption experiments add a second axis to this trade-off: **diffusion and error propagation are two sides of the same coin**. The very avalanche property that gives CBC modes ideal differential behavior makes them maximally brittle to ciphertext noise (any dense corruption destroys recoverability), whereas UHC's weak-diffusion block locality yields graceful degradation and guaranteed decodability. For noisy agro-IoT links this suggests a practical deployment rule — pair the hybrid scheme with message authentication and forward error correction rather than assuming a pristine channel, or consciously route delay-tolerant, corruption-prone transfers toward modes with localized error propagation.

Key-space considerations temper the headline numbers honestly: although the structural UHC family spans ≈2^1072 matrices, the effective key derives from a short password via a non-cryptographic logistic map, and the deployed Blowfish key provides 144 effective bits; the hybrid combination (≈2^1216 structural) should therefore be read as an upper bound, not a measured strength.

The adaptive-versus-baseline normalization (Table 12) makes the first trade-off explicit. With security = min-max(cipher entropy) and performance = inverse min-max(latency), Blowfish ranks first, Hybrid second, Adaptive third, and UHC fourth. The adaptive score is penalized by the UHC subset; this is an honest representation of the cost of selective routing, not evidence of superiority.

**Table 12.** Normalized adaptive-versus-baseline comparison.

| Method | Security | Performance | Combined | Rank |
| --- | --- | --- | --- | --- |
| Blowfish | 100.0 | 100.0 | 100.0 | 1 |
| Hybrid UHC-Blowfish | 100.0 | 0.0 | 50.0 | 2 |
| Adaptive | 0.69 | 73.67 | 37.18 | 3 |
| UHC | 0.0 | 18.85 | 9.42 | 4 |

### 4.3. Microservices Orchestration

The load test shows that the architecture behaves predictably under concurrency: throughput saturates near 3.2–4.1 requests/s, latency rises linearly with user count, and errors remain at 0%. The encryption service is the clear bottleneck (CPU 54–66%), consistent with it performing the most compute-intensive work (key matrix inversion, two-layer hybrid processing). The gateway and feature services remain lightly loaded (≈17% and ≈10% CPU), and the selector is nearly free (≈1.5%). These results indicate that the current single-node, single-worker deployment is adequate for small-scale field validation but would require horizontal scaling of the encryption service (e.g., multiple replicas behind a load balancer) to support higher throughput in production.

### 4.4. Limitations

Several limitations bound the interpretation of these results. (1) The AI Selector is a **rule-derived placeholder**, not a classifier trained on ground-truth optimal-method labels; therefore classification accuracy against empirical optima is not reported and the proposal's ≥85% target could not be evaluated — the 100% consistency score in §3.2 measures fidelity to the routing policy, not external correctness. (2) **PSNR = ∞ only proves lossless fidelity**, not security; no claim of full cryptographic strength is made, and SSIM ≡ 1 follows mathematically from losslessness rather than being independently measured on rendered imagery. (3) **Ciphertext-quality and corruption metrics were computed on subsets** (300 payloads per method for byte metrics; 10 images for NPCR/UACI; 10 payloads per method per corruption model). (4) **NPCR/UACI used a fixed Blowfish IV** (documented deviation) to measure block sensitivity rather than IV randomness. (5) The **chi-square test measures histogram uniformity**, not cryptographic randomness. (6) **UHC's effective key entropy is bounded by its password-seeded logistic map** (non-cryptographic seeding, static per deployment), despite the ≈2^1072 structural family; the configured Blowfish key provides 144 effective bits, below the algorithm's 448-bit ceiling. (7) **Blowfish CBC runs without a MAC**, and payload headers and IV are transmitted unencrypted — precisely why corruption tests show unauthenticated CBC failing without detection. (8) The **load test is single-node, single-worker**, so horizontal scalability is not demonstrated. (9) A real field trial with farmers, perceptual metrics beyond derivational SSIM, and Kubernetes/n8n orchestration (as envisioned in the proposal) remain future work.

### 4.5. Implications and Future Work

The findings demonstrate that an image-feature-aware cipher-selection workflow is feasible in a service-oriented edge-cloud architecture: the pipeline runs deterministically, recovers every image losslessly, exposes interpretable routing decisions, and behaves predictably both under cryptographic attack indicators and under ciphertext corruption. For agro-IoT security, this suggests that adaptive encryption — rather than a static single cipher — can balance cost and security based on image content, provided link-level integrity and error-control are engineered alongside it. Future work includes: training the selector on ground-truth optimal-method labels derived from per-image multi-metric evaluation (enabling genuine accuracy reporting); extending corruption testing to authenticated modes (Encrypt-then-MAC) and channel-coded transmission; rendering-based SSIM/histogram analyses; horizontal scaling and Kubernetes/n8n orchestration; PostgreSQL/Redis-backed persistence and caching; a field trial with farmers using a mobile app; and eventually quantum-resistant cipher integration as part of the longer-term roadmap.

## 5. Conclusion

This study designed, implemented, and evaluated a Decision Tree-based adaptive AI Selector for hybrid image encryption in a microservices edge-cloud architecture applied to coffee disease images. Using a mixed dataset of 2,834 images from five sources, all 12,670 primary requests completed with 100% lossless recovery. The selector distributed decisions as UHC 20.57%, Blowfish 72.41%, and Hybrid 7.02%; a policy-distillation refit showed the entire routing behavior is reproducible by an interpretable depth-2 Decision Tree with 100% test consistency, driven by image entropy (importance 0.70) and GLCM contrast (0.30). Cryptographic analysis showed that Blowfish and Hybrid approach ideal diffusion (entropy 7.9999 bit/byte, NPCR ≈ 99.61%, UACI ≈ 33.47%), while UHC exhibited weak one-byte avalanche (NPCR ≈ 0.001%), empirically justifying the hybrid design. Ciphertext-corruption tests quantified the complementary cost of that diffusion: CBC-based modes fail outright under dense ciphertext noise, whereas UHC always decrypts with localized degradation — a trade-off that must be paired with authentication and channel coding on real links. A load test identified the encryption service as the throughput bottleneck (≈3.2–4.1 requests/s, 0% error).

The main contribution is the demonstration of an AI-driven cipher-type selection paradigm in a containerized agro-IoT architecture, with interpretable, reproducible routing and clearly quantified trade-offs between cryptographic quality, processing cost, and robustness. The selector, however, must be understood as a rule-derived prototype rather than a trained classifier, and several proposal-planned items (accuracy against empirical optima, field trials, Kubernetes orchestration) remain to be implemented in future work.

## References

*(Placeholder — IEEE style, minimum 25 references, to be compiled with Mendeley per the proposal's related-work sources: UHC, Blowfish, hybrid image encryption, agro-IoT security, microservices security, Decision Tree classifier.)*

[1] [Reference 1 – title, authors, year, journal, DOI]
[2] [Reference 2]
...
