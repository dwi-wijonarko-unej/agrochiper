# Adaptive Agro-IoT Image Encryption Using Entropy and GLCM Features with Hybrid UHC-Blowfish Microservices

**First Author**1, **Second Author**1, **Third Author**2
1 Department/Study Program, Faculty, University, City, Country
2 Department/Study Program, Faculty, University, City, Country

**Corresponding Author:**
Name of Corresponding Author
Faculty and Study Program
Affiliation, City, Country
Email: corresponding.author@email.com

## Abstract

Coffee disease monitoring increasingly relies on agro-IoT and computer vision, but image transmission from field devices to cloud services introduces confidentiality and integrity risks. This study evaluates a containerized microservices prototype for adaptive coffee disease image encryption using entropy and Gray Level Co-occurrence Matrix (GLCM) features with Unimodular Hill Cipher (UHC), Blowfish, and Hybrid UHC-Blowfish. The prototype consists of a Go gateway, Python/FastAPI feature-, selector-, and encryption-services, SQLite logging, and a batch experiment client. A Decision Tree-based selector routes each image according to entropy and texture features. Experiments used 2,834 coffee disease images across four series covering adaptive routing, forced-method baselines, ciphertext analysis, and load testing. All 19,838 primary requests completed with lossless recovery. Blowfish had the lowest encryption runtime (21.4 ms) and near-maximum ciphertext entropy (7.9999 bit/byte), while Hybrid UHC-Blowfish provided comparable ciphertext quality with the highest overhead (89.6 ms). Differential analysis showed strong diffusion for Blowfish and Hybrid (NPCR approximately 99.6%; UACI approximately 33.5%) but weak one-byte avalanche for UHC. Throughput saturated at approximately 4.6–5.0 requests/s under concurrent load, with the encryption service identified as the bottleneck. The results demonstrate a reproducible image-feature-aware encryption workflow for agro-IoT while exposing the security-performance trade-offs of adaptive routing.

## Keywords

Agro-IoT; image encryption; microservices; UHC-Blowfish; entropy; GLCM.

## 1 Introduction

The use of Internet of Things (IoT) devices and computer vision has expanded the capacity of agriculture to monitor crops, detect disease symptoms, and support data-driven decisions. In coffee cultivation, leaf images collected by smartphones, cameras, or edge devices can support early identification of disease conditions such as *leaf rust* and *anthracnose*. These images, however, are commonly transmitted through public or heterogeneous networks before they reach cloud-based analytics services. Consequently, the image stream becomes a security-sensitive asset: interception, modification, or unauthorized reuse can expose information about field conditions, disease incidence, and agricultural production.

**Figure 1** presents the operational setting addressed in this study. It should combine the agro-IoT image-capture scenario with the system architecture: a field device uploads a coffee leaf image through the API gateway; the image is characterized by the feature-service, routed by the selector-service, encrypted by the encryption-service, and logged for later analysis. The combined illustration is intended to show why image security and modular service orchestration must be considered together rather than as isolated concerns.

[INSERT results/FIGURES/fig1_architecture.png HERE]

**Figure 1.** AgroCipher operational scenario and containerized microservices architecture for adaptive coffee disease image encryption.

Conventional image encryption approaches commonly involve a trade-off between cryptographic properties and processing cost. Hill Cipher is attractive because its matrix operations are straightforward, but classical formulations are vulnerable when key construction is weak and may provide limited diffusion under small input changes. Blowfish is a symmetric block cipher with practical runtime characteristics, but a fixed Blowfish-only configuration does not explicitly exploit variation in image complexity or texture. Hybrid encryption is therefore relevant because it can combine complementary transformations; however, applying the hybrid route to every image can increase computational overhead unnecessarily.

The present study considers image entropy and Gray Level Co-occurrence Matrix (GLCM) texture descriptors as observable characteristics for adaptive method selection. Entropy represents information variability, while GLCM contrast and correlation describe spatial texture properties. Rather than applying one method to all images, the proposed selector routes each input to UHC, Blowfish, or Hybrid UHC-Blowfish. **Figure 2** summarizes this routing logic. Low-entropy images are directed to UHC, moderate-to-high entropy images are directed to Blowfish, and images with high entropy combined with high GLCM contrast are directed to the Hybrid route. The figure should clarify that the selector is a routing mechanism based on image features, not a disease classifier.

[INSERT results/FIGURES/fig2_decision_flow.png HERE]

**Figure 2.** Entropy- and GLCM-driven decision flow for selecting UHC, Blowfish, or Hybrid UHC-Blowfish.

