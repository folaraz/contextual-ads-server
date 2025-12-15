package utils

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"time"
)

var BaseClickUrl = "http://localhost:8080/click"

func GenerateSignedImpressionURL(adId string, pubId string) string {
	timestamp := strconv.FormatInt(time.Now().Unix(), 10)
	params := url.Values{}
	params.Add("adId", adId)
	params.Add("pubId", pubId)
	params.Add("nonce", generateNonce(24))
	params.Add("ts", timestamp)

	payload := params.Encode()

	signature := generateHMACSignature(payload)

	params.Add("sig", signature)

	signedURL := fmt.Sprintf("%s?%s", BaseClickUrl, params.Encode())
	return signedURL
}
func GenerateSignedClickURL(adId string, bidAmount float64, pubId string) string {

	timestamp := strconv.FormatInt(time.Now().Unix(), 10)
	params := url.Values{}
	params.Add("adId", adId)
	params.Add("bid", fmt.Sprintf("%.5f", bidAmount))
	params.Add("pubId", pubId)
	params.Add("nonce", generateNonce(24))
	params.Add("ts", timestamp)

	payload := params.Encode()

	signature := generateHMACSignature(payload)

	params.Add("sig", signature)

	signedURL := fmt.Sprintf("%s?%s", BaseClickUrl, params.Encode())
	return signedURL
}

func generateNonce(length int) string {
	bytes := make([]byte, length)
	rand.Read(bytes)
	return hex.EncodeToString(bytes)
}

func generateHMACSignature(payload string) string {
	h := hmac.New(sha256.New, []byte(os.Getenv("SECRET_KEY")))
	h.Write([]byte(payload))
	return hex.EncodeToString(h.Sum(nil))
}
