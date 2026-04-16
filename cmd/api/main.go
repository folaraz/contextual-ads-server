package main

import (
	"context"
	"errors"
	"net/http"
	"time"

	"github.com/cenkalti/backoff/v4"
	db "github.com/folaraz/contextual-ads-server/db/sqlc"
	"github.com/folaraz/contextual-ads-server/internal/cache"
	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/handlers"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/service"
	"github.com/folaraz/contextual-ads-server/internal/service/indexing"
	"github.com/folaraz/contextual-ads-server/internal/storage/postgres"
	"github.com/folaraz/contextual-ads-server/internal/storage/redis"
)

var (
	advertiserHandler *handlers.AdvertiserHandler
	campaignHandler   *handlers.CampaignHandler
	adServeHandler    *handlers.AdServeHandler
	eventHandler      *handlers.EventHandler
	publisherHandler  *handlers.PublisherHandler
)

var services *service.Services

var obs *observability.Observability

func initApp(ctx context.Context) error {
	redisConfig := redis.DefaultConfig()
	if err := redis.InitClient(redisConfig); err != nil {
		observability.Warn(ctx, "Failed to initialize Redis", "error", err)
	}

	redisClient := redis.GetRedisClient()

	contextextractor.InitRequestExtractorDB()

	cfg := postgres.DefaultConfig()
	if err := postgres.InitDB(cfg); err != nil {
		observability.Warn(ctx, "Failed to connect to PostgreSQL", "error", err)
		observability.Info(ctx, "Advertiser and Campaign endpoints will not be available")
		return nil
	}

	database, err := postgres.GetDB()
	if err != nil {
		observability.Warn(ctx, "Failed to get database connection", "error", err)
		return nil
	}

	if err := cache.InitTaxonomyCache(database); err != nil {
		observability.Warn(ctx, "Failed to initialize taxonomy cache", "error", err)
	}

	queries := db.New(database)

	services = service.NewServices(service.Dependencies{
		DB:          database,
		RedisClient: redisClient,
	})

	initCtx, initCancel := context.WithTimeout(ctx, 30*time.Second)
	if err := services.Taxonomy.LoadTaxonomies(initCtx); err != nil {
		observability.Error(ctx, "Unable to load IAB Taxonomies", "error", err)
	}

	if _, err := services.Indexing.Initialize(initCtx); err != nil {
		observability.Warn(ctx, "Failed to initialize ad index", "error", err)
	} else {
		observability.Info(ctx, "Initial ad index loaded successfully")
	}
	initCancel()

	advertiserHandler = handlers.NewAdvertiserHandler(queries)
	campaignHandler = handlers.NewCampaignHandler(services.Campaign)
	adServeHandler = handlers.NewAdServeHandler(services.AdServe)
	eventHandler = handlers.NewEventHandler(redisClient)
	publisherHandler = handlers.NewPublisherHandler(services.Publisher)

	go startIndexRefreshWorker(ctx, services.Indexing)

	observability.Info(ctx, "Database, services, and handlers initialized successfully")
	return nil
}

func startIndexRefreshWorker(ctx context.Context, indexingSvc *indexing.IndexingService) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	consecutiveFailures := 0
	const maxConsecutiveFailures = 3

	for range ticker.C {
		currentIdx := indexing.GetCurrentIndex()
		if currentIdx == nil {
			observability.Warn(ctx, "Skipping index refresh: initial index not loaded")
			continue
		}

		lastUpdateTime := currentIdx.LastUpdated

		expBackoff := backoff.NewExponentialBackOff()
		expBackoff.InitialInterval = 30 * time.Second
		expBackoff.MaxInterval = 2 * time.Minute
		expBackoff.MaxElapsedTime = 5 * time.Minute
		expBackoff.Multiplier = 2.0

		var newIndex *indexing.GlobalIndex
		operation := func() error {
			// Create a fresh context with timeout for each attempt
			refreshCtx, refreshCancel := context.WithTimeout(context.Background(), 3*time.Minute)
			defer refreshCancel()

			var err error
			newIndex, err = indexingSvc.Refresh(refreshCtx, lastUpdateTime)
			if err != nil {
				observability.Warn(ctx, "Index refresh attempt failed", "error", err)
				return err
			}
			return nil
		}

		err := backoff.Retry(operation, backoff.WithMaxRetries(expBackoff, 3))

		if err != nil {
			consecutiveFailures++
			observability.Error(ctx, "Error refreshing index after retries", "error", err, "consecutiveFailures", consecutiveFailures)

			if consecutiveFailures >= maxConsecutiveFailures {
				observability.Warn(ctx, "Index refresh has failed consecutive times. Index may be stale.", "consecutiveFailures", consecutiveFailures, "lastSuccessfulUpdate", currentIdx.LastUpdated)
			}
			continue
		}

		// Success - reset failure counter
		consecutiveFailures = 0
		observability.Info(ctx, "Ad index refreshed successfully", "totalAdsIndexed", len(newIndex.Ads))
	}
}

