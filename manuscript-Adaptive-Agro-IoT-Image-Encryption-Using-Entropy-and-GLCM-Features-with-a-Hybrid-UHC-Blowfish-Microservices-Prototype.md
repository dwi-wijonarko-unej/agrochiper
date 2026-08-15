# Adaptive Agro-IoT Image Encryption Using Entropy and GLCM Features with a Hybrid UHC-Blowfish Microservices Prototype

**First Author**1, **Second Author**1, **Third Author**2
1 Department/Study Program, Faculty, University, City, Country
2 Department/Study Program, Faculty, University, City, Country

**Corresponding Author:**
Name of Corresponding Author
Faculty and Study Program
Affiliation, City, Country
Email: corresponding.author@email.com

## Abstract

The increasing use of agro-IoT and computer vision in coffee disease monitoring has improved early detection capabilities, but it also raises new concerns regarding the security of image transmission from field devices to cloud-based services [1]. This study proposes and evaluates a containerized microservices prototype for adaptive coffee disease image encryption by integrating entropy and Gray Level Co-occurrence Matrix (GLCM) features with a hybrid Unimodular Hill Cipher (UHC)-Blowfish approach [2][1]. The system consists of a gateway service, feature-service, selector-service, and encryption-service, where a Decision Tree-based AI Selector determines whether an input image should be processed using UHC, Blowfish, or Hybrid UHC-Blowfish based on image characteristics [2][1]. Experiments were conducted on a mixed dataset of 2,834 coffee disease images (six normalized classes assembled from five sources) across four experiment series (EXP-001–EXP-004). All 12,670 primary requests completed successfully with 100% lossless recovery (PSNR = ∞ and decrypt-verification passed). The selector distributed its decisions as UHC 20.6%, Blowfish 72.4%, and Hybrid UHC-Blowfish 7.0%, driven primarily by image entropy and GLCM contrast. Ciphertext analysis showed that Blowfish and Hybrid approach near-ideal diffusion (entropy ≈ 7.9999 bit/byte, NPCR ≈ 99.6%, UACI ≈ 33.5%), whereas UHC exhibits weak one-byte avalanche (NPCR ≈ 0.001%), which empirically justifies the hybrid design. A load test identified the encryption service as the throughput bottleneck (≈4.6–5.0 requests/s at saturation, 0% error rate). The prototype demonstrates an image-feature-aware cipher-selection workflow with modular service orchestration, contributing to adaptive image security in agro-IoT environments [2][1].

## Keywords

Agro-IoT; image encryption; microservices; UHC-Blowfish; entropy; GLCM.

## 1 Introduction

Digital transformation in agriculture has encouraged the use of Internet of Things (IoT) devices and computer vision to support crop monitoring, disease identification, and decision making in precision farming [1]. In coffee cultivation, image-based disease monitoring is especially relevant because visual symptoms on leaves can provide important early indicators of plant health conditions and productivity threats [1]. However, the transmission of disease images from mobile devices or edge nodes to cloud services also introduces new risks related to confidentiality, integrity, and misuse of visual agricultural data [1].

The proposal underlying this manuscript highlights that coffee is a strategic commodity and that coffee plantations face serious threats from diseases such as *leaf rust* and *anthracnose*, creating substantial economic consequences for farmers and regional agricultural systems [1]. At the same time, the adoption of digital agriculture increases dependency on networked systems, which means image data is no longer only an analytic asset but also a cybersecurity object that must be protected [1]. Without proper image protection, sensitive agricultural information may be intercepted, manipulated, or reused by unauthorized parties during transmission and storage [1].

Previous studies on image encryption have shown that single algorithms often involve trade-offs between security strength, computational efficiency, and implementation simplicity [1]. Hill Cipher and its variants are attractive because of their matrix-based formulation and relatively simple implementation, but classical Hill Cipher is known to be vulnerable to known-plaintext attacks if key design is weak [1]. Blowfish, as a symmetric block cipher, offers good performance and has been considered efficient for practical use, yet its isolated application to image data does not always address the structural characteristics of visual information optimally [1]. Therefore, hybrid encryption approaches become relevant because they can combine the advantages of different cryptographic mechanisms in a more adaptive framework [1].

