package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/service/campaigns"
)

type CampaignHandler struct {
	service *campaigns.CampaignService
}

func NewCampaignHandler(svc *campaigns.CampaignService) *CampaignHandler {
	return &CampaignHandler{service: svc}
}

type CampaignInput struct {
	Name      string  `json:"name" validate:"required,min=1"`
	Status    string  `json:"status,omitempty" validate:"omitempty,oneof=ACTIVE PAUSED COMPLETED active paused completed"`
	Budget    float64 `json:"budget" validate:"gte=0"`
	Currency  string  `json:"currency" validate:"omitempty,len=3"`
	StartDate string  `json:"start_date" validate:"required"`
	EndDate   string  `json:"end_date,omitempty"`
}

type AdSetInput struct {
	Name         string  `json:"name,omitempty"`
	BidAmount    float64 `json:"bid_amount" validate:"gte=0"`
	DailyBudget  float64 `json:"daily_budget" validate:"gte=0"`
	PricingModel string  `json:"pricing_model" validate:"required,oneof=CPC CPM cpc cpm"`
}

type CreativeInput struct {
	Headline       string `json:"headline" validate:"required,min=1"`
	Description    string `json:"description"`
	ImageURL       string `json:"image_url" validate:"omitempty,url"`
	CallToAction   string `json:"call_to_action,omitempty"`
	LandingPageURL string `json:"landing_page_url" validate:"required,url"`
	Status         string `json:"status,omitempty" validate:"omitempty,oneof=ACTIVE PAUSED ARCHIVED PENDING_ANALYSIS active paused archived pending_analysis"`
	CreativeType   string `json:"creative_type,omitempty" validate:"omitempty,oneof=banner"`
}

type EntityInput struct {
	Type string `json:"type" validate:"required,oneof=brand person organization product BRAND PERSON ORGANIZATION PRODUCT"`
	Name string `json:"name" validate:"required,min=1"`
}

type TargetingInput struct {
	Keywords  []string      `json:"keywords,omitempty"`
	Topics    []int32       `json:"topics,omitempty" validate:"omitempty,dive,gt=0"`
	Entities  []EntityInput `json:"entities,omitempty" validate:"omitempty,dive"`
	Countries []string      `json:"countries,omitempty"`
	Devices   []string      `json:"devices,omitempty" validate:"omitempty,dive,oneof=mobile desktop tablet"`
}

type CreateCampaignHTTPRequest struct {
	AdvertiserID int32          `json:"advertiser_id" validate:"required"`
	Campaign     CampaignInput  `json:"campaign" validate:"required"`
	AdSet        AdSetInput     `json:"ad_set,omitempty"`
	Creative     CreativeInput  `json:"creative" validate:"required"`
	Targeting    TargetingInput `json:"targeting"`
}

type CreateCampaignResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Data    struct {
		CampaignID int32 `json:"campaign_id"`
		AdSetID    int32 `json:"ad_set_id"`
		AdID       int32 `json:"ad_id"`
	} `json:"data"`
}

func (h *CampaignHandler) CreateCampaign(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var req CreateCampaignHTTPRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, http.StatusBadRequest, "Invalid JSON payload", err)
		return
	}

	serviceReq, validationErrors := h.convertToServiceRequest(req)
	if len(validationErrors) > 0 {
		payloadJSON, _ := json.Marshal(req)
		observability.Warn(ctx, "Campaign creation validation failed",
			"advertiser_id", req.AdvertiserID,
			"campaign_name", req.Campaign.Name,
			"validation_errors", validationErrors,
			"payload", string(payloadJSON),
		)
		writeValidationErrors(w, validationErrors)
		return
	}

	result, err := h.service.CreateCampaignWithDependencies(ctx, *serviceReq)
	if err != nil {
		payloadJSON, _ := json.Marshal(req)
		observability.Error(ctx, "Failed to create campaign",
			"error", err,
			"advertiser_id", req.AdvertiserID,
			"campaign_name", req.Campaign.Name,
			"payload", string(payloadJSON),
		)
		writeJSONError(w, http.StatusInternalServerError, "Failed to create campaign", err)
		return
	}

	response := CreateCampaignResponse{
		Success: true,
		Message: "Campaign created successfully",
	}
	response.Data.CampaignID = result.Campaign.ID
	response.Data.AdSetID = result.AdSet.ID
	response.Data.AdID = result.Ad.ID

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(response)
}

func (h *CampaignHandler) convertToServiceRequest(req CreateCampaignHTTPRequest) (*campaigns.CreateCampaignRequest,
	[]ValidationError) {
	errors := ValidateStruct(req)

	startDate, err := time.Parse("2006-01-02", req.Campaign.StartDate)
	if err != nil && req.Campaign.StartDate != "" {
		errors = append(errors, ValidationError{
			Field:   "campaign.start_date",
			Message: "Invalid start date format, use YYYY-MM-DD",
		})
	}

	var endDate *time.Time
	if req.Campaign.EndDate != "" {
		ed, err := time.Parse("2006-01-02", req.Campaign.EndDate)
		if err != nil {
			errors = append(errors, ValidationError{
				Field:   "campaign.end_date",
				Message: "Invalid end date format, use YYYY-MM-DD",
			})
		} else {
			endDate = &ed
		}
	}

	if len(errors) > 0 {
		return nil, errors
	}

	pricingModel := strings.ToUpper(req.AdSet.PricingModel)

	serviceReq := &campaigns.CreateCampaignRequest{
		AdvertiserID: req.AdvertiserID,
		Campaign: campaigns.CampaignInput{
			Name:             req.Campaign.Name,
			Status:           strings.ToUpper(req.Campaign.Status),
			TotalBudgetCents: int64(req.Campaign.Budget * 100), // Convert to cents
			StartDate:        startDate,
			EndDate:          endDate,
		},
		AdSet: campaigns.AdSetInput{
			Name:             req.AdSet.Name,
			BidAmountCents:   int64(req.AdSet.BidAmount * 100),   // Convert to cents
			DailyBudgetCents: int64(req.AdSet.DailyBudget * 100), // Convert to cents
			PricingModel:     pricingModel,
		},
		Ad: campaigns.AdInput{
			Headline:       req.Creative.Headline,
			Description:    req.Creative.Description,
			CreativeType:   req.Creative.CreativeType,
			MediaURL:       req.Creative.ImageURL,
			DestinationURL: req.Creative.LandingPageURL,
			Status:         req.Creative.Status,
		},
		TargetingKeywords:  req.Targeting.Keywords,
		TargetingCountries: req.Targeting.Countries,
		TargetingDevices:   req.Targeting.Devices,
	}

	for _, topicID := range req.Targeting.Topics {
		serviceReq.TargetingTopics = append(serviceReq.TargetingTopics, campaigns.TopicTargeting{
			TopicID:        topicID,
			RelevanceScore: 1.0, // Default relevance score
		})
	}

	for _, entity := range req.Targeting.Entities {
		entityType := strings.ToLower(entity.Type)
		serviceReq.TargetingEntities = append(serviceReq.TargetingEntities, campaigns.EntityTargeting{
			EntityID:   entity.Name,
			EntityType: entityType,
		})
	}

	if serviceReq.Campaign.Status == "" {
		serviceReq.Campaign.Status = "ACTIVE"
	}
	if serviceReq.AdSet.Name == "" {
		serviceReq.AdSet.Name = fmt.Sprintf("%s - Default Ad Set", req.Campaign.Name)
	}
	if serviceReq.Ad.CreativeType == "" {
		serviceReq.Ad.CreativeType = "banner"
	}

	return serviceReq, nil
}