func createAdvertiserHandler(w http.ResponseWriter, r *http.Request) {
	if advertiserHandler == nil {
		http.Error(w, "Database not configured", http.StatusServiceUnavailable)
		return
	}
	advertiserHandler.CreateAdvertiser(w, r)
}

func listAdvertisersHandler(w http.ResponseWriter, r *http.Request) {
	if advertiserHandler == nil {
		http.Error(w, "Database not configured", http.StatusServiceUnavailable)
		return
	}
	advertiserHandler.ListAdvertisers(w, r)
}

func createCampaignHandler(w http.ResponseWriter, r *http.Request) {
	if campaignHandler == nil {
		http.Error(w, "Database not configured", http.StatusServiceUnavailable)
		return
	}
	campaignHandler.CreateCampaign(w, r)
}

func serveAdHandler(w http.ResponseWriter, r *http.Request) {
	if adServeHandler == nil {
		http.Error(w, "Ad serving handler not configured", http.StatusServiceUnavailable)
		return
	}
	adServeHandler.ServeAd(w, r)
}

func clickEventHandler(w http.ResponseWriter, r *http.Request) {
	if eventHandler == nil {
		http.Error(w, "Event handler not configured", http.StatusServiceUnavailable)
		return
	}
	eventHandler.HandleClick(w, r)
}

func impressionEventHandler(w http.ResponseWriter, r *http.Request) {
	if eventHandler == nil {
		http.Error(w, "Event handler not configured", http.StatusServiceUnavailable)
		return
	}
	eventHandler.HandleImpression(w, r)
}

func createPublisherHandler(w http.ResponseWriter, r *http.Request) {
	if publisherHandler == nil {
		http.Error(w, "Database not configured", http.StatusServiceUnavailable)
		return
	}
	publisherHandler.CreatePublisher(w, r)
}

func listPublishersHandler(w http.ResponseWriter, r *http.Request) {
	if publisherHandler == nil {
		http.Error(w, "Database not configured", http.StatusServiceUnavailable)
		return
	}
	publisherHandler.ListPublishers(w, r)
}

func getPublisherHandler(w http.ResponseWriter, r *http.Request) {
	if publisherHandler == nil {
		http.Error(w, "Database not configured", http.StatusServiceUnavailable)
		return
	}
	publisherHandler.GetPublisher(w, r)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == "" {
			origin = "*"
		}
		w.Header().Set("Access-Control-Allow-Origin", origin)
		w.Header().Set("Access-Control-Allow-Credentials", "true")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Forwarded-For")
		w.Header().Set("Access-Control-Max-Age", "3600")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	obs = observability.NewObservability("contextual-ads-server")

	if err := initApp(ctx); err != nil {
		obs.Fatal(err, "Failed to initialize application")
	}

	mux := http.NewServeMux()

	mux.HandleFunc("POST /api/ads/serve", serveAdHandler)
	mux.HandleFunc("POST /api/advertisers", createAdvertiserHandler)
	mux.HandleFunc("GET /api/advertisers", listAdvertisersHandler)
	mux.HandleFunc("POST /api/campaigns", createCampaignHandler)
	mux.HandleFunc("POST /api/publishers", createPublisherHandler)
	mux.HandleFunc("GET /api/publishers", listPublishersHandler)
	mux.HandleFunc("GET /api/publishers/{publisherID}", getPublisherHandler)
	mux.HandleFunc("POST /api/events/impression", impressionEventHandler)
	mux.HandleFunc("GET /api/events/click", clickEventHandler)

	handler := corsMiddleware(observability.MetricsMiddleware(observability.TracingMiddleware(mux)))

	srv := &http.Server{
		Addr:    ":8090",
		Handler: handler,
	}

	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		obs.Fatal(err, "ListenAndServe failed")
	}
}