This study focuses on Hybrid UHC-Blowfish as a candidate approach for coffee disease image encryption. The unimodular form of Hill Cipher is considered useful for structured transformation or pixel-level rearrangement, while Blowfish strengthens block-based symmetric protection in subsequent processing [1]. However, not all images exhibit the same entropy level, texture pattern, or file characteristics, meaning that a fixed encryption strategy may not always be the most appropriate choice [1]. This condition creates the need for an adaptive mechanism capable of selecting encryption methods according to image properties rather than applying a static scheme to all inputs [1].

Recent developments in software architecture also support this adaptive perspective. Microservices architectures have become increasingly important for IoT-based systems because they offer modularity, service separation, and easier extensibility compared with monolithic designs [1]. Nevertheless, service fragmentation also increases orchestration complexity and expands the attack surface, especially when routing and security decisions are not informed by data characteristics [1]. In the implemented AgroCipher prototype, this challenge is addressed using a service-based workflow in which feature extraction, decision making, and encryption are separated into dedicated components [2].

The repository currently implements a containerized microservices prototype consisting of a Go-based gateway, a Python/FastAPI feature-service for entropy and GLCM extraction, a selector-service for Decision Tree-based adaptive routing, and an encryption-service for UHC, Blowfish, and Hybrid encryption with decrypt-verify and SQLite logging [2]. In addition, a batch runner is available to process image datasets recursively and export experiment-level metrics such as selected method, encryption time, decryption time, ciphertext entropy, PSNR, and image features into CSV files [2]. These implementation details make the system suitable not only for conceptual design discussion, but also for reproducible experimental evaluation [2].

Based on this context, the research gap addressed in this manuscript lies in the limited integration of three elements: adaptive cipher selection based on image features, hybrid UHC-Blowfish encryption for coffee disease images, and a microservices-based orchestration model for agro-IoT environments [2][1]. Existing studies tend to discuss cryptographic algorithms, computer vision for coffee disease detection, or microservices security separately, while the combination of entropy- and GLCM-driven AI selection with hybrid image encryption in a service-oriented architecture remains underexplored [1]. Accordingly, this study aims to design and implement a microservices prototype that can adaptively choose encryption methods for coffee disease images and provide an experimental basis for evaluating both cryptographic and system-level performance [2][1].

The main contributions of this manuscript are threefold. First, it proposes an adaptive image encryption workflow using entropy and GLCM features as decision inputs for selecting UHC, Blowfish, or Hybrid UHC-Blowfish [2][1]. Second, it presents a containerized microservices prototype that separates gateway, feature extraction, AI selection, and encryption functions into interoperable services [2]. Third, it provides a structured experimental evaluation of image-feature behavior, selector decisions, encryption performance, ciphertext quality, and service-level processing in an agro-IoT setting [2][1].

**Figure 1.** Proposed Agro-IoT image security scenario for coffee disease monitoring from field image capture to adaptive encrypted transmission.

**Figure 2.** Architecture of the AgroCipher microservices prototype consisting of gateway, feature-service, selector-service, encryption-service, and batch experiment client.

**Figure 3.** Adaptive encryption decision flow based on entropy and GLCM features for selecting UHC, Blowfish, or Hybrid UHC-Blowfish.

## 2 Research Method

This study employs a quantitative experimental approach with a prototype-oriented design aligned with the concept formulation stage of technology readiness [1]. The main purpose of the method is to evaluate whether an adaptive image encryption workflow can be implemented consistently in a microservices environment and whether the resulting system can produce measurable outputs related to image characteristics, encryption behavior, and processing performance [2][1]. The research does not yet emphasize full-scale production deployment, but rather focuses on the design, execution, and reproducible observation of the proposed prototype [1].

The research object consists of coffee disease images and the AgroCipher application prototype. The experimental dataset (v2) comprises **2,834 coffee disease images**, assembled from five public and community sources and normalized into six classes (Healthy, Rust, Miner, Phoma, Red Spider Mite, Cerscospora) using deterministic round-robin sampling across sources (seed 42, cap 500 images per class). All images were downscaled to a maximum dimension of 1,024 px and stored as RGB JPEG (quality 90), with a manifest file recording the source-to-class mapping for reproducibility. The implemented system provides a batch-processing client for recursively sending images to the gateway service and storing the returned metrics in CSV format [2][1]. As a result, the data analyzed in this study includes both visual image characteristics and system-generated outputs produced during encryption and decryption workflows [2].

