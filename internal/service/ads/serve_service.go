package ads

import (
	"context"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/models/request"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/publisher"
	"github.com/folaraz/contextual-ads-server/internal/service/indexing"
	"github.com/folaraz/contextual-ads-server/internal/service/pages"
	"github.com/folaraz/contextual-ads-server/internal/utils"
)

type AdServeService struct {
	pageContextService *pages.PageContextService
	adRankingService   *AdRankingService
	auctionService     *AuctionService
	publisher          *publisher.KafkaPublisher
}

func NewAdServeService(pub *publisher.KafkaPublisher, pageContextSvc *pages.PageContextService,
	rankingSvc *AdRankingService, auctionSvc *AuctionService) *AdServeService {
	return &AdServeService{
		pageContextService: pageContextSvc,
		adRankingService:   rankingSvc,
		auctionService:     auctionSvc,
		publisher:          pub,
	}
}

func (a *AdServeService) GetAdAuctionResult(ctx context.Context, adServeRequest request.AdServeRequest,
	requestContext contextextractor.RequestContext) models.AuctionResult {
	ctx, span := observability.StartSpan(ctx, "AdServeService.GetAdAuctionResult")
	defer span.End()

	adServeContext := adServeRequest.Context

	urlHash, err := utils.GenerateHashAndURL(adServeContext.URL)
	if err != nil {
		observability.RecordSpanError(ctx, err)
		observability.Error(ctx, "Error generating URL hash", "error", err)
		return models.AuctionResult{}
	}

	// Run page context fetch and candidate finding in parallel
	type pageResult struct {
		contextResult pages.PageContextResult
	}
	type indexResult struct {
		candidateAds    map[uint32]*models.Ad
		totalAdsInIndex int
	}

	pageCh := make(chan pageResult, 1)
	indexCh := make(chan indexResult, 1)

	go func() {
		_, pageSpan := observability.StartSpan(ctx, "GetPageContext")
		cr := a.pageContextService.GetPageContextOrDefault(urlHash, adServeContext.Keywords)
		pageSpan.End()
		pageCh <- pageResult{contextResult: cr}
	}()

	go func() {
		_, indexSpan := observability.StartSpan(ctx, "FindCandidates.Prepare")
		var candidates map[uint32]*models.Ad
		var total int
		if index := indexing.GetCurrentIndex(); index != nil {
			total = len(index.Ads)
			candidates = index.FindCandidates(requestContext, models.PageContext{
				Keywords: a.keywordsFromRequest(adServeContext.Keywords),
			})
		}
		indexSpan.End()
		indexCh <- indexResult{candidateAds: candidates, totalAdsInIndex: total}
	}()

	// Wait for both results
	pr := <-pageCh
	ir := <-indexCh

	contextResult := pr.contextResult
	candidateAds := ir.candidateAds
	totalAdsInIndex := ir.totalAdsInIndex

	var pageContext models.PageContext

	if !contextResult.CacheHit {
		observability.AddSpanAttributes(ctx, observability.BoolAttr("cache_hit", false))
		observability.Debug(ctx, "Page context cache miss", "url_hash", urlHash)

		// Use request-level keywords as fallback for targeting
		if len(adServeContext.Keywords) > 0 {
			pageContext.Keywords = make(map[string]float64, len(adServeContext.Keywords))
			for _, kw := range adServeContext.Keywords {
				pageContext.Keywords[kw] = 1.0
			}
		}

		a.sendPageAnalysisEvent(urlHash, adServeContext.URL, adServeRequest.PublisherID)
	} else {
		observability.AddSpanAttributes(ctx, observability.BoolAttr("cache_hit", true))
		observability.Debug(ctx, "Page context cache hit", "url_hash", urlHash)
		pageContext = contextResult.Context

		// Re-filter candidates with full page context if we have richer context now
		if index := indexing.GetCurrentIndex(); index != nil {
			_, indexSpan := observability.StartSpan(ctx, "FindCandidates.WithContext")
			candidateAds = index.FindCandidates(requestContext, pageContext)
			totalAdsInIndex = len(index.Ads)
			indexSpan.End()
		}
	}

	// Calculate targeting filtering
	filteredByTargeting := totalAdsInIndex - len(candidateAds)
	observability.AddSpanAttributes(ctx,
		observability.IntAttr("total_ads_in_index", totalAdsInIndex),
		observability.IntAttr("candidate_count", len(candidateAds)),
		observability.IntAttr("filtered_by_targeting", filteredByTargeting),
	)

	if len(candidateAds) == 0 {
		observability.Debug(ctx, "No candidate ads found", "url_hash", urlHash)
		return models.AuctionResult{
			Stats: models.AuctionStats{
				TotalCandidates:     totalAdsInIndex,
				FilteredByTargeting: filteredByTargeting,
			},
		}
	}

	// Rank ads by vector similarity
	ctx, rankSpan := observability.StartSpan(ctx, "RankAds")
	rankedAds := a.adRankingService.RankAds(ctx, pageContext, candidateAds)
	rankSpan.End()

	// Run auction on ranked ads
	ctx, auctionSpan := observability.StartSpan(ctx, "RunAuction")
	auctionResult := a.auctionService.RunAuction(rankedAds, pageContext)
	auctionSpan.End()

	auctionResult.PageHash = urlHash
	auctionResult.AuctionID = utils.GenerateAuctionID()

	// Update stats with targeting filtering info
	auctionResult.Stats.TotalCandidates = totalAdsInIndex
	auctionResult.Stats.FilteredByTargeting = filteredByTargeting

	observability.AddSpanAttributes(ctx,
		observability.BoolAttr("has_winner", auctionResult.HasWinner),
		observability.StringAttr("auction_id", auctionResult.AuctionID),
	)

	a.sendAuctionEvent(auctionResult, adServeRequest, requestContext)

	return auctionResult
}

