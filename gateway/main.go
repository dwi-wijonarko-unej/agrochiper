package main

import (
	"bytes"
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"strings"
)

type FeatureResponse struct {
	Entropy         float64 `json:"entropy"`
	SizeKB          float64 `json:"size_kb"`
	GLCMCorrelation float64 `json:"glcm_correlation"`
	GLCMContrast    float64 `json:"glcm_contrast"`
}

type SelectorRequest struct {
	Entropy         float64 `json:"entropy"`
	SizeKB          float64 `json:"size_kb"`
	GLCMCorrelation float64 `json:"glcm_correlation"`
	GLCMContrast    float64 `json:"glcm_contrast"`
}

type SelectorResponse struct {
	DecisionCode      int    `json:"decision_code"`
	RecommendedCipher string `json:"recommended_cipher"`
	Reasoning         string `json:"reasoning"`
}

type EncryptResponse struct {
	Method         string  `json:"method"`
	EncryptionTime float64 `json:"encryption_time"`
	DecryptionTime float64 `json:"decryption_time"`
	CipherEntropy  float64 `json:"cipher_entropy"`
	PSNR           string  `json:"psnr"`
	OutputFilename string  `json:"output_filename"`
	CipherBase64   string  `json:"cipher_base64"`
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
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	featureURL := os.Getenv("FEATURE_SERVICE_URL") + "/extractor/v1/analyze"
	selectorURL := os.Getenv("SELECTOR_SERVICE_URL") + "/selector/v1/predict"
	encryptionURL := os.Getenv("ENCRYPTION_SERVICE_URL") + "/encryption/v1/process"

	file, header, err := r.FormFile("file")
	if err != nil {
		http.Error(w, "file is required", http.StatusBadRequest)
		return
	}
	defer file.Close()

	fileBytes, err := io.ReadAll(file)
	if err != nil {
		http.Error(w, "failed to read file", http.StatusInternalServerError)
		return
	}

	// Call Feature Extractor Service
	respFeature, err := postMultipart(featureURL, "file", header.Filename, fileBytes, nil)
	if err != nil {
		http.Error(w, "failed to call feature service: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer respFeature.Body.Close()

	var features FeatureResponse
	if err := json.NewDecoder(respFeature.Body).Decode(&features); err != nil {
		http.Error(w, "invalid feature response", http.StatusBadGateway)
		return
	}

	// Call AI Selector Service
	selectorReq := SelectorRequest(features)
	selectorBody, _ := json.Marshal(selectorReq)

	respSelector, err := http.Post(selectorURL, "application/json", bytes.NewBuffer(selectorBody))
	if err != nil {
		http.Error(w, "failed to call selector service: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer respSelector.Body.Close()

	var selectorResp SelectorResponse
	if err := json.NewDecoder(respSelector.Body).Decode(&selectorResp); err != nil {
		http.Error(w, "invalid selector response", http.StatusBadGateway)
		return
	}

	// Call Encryption Service
	extra := map[string]string{"cipher_mode": selectorResp.RecommendedCipher}
	respEncrypt, err := postMultipart(encryptionURL, "file", header.Filename, fileBytes, extra)
	if err != nil {
		http.Error(w, "failed to call encryption service: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer respEncrypt.Body.Close()

	var encryptResp EncryptResponse
	if err := json.NewDecoder(respEncrypt.Body).Decode(&encryptResp); err != nil {
		http.Error(w, "invalid encryption response", http.StatusBadGateway)
		return
	}

	result := map[string]interface{}{
		"file":     header.Filename,
		"features": features,
		"selector": selectorResp,
		"result":   encryptResp,
	}

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
		// TrimSpace guards against env files with CRLF line endings or
		// trailing whitespace, a common cause of silent key mismatches.
		serverKey := strings.TrimSpace(os.Getenv("GATEWAY_API_KEY"))
		if serverKey == "" {
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
			writeJSONError(w, http.StatusUnauthorized, "invalid or missing API key")
			return
		}

		next(w, r)
	}
}

func main() {
	if os.Getenv("GATEWAY_API_KEY") == "" {
		fmt.Println("WARNING: GATEWAY_API_KEY is not set; API requests will be rejected")
	}
	http.HandleFunc("/api/v1/encrypt-image", requireAPIKey(encryptHandler))
	http.HandleFunc("/health", healthHandler)
	fmt.Println("Gateway listening on :8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Println("Gateway error:", err)
	}
}