At the system level, the prototype is composed of four main services. The **gateway** service, implemented in Go, acts as the main API entry point and orchestrates the request flow [2]. The **feature-service**, implemented using Python/FastAPI, extracts image characteristics including entropy and GLCM-based texture attributes [2]. The **selector-service** applies a Decision Tree-based mechanism to determine the most appropriate encryption route for each input image [2][1]. The **encryption-service** executes UHC, Blowfish, or Hybrid UHC-Blowfish encryption, performs decrypt-verification, and logs selected metrics into SQLite storage [2]. The services are configured through an environment file and orchestrated in a containerized environment using Docker Compose [2].

The research workflow begins with dataset preparation and service validation. Input images are prepared in class folders and tested through the available API endpoint protected by an API key [2]. The gateway forwards each uploaded image to the feature-service, which computes entropy, file size, and GLCM-based values, including correlation and contrast [2]. These values are then passed to the selector-service to determine whether the image should be encrypted using UHC, Blowfish, or Hybrid UHC-Blowfish [2]. Finally, the selected method is executed by the encryption-service, which returns encryption time, decryption time, ciphertext entropy, PSNR, and encrypted payload information, while logging the request into SQLite [2].

To support large-scale experiments, the prototype includes `client/batch_runner.py`, which scans the dataset recursively, sends each image to the API gateway, records the selected method and related metrics, and exports the results into CSV format [2]. This mechanism enables consistent batch-level data acquisition and provides a reproducible basis for result analysis [2]. The batch runner also supports resumable execution, which is useful when processing large image collections in iterative experiments [2].

Four experiment series were executed to collect the evidence reported in Section 3:

- **EXP-001** — adaptive behavior of the AI Selector (repeated 3 times per image, warm-up 10) on the full dataset: 8,502 primary requests.
- **EXP-002** — forced-method baselines (UHC, Blowfish, Hybrid UHC-Blowfish, Adaptive; 1 request per image, warm-up 5): 2,834 requests per scenario.
- **EXP-003** — ciphertext collection for cryptographic analysis: a deterministic, evenly strided sample of 300 payloads per scenario (1,136 payloads total) to limit storage while covering all classes.
- **EXP-004** — microservices load test with 1, 5, 10, and 20 virtual users, 120 s per scenario, warm-up 10 s.

The input variables used in the prototype include image entropy, file size, GLCM correlation, and GLCM contrast [2][1]. These variables serve as feature inputs for the AI Selector and are expected to represent image complexity and texture variation relevant to encryption decisions [2][1]. The process variables include the selected encryption method, decision code, reasoning string, encryption time, and decryption time [2]. The output variables include ciphertext entropy, PSNR, decrypted image verification status, and additional service-level records captured through log files or database tables [2].

Data collection is conducted through system-driven experimentation rather than survey-based techniques. First, the study uses documentation and repository inspection to identify the actual service flow, available metrics, and implemented components [2][1]. Second, image data is submitted to the system using the provided API and batch runner [2]. Third, the resulting metrics are collected automatically from CSV batch outputs and SQLite encryption logs, ensuring that the analyzed data corresponds directly to system execution rather than manual measurement [2]. This approach is suitable for software and cybersecurity experimentation because it provides traceable and reproducible technical evidence [2][1].

The data analysis method in this manuscript is quantitative and descriptive-comparative. Descriptive analysis is used to summarize image feature distributions, selector decisions, encryption and decryption runtime, ciphertext entropy, and PSNR values [2]. Comparative analysis is used to examine differences between adaptive selection and fixed-method baselines, and to interpret the behavior of the adaptive mechanism across varying image characteristics [2][1].

The evaluation plan is centered on several measurable indicators. Feature-level evaluation considers entropy and GLCM-based descriptors as decision inputs [2][1]. Encryption-level evaluation considers processing time, ciphertext entropy, and decryption fidelity measured through PSNR and verification outputs [2]. Cryptographic evaluation additionally considers ciphertext uniformity (chi-square test), adjacent-byte correlation, and differential analysis (NPCR/UACI) on the collected payloads. System-level evaluation considers batch execution behavior, load-test latency/throughput, and log consistency produced by the service architecture [2]. The finalized results of these evaluations are presented in Section 3.