func (a *AdServeService) sendAuctionEvent(auctionResult models.AuctionResult, adServeRequest request.AdServeRequest,
	requestContext contextextractor.RequestContext) {
	go func() {
		msg := publisher.AuctionMessage{
			BaseMessage:          publisher.BaseMessage{Timestamp: time.Now().Unix()},
			AuctionID:            auctionResult.AuctionID,
			Winner:               auctionResult.GetWinningAuctionCandidateForEvent(),
			Candidates:           auctionResult.GetRunnerUpAuctionCandidatesForEvent(),
			NumOfCandidates:      auctionResult.Stats.TotalCandidates,
			NumFilteredBudget:    auctionResult.Stats.FilteredByBudget,
			NumFilteredTargeting: auctionResult.Stats.FilteredByTargeting,
			NumEligible:          auctionResult.Stats.EligibleForAuction,
			PageURL:              adServeRequest.Context.URL,
			PublisherID:          adServeRequest.PublisherID,
			DeviceType:           adServeRequest.Device.Type,
			UserAgent:            adServeRequest.Device.UserAgent,
			IPAddress:            requestContext.IP,
		}

		if err := a.publisher.Publish(msg); err != nil {
			observability.Error(context.Background(), "Failed to publish auction event",
				"auction_id", auctionResult.AuctionID, "error", err)
		} else {
			observability.Debug(context.Background(), "Published auction event",
				"auction_id", auctionResult.AuctionID,
				"total_candidates", auctionResult.Stats.TotalCandidates,
				"filtered_targeting", auctionResult.Stats.FilteredByTargeting,
				"filtered_budget", auctionResult.Stats.FilteredByBudget,
				"eligible", auctionResult.Stats.EligibleForAuction)
		}
	}()
}

func (a *AdServeService) sendPageAnalysisEvent(urlHash string, url string, publisherID string) {
	go func() {
		msg := publisher.PageAnalyzeMessage{
			BaseMessage: publisher.BaseMessage{Timestamp: time.Now().Unix()},
			PageUrlHash: urlHash,
			PageUrl:     url,
			PublisherID: publisherID,
		}
		if err := a.publisher.Publish(msg); err != nil {
			observability.Error(context.Background(), "Failed to publish page analyze message",
				"url_hash", urlHash, "error", err)
		} else {
			observability.Debug(context.Background(), "Published page analyze message", "url_hash", urlHash)
		}
	}()
}

func (a *AdServeService) keywordsFromRequest(keywords []string) map[string]float64 {
	if len(keywords) == 0 {
		return nil
	}
	m := make(map[string]float64, len(keywords))
	for _, kw := range keywords {
		m[kw] = 1.0
	}
	return m
}
