package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	sqlc "github.com/folaraz/contextual-ads-server/db/sqlc"
)

type AdvertiserHandler struct {
	queries *sqlc.Queries
}

func NewAdvertiserHandler(queries *sqlc.Queries) *AdvertiserHandler {
	return &AdvertiserHandler{queries: queries}
}

type CreateAdvertiserRequest struct {
	Name    string `json:"name" validate:"required,min=1"`
	Website string `json:"website,omitempty" validate:"omitempty,url"`
}

type AdvertiserResponse struct {
	ID      int32  `json:"id"`
	Name    string `json:"name"`
	Website string `json:"website,omitempty"`
}

func (h *AdvertiserHandler) CreateAdvertiser(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var req CreateAdvertiserRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, http.StatusBadRequest, "Invalid JSON payload", err)
		return
	}

	if errors := ValidateStruct(req); len(errors) > 0 {
		writeValidationErrors(w, errors)
		return
	}

	advertiser, err := h.queries.CreateAdvertiser(ctx, sqlc.CreateAdvertiserParams{
		Name:    req.Name,
		Website: sql.NullString{String: req.Website, Valid: req.Website != ""},
	})
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "Failed to create advertiser", err)
		return
	}

	response := map[string]interface{}{
		"success": true,
		"message": "Advertiser created successfully",
		"data": AdvertiserResponse{
			ID:      advertiser.ID,
			Name:    advertiser.Name,
			Website: advertiser.Website.String,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(response)
}

func (h *AdvertiserHandler) ListAdvertisers(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	advertisers, err := h.queries.ListAdvertisers(ctx)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "Failed to list advertisers", err)
		return
	}

	var response []AdvertiserResponse
	for _, adv := range advertisers {
		response = append(response, AdvertiserResponse{
			ID:      adv.ID,
			Name:    adv.Name,
			Website: adv.Website.String,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"data":    response,
	})
}