**Figure 4.** Research workflow from coffee disease image dataset preparation, feature extraction, adaptive selection, and encryption-decryption verification to batch result logging.

**Figure 5.** Sequence diagram of request processing in the AgroCipher prototype from gateway request reception to selector decision and encryption response.

**Figure 6.** Experimental data acquisition pipeline using batch runner CSV output and SQLite logging for reproducible analysis.

## 3 Results and Analysis

This section presents the finalized experimental results obtained from the batch experiments EXP-001–EXP-004. In accordance with the MATRIK template, the section combines numerical findings and analytical discussion in an integrated manner [3]. All reported values are traceable to the raw experiment outputs (CSV batch files, SQLite logs, and collected ciphertext payloads). A summary of experimental integrity: all 12,670 primary requests (EXP-001 + EXP-002) completed successfully with `http_status = 200`, and every request achieved lossless recovery (`psnr = "∞"`, `decrypt_verified = True`); no request failed.

### 3.1 Experimental Setup

The prototype ran in a **single-node Docker Compose** environment (Go gateway; Python/FastAPI feature-, selector-, and encryption-services; uvicorn single worker; host with 3.7 GB RAM). The gateway protected its endpoint with a 64-character API key (`GATEWAY_API_KEY`). The experiment mode (`EXPERIMENT_MODE`) enabled a forced-method header exclusively for the baseline scenarios (EXP-002) and was disabled during analysis.

#### Dataset

Table 1 summarizes the mixed experimental dataset assembled from five sources and normalized into six classes. Red Spider Mite is smaller (334 images) because it is the least represented class across all sources.

**Table 1.** Composition of the mixed experimental dataset (v2).

| Class | Count | Source composition |
| --- | --- | --- |
| Healthy | 500 | OLD 100, COF 100, DRIVE 100, ETH-test 100, ETH-aug 100 |
| Rust | 500 | OLD 100, COF 100, DRIVE 100, ETH-test 100, ETH-aug 100 |
| Miner | 500 | OLD 250, DRIVE 250 |
| Phoma | 500 | OLD 125, DRIVE 125, ETH-test 125, ETH-aug 125 |
| Red Spider Mite | 334 | OLD 167, COF 167 |
| Cerscospora | 500 | ETH-test 250, ETH-aug 250 |
| **Total** | **2834** | — |

**Table 2.** Experiment series executed on the prototype.

| ID | Purpose | Configuration | Primary requests |
| --- | --- | --- | --- |
| EXP-001 | Adaptive selector behavior | repeat 3, warm-up 10 | 8,502 (0 failed) |
| EXP-002 | Forced-method baselines (UHC/Blowfish/Hybrid/Adaptive) | repeat 1, warm-up 5 | 2,834 × 4 (0 failed) |
| EXP-003 | Ciphertext cryptographic analysis | deterministic stride sample, 300/scenario | 1,136 payloads |
| EXP-004 | Microservices load test | VU 1/5/10/20, 120 s, warm-up 10 s | 430–604/scenario |

### 3.2 Feature Characteristics and Selector Decisions

#### 3.2.1 Image feature profile

The mean Shannon entropy per class (EXP-001) is reported in Table 3. The mixed dataset spans a wide entropy range (≈1.15–7.90 bit/byte), providing sufficient variation in image characteristics to exercise the adaptive decision mechanism.

**Table 3.** Mean image entropy per class.

| Class | Mean entropy |
| --- | --- |
| Red Spider Mite | 7.5692 |
| Healthy | 6.4230 |
| Cerscospora | 6.0164 |
| Rust | 6.1331 |
| Phoma | 5.7387 |
| Miner | 5.2429 |

#### 3.2.2 AI Selector decision distribution

The AI Selector (DecisionTree, `max_depth = 3`, seed 42) distributed its decisions over the 2,834 images as summarized in Table 4.

**Table 4.** Distribution of AI Selector decisions and mean feature values per selected method (EXP-001).

