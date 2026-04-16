package service

import (
	"database/sql"
	"log"

	"github.com/folaraz/contextual-ads-server/internal/publisher"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	"github.com/folaraz/contextual-ads-server/internal/service/campaigns"
	"github.com/folaraz/contextual-ads-server/internal/service/indexing"
	"github.com/folaraz/contextual-ads-server/internal/service/pages"
	"github.com/folaraz/contextual-ads-server/internal/service/publishers"
	"github.com/folaraz/contextual-ads-server/internal/service/reference"
	"github.com/folaraz/contextual-ads-server/internal/service/targeting"
	goredis "github.com/redis/go-redis/v9"
)

type Services struct {
	// Ads domain
	AdServe   *ads.AdServeService
	AdRanking *ads.AdRankingService
	Auction   *ads.AuctionService
	AdEvent   *ads.AdEventService

	// Targeting domain
	Targeting *targeting.AdTargetingService

	// Pages domain
	PageContext *pages.PageContextService

	// Campaigns domain
	Campaign *campaigns.CampaignService

	// Publisher domain
	Publisher *publishers.PublisherService

	// Indexing domain
	Indexing *indexing.IndexingService

	// Reference data
	Taxonomy *reference.TaxonomyService

	kafkaPublisher *publisher.KafkaPublisher
}

type Dependencies struct {
	DB          *sql.DB
	RedisClient *goredis.Client
}

func NewServices(deps Dependencies) *Services {
	// Create page context service (used by ad serve)
	pageContextSvc := pages.NewPageContextService()

	// Create ranking and auction services
	rankingSvc := ads.NewAdRankingService()
	auctionSvc := ads.NewAuctionService(deps.RedisClient)

	// Create Kafka publisher
	kafkaPub := publisher.NewKafkaPublisher()
	log.Println("[Services] Kafka publisher initialized")

	// Create ad serve service with its dependencies
	adServeSvc := ads.NewAdServeService(
		kafkaPub,
		pageContextSvc,
		rankingSvc,
		auctionSvc,
	)

	return &Services{
		// Ads
		AdServe:   adServeSvc,
		AdRanking: rankingSvc,
		Auction:   auctionSvc,
		AdEvent:   ads.NewAdEventService(deps.RedisClient),

		// Targeting
		Targeting: targeting.NewAdTargetingService(deps.DB),

		// Pages
		PageContext: pageContextSvc,

		// Campaigns
		Campaign: campaigns.NewCampaignService(deps.DB, kafkaPub, deps.RedisClient),

		// Publishers
		Publisher: publishers.NewPublisherService(deps.DB),

		// Indexing
		Indexing: indexing.NewIndexingService(deps.DB),

		// Reference
		Taxonomy: reference.NewTaxonomyService(deps.DB),

		// Store publisher for cleanup
		kafkaPublisher: kafkaPub,
	}
}

func (s *Services) Close() error {
	if s.kafkaPublisher != nil {
		return s.kafkaPublisher.Close()
	}
	return nil
}
