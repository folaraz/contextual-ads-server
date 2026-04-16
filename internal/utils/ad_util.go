package utils

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/models"
)

const (
	DefaultTrackingBaseURL = "http://localhost:8090/api/events"
)

var (
	TrackingBaseURL = getEnvOrDefault("TRACKING_BASE_URL", DefaultTrackingBaseURL)
)

func PricingModelToString(s models.Strategy) string {
	switch s {
	case models.CPM:
		return "cpm"
	case models.CPC:
		return "cpc"
	default:
		return "unknown"
	}
}

type TrackingParams struct {
	AdID           int32
	AuctionID      string
	CampaignID     int32
	PageURLHash    string
	PublisherID    string
	PricingModel   models.Strategy
	PriceCents     int64
	DestinationURL string
	Timestamp      int64
}

func NewTrackingParams(adID int32, publisherID string, pricingModel models.Strategy, priceCents int64,
	auctionId string, campaignId int32, pageUrlHash string) TrackingParams {

	return TrackingParams{
		AdID:         adID,
		CampaignID:   campaignId,
		PageURLHash:  pageUrlHash,
		AuctionID:    auctionId,
		PublisherID:  publisherID,
		PricingModel: pricingModel,
		PriceCents:   priceCents,
		Timestamp:    time.Now().UnixMilli(),
	}
}

func GenerateAuctionID() string {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err != nil {
		return fmt.Sprintf("auc_%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(bytes)
}

func GenerateImpressionURLWithBaseURL(baseURL string, params TrackingParams) string {
	return buildTrackingURL(baseURL, "impression", params)
}

func GenerateClickURLWithBaseURL(baseURL string, params TrackingParams) string {
	return buildTrackingURL(baseURL, "click", params)
}

func TrackingBaseURLFromRequest(r *http.Request) string {
	if r == nil {
		return TrackingBaseURL
	}

	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}

	if forwardedProto := r.Header.Get("X-Forwarded-Proto"); forwardedProto != "" {
		scheme = strings.ToLower(strings.TrimSpace(strings.Split(forwardedProto, ",")[0]))
	}

	host := r.Host
	if forwardedHost := r.Header.Get("X-Forwarded-Host"); forwardedHost != "" {
		host = strings.TrimSpace(strings.Split(forwardedHost, ",")[0])
	}

	if host == "" {
		return TrackingBaseURL
	}

	return fmt.Sprintf("%s://%s/api/events", scheme, host)
}

func buildTrackingURL(baseURL, eventType string, params TrackingParams) string {
	u, _ := url.Parse(strings.TrimRight(baseURL, "/") + "/" + eventType)
	q := u.Query()

	q.Set("ad_id", strconv.Itoa(int(params.AdID)))
	q.Set("campaign_id", strconv.Itoa(int(params.CampaignID)))
	q.Set("page_url_hash", params.PageURLHash)
	q.Set("pub_id", params.PublisherID)
	q.Set("ts", strconv.FormatInt(params.Timestamp, 10))
	q.Set("nonce", generateNonce(12))

	if eventType == "click" && params.DestinationURL != "" {
		q.Set("dest", params.DestinationURL)
	}

	q.Set("auction_id", params.AuctionID)
	q.Set("price", strconv.FormatInt(params.PriceCents, 10))

	q.Set("sig", GenerateHMACSignature(q.Encode()))
	u.RawQuery = q.Encode()
	return u.String()
}

func generateNonce(length int) string {
	bytes := make([]byte, length)
	rand.Read(bytes)
	return hex.EncodeToString(bytes)
}

func GenerateHMACSignature(payload string) string {
	secret := os.Getenv("SECRET_KEY")
	if secret == "" {
		secret = "default-secret-key"
	}
	h := hmac.New(sha256.New, []byte(secret))
	h.Write([]byte(payload))
	return hex.EncodeToString(h.Sum(nil))
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