Research on coffee imagery often focuses on disease classification accuracy, whereas research on image encryption commonly evaluates cryptographic methods outside of the agro-IoT deployment context. Similarly, microservices security studies often emphasize authentication, authorization, or container hardening instead of feature-aware cipher selection. The research gap is therefore the limited integration of adaptive image-feature-based selection, Hybrid UHC-Blowfish encryption, and microservices orchestration for coffee disease images.

This study addresses that gap through a containerized prototype named AgroCipher. The study makes three contributions. First, it implements an image-feature-aware routing workflow using entropy and GLCM features to select UHC, Blowfish, or Hybrid UHC-Blowfish. Second, it separates gateway, feature extraction, selection, encryption, and logging responsibilities into interoperable services. Third, it evaluates the prototype using method-comparison, ciphertext-quality, and load-test experiments. The goal is not to claim complete cryptographic security or production-scale elasticity, but to provide reproducible evidence of the design trade-offs within a single-node microservices prototype.

## 2 Research Method

### 2.1 Dataset and Prototype Environment

The study used a normalized dataset of 2,834 coffee disease images collected from five public and community sources. The images were organized into six classes—Healthy, Rust, Miner, Phoma, Red Spider Mite, and Cerscospora—through deterministic sampling with seed 42. Images were converted to RGB JPEG and resized to a maximum dimension of 1,024 px. This normalization reduced variation caused by incompatible formats while preserving visual differences relevant to entropy and texture analysis.

**Table 1** summarizes the dataset composition. The class distribution is intentionally close to balanced for five classes, while Red Spider Mite has fewer samples because its availability was lower across the input sources. Retaining this smaller class preserves the available diversity rather than artificially duplicating images.

**Table 1.** Composition of the mixed coffee disease image dataset.

| Class | Images | Source composition |
| --- | ---: | --- |
| Healthy | 500 | OLD 100, COF 100, DRIVE 100, ETH-test 100, ETH-aug 100 |
| Rust | 500 | OLD 100, COF 100, DRIVE 100, ETH-test 100, ETH-aug 100 |
| Miner | 500 | OLD 250, DRIVE 250 |
| Phoma | 500 | OLD 125, DRIVE 125, ETH-test 125, ETH-aug 125 |
| Red Spider Mite | 334 | OLD 167, COF 167 |
| Cerscospora | 500 | ETH-test 250, ETH-aug 250 |
| **Total** | **2,834** | — |

As shown in **Table 1**, the dataset provides both class coverage and source-level variation. This variation is useful because the selector processes individual images with different texture, entropy, resolution, and size characteristics rather than relying solely on class labels.

The prototype was deployed in a single-node Docker Compose environment. It consists of: (1) a Go-based gateway that authenticates and orchestrates requests; (2) a Python/FastAPI feature-service that extracts entropy, file size, GLCM correlation, and GLCM contrast; (3) a Python/FastAPI selector-service that applies a Decision Tree; and (4) a Python/FastAPI encryption-service that performs UHC, Blowfish, or Hybrid UHC-Blowfish encryption, decrypt-verification, and SQLite logging. A batch runner recursively submits image files to the gateway and stores experiment-level outputs in CSV files.

### 2.2 Research Workflow

The study follows the workflow shown in **Figure 3**, which integrates the dataset, the processing services, and the evaluation pipeline into a single reproducible flow. The workflow begins with dataset preparation, in which raw coffee leaf images are collected, labelled, and organized into class folders. Preprocessing then normalizes each image by converting it to RGB JPEG and resizing it to a maximum dimension of 1,024 px. In the feature-extraction stage, the feature-service computes entropy, file size, GLCM correlation, and GLCM contrast for every image. These features feed the adaptive-selection stage, in which a Decision Tree routes each image to UHC, Blowfish, or Hybrid UHC-Blowfish. The selected method is then applied in the image-encryption stage, and every encrypted payload is immediately decrypt-verified to confirm lossless recovery. The same pipeline is executed repeatedly by the batch runner, producing per-image results that are stored as CSV files in the batch-execution and log-collection stages. Finally, the statistical-analysis stage aggregates the stored results into the method-comparison, ciphertext-quality, and load-test summaries discussed in Section 3.

[INSERT results/FIGURES/fig3_research_workflow.png HERE]

**Figure 3.** Research workflow from coffee disease image dataset preparation, feature extraction, adaptive selection, and encryption-decryption verification to batch result logging.

### 2.3 Adaptive Encryption Workflow

For each uploaded image, the gateway forwards the payload to the feature-service. The feature-service computes entropy, file size, GLCM correlation, and GLCM contrast. The selector-service then uses these features to select one encryption route. The encryption-service executes the selected route, decrypts the payload for verification, computes relevant output metrics, persists its logs, and returns the response through the gateway. Batch processing adds request-level identifiers and stores the returned results for later analysis.

