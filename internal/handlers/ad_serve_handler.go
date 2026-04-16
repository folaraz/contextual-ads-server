package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/models/request"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	"github.com/folaraz/contextual-ads-server/internal/utils"
)

type AdServeHandler struct {
	service *ads.AdServeService
}

func NewAdServeHandler(service *ads.AdServeService) *AdServeHandler {
	return &AdServeHandler{
		service: service,
	}
}

type AdResponse struct {
	AdID          int32  `json:"ad_id"`
	AuctionID     string `json:"auction_id,omitempty"`
	PublisherID   string `json:"publisher_id"`
	MediaURL      string `json:"media_url,omitempty"`
	Headline      string `json:"headline,omitempty"`
	Description   string `json:"description,omitempty"`
	ClickURL      string `json:"click_url"`
	ImpressionURL string `json:"impression_url"`
	PricingModel  string `json:"pricing_model"`
	PriceCents    int64  `json:"price_cents"`
}

func (h *AdServeHandler) ServeAd(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	ctx, span := observability.StartSpan(ctx, "AdServeHandler.ServeAd")
	defer span.End()
	start := time.Now()

	observability.Info(ctx, "Ad serve request received",
		"method", r.Method,
		"remote_addr", r.RemoteAddr,
	)

	var adServeRequest request.AdServeRequest
	if err := json.NewDecoder(r.Body).Decode(&adServeRequest); err != nil {
		observability.RecordSpanError(ctx, err)
		observability.Warn(ctx, "Ad serve request decode failed", "error", err.Error())
		http.Error(w, fmt.Sprintf("Invalid request payload: %v", err), http.StatusBadRequest)
		return
	}

	observability.AddSpanAttributes(ctx,
		observability.StringAttr("publisher_id", adServeRequest.PublisherID),
		observability.StringAttr("page_url", adServeRequest.Context.URL),
	)

	observability.Info(ctx, "Ad serve request decoded",
		"publisher_id", adServeRequest.PublisherID,
		"page_url", adServeRequest.Context.URL,
	)

	requestContext := contextextractor.RetrieveRequestContext(r)
	auctionResult := h.service.GetAdAuctionResult(ctx, adServeRequest, requestContext)

	duration := time.Since(start)
	candidateCount := auctionResult.LengthOfCandidates()
	pageURL := adServeRequest.Context.URL

	if !auctionResult.HasWinner {
		observability.RecordAdServe(ctx, adServeRequest.PublisherID, false,
			candidateCount, 0, "", duration)
		observability.LogAdServeRequest(ctx, adServeRequest.PublisherID,
			pageURL, candidateCount, false, duration.Milliseconds())

		observability.Info(ctx, "Ad serve no-fill",
			"publisher_id", adServeRequest.PublisherID,
			"page_url", pageURL,
			"candidate_count", candidateCount,
			"duration_ms", duration.Milliseconds(),
		)

		w.WriteHeader(http.StatusNoContent)
		return
	}

	adResponse := h.buildAdResponse(r, auctionResult, adServeRequest.PublisherID)

	pricingModel := ""
	if auctionResult.Winner != nil {
		pricingModel = utils.PricingModelToString(auctionResult.Winner.Ad.PricingModel)
	}
	observability.RecordAdServe(ctx, adServeRequest.PublisherID, true, candidateCount, adResponse.PriceCents, pricingModel, duration)
	observability.LogAdServeRequest(ctx, adServeRequest.PublisherID, pageURL, candidateCount, true, duration.Milliseconds())

	observability.Info(ctx, "Ad serve fill",
		"publisher_id", adServeRequest.PublisherID,
		"page_url", pageURL,
		"ad_id", adResponse.AdID,
		"auction_id", adResponse.AuctionID,
		"pricing_model", adResponse.PricingModel,
		"price_cents", adResponse.PriceCents,
		"impression_url", adResponse.ImpressionURL,
		"click_url", adResponse.ClickURL,
		"candidate_count", candidateCount,
		"duration_ms", duration.Milliseconds(),
	)

	envelope := map[string]interface{}{
		"success": true,
		"data":    adResponse,
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(envelope); err != nil {
		observability.Error(ctx, "Failed to encode ad serve response", "error", err.Error())
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
	}
}

func (h *AdServeHandler) buildAdResponse(r *http.Request, result models.AuctionResult, publisherID string) AdResponse {
	ctx := r.Context()

	if result.Winner == nil {
		observability.Debug(ctx, "buildAdResponse called with nil winner")
		return AdResponse{}
	}

	winner := result.Winner
	ad := winner.Ad
	priceCents := int64(result.PricePaid * 100)
	auctionId := result.AuctionID

	params := utils.NewTrackingParams(ad.AdID, publisherID, ad.PricingModel, priceCents, auctionId, ad.CampaignID, result.PageHash)
	params.DestinationURL = ad.DestinationURL
	trackingBaseURL := utils.TrackingBaseURLFromRequest(r)

	observability.Debug(ctx, "Building tracking URLs",
		"tracking_base_url", trackingBaseURL,
		"ad_id", ad.AdID,
		"auction_id", auctionId,
		"pricing_model", utils.PricingModelToString(ad.PricingModel),
		"destination_url", ad.DestinationURL,
	)

	var clickURL string
	if ad.DestinationURL != "" && ad.PricingModel != models.CPM {
		clickURL = utils.GenerateClickURLWithBaseURL(trackingBaseURL, params)
	} else {
		clickURL = ""
		observability.Debug(ctx, "Click URL not generated",
			"ad_id", ad.AdID,
			"has_destination_url", ad.DestinationURL != "",
			"pricing_model", utils.PricingModelToString(ad.PricingModel),
		)
	}

	impressionURL := utils.GenerateImpressionURLWithBaseURL(trackingBaseURL, params)

	observability.Debug(ctx, "Tracking URLs generated",
		"ad_id", ad.AdID,
		"impression_url", impressionURL,
		"click_url", clickURL,
	)

	return AdResponse{
		AdID:          ad.AdID,
		AuctionID:     auctionId,
		PublisherID:   publisherID,
		MediaURL:      ad.MediaURL,
		Headline:      ad.Headline,
		Description:   ad.Description,
		ClickURL:      clickURL,
		ImpressionURL: impressionURL,
		PricingModel:  utils.PricingModelToString(ad.PricingModel),
		PriceCents:    priceCents,
	}
}
