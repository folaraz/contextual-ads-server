package handlers

import (
	"errors"
	"fmt"
	"net/http"
	"strconv"

	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	goredis "github.com/redis/go-redis/v9"
)

type EventHandler struct {
	service *ads.AdEventService
}

func NewEventHandler(redisClient *goredis.Client) *EventHandler {
	return &EventHandler{
		service: ads.NewAdEventService(redisClient),
	}
}

func (h *EventHandler) HandleImpression(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	params := r.URL.Query()

	observability.Info(ctx, "Impression event received",
		"method", r.Method,
		"remote_addr", r.RemoteAddr,
		"query", r.URL.RawQuery,
	)

	adIDStr := params.Get("ad_id")
	if adIDStr == "" {
		observability.Warn(ctx, "Impression event missing ad_id parameter")
		http.Error(w, "Missing required parameter: ad_id", http.StatusBadRequest)
		return
	}

	adID, err := strconv.ParseInt(adIDStr, 10, 32)
	if err != nil {
		observability.Warn(ctx, "Impression event invalid ad_id", "ad_id", adIDStr, "error", err)
		http.Error(w, "Invalid ad_id", http.StatusBadRequest)
		return
	}

	reqCtx := contextextractor.RetrieveRequestContext(r)

	eventData := ads.EventData{
		AdID:        adIDStr,
		PublisherID: params.Get("pub_id"),
		PageURLHash: params.Get("page_url_hash"),
		AuctionID:   params.Get("auction_id"),
		CampaignID:  params.Get("campaign_id"),
		PriceCents:  parseInt(params.Get("price")),
		DeviceType:  reqCtx.Device.Device,
		UserAgent:   r.UserAgent(),
		IPAddress:   reqCtx.IP,
	}

	observability.Info(ctx, "Processing impression event",
		"ad_id", adID,
		"publisher_id", eventData.PublisherID,
		"auction_id", eventData.AuctionID,
		"campaign_id", eventData.CampaignID,
		"price_cents", eventData.PriceCents,
		"device_type", eventData.DeviceType,
		"ip_address", eventData.IPAddress,
	)

	if err := h.service.ProcessImpression(ctx, params, eventData); err != nil {
		observability.Warn(ctx, "Impression processing failed",
			"ad_id", adID,
			"publisher_id", eventData.PublisherID,
			"auction_id", eventData.AuctionID,
			"error", err,
		)
		http.Error(w, "Failed to process impression event", eventStatusCode(err))
		return
	}

	observability.Info(ctx, "Impression event processed successfully",
		"ad_id", adID,
		"publisher_id", eventData.PublisherID,
		"auction_id", eventData.AuctionID,
	)

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-cache, no-store, must-revalidate")
	w.WriteHeader(http.StatusOK)
}

func (h *EventHandler) HandleClick(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	params := r.URL.Query()

	observability.Info(ctx, "Click event received",
		"method", r.Method,
		"remote_addr", r.RemoteAddr,
		"query", r.URL.RawQuery,
	)

	adIDStr := params.Get("ad_id")
	if adIDStr == "" {
		observability.Warn(ctx, "Click event missing ad_id parameter")
		http.Error(w, "Missing required parameter: ad_id", http.StatusBadRequest)
		return
	}

	adID, err := strconv.ParseInt(adIDStr, 10, 32)
	if err != nil {
		observability.Warn(ctx, "Click event invalid ad_id", "ad_id", adIDStr, "error", err)
		http.Error(w, "Invalid ad_id", http.StatusBadRequest)
		return
	}

	destURL := params.Get("dest")
	if destURL == "" {
		observability.Warn(ctx, "Click event missing dest parameter", "ad_id", adID)
		http.Error(w, "Missing required parameter: dest", http.StatusBadRequest)
		return
	}

	reqCtx := contextextractor.RetrieveRequestContext(r)

	eventData := ads.EventData{
		AdID:        fmt.Sprintf("%d", adID),
		PublisherID: params.Get("pub_id"),
		PageURLHash: params.Get("page_url_hash"),
		DestURL:     destURL,
		AuctionID:   params.Get("auction_id"),
		CampaignID:  params.Get("campaign_id"),
		PriceCents:  parseInt(params.Get("price")),
		DeviceType:  reqCtx.Device.Device,
		UserAgent:   r.UserAgent(),
		IPAddress:   reqCtx.IP,
	}

	observability.Info(ctx, "Processing click event",
		"ad_id", adID,
		"publisher_id", eventData.PublisherID,
		"auction_id", eventData.AuctionID,
		"campaign_id", eventData.CampaignID,
		"price_cents", eventData.PriceCents,
		"dest_url", destURL,
		"device_type", eventData.DeviceType,
		"ip_address", eventData.IPAddress,
	)

	if err := h.service.ProcessClick(ctx, params, eventData); err != nil {
		observability.Warn(ctx, "Click processing failed",
			"ad_id", adID,
			"publisher_id", eventData.PublisherID,
			"auction_id", eventData.AuctionID,
			"error", err,
		)
		http.Error(w, "Failed to process click event", eventStatusCode(err))
		return
	}

	observability.Info(ctx, "Click event processed successfully, redirecting",
		"ad_id", adID,
		"publisher_id", eventData.PublisherID,
		"auction_id", eventData.AuctionID,
		"dest_url", destURL,
	)

	http.Redirect(w, r, destURL, http.StatusFound)
}

func eventStatusCode(err error) int {
	switch {
	case errors.Is(err, ads.ErrInvalidEventSignature), errors.Is(err, ads.ErrMissingEventNonce):
		return http.StatusBadRequest
	default:
		return http.StatusInternalServerError
	}
}

func parseInt(s string) int64 {
	if s == "" {
		return 0
	}
	val, _ := strconv.ParseInt(s, 10, 64)
	return val
}
