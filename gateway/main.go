package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"strings"
	"time"
)

type ctxKey string

const requestIDKey ctxKey = "request_id"

type FeatureResponse struct {
	Entropy                 float64 `json:"entropy"`
	SizeKB                  float64 `json:"size_kb"`
	GLCMCorrelation         float64 `json:"glcm_correlation"`
	GLCMContrast            float64 `json:"glcm_contrast"`
	RequestID               string  `json:"request_id"`
	ImageWidth              int     `json:"image_width"`
	ImageHeight             int     `json:"image_height"`
	FileExtension           string  `json:"file_extension"`
	FeatureExtractionTimeMs float64 `json:"feature_extraction_time_ms"`
}

type SelectorRequest struct {
	Entropy         float64 `json:"entropy"`
	SizeKB          float64 `json:"size_kb"`
	GLCMCorrelation float64 `json:"glcm_correlation"`
	GLCMContrast    float64 `json:"glcm_contrast"`
	RequestID       string  `json:"request_id"`
}

type SelectorResponse struct {
	DecisionCode            int     `json:"decision_code"`
	RecommendedCipher       string  `json:"recommended_cipher"`
	Reasoning               string  `json:"reasoning"`
	RequestID               string  `json:"request_id"`
	SelectorInferenceTimeMs float64 `json:"selector_inference_time_ms"`
	ModelVersion            string  `json:"model_version"`
	ModelFeaturesUsed       string  `json:"model_features_used"`
}

type EncryptResponse struct {
	Method                    string  `json:"method"`
	EncryptionTime            float64 `json:"encryption_time"`
	DecryptionTime            float64 `json:"decryption_time"`
	CipherEntropy             float64 `json:"cipher_entropy"`
	PSNR                      string  `json:"psnr"`
	OutputFilename            string  `json:"output_filename"`
	CipherBase64              string  `json:"cipher_base64"`
	RequestID                 string  `json:"request_id"`
	EncryptionTimeMs          float64 `json:"encryption_time_ms"`
	DecryptionTimeMs          float64 `json:"decryption_time_ms"`
	PSNRIsInfinite            bool    `json:"psnr_is_infinite"`
	DecryptVerified           bool    `json:"decrypt_verified"`
	EncryptedPayloadSizeBytes int     `json:"encrypted_payload_size_bytes"`
	OriginalPayloadSizeBytes  int     `json:"original_payload_size_bytes"`
}

// gatewayLogEntry is the JSONL row for gateway experiment logging. Written to
// GATEWAY_EXPERIMENT_LOG (fail-open; logging never blocks the request).
type gatewayLogEntry struct {
	RequestID           string  `json:"request_id"`
	Filename            string  `json:"filename"`
	Method              string  `json:"method"`
	TimestampUTC        string  `json:"timestamp_utc"`
	GatewayStartTimeUTC string  `json:"gateway_start_time_utc"`
	GatewayEndTimeUTC   string  `json:"gateway_end_time_utc"`
	EndToEndLatencyMs   float64 `json:"end_to_end_latency_ms"`
	HTTPSStatus         int     `json:"http_status"`
	ErrorType           string  `json:"error_type"`
	FeatureServiceMs    float64 `json:"feature_service_ms"`
	SelectorServiceMs   float64 `json:"selector_service_ms"`
	EncryptionServiceMs float64 `json:"encryption_service_ms"`
	EffectiveMethod     string  `json:"effective_method"`
	ForcedMethod        string  `json:"experiment_forced_method,omitempty"`
}

func genRequestID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("gateway-%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b)
}

func nowUTC() string { return time.Now().UTC().Format(time.RFC3339Nano) }

