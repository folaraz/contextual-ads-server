package observability

import (
	"context"
	"net/http"
	"os"
	"strconv"
	"sync/atomic"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/metric"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
)

var (
	meter metric.Meter

	// HTTP metrics
	httpRequestsTotal    metric.Int64Counter
	httpRequestDuration  metric.Float64Histogram
	httpRequestsInFlight metric.Int64UpDownCounter

	// Ad serving metrics
	adServeRequestsTotal metric.Int64Counter
	adServeDuration      metric.Float64Histogram
	adAuctionCandidates  metric.Float64Histogram
	adFillTotal          metric.Int64Counter
	auctionWinningBid    metric.Float64Histogram

	// Cache metrics
	cacheOperationsTotal metric.Int64Counter
	cacheLatency         metric.Float64Histogram

	// Event metrics
	eventsTotal             metric.Int64Counter
	eventProcessingDuration metric.Float64Histogram

	// Index metrics
	indexSize             metric.Int64ObservableGauge
	indexGeoSize          metric.Int64ObservableGauge
	indexDeviceSize       metric.Int64ObservableGauge
	indexKeywordSize      metric.Int64ObservableGauge
	indexTopicSize        metric.Int64ObservableGauge
	indexEntitySize       metric.Int64ObservableGauge
	indexRefreshDuration  metric.Float64Histogram
	indexRefreshErrors    metric.Int64Counter
	indexLastRefresh      metric.Int64ObservableGauge
	indexDBQueryDuration  metric.Float64Histogram
	indexBuildDuration    metric.Float64Histogram
	indexLookupDuration   metric.Float64Histogram
	indexLookupCandidates metric.Float64Histogram

	// Database metrics
	dbQueryDuration metric.Float64Histogram
	dbErrors        metric.Int64Counter

	// Kafka metrics
	kafkaMessagesPublished metric.Int64Counter
	kafkaPublishLatency    metric.Float64Histogram

	// Observable gauge values for index (atomic for goroutine-safe access)
	currentIndexSize        atomic.Int64
	currentGeoIndexSize     atomic.Int64
	currentDeviceIndexSize  atomic.Int64
	currentKeywordIndexSize atomic.Int64
	currentTopicIndexSize   atomic.Int64
	currentEntityIndexSize  atomic.Int64
	lastRefreshTimestamp    atomic.Int64
)

func InitMetrics(ctx context.Context, res *resource.Resource) (func(context.Context) error, error) {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4317"
	}

	exporter, err := otlpmetricgrpc.New(ctx,
		otlpmetricgrpc.WithEndpoint(endpoint),
		otlpmetricgrpc.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	// Use second-scale bucket boundaries for all histograms declared with unit "s".
	// The OTel SDK default buckets [0, 5, 10, 25, …] are millisecond-scale; without
	// this view every sub-second latency observation falls into the single [0,5) bucket
	// and histogram_quantile returns wildly inaccurate percentiles (~2.5 s for p50).
	secondBuckets := sdkmetric.AggregationExplicitBucketHistogram{
		Boundaries: []float64{
			0.001, 0.005, 0.01, 0.025, 0.05, 0.075,
			0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0,
		},
	}
	secondsView := sdkmetric.NewView(
		sdkmetric.Instrument{
			Kind: sdkmetric.InstrumentKindHistogram,
			Unit: "s",
		},
		sdkmetric.Stream{Aggregation: secondBuckets},
	)

	provider := sdkmetric.NewMeterProvider(
		sdkmetric.WithResource(res),
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(exporter, sdkmetric.WithInterval(10*time.Second))),
		sdkmetric.WithView(secondsView),
	)

	otel.SetMeterProvider(provider)
	meter = provider.Meter(ServiceName)

	if err := createMetrics(); err != nil {
		return nil, err
	}

	return provider.Shutdown, nil
}

