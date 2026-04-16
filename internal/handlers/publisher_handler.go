package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/folaraz/contextual-ads-server/internal/service/publishers"
)

type PublisherHandler struct {
	service *publishers.PublisherService
}

func NewPublisherHandler(service *publishers.PublisherService) *PublisherHandler {
	return &PublisherHandler{
		service: service,
	}
}

type CreatePublisherRequest struct {
	Name   string `json:"name" validate:"required,min=1"`
	Domain string `json:"domain" validate:"required,min=1"`
	Email  string `json:"email,omitempty" validate:"omitempty,email"`
}

func (h *PublisherHandler) CreatePublisher(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var req CreatePublisherRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSONError(w, http.StatusBadRequest, "Invalid JSON payload", err)
		return
	}

	if errors := ValidateStruct(req); len(errors) > 0 {
		writeValidationErrors(w, errors)
		return
	}

	serviceReq := publishers.CreatePublisherRequest{
		Name:   req.Name,
		Domain: req.Domain,
	}

	publisher, err := h.service.CreatePublisher(ctx, serviceReq)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "Failed to create publisher", err)
		return
	}

	response := map[string]interface{}{
		"success": true,
		"message": "Publisher created successfully",
		"data":    publisher,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(response)
}

func (h *PublisherHandler) GetPublisher(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	publisherIDStr := r.PathValue("publisherID")
	if publisherIDStr == "" {
		writeJSONError(w, http.StatusBadRequest, "Publisher ID is required", nil)
		return
	}

	publisherID, err := strconv.ParseInt(publisherIDStr, 10, 32)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "Invalid publisher ID", err)
		return
	}

	publisher, err := h.service.GetPublisher(ctx, int32(publisherID))
	if err != nil {
		if err.Error() == "publisher not found" {
			writeJSONError(w, http.StatusNotFound, "Publisher not found", nil)
		} else {
			writeJSONError(w, http.StatusInternalServerError, "Failed to get publisher", err)
		}
		return
	}

	response := map[string]interface{}{
		"success": true,
		"data":    publisher,
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response)
}

func (h *PublisherHandler) ListPublishers(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	publishers, err := h.service.ListPublishers(ctx)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "Failed to list publishers", err)
		return
	}

	response := map[string]interface{}{
		"success": true,
		"data":    publishers,
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(response)
}