The workflow is evaluated as a system pipeline rather than as four unrelated components. The implementation records method selection, encryption and decryption time, ciphertext entropy, PSNR, verification status, and request outcome. This design makes it possible to compare cryptographic outcomes with the cost of service-based processing.

### 2.4 Experiment Design and Metrics

The evaluation was divided into four experiment series. **Table 2** summarizes the purpose and configuration of each series. Separating the experiments prevents metrics obtained under adaptive routing, forced-method baselines, ciphertext sampling, and concurrent load from being interpreted as if they were generated under one identical condition.

**Table 2.** Experiment design and request volume.

| ID | Objective | Configuration | Primary observations |
| --- | --- | --- | ---: |
| EXP-001 | Adaptive selector behavior | 3 repetitions/image; 10 warm-up requests | 8,502 requests |
| EXP-002 | Forced UHC, Blowfish, Hybrid, and Adaptive comparison | 1 repetition/image/scenario; 5 warm-up requests | 11,336 requests |
| EXP-003 | Ciphertext byte-level and differential analysis | deterministic sample of 300 payloads/scenario | 1,136 payloads |
| EXP-004 | Microservices load test | 1, 5, 10, and 20 virtual users; 120 s/scenario | 430–604 requests/scenario |

EXP-001 describes how the selector distributes images across methods. EXP-002 compares methods under a common dataset condition. EXP-003 limits ciphertext collection to a deterministic sample so that byte-level and differential analysis remain manageable. EXP-004 measures prototype behavior as concurrent request load increases.

The evaluation uses four groups of indicators. First, selector behavior is described using method distribution and input-feature profiles. Second, runtime and fidelity are assessed using encryption time, decryption time, end-to-end latency, PSNR, and decrypt-verification status. Third, ciphertext properties are assessed through entropy, adjacent-byte correlation, chi-square uniformity, Number of Pixel Change Rate (NPCR), and Unified Average Changing Intensity (UACI). Fourth, microservices behavior is assessed using throughput, latency percentiles, encryption-service CPU utilization, and error rate. PSNR is used only to verify reconstruction fidelity; it is not interpreted as a security metric.

## 3 Results and Analysis

All 19,838 primary requests reported in the adaptive and forced-method datasets completed successfully with HTTP status 200. Every request passed decrypt-verification and produced PSNR = ∞, indicating lossless recovery. The following sections examine selector behavior, method performance, ciphertext quality, and load behavior separately.

### 3.1 Image Features and Selector Behavior

The dataset exhibited substantial image-level variation. Mean entropy values ranged from 5.2429 for Miner to 7.5692 for Red Spider Mite at the class level, confirming that the image collection contains different levels of visual information complexity. However, the selector operates per image rather than per class. **Table 3** therefore reports the distribution of actual selector decisions and the mean features associated with each selected method.

**Table 3.** Selector distribution and mean input features by selected method (EXP-001).