func createMetrics() error {
	var err error

	// HTTP metrics
	httpRequestsTotal, err = meter.Int64Counter("http_requests_total",
		metric.WithDescription("Total number of HTTP requests"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	httpRequestDuration, err = meter.Float64Histogram("http_request_duration_seconds",
		metric.WithDescription("HTTP request latency in seconds"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	httpRequestsInFlight, err = meter.Int64UpDownCounter("http_requests_in_flight",
		metric.WithDescription("Current number of HTTP requests being processed"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	// Ad serving metrics
	adServeRequestsTotal, err = meter.Int64Counter("ad_serve_requests_total",
		metric.WithDescription("Total number of ad serve requests"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	adServeDuration, err = meter.Float64Histogram("ad_serve_duration_seconds",
		metric.WithDescription("Ad serve request latency in seconds"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	adAuctionCandidates, err = meter.Float64Histogram("ad_auction_candidates",
		metric.WithDescription("Number of candidate ads per auction"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	adFillTotal, err = meter.Int64Counter("ad_fill_total",
		metric.WithDescription("Total ad fill tracking"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	auctionWinningBid, err = meter.Float64Histogram("auction_winning_bid_cents",
		metric.WithDescription("Winning bid amount in cents"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	// Cache metrics
	cacheOperationsTotal, err = meter.Int64Counter("cache_operations_total",
		metric.WithDescription("Total cache operations"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	cacheLatency, err = meter.Float64Histogram("cache_operation_duration_seconds",
		metric.WithDescription("Cache operation latency in seconds"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	// Event metrics
	eventsTotal, err = meter.Int64Counter("events_total",
		metric.WithDescription("Total events processed"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	eventProcessingDuration, err = meter.Float64Histogram("event_processing_duration_seconds",
		metric.WithDescription("Event processing latency in seconds"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	// Index metrics
	indexSize, err = meter.Int64ObservableGauge("ad_index_size",
		metric.WithDescription("Number of ads in the current index"),
		metric.WithUnit("1"),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			o.Observe(currentIndexSize.Load())
			return nil
		}))
	if err != nil {
		return err
	}

	indexRefreshDuration, err = meter.Float64Histogram("ad_index_refresh_duration_seconds",
		metric.WithDescription("Time taken to refresh the ad index"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	indexRefreshErrors, err = meter.Int64Counter("ad_index_refresh_errors_total",
		metric.WithDescription("Total number of index refresh failures"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	indexLastRefresh, err = meter.Int64ObservableGauge("ad_index_last_refresh_timestamp",
		metric.WithDescription("Unix timestamp of last successful index refresh"),
		metric.WithUnit("1"),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			o.Observe(lastRefreshTimestamp.Load())
			return nil
		}))
	if err != nil {
		return err
	}

	// Index breakdown by type
	indexGeoSize, err = meter.Int64ObservableGauge("ad_index_geo_size",
		metric.WithDescription("Number of unique geo entries in the index"),
		metric.WithUnit("1"),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			o.Observe(currentGeoIndexSize.Load())
			return nil
		}))
	if err != nil {
		return err
	}

	indexDeviceSize, err = meter.Int64ObservableGauge("ad_index_device_size",
		metric.WithDescription("Number of unique device entries in the index"),
		metric.WithUnit("1"),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			o.Observe(currentDeviceIndexSize.Load())
			return nil
		}))
	if err != nil {
		return err
	}

	indexKeywordSize, err = meter.Int64ObservableGauge("ad_index_keyword_size",
		metric.WithDescription("Number of unique keyword entries in the index"),
		metric.WithUnit("1"),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			o.Observe(currentKeywordIndexSize.Load())
			return nil
		}))
	if err != nil {
		return err
	}

	indexTopicSize, err = meter.Int64ObservableGauge("ad_index_topic_size",
		metric.WithDescription("Number of unique topic entries in the index"),
		metric.WithUnit("1"),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			o.Observe(currentTopicIndexSize.Load())
			return nil
		}))
	if err != nil {
		return err
	}

	indexEntitySize, err = meter.Int64ObservableGauge("ad_index_entity_size",
		metric.WithDescription("Number of unique entity entries in the index"),
		metric.WithUnit("1"),
		metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
			o.Observe(currentEntityIndexSize.Load())
			return nil
		}))
	if err != nil {
		return err
	}

	// Index operation duration metrics
	indexDBQueryDuration, err = meter.Float64Histogram("ad_index_db_query_duration_seconds",
		metric.WithDescription("Time spent querying database during index refresh"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	indexBuildDuration, err = meter.Float64Histogram("ad_index_build_duration_seconds",
		metric.WithDescription("Time spent building index data structures"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	indexLookupDuration, err = meter.Float64Histogram("ad_index_lookup_duration_seconds",
		metric.WithDescription("Time spent looking up candidates in the index"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	indexLookupCandidates, err = meter.Float64Histogram("ad_index_lookup_candidates",
		metric.WithDescription("Number of candidates found during index lookup"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	// Database metrics
	dbQueryDuration, err = meter.Float64Histogram("db_query_duration_seconds",
		metric.WithDescription("Database query latency in seconds"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	dbErrors, err = meter.Int64Counter("db_errors_total",
		metric.WithDescription("Total database errors"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	// Kafka metrics
	kafkaMessagesPublished, err = meter.Int64Counter("kafka_messages_published_total",
		metric.WithDescription("Total messages published to Kafka"),
		metric.WithUnit("1"))
	if err != nil {
		return err
	}

	kafkaPublishLatency, err = meter.Float64Histogram("kafka_publish_duration_seconds",
		metric.WithDescription("Kafka message publish latency in seconds"),
		metric.WithUnit("s"))
	if err != nil {
		return err
	}

	return nil
}

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func newResponseWriter(w http.ResponseWriter) *responseWriter {
	return &responseWriter{w, http.StatusOK}
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func MetricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		httpRequestsInFlight.Add(ctx, 1)
		defer httpRequestsInFlight.Add(ctx, -1)

		start := time.Now()
		rw := newResponseWriter(w)

		next.ServeHTTP(rw, r)

		duration := time.Since(start).Seconds()
		path := normalizePath(r.URL.Path)
		status := strconv.Itoa(rw.statusCode)

		httpRequestsTotal.Add(ctx, 1,
			metric.WithAttributes(
				attribute.String("method", r.Method),
				attribute.String("path", path),
				attribute.String("status", status),
			))
		httpRequestDuration.Record(ctx, duration,
			metric.WithAttributes(
				attribute.String("method", r.Method),
				attribute.String("path", path),
			))
	})
}

func normalizePath(path string) string {
	switch {
	case len(path) > 16 && path[:16] == "/api/publishers/":
		return "/api/publishers/{id}"
	case len(path) > 15 && path[:15] == "/api/campaigns/":
		return "/api/campaigns/{id}"
	case len(path) > 17 && path[:17] == "/api/advertisers/":
		return "/api/advertisers/{id}"
	default:
		return path
	}
}

func RecordAdServe(ctx context.Context, publisherID string, filled bool, candidateCount int, priceCents int64,
	pricingModel string, duration time.Duration) {
	status := "filled"
	if !filled {
		status = "no_fill"
	}

	adServeRequestsTotal.Add(ctx, 1,
		metric.WithAttributes(
			attribute.String("status", status),
			attribute.String("publisher_id", publisherID),
		))
	adServeDuration.Record(ctx, duration.Seconds(),
		metric.WithAttributes(attribute.String("publisher_id", publisherID)))
	adAuctionCandidates.Record(ctx, float64(candidateCount),
		metric.WithAttributes(attribute.String("publisher_id", publisherID)))

	filledStr := "false"
	if filled {
		filledStr = "true"
		auctionWinningBid.Record(ctx, float64(priceCents),
			metric.WithAttributes(attribute.String("pricing_model", pricingModel)))
	}
	adFillTotal.Add(ctx, 1, metric.WithAttributes(attribute.String("filled", filledStr)))
}

func RecordCacheOperation(ctx context.Context, cacheName, operation string, hit bool, duration time.Duration) {
	result := "miss"
	if hit {
		result = "hit"
	}
	cacheOperationsTotal.Add(ctx, 1,
		metric.WithAttributes(
			attribute.String("cache", cacheName),
			attribute.String("operation", operation),
			attribute.String("result", result),
		))
	cacheLatency.Record(ctx, duration.Seconds(),
		metric.WithAttributes(
			attribute.String("cache", cacheName),
			attribute.String("operation", operation),
		))
}

func RecordEvent(ctx context.Context, eventType string, success bool, duration time.Duration) {
	status := "success"
	if !success {
		status = "error"
	}
	eventsTotal.Add(ctx, 1,
		metric.WithAttributes(
			attribute.String("event_type", eventType),
			attribute.String("status", status),
		))
	eventProcessingDuration.Record(ctx, duration.Seconds(),
		metric.WithAttributes(attribute.String("event_type", eventType)))
}

func RecordIndexRefresh(ctx context.Context, adCount int, duration time.Duration, err error) {
	indexRefreshDuration.Record(ctx, duration.Seconds())
	if err != nil {
		indexRefreshErrors.Add(ctx, 1)
	} else {
		currentIndexSize.Store(int64(adCount))
		lastRefreshTimestamp.Store(time.Now().Unix())
	}
}

func RecordIndexRefreshDetailed(ctx context.Context, stats IndexRefreshStats) {
	// Record total refresh duration
	indexRefreshDuration.Record(ctx, stats.TotalDuration.Seconds())

	if stats.Error != nil {
		indexRefreshErrors.Add(ctx, 1)
	} else {
		// Update observable gauge values (these will be picked up by the callback)
		currentIndexSize.Store(int64(stats.TotalAds))
		currentGeoIndexSize.Store(int64(stats.GeoIndexSize))
		currentDeviceIndexSize.Store(int64(stats.DeviceIndexSize))
		currentKeywordIndexSize.Store(int64(stats.KeywordIndexSize))
		currentTopicIndexSize.Store(int64(stats.TopicIndexSize))
		currentEntityIndexSize.Store(int64(stats.EntityIndexSize))
		lastRefreshTimestamp.Store(time.Now().Unix())
	}

	// Record DB query duration
	indexDBQueryDuration.Record(ctx, stats.DBQueryDuration.Seconds())

	// Record index build duration
	indexBuildDuration.Record(ctx, stats.IndexingDuration.Seconds())

	// Log detailed metrics for debugging
	Logger.Info("index_refresh_complete",
		"total_ads", stats.TotalAds,
		"active_ads_processed", stats.ActiveAdsProcessed,
		"inactive_ads_removed", stats.InactiveAdsRemoved,
		"geo_index_size", stats.GeoIndexSize,
		"device_index_size", stats.DeviceIndexSize,
		"keyword_index_size", stats.KeywordIndexSize,
		"topic_index_size", stats.TopicIndexSize,
		"entity_index_size", stats.EntityIndexSize,
		"db_query_duration_ms", stats.DBQueryDuration.Milliseconds(),
		"indexing_duration_ms", stats.IndexingDuration.Milliseconds(),
		"total_duration_ms", stats.TotalDuration.Milliseconds(),
	)
}

type IndexRefreshStats struct {
	TotalAds           int
	ActiveAdsProcessed int
	InactiveAdsRemoved int
	GeoIndexSize       int
	DeviceIndexSize    int
	KeywordIndexSize   int
	TopicIndexSize     int
	EntityIndexSize    int
	DBQueryDuration    time.Duration
	IndexingDuration   time.Duration
	TotalDuration      time.Duration
	Error              error
}

func RecordIndexLookup(ctx context.Context, lookupType string, candidatesFound int, duration time.Duration) {
	// Record lookup duration
	indexLookupDuration.Record(ctx, duration.Seconds(),
		metric.WithAttributes(
			attribute.String("lookup_type", lookupType),
		))

	// Record number of candidates found
	indexLookupCandidates.Record(ctx, float64(candidatesFound),
		metric.WithAttributes(
			attribute.String("lookup_type", lookupType),
		))

	Logger.Debug("index_lookup",
		"lookup_type", lookupType,
		"candidates_found", candidatesFound,
		"duration_ms", duration.Milliseconds(),
	)
}

func RecordDBQuery(ctx context.Context, queryType string, duration time.Duration, err error) {
	dbQueryDuration.Record(ctx, duration.Seconds(),
		metric.WithAttributes(attribute.String("query_type", queryType)))
	if err != nil {
		dbErrors.Add(ctx, 1, metric.WithAttributes(attribute.String("operation", queryType)))
	}
}

func RecordKafkaPublish(ctx context.Context, topic string, success bool, duration time.Duration) {
	status := "success"
	if !success {
		status = "error"
	}
	kafkaMessagesPublished.Add(ctx, 1,
		metric.WithAttributes(
			attribute.String("topic", topic),
			attribute.String("status", status),
		))
	kafkaPublishLatency.Record(ctx, duration.Seconds(),
		metric.WithAttributes(attribute.String("topic", topic)))
}
