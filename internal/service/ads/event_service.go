package ads

import (
	"context"
	"crypto/hmac"
	"errors"
	"fmt"
	"net/url"
	"strconv"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/publisher"
	"github.com/folaraz/contextual-ads-server/internal/utils"
	goredis "github.com/redis/go-redis/v9"
)

const (
	nonceExpiry      = 24 * time.Hour
	signatureMaxAge  = 3600 // 1 hour in seconds
	clickNoncePrefix = "click_nonce:"
	impNoncePrefix   = "imp_nonce:"
)

var (
	ErrInvalidEventSignature = errors.New("invalid event signature")
	ErrMissingEventNonce     = errors.New("missing event nonce")
)

type EventData struct {
	AdID        string
	CampaignID  string
	PublisherID string
	PageURLHash string
	DestURL     string
	AuctionID   string
	PriceCents  int64
	DeviceType  string
	UserAgent   string
	IPAddress   string
}

type AdEventService struct {
	publisher   *publisher.KafkaPublisher
	redisClient *goredis.Client
}

func NewAdEventService(redisClient *goredis.Client) *AdEventService {
	return &AdEventService{
		publisher:   publisher.NewKafkaPublisher(),
		redisClient: redisClient,
	}
}

func (s *AdEventService) ProcessClick(ctx context.Context, params url.Values, eventData EventData) error {
	start := time.Now()

	if !s.verifySignature(params) {
		observability.Warn(ctx, "Click signature verification failed", "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "click", false, time.Since(start))
		return ErrInvalidEventSignature
	}

	nonce := params.Get("nonce")
	if nonce == "" {
		observability.Warn(ctx, "Missing nonce for click event", "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "click", false, time.Since(start))
		return ErrMissingEventNonce
	}

	isNew, err := s.redisClient.SetNX(ctx, clickNoncePrefix+nonce, "1", nonceExpiry).Result()
	if err != nil {
		observability.Error(ctx, "Redis error checking click nonce", "error", err, "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "click", false, time.Since(start))
		return fmt.Errorf("check click nonce: %w", err)
	}

	if !isNew {
		observability.Debug(ctx, "Duplicate click nonce detected", "nonce", nonce, "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "click", true, time.Since(start))
		return nil
	}

	s.incrementSpend(ctx, eventData)
	s.publishClickEvent(eventData)
	observability.RecordEvent(ctx, "click", true, time.Since(start))
	observability.LogEvent(ctx, "click", eventData.AdID, eventData.PublisherID, eventData.AuctionID, eventData.PriceCents)
	return nil
}

func (s *AdEventService) ProcessImpression(ctx context.Context, params url.Values, eventData EventData) error {
	start := time.Now()

	if !s.verifySignature(params) {
		observability.Warn(ctx, "Impression signature verification failed", "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "impression", false, time.Since(start))
		return ErrInvalidEventSignature
	}

	nonce := params.Get("nonce")
	if nonce == "" {
		observability.Warn(ctx, "Missing nonce for impression event", "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "impression", false, time.Since(start))
		return ErrMissingEventNonce
	}

	isNew, err := s.redisClient.SetNX(ctx, impNoncePrefix+nonce, "1", nonceExpiry).Result()
	if err != nil {
		observability.Error(ctx, "Redis error checking impression nonce", "error", err, "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "impression", false, time.Since(start))
		return fmt.Errorf("check impression nonce: %w", err)
	}

	if !isNew {
		observability.Debug(ctx, "Duplicate impression nonce detected", "nonce", nonce, "ad_id", eventData.AdID)
		observability.RecordEvent(ctx, "impression", true, time.Since(start))
		return nil
	}

	s.incrementSpend(ctx, eventData)
	s.publishImpressionEvent(eventData)
	observability.RecordEvent(ctx, "impression", true, time.Since(start))
	observability.LogEvent(ctx, "impression", eventData.AdID, eventData.PublisherID, eventData.AuctionID, eventData.PriceCents)
	return nil
}

func (s *AdEventService) incrementSpend(ctx context.Context, data EventData) {
	if data.PriceCents <= 0 {
		return
	}
	today := time.Now().UTC().Format("2006-01-02")
	dailyKey := fmt.Sprintf("campaign:%s:daily:%s", data.CampaignID, today)
	metricsKey := fmt.Sprintf("campaign:%s:metrics", data.CampaignID)

	pipe := s.redisClient.Pipeline()
	pipe.HIncrBy(ctx, dailyKey, "spend_cents", data.PriceCents)
	pipe.HIncrBy(ctx, metricsKey, "spend_cents", data.PriceCents)
	pipe.Expire(ctx, dailyKey, 48*time.Hour)
	if _, err := pipe.Exec(ctx); err != nil {
		observability.Error(ctx, "Failed to increment spend in Redis",
			"error", err, "campaign_id", data.CampaignID, "price_cents", data.PriceCents)
	}
}

func (s *AdEventService) verifySignature(params url.Values) bool {
	sig := params.Get("sig")
	if sig == "" {
		return false
	}

	// Create a copy to avoid modifying the original
	paramsCopy := make(url.Values)
	for k, v := range params {
		if k != "sig" {
			paramsCopy[k] = v
		}
	}

	payload := paramsCopy.Encode()

	expectedSig := utils.GenerateHMACSignature(payload)

	if !hmac.Equal([]byte(expectedSig), []byte(sig)) {
		return false
	}

	timestamp := params.Get("ts")
	if timestamp == "" {
		return false
	}

	ts, err := strconv.ParseInt(timestamp, 10, 64)
	if err != nil {
		return false
	}

	now := time.Now().UnixMilli()
	if now-ts > signatureMaxAge*1000 {
		return false
	}

	return true
}

func (s *AdEventService) publishImpressionEvent(data EventData) {
	s.publishAdEvent(data, publisher.AdEventImpression)
}

func (s *AdEventService) publishClickEvent(data EventData) {
	s.publishAdEvent(data, publisher.AdEventClick)
}

func (s *AdEventService) publishAdEvent(data EventData, eventType publisher.AdEventType) {
	go func() {
		msg := publisher.AdEventMessage{
			BaseMessage: publisher.BaseMessage{Timestamp: time.Now().Unix()},
			EventType:   eventType,
			AdID:        data.AdID,
			CampaignID:  data.CampaignID,
			AuctionID:   data.AuctionID,
			PriceCents:  data.PriceCents,
			ClickURL:    data.DestURL,
			PublisherID: data.PublisherID,
			PageURL:     data.PageURLHash,
			DeviceType:  data.DeviceType,
			IPAddress:   data.IPAddress,
			UserAgent:   data.UserAgent,
		}

		errChan := s.publisher.PublishAsync(msg)
		if err := <-errChan; err != nil {
			ctx := context.Background()
			observability.Error(ctx, "Failed to publish event",
				"event_type", string(eventType), "ad_id", data.AdID, "error", err)
		}
	}()
}

func (s *AdEventService) Close() error {
	if s.publisher != nil {
		return s.publisher.Close()
	}
	return nil
}