| Method | Images | Share (%) | Entropy | GLCM corr. | GLCM contrast | Size (KB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| UHC | 583 | 20.57 | 3.25 | 0.985 | 0.04 | 46.9 |
| Blowfish | 2,052 | 72.41 | 6.76 | 0.984 | 0.07 | 84.4 |
| Hybrid UHC-Blowfish | 199 | 7.02 | 7.68 | 0.897 | 0.64 | 220.9 |

**Table 3** shows that Blowfish is selected for most images. UHC is associated with the lowest entropy and contrast values, whereas Hybrid UHC-Blowfish is selected for a smaller high-entropy, high-contrast, and larger-size subgroup. The fitted Decision Tree uses entropy as the primary split and GLCM contrast as the secondary split for the Hybrid branch; its feature importance values are 0.869 for entropy and 0.131 for GLCM contrast, with zero contribution from size and GLCM correlation in the final tree.

The relationship between these features and selected methods is visualized in **Figure 4**. The figure should display entropy against GLCM contrast using a separate color for each decision. It is intended to show the selector’s routing regions: low-entropy images in the UHC region, most moderate-to-high entropy images in the Blowfish region, and high-entropy/high-contrast images in the Hybrid region.

[INSERT results/FIGURES/fig1_selector_scatter.png HERE]

**Figure 4.** Entropy and GLCM-contrast distribution of images grouped by AI Selector decision.

The selector labels are generated by a rule-derived Decision Tree and do not represent a ground-truth “best encryption method” label. Thus, the results describe routing behavior and its relationship to image characteristics; they do not constitute a classification-accuracy result.

### 3.2 Runtime, Fidelity, and Adaptive Trade-off

The forced-method experiment compared UHC, Blowfish, Hybrid UHC-Blowfish, and Adaptive routing on the same image collection. **Table 4** summarizes processing time, end-to-end latency, ciphertext entropy, lossless recovery, and normalized trade-off scores. The score is included only to make the configuration-specific balance between ciphertext randomness and runtime visible; it is not a universal ranking of algorithms.

**Table 4.** Method performance, ciphertext entropy, and normalized trade-off score (EXP-002).

| Method | Encrypt (ms) | Decrypt (ms) | E2E mean (ms) | Cipher entropy | Lossless | Combined score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| UHC | 77.58 | 70.58 | 325.74 | 7.7376 | 100% | 9.42 |
| Blowfish | 21.39 | 21.14 | 216.10 | 7.9999 | 100% | 100.00 |
| Hybrid UHC-Blowfish | 89.63 | 88.20 | 352.19 | 7.9999 | 100% | 50.00 |
| Adaptive | 36.47 | 38.16 | 254.83 | 7.7394 | 100% | 37.18 |

As presented in **Table 4**, Blowfish has the lowest encryption and decryption time while attaining near-maximum ciphertext entropy. Hybrid UHC-Blowfish attains similar entropy but incurs the largest runtime because it combines two transformation stages. Adaptive routing is faster than Hybrid but slower than Blowfish because its workload includes UHC, Blowfish, and Hybrid decisions. Its lower ciphertext entropy reflects the 20.57% of images routed to UHC, which makes the adaptive result an explicit security-performance trade-off rather than evidence of universal superiority.

**Figure 5** should compare encryption time, decryption time, end-to-end latency, and ciphertext entropy for the four scenarios. A multi-panel bar chart or a combined bar-and-line chart is suitable because it allows the reader to compare processing cost and ciphertext entropy without reading each table value individually.

[INSERT results/FIGURES/fig2_method_performance.png HERE]

**Figure 5.** Runtime and ciphertext-entropy comparison among UHC, Blowfish, Hybrid UHC-Blowfish, and Adaptive routing.

All methods achieved 100% decrypt-verification and infinite PSNR. Accordingly, performance differences in **Table 4** concern computational cost and ciphertext behavior rather than loss of image content after decryption.

### 3.3 Ciphertext Quality and Differential Sensitivity

Runtime results do not fully describe the diffusion behavior of encrypted payloads. The EXP-003 sample was therefore evaluated using byte-level entropy, correlation, chi-square uniformity, payload expansion, NPCR, and UACI. **Table 5** combines these indicators to compare UHC, Blowfish, and Hybrid UHC-Blowfish under the same ciphertext-analysis procedure.

**Table 5.** Ciphertext-quality and differential-analysis results (EXP-003).

| Method | Entropy | Adjacent corr. | Uniform pass (%) | Expansion | NPCR (%) | UACI (%) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| UHC | 7.5459 | 0.11920 | 20.7 | 1.000009 | 0.001 | 0.000 |
| Blowfish | 7.9999 | 0.00004 | 94.3 | 1.000015 | 99.607 | 33.470 |
| Hybrid UHC-Blowfish | 7.9999 | −0.00001 | 93.3 | 1.000017 | 99.606 | 33.467 |

The results in **Table 5** separate UHC from the two Blowfish-containing methods. Blowfish and Hybrid UHC-Blowfish approach maximum entropy, have near-zero adjacent-byte correlation, and pass the uniformity test for more than 93% of sampled payloads. They also produce NPCR and UACI values near the expected diffusion range after a one-byte image modification. In contrast, UHC has lower entropy, positive correlation, and negligible NPCR/UACI values. This indicates weak one-byte avalanche in the tested UHC implementation and provides the main empirical rationale for the hybrid design: the Blowfish layer substantially improves diffusion.

**Figure 6** should present the indicators in **Table 5** as a compact multi-panel figure. The recommended panels are entropy, adjacent-byte correlation, NPCR, and UACI. This presentation should emphasize the contrast between UHC and the Blowfish-containing routes while avoiding decorative images unrelated to the measured data.

[INSERT results/FIGURES/fig3_ciphertext_quality.png HERE]

**Figure 6.** Ciphertext entropy, adjacent-byte correlation, NPCR, and UACI across UHC, Blowfish, and Hybrid UHC-Blowfish.

Payload expansion is negligible for all tested methods, remaining close to 1.0. Therefore, the measured difference among methods is primarily cryptographic behavior and runtime, not transmission-size overhead.

### 3.4 Microservices Load Behavior

The load experiment evaluated the single-node prototype using 1, 5, 10, and 20 virtual users. **Table 6** reports throughput, p95 latency, encryption-service CPU utilization, and error rate; these indicators were selected to summarize saturation behavior without reproducing all raw latency statistics.

**Table 6.** Load-test summary of the microservices prototype (EXP-004).

| Virtual users | Throughput (req/s) | p95 latency (ms) | Encryption CPU (%) | Error rate |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 3.58 | 398 | 54.3 | 0% |
| 5 | 4.63 | 1,574 | 63.2 | 0% |
| 10 | 4.58 | 3,335 | 66.3 | 0% |
| 20 | 5.03 | 6,656 | 63.7 | 0% |

As shown in **Table 6**, throughput increases from 3.58 requests/s at one virtual user and then saturates at approximately 4.6–5.0 requests/s. In contrast, p95 latency rises sharply as concurrency increases. Encryption-service CPU utilization remains higher than that of the gateway, feature-service, and selector-service, identifying encryption as the primary bottleneck in this single-worker deployment. The zero error rate indicates that the prototype continued to accept requests under the tested load, although waiting time increased.

**Figure 7** should plot throughput and p95 latency against virtual-user level. The two metrics should use separate panels or clearly separated axes because their scales differ substantially. The intended interpretation is that the prototype saturates in throughput while its response time grows with concurrent demand.

[INSERT results/FIGURES/fig4_load_test.png HERE]

**Figure 7.** Throughput and p95 latency across virtual-user levels in the microservices load test.

Taken together, the results show that the prototype performs feature extraction, selection, encryption, verification, and logging consistently in a service-based pipeline. The selector produces distinct routing groups based mainly on entropy and GLCM contrast; Blowfish and Hybrid provide substantially stronger ciphertext diffusion than UHC; and the encryption-service is the main performance bottleneck under concurrent load. These results remain limited to a rule-derived selector and a single-node Docker Compose environment. They should not be generalized as evidence of ground-truth selector accuracy, full cryptographic proof, or horizontal scalability. Experiment artifacts, including request-linked CSV files, SQLite logs, ciphertext samples, configuration metadata, and the audit commit, were retained to support reproducibility.

## 4 Conclusion

This study implemented and evaluated AgroCipher, a containerized microservices prototype for adaptive coffee disease image encryption. The system uses entropy and GLCM features to route images to UHC, Blowfish, or Hybrid UHC-Blowfish, while separating gateway, feature extraction, selection, encryption, and logging functions. Across 2,834 coffee disease images, all 19,838 primary requests achieved lossless recovery.

The experiments showed that Blowfish had the lowest runtime and near-maximum ciphertext entropy. Hybrid UHC-Blowfish achieved comparable ciphertext quality and strong differential sensitivity but incurred the largest processing overhead. UHC alone showed weak byte-level diffusion and negligible one-byte avalanche, supporting the inclusion of Blowfish in the hybrid route. Adaptive routing exposed a measurable trade-off: it reduced average processing cost relative to always using Hybrid encryption, but its use of UHC for low-entropy images reduced aggregate ciphertext entropy. The load test further identified the encryption-service as the bottleneck, with throughput saturating around 4.6–5.0 requests/s while latency increased under concurrency.

Future work should evaluate selector decisions against empirically established ground-truth method preferences, assess key sensitivity and larger ciphertext samples, and test horizontal scaling or edge-cloud deployment scenarios.

## 5 Acknowledgements

The authors acknowledge the research grant program, institutional support, laboratory resources, and collaborators who contributed to dataset preparation, prototype implementation, and experimental activities.

## 6 Declarations

### AI Usage Statement

During the preparation of this manuscript, the author(s) used generative AI tools to support language refinement, outline preparation, and manuscript drafting assistance. The author(s) reviewed, revised, and validated the resulting content and take full responsibility for the final manuscript.

### Author Contribution

First Author: conceptualization, methodology, software, investigation, data curation, and writing—original draft.
Second Author: supervision, validation, methodology review, and writing—review and editing.
Third Author: system testing, formal-analysis support, and documentation.

> **Note:** Adjust this statement to reflect the actual contribution of every author.

### Funding Statement

This work was supported by the beginner lecturer research grant program at Universitas Jember.

> **Note:** Replace with the exact official funding number and required acknowledgement wording before submission.

### Competing Interest

The author(s) declare no competing interest.

## References

> **Placeholder:** Insert at least 25 relevant and recent references in IEEE style using Mendeley. Add citations manually throughout the manuscript after the reference list has been finalized.