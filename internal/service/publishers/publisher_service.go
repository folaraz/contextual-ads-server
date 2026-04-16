package publishers

import (
	"context"
	"database/sql"
	"fmt"

	db "github.com/folaraz/contextual-ads-server/db/sqlc"
	"github.com/folaraz/contextual-ads-server/internal/validation"
)

type PublisherService struct {
	db      *sql.DB
	queries *db.Queries
}

func NewPublisherService(database *sql.DB) *PublisherService {
	return &PublisherService{
		db:      database,
		queries: db.New(database),
	}
}

type CreatePublisherRequest struct {
	Name   string `validate:"required,min=1"`
	Domain string `validate:"required,min=1"`
	Email  string `validate:"omitempty,email"`
}

type PublisherResponse struct {
	ID        int32   `json:"id"`
	Name      string  `json:"name"`
	Domain    string  `json:"domain"`
	Email     *string `json:"email,omitempty"`
	CreatedAt string  `json:"created_at"`
	UpdatedAt string  `json:"updated_at"`
}

func (s *PublisherService) CreatePublisher(ctx context.Context, req CreatePublisherRequest) (*PublisherResponse,
	error) {
	// Validate request
	if err := validation.Validate(req); err != nil {
		messages := validation.FormatValidationErrors(err)
		return nil, fmt.Errorf("validation failed: %v", messages)
	}

	// Create publisher
	publisher, err := s.queries.CreatePublisher(ctx, db.CreatePublisherParams{
		Name:   req.Name,
		Domain: req.Domain,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create publisher: %w", err)
	}

	// Build response
	response := &PublisherResponse{
		ID:        publisher.ID,
		Name:      publisher.Name,
		Domain:    publisher.Domain,
		CreatedAt: publisher.CreatedAt.Time.Format("2006-01-02T15:04:05Z"),
		UpdatedAt: publisher.UpdatedAt.Time.Format("2006-01-02T15:04:05Z"),
	}

	return response, nil
}

func (s *PublisherService) GetPublisher(ctx context.Context, publisherID int32) (*PublisherResponse, error) {
	publisher, err := s.queries.GetPublisher(ctx, publisherID)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("publisher not found")
		}
		return nil, fmt.Errorf("failed to get publisher: %w", err)
	}

	response := &PublisherResponse{
		ID:        publisher.ID,
		Name:      publisher.Name,
		Domain:    publisher.Domain,
		CreatedAt: publisher.CreatedAt.Time.Format("2006-01-02T15:04:05Z"),
		UpdatedAt: publisher.UpdatedAt.Time.Format("2006-01-02T15:04:05Z"),
	}

	return response, nil
}

func (s *PublisherService) ListPublishers(ctx context.Context) ([]PublisherResponse, error) {
	publishers, err := s.queries.ListPublishers(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to list publishers: %w", err)
	}

	var response []PublisherResponse
	for _, p := range publishers {
		response = append(response, PublisherResponse{
			ID:        p.ID,
			Name:      p.Name,
			Domain:    p.Domain,
			CreatedAt: p.CreatedAt.Time.Format("2006-01-02T15:04:05Z"),
			UpdatedAt: p.UpdatedAt.Time.Format("2006-01-02T15:04:05Z"),
		})
	}

	return response, nil
}