| Method | Images (mode) | % | Mean entropy | Mean GLCM corr. | Mean GLCM contrast | Mean size (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 583 | 20.57 | 3.25 | 0.985 | 0.04 | 46.9 |
| Blowfish | 2,052 | 72.41 | 6.76 | 0.984 | 0.07 | 84.4 |
| Hybrid UHC-Blowfish | 199 | 7.02 | 7.68 | 0.897 | 0.64 | 220.9 |

The extracted decision tree (Figure 3) shows that images with low entropy (≈1.15–4.78) are routed to **UHC**, images with moderate-to-high entropy to **Blowfish**, and images with very high entropy combined with high GLCM contrast (>0.23) to **Hybrid UHC-Blowfish**:

```
entropy <= 4.78                            -> UHC
entropy > 4.78
 ├─ entropy <= 6.24                        -> Blowfish
 └─ entropy > 6.24
     ├─ glcm_contrast <= 0.23              -> Blowfish
     └─ glcm_contrast >  0.23              -> Hybrid UHC-Blowfish
```

The computed feature importance was `entropy = 0.869`, `glcm_contrast = 0.131`, `size_kb = 0`, and `glcm_correlation = 0`, consistent with the tree structure in which entropy performs the primary split and GLCM contrast separates the hybrid branch. Full per-method feature statistics are available in `selector_feature_summary.csv`.

**Limitation stated explicitly**: the decision labels are generated from a synthetic rule-derived model (no ground-truth "best method" per image exists), so the interpretation above is descriptive and correlational rather than a classification-accuracy claim.

### 3.3 Encryption and Decryption Performance

The comparison among methods (EXP-002, 2,834 requests per scenario, 100% success) is shown in Table 5.

**Table 5.** Encryption and decryption performance per method (EXP-002).

| Method | Encrypt (ms) | Decrypt (ms) | E2E mean (ms) | E2E p95 (ms) | Cipher entropy | Lossless |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 72.4 | 59.0 | 285.5 | 440 | 7.7376 | 100% |
| Blowfish | 19.1 | 18.5 | 214.7 | 324 | 7.9999 | 100% |
| Hybrid UHC-Blowfish | 99.5 | 88.4 | 357.1 | 544 | 7.9999 | 100% |
| Adaptive | 38.8 | 31.7 | 241.3 | 405 | 7.7394 | 100% |

Observations:
- **Blowfish** is the fastest method (19.1 ms) and achieves the highest ciphertext entropy (7.9999); **Hybrid UHC-Blowfish** is the slowest (99.5 ms) because it applies two layers of transformation.
- **Adaptive** routing (38.8 ms) occupies an intermediate position — faster than Hybrid but slower than Blowfish — because 20.6% of images are routed to UHC.
- The cipher entropy of Adaptive and UHC (7.74) is lower than that of Blowfish and Hybrid (7.9999), reflecting the weak diffusion of UHC discussed in Section 3.4.

#### Adaptive versus baseline (normalized scores)

The scores were computed as `security = min-max(cipher_entropy_mean)`, `performance = inverse min-max(encryption_time + E2E latency)`, and `combined = 0.5·security + 0.5·performance`.

**Table 6.** Normalized adaptive-versus-baseline comparison (EXP-002).

| Method | Security | Performance | Combined | Rank |
| --- | --- | --- | --- | --- |
| Blowfish | 100.0 | 100.0 | 100.0 | 1 |
| Hybrid UHC-Blowfish | 100.0 | 0.0 | 50.0 | 2 |
| Adaptive | 0.69 | 79.18 | 39.93 | 3 |
| UHC | 0.0 | 44.29 | 22.14 | 4 |

**Honest interpretation**: because adaptive routing directs 20.6% of images to UHC, whose ciphertext entropy is lower, the adaptive *security* score drops sharply. This result reveals an **explicit trade-off**: adaptive routing exchanges a small amount of diffusion quality for processing speed on the low-entropy subpopulation — it is not evidence of superiority.

### 3.4 Ciphertext Quality and Security Indicators

#### 3.4.1 Ciphertext byte metrics (EXP-003, 300 payloads per method)

**Table 7.** Ciphertext byte-level metrics per method.

| Method | Payload entropy | Adjacent-byte corr. | Row-gap corr. | χ² statistic | Uniform pass (α = 0.05) | Expansion |
| --- | --- | --- | --- | --- | --- | --- |
| UHC | 7.5459 | 0.1192 | 0.1280 | 12,079,299 | 20.7% | 1.000009 |
| Blowfish | 7.9999 | 0.00004 | 0.00004 | 253.5 | 94.3% | 1.000015 |
| Hybrid UHC-Blowfish | 7.9999 | −0.00001 | 0.00000 | 256.6 | 93.3% | 1.000017 |

- Blowfish and Hybrid achieve near-maximum entropy (≈8 bit/byte), near-zero byte correlation, and a histogram that is close to uniform (93–94% pass rate in a chi-square test against a uniform distribution; critical value `χ²(255)@0.05 ≈ 292.98`).
- UHC shows lower entropy (7.55), non-negligible byte correlation (≈0.12), and a chi-square statistic in the tens of millions with only a 20.7% pass rate, indicating **weak diffusion** on the diverse dataset.
- Payload expansion (`encrypted/original ≈ 1.0000x`) is negligible for all methods (header + IV + PKCS7 padding ≤ 16 bytes).

#### 3.4.2 Differential analysis (NPCR/UACI)

A one-byte flip at pixel (0,0) (red channel) was applied and both versions were re-encrypted offline with the same mode and key (Blowfish used a fixed documented IV for identical ciphertext length).

**Table 8.** NPCR/UACI differential test (mean over 10 images).

| Method | NPCR mean (%) | UACI mean (%) |
| --- | --- | --- |
| UHC | 0.001 | 0.000 |
| Blowfish | 99.607 | 33.470 |
| Hybrid UHC-Blowfish | 99.606 | 33.467 |
| Baseline without encryption | 0.00006 | 0.0000 |

Blowfish and Hybrid approach the ideal values (NPCR ≈ 99.61%, UACI ≈ 33.46%). UHC is almost insensitive to a one-byte change (NPCR ≈ 16/1,572,864) because the Hill cipher processes blocks of size *n* = 16, resulting in **weak one-byte avalanche**. This finding is the main empirical justification for the **Hybrid UHC-Blowfish** architecture: the Blowfish layer corrects the diffusion weakness of UHC.

#### 3.4.3 Decryption fidelity

All primary requests (EXP-001 + EXP-002 = 12,670 requests) produced `decrypt_verified = True` and PSNR = ∞, giving a **lossless recovery rate of 100%**. As stated in the research method, PSNR only proves fidelity and does not by itself constitute a security guarantee.

### 3.5 Discussion of Microservices-Based Adaptive Encryption

#### 3.5.1 Service performance under load (EXP-004)

A load test using 40 test images, 120 s per scenario, and virtual users (VU) of 1, 5, 10, and 20 produced the results in Table 9, with a 0% error rate in every scenario.

**Table 9.** Load-test performance of the microservices prototype (EXP-004).

| VU | Requests | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) | Encryption CPU (%) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 430 | 3.58 | 252 | 398 | 490 | 54.3 |
| 5 | 556 | 4.63 | 1,017 | 1,574 | 1,848 | 63.2 |
| 10 | 550 | 4.58 | 2,184 | 3,335 | 3,719 | 66.3 |
| 20 | 604 | 5.03 | 4,031 | 6,656 | 8,184 | 63.7 |