func logGatewayEntry(entry gatewayLogEntry) {
	path := os.Getenv("GATEWAY_EXPERIMENT_LOG")
	if path == "" {
		return
	}
	line, err := json.Marshal(entry)
	if err != nil {
		return
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	f.Write(append(line, '\n'))
}

func writeGatewayLog(rid, filename string, start time.Time, fMs float64,
	status int, errType, effectiveMethod string, sMs, eMs float64, forcedMethod string) {
	logGatewayEntry(gatewayLogEntry{
		RequestID:           rid,
		Filename:            filename,
		Method:              "POST /api/v1/encrypt-image",
		TimestampUTC:        nowUTC(),
		GatewayStartTimeUTC: start.UTC().Format(time.RFC3339Nano),
		GatewayEndTimeUTC:   nowUTC(),
		EndToEndLatencyMs:   float64(time.Since(start).Milliseconds()),
		HTTPSStatus:         status,
		ErrorType:           errType,
		FeatureServiceMs:    fMs,
		SelectorServiceMs:   sMs,
		EncryptionServiceMs: eMs,
		EffectiveMethod:     effectiveMethod,
		ForcedMethod:        forcedMethod,
	})
}

func requestIDFrom(r *http.Request) string {
	if v, ok := r.Context().Value(requestIDKey).(string); ok {
		return v
	}
	return genRequestID()
}

func postMultipart(url string, fieldName, fileName string, fileBytes []byte, extra map[string]string) (*http.Response, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	part, err := writer.CreateFormFile(fieldName, fileName)
	if err != nil {
		return nil, err
	}
	if _, err = part.Write(fileBytes); err != nil {
		return nil, err
	}

	for k, v := range extra {
		_ = writer.WriteField(k, v)
	}

	if err = writer.Close(); err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", url, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	client := &http.Client{}
	return client.Do(req)
}

func encryptHandler(w http.ResponseWriter, r *http.Request) {
	rid := requestIDFrom(r)
	start := time.Now()
	filename := ""

	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		writeGatewayLog(rid, "", start, 0, http.StatusBadRequest, "file_required", "", 0, 0, "")
		http.Error(w, "file is required", http.StatusBadRequest)
		return
	}
	defer file.Close()
	filename = header.Filename

	fileBytes, err := io.ReadAll(file)
	if err != nil {
		writeGatewayLog(rid, filename, start, 0, http.StatusInternalServerError, "read_file_failed", "", 0, 0, "")
		http.Error(w, "failed to read file", http.StatusInternalServerError)
		return
	}

	featureURL := os.Getenv("FEATURE_SERVICE_URL") + "/extractor/v1/analyze"
	selectorURL := os.Getenv("SELECTOR_SERVICE_URL") + "/selector/v1/predict"
	encryptionURL := os.Getenv("ENCRYPTION_SERVICE_URL") + "/encryption/v1/process"

	// Call Feature Extractor Service
	fStart := time.Now()
	respFeature, err := postMultipart(featureURL, "file", header.Filename, fileBytes,
		map[string]string{"request_id": rid})
	fMs := float64(time.Since(fStart).Milliseconds())
	if err != nil {
		writeGatewayLog(rid, filename, start, fMs, http.StatusBadGateway, "feature_service_call_failed", "", 0, 0, "")
		http.Error(w, "failed to call feature service: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer respFeature.Body.Close()

	var features FeatureResponse
	if err := json.NewDecoder(respFeature.Body).Decode(&features); err != nil {
		writeGatewayLog(rid, filename, start, fMs, http.StatusBadGateway, "invalid_feature_response", "", 0, 0, "")
		http.Error(w, "invalid feature response", http.StatusBadGateway)
		return
	}

	// Call AI Selector Service
	selectorReq := SelectorRequest{
		Entropy:         features.Entropy,
		SizeKB:          features.SizeKB,
		GLCMCorrelation: features.GLCMCorrelation,
		GLCMContrast:    features.GLCMContrast,
		RequestID:       rid,
	}
	selectorBody, _ := json.Marshal(selectorReq)

	sStart := time.Now()
	respSelector, err := http.Post(selectorURL, "application/json", bytes.NewBuffer(selectorBody))
	sMs := float64(time.Since(sStart).Milliseconds())
	if err != nil {
		writeGatewayLog(rid, filename, start, fMs, http.StatusBadGateway, "selector_service_call_failed", "", sMs, 0, "")
		http.Error(w, "failed to call selector service: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer respSelector.Body.Close()

	var selectorResp SelectorResponse
	if err := json.NewDecoder(respSelector.Body).Decode(&selectorResp); err != nil {
		writeGatewayLog(rid, filename, start, fMs, http.StatusBadGateway, "invalid_selector_response", "", sMs, 0, "")
		http.Error(w, "invalid selector response", http.StatusBadGateway)
		return
	}

	// Effective cipher: default = AI Selector decision. Experiment override is
	// only honored when EXPERIMENT_MODE=true (never on production).
	effectiveMethod := selectorResp.RecommendedCipher
	forcedMethod := ""
	if os.Getenv("EXPERIMENT_MODE") == "true" {
		if h := strings.TrimSpace(r.Header.Get("X-Experiment-Force-Method")); h != "" {
			switch h {
			case "UHC", "Blowfish", "Hybrid UHC-Blowfish":
				effectiveMethod = h
				forcedMethod = h
			default: // "adaptive" or invalid -> AI Selector
				forcedMethod = "adaptive"
			}
		}
	}

	// Call Encryption Service
	eStart := time.Now()
	extra := map[string]string{
		"cipher_mode": effectiveMethod,
		"request_id":  rid,
	}
	respEncrypt, err := postMultipart(encryptionURL, "file", header.Filename, fileBytes, extra)
	eMs := float64(time.Since(eStart).Milliseconds())
	if err != nil {
		writeGatewayLog(rid, filename, start, fMs, http.StatusBadGateway, "encryption_service_call_failed", effectiveMethod, sMs, eMs, forcedMethod)
		http.Error(w, "failed to call encryption service: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer respEncrypt.Body.Close()

	var encryptResp EncryptResponse
	if err := json.NewDecoder(respEncrypt.Body).Decode(&encryptResp); err != nil {
		writeGatewayLog(rid, filename, start, fMs, http.StatusBadGateway, "invalid_encryption_response", effectiveMethod, sMs, eMs, forcedMethod)
		http.Error(w, "invalid encryption response", http.StatusBadGateway)
		return
	}

	result := map[string]interface{}{
		"file":     header.Filename,
		"features": features,
		"selector": selectorResp,
		"result":   encryptResp,
		"request_id":              rid,
		"end_to_end_latency_ms":   float64(time.Since(start).Milliseconds()),
		"gateway_start_time_utc":  start.UTC().Format(time.RFC3339Nano),
		"gateway_end_time_utc":    time.Now().UTC().Format(time.RFC3339Nano),
		"feature_service_ms":      fMs,
		"selector_service_ms":     sMs,
		"encryption_service_ms":   eMs,
		"experiment_forced_method": forcedMethod,
	}

	writeGatewayLog(rid, filename, start, fMs, http.StatusOK, "", effectiveMethod, sMs, eMs, forcedMethod)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"status":"ok","service":"gateway"}`)
}

// writeJSONError writes a JSON error response with the given status code.
func writeJSONError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	fmt.Fprintf(w, `{"error":%q}`, msg)
}

// requireAPIKey is middleware that validates the client API key.
// The key is read from the GATEWAY_API_KEY environment variable.
// Clients may send it via the "X-API-Key" header or as a Bearer token
// in the "Authorization" header. If the server key is not configured,
// all requests are rejected (fail-closed).
func requireAPIKey(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		rid := genRequestID()
		r = r.WithContext(context.WithValue(r.Context(), requestIDKey, rid))

		// TrimSpace guards against env files with CRLF line endings or
		// trailing whitespace, a common cause of silent key mismatches.
		serverKey := strings.TrimSpace(os.Getenv("GATEWAY_API_KEY"))
		if serverKey == "" {
			writeGatewayLog(rid, "", time.Now(), 0, http.StatusServiceUnavailable, "api_key_not_configured", "", 0, 0, "")
			writeJSONError(w, http.StatusServiceUnavailable, "API key not configured on server")
			return
		}

		provided := strings.TrimSpace(r.Header.Get("X-API-Key"))
		if provided == "" {
			if auth := strings.TrimSpace(r.Header.Get("Authorization")); strings.HasPrefix(auth, "Bearer ") {
				provided = strings.TrimSpace(strings.TrimPrefix(auth, "Bearer "))
			}
		}

		if subtle.ConstantTimeCompare([]byte(provided), []byte(serverKey)) != 1 {
			writeGatewayLog(rid, "", time.Now(), 0, http.StatusUnauthorized, "auth_failed", "", 0, 0, "")
			writeJSONError(w, http.StatusUnauthorized, "invalid or missing API key")
			return
		}

		next(w, r)
	}
}

func logsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	if r.Method == http.MethodOptions {
		w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "*")
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != http.MethodGet {
		writeJSONError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	logsURL := os.Getenv("ENCRYPTION_SERVICE_URL") + "/encryption/v1/logs"
	resp, err := http.Get(logsURL)
	if err != nil {
		writeJSONError(w, http.StatusBadGateway, "failed to fetch logs: "+err.Error())
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func main() {
	if os.Getenv("GATEWAY_API_KEY") == "" {
		fmt.Println("WARNING: GATEWAY_API_KEY is not set; API requests will be rejected")
	}
	http.HandleFunc("/api/v1/encrypt-image", requireAPIKey(encryptHandler))
	http.HandleFunc("/api/v1/logs", logsHandler)
	http.HandleFunc("/health", healthHandler)
	fmt.Println("Gateway listening on :8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Println("Gateway error:", err)
	}
}