- **Throughput saturates at ≈4.6–5.0 requests/s** for VU ≥ 5, while latency grows almost linearly with the number of users. The bottleneck is the **encryption-service** (CPU 54–66%, uvicorn single worker); the gateway uses 16–19%, feature-service 9–13%, and selector-service ≈1–2% (see `service_resource_usage.csv`).
- No request failed even at VU = 20, indicating that the prototype degrades gracefully (increasing latency rather than returning errors).

#### 3.5.2 Synthesis

The experimental findings connect the three layers that constitute the research gap. (i) *Image-feature-aware cipher selection* (entropy + GLCM → UHC/Blowfish/Hybrid) runs consistently and produces a meaningful decision distribution on the mixed dataset. (ii) *Hybrid UHC-Blowfish* delivers the best ciphertext quality and corrects the weak diffusion of UHC, at a clearly measurable time overhead. (iii) *Microservices orchestration* supports a separated yet measurable feature→selection→encryption pipeline, with the bottleneck correctly identified at the encryption service. All findings are descriptive-comparative on a single-node prototype; **no claims are made regarding selector accuracy, full cryptographic security, or horizontal scalability**.

**Figure 7.** Distribution of image entropy and GLCM contrast versus selector decision across the experimental dataset (plotted from `FIGURE_DATA/`).

**Figure 8.** Comparison of encryption/decryption time and cipher entropy among UHC, Blowfish, Hybrid, and Adaptive routing (plotted from `FIGURE_DATA/`).

**Figure 9.** Load-test latency (p50/p95/p99) and throughput per virtual-user scenario (plotted from `FIGURE_DATA/`).

### 3.6 Reproducibility

- Audit commit: `34f9a398dbcc31e714cdceebdd5481aafc15b940`; container versions as reported by `docker compose ps`; all metrics are linked by `request_id` across batch CSVs, SQLite logs (`data/experiment/*`), and EXP-003 payloads.
- Parameters: dataset v2 (2,834 images, seed 42, cap 500/class, max dimension 1,024); EXP-001 repeat 3; EXP-002 repeat 1; EXP-003 stride sample of 300/scenario; EXP-004 VU 1/5/10/20, 120 s. The `.env` file is git-ignored (random 64-character API key).
- Analysis artifacts: `PAPER_DATASET.csv`, `PAPER_TABLES.xlsx`, `PAPER_SUMMARY.md`, `FIGURE_DATA/*.csv`, `analysis/*.csv`, `EXP-004/*`.

## 4 Conclusion

This study designed, implemented, and evaluated a containerized microservices prototype for adaptive coffee disease image encryption that combines entropy- and GLCM-driven AI selection with a Hybrid UHC-Blowfish scheme. Experiments on a mixed dataset of 2,834 coffee disease images demonstrated consistent system behavior: all 12,670 primary requests completed with 100% lossless recovery. The AI Selector produced a meaningful decision distribution (UHC 20.6%, Blowfish 72.4%, Hybrid 7.0%) governed primarily by image entropy and GLCM contrast. Cryptographic analysis showed that Blowfish and Hybrid approach near-ideal diffusion (entropy ≈ 7.9999 bit/byte; NPCR ≈ 99.6%; UACI ≈ 33.5%), whereas UHC alone exhibited weak one-byte avalanche (NPCR ≈ 0.001%), empirically justifying the hybrid design. A load test identified the encryption service as the throughput bottleneck of the prototype (≈4.6–5.0 requests/s at saturation with 0% error rate).

The findings address the research objectives and the identified gap in adaptive, image-feature-aware image encryption for agro-IoT coffee disease monitoring. Future development may include broader deployment scenarios, additional security indicators (e.g., key sensitivity and histogram analysis on the full payload), and an extended selector evaluation based on ground-truth method preferences [3].

## 5 Acknowledgements

The authors would like to acknowledge the support of the research grant program and the institutional environment that enabled the development of the AgroCipher prototype. Appreciation is also addressed to the faculty, laboratory, collaborators, and all parties who contributed to the preparation of the dataset, system implementation, and research activities related to this manuscript [1][3].

## 6 Declarations

### AI Usage Statement

During the preparation of this manuscript, the author(s) used generative AI tools to support language refinement, outline preparation, and manuscript drafting assistance. After using these tools, the author(s) reviewed, revised, and validated the content as needed and take full responsibility for the final content of the manuscript [3].

### Author Contribution

First Author: conceptualization, methodology, software, investigation, data curation, writing—original draft.  
Second Author: supervision, validation, methodology review, writing—review and editing.  
Third Author: system testing, formal analysis support, and documentation.  

> **Note:** Please adjust the contribution statement to match the actual roles of each author before submission.

### Funding Statement

This work was supported by the beginner lecturer research grant program at Universitas Jember under the approved research scheme described in the proposal document [1][3].

> **Note:** Please replace this sentence with the exact official funding acknowledgment number and wording required by the grant administrator.

### Competing Interest

The author(s) declare that there is no competing interest related to this manuscript [3].

## References

> **Placeholder:** References will be compiled in IEEE style using Mendeley, following the MATRIK journal requirement of prioritizing recent and relevant journal articles with DOI information and a minimum of 25 references [3].