package indexing

import (
	"context"
	"database/sql"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/RoaringBitmap/roaring/v2"
	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/service/targeting"
)

type AdIndex interface {
	FindCandidates(requestContext contextextractor.RequestContext, pageCtx models.PageContext) []uint32
}

type GlobalIndex struct {
	GeoIndex     map[string]*roaring.Bitmap // Country Code -> Ad IDs
	DeviceIndex  map[string]*roaring.Bitmap // Device type -> Ad IDs
	KeywordIndex map[string]*roaring.Bitmap // Keyword -> Ad IDs
	TopicIndex   map[int32]*roaring.Bitmap  // Topic ID -> Ad IDs
	EntityIndex  map[string]*roaring.Bitmap // Entity -> Ad IDs
	Ads          map[uint32]*models.Ad      // Ad ID -> Ad
	LastUpdated  time.Time
}

var currentIndex atomic.Pointer[GlobalIndex]

type IndexingService struct {
	db *sql.DB
}

func NewIndexingService(database *sql.DB) *IndexingService {
	return &IndexingService{db: database}
}

func (s *IndexingService) Initialize(ctx context.Context) (*GlobalIndex, error) {
	return InitializeIndex(s.db, ctx)
}

func (s *IndexingService) Refresh(ctx context.Context, lastUpdated time.Time) (*GlobalIndex, error) {
	return IndexRefresh(s.db, lastUpdated, ctx)
}

func GetCurrentIndex() *GlobalIndex {
	return currentIndex.Load()
}

func NewGlobalIndex() *GlobalIndex {
	return &GlobalIndex{
		GeoIndex:     make(map[string]*roaring.Bitmap),
		DeviceIndex:  make(map[string]*roaring.Bitmap),
		KeywordIndex: make(map[string]*roaring.Bitmap),
		TopicIndex:   make(map[int32]*roaring.Bitmap),
		EntityIndex:  make(map[string]*roaring.Bitmap),
		Ads:          make(map[uint32]*models.Ad),
		LastUpdated:  time.Now(),
	}
}

func InitializeIndex(database *sql.DB, ctx context.Context) (*GlobalIndex, error) {
	totalStart := time.Now()
	idx := NewGlobalIndex()

	adTargetingService := targeting.NewAdTargetingService(database)

	dbStart := time.Now()
	activeAds, err := adTargetingService.GetAllActiveAds(ctx)
	dbDuration := time.Since(dbStart)

	if err != nil {
		observability.RecordIndexRefreshDetailed(ctx, observability.IndexRefreshStats{
			Error:           err,
			DBQueryDuration: dbDuration,
			TotalDuration:   time.Since(totalStart),
		})
		return nil, err
	}

	indexingStart := time.Now()
	for _, ad := range activeAds {
		adID := uint32(ad.AdID)
		idx.Ads[adID] = &ad

		// Index by Geo
		for _, country := range ad.Countries {
			if idx.GeoIndex[country.CountryISOCode] == nil {
				idx.GeoIndex[country.CountryISOCode] = roaring.NewBitmap()
			}
			idx.GeoIndex[country.CountryISOCode].Add(adID)
		}

		// Index by Device
		for _, device := range ad.Devices {
			if idx.DeviceIndex[device.DeviceType] == nil {
				idx.DeviceIndex[device.DeviceType] = roaring.NewBitmap()
			}
			idx.DeviceIndex[device.DeviceType].Add(adID)
		}

		// Index by Keyword
		for _, kw := range ad.Keywords {
			if idx.KeywordIndex[kw.Keyword] == nil {
				idx.KeywordIndex[kw.Keyword] = roaring.NewBitmap()
			}
			idx.KeywordIndex[kw.Keyword].Add(adID)
		}

		// Index by Topic
		for _, topic := range ad.Topics {
			if idx.TopicIndex[topic.TopicID] == nil {
				idx.TopicIndex[topic.TopicID] = roaring.NewBitmap()
			}
			idx.TopicIndex[topic.TopicID].Add(adID)
		}

		// Index by Entity
		for _, entity := range ad.Entities {
			if idx.EntityIndex[entity.EntityID] == nil {
				idx.EntityIndex[entity.EntityID] = roaring.NewBitmap()
			}
			idx.EntityIndex[entity.EntityID].Add(adID)
		}
	}
	indexingDuration := time.Since(indexingStart)

	currentIndex.Store(idx)

	// Record detailed metrics
	observability.RecordIndexRefreshDetailed(ctx, observability.IndexRefreshStats{
		TotalAds:           len(idx.Ads),
		ActiveAdsProcessed: len(activeAds),
		GeoIndexSize:       len(idx.GeoIndex),
		DeviceIndexSize:    len(idx.DeviceIndex),
		KeywordIndexSize:   len(idx.KeywordIndex),
		TopicIndexSize:     len(idx.TopicIndex),
		EntityIndexSize:    len(idx.EntityIndex),
		DBQueryDuration:    dbDuration,
		IndexingDuration:   indexingDuration,
		TotalDuration:      time.Since(totalStart),
	})

	return idx, nil
}

func IndexRefresh(db *sql.DB, lastUpdated time.Time, ctx context.Context) (*GlobalIndex, error) {
	totalStart := time.Now()

	oldIdx := currentIndex.Load()
	if oldIdx == nil {
		return InitializeIndex(db, ctx)
	}

	idx := oldIdx.Clone()

	adTargetingService := targeting.NewAdTargetingService(db)

	dbStart := time.Now()
	changedAds, err := adTargetingService.GetAllAdsChangedSince(ctx, lastUpdated)
	dbDuration := time.Since(dbStart)

	if err != nil {
		observability.RecordIndexRefreshDetailed(ctx, observability.IndexRefreshStats{
			Error:           err,
			DBQueryDuration: dbDuration,
			TotalDuration:   time.Since(totalStart),
		})
		return nil, err
	}

	observability.Info(ctx, "IndexRefresh: Processing changed ads",
		"changed_ads_count", len(changedAds),
		"since", lastUpdated)

	indexingStart := time.Now()
	activeCount := 0
	inactiveCount := 0

	for _, ad := range changedAds {
		adID := uint32(ad.AdID)

		isActive := strings.EqualFold(ad.Status, "ACTIVE") && strings.EqualFold(ad.CampaignStatus, "ACTIVE") &&
			time.Now().After(ad.StartDate) && (ad.EndDate == nil || time.Now().Before(*ad.EndDate))

		if isActive {
			activeCount++
			idx.Ads[adID] = &ad

			// Remove old entries if they exist (for updates)
			removeAdFromBitmaps(idx, adID)

			// Re-index by Geo
			for _, country := range ad.Countries {
				if idx.GeoIndex[country.CountryISOCode] == nil {
					idx.GeoIndex[country.CountryISOCode] = roaring.NewBitmap()
				}
				idx.GeoIndex[country.CountryISOCode].Add(adID)
			}

			// Re-index by Device
			for _, device := range ad.Devices {
				if idx.DeviceIndex[device.DeviceType] == nil {
					idx.DeviceIndex[device.DeviceType] = roaring.NewBitmap()
				}
				idx.DeviceIndex[device.DeviceType].Add(adID)
			}

			// Re-index by Keyword
			for _, kw := range ad.Keywords {
				if idx.KeywordIndex[kw.Keyword] == nil {
					idx.KeywordIndex[kw.Keyword] = roaring.NewBitmap()
				}
				idx.KeywordIndex[kw.Keyword].Add(adID)
			}

			// Re-index by Topic
			for _, topic := range ad.Topics {
				topicID := topic.TopicID
				if idx.TopicIndex[topicID] == nil {
					idx.TopicIndex[topicID] = roaring.NewBitmap()
				}
				idx.TopicIndex[topicID].Add(adID)
			}

			// Re-index by Entity
			for _, entity := range ad.Entities {
				if idx.EntityIndex[entity.EntityID] == nil {
					idx.EntityIndex[entity.EntityID] = roaring.NewBitmap()
				}
				idx.EntityIndex[entity.EntityID].Add(adID)
			}
		} else {
			inactiveCount++
			delete(idx.Ads, adID)
			removeAdFromBitmaps(idx, adID)
		}
	}

	observability.Info(ctx, "IndexRefresh: Processed ads",
		"active_count", activeCount,
		"inactive_count", inactiveCount)

	indexingDuration := time.Since(indexingStart)

	// Update timestamp and store the new index
	idx.LastUpdated = time.Now()
	currentIndex.Store(idx)

	// Record detailed metrics
	observability.RecordIndexRefreshDetailed(ctx, observability.IndexRefreshStats{
		TotalAds:           len(idx.Ads),
		ActiveAdsProcessed: activeCount,
		InactiveAdsRemoved: inactiveCount,
		GeoIndexSize:       len(idx.GeoIndex),
		DeviceIndexSize:    len(idx.DeviceIndex),
		KeywordIndexSize:   len(idx.KeywordIndex),
		TopicIndexSize:     len(idx.TopicIndex),
		EntityIndexSize:    len(idx.EntityIndex),
		DBQueryDuration:    dbDuration,
		IndexingDuration:   indexingDuration,
		TotalDuration:      time.Since(totalStart),
	})

	return idx, nil
}

func removeAdFromBitmaps(idx *GlobalIndex, adID uint32) {
	for _, bitmap := range idx.GeoIndex {
		bitmap.Remove(adID)
	}
	for _, bitmap := range idx.DeviceIndex {
		bitmap.Remove(adID)
	}
	for _, bitmap := range idx.KeywordIndex {
		bitmap.Remove(adID)
	}
	for _, bitmap := range idx.TopicIndex {
		bitmap.Remove(adID)
	}
	for _, bitmap := range idx.EntityIndex {
		bitmap.Remove(adID)
	}
}

func (idx *GlobalIndex) Clone() *GlobalIndex {
	newIdx := &GlobalIndex{
		GeoIndex:     make(map[string]*roaring.Bitmap),
		DeviceIndex:  make(map[string]*roaring.Bitmap),
		KeywordIndex: make(map[string]*roaring.Bitmap),
		TopicIndex:   make(map[int32]*roaring.Bitmap),
		EntityIndex:  make(map[string]*roaring.Bitmap),
		Ads:          make(map[uint32]*models.Ad, len(idx.Ads)),
		LastUpdated:  time.Now(),
	}

	for k, v := range idx.GeoIndex {
		newIdx.GeoIndex[k] = v.Clone()
	}
	for k, v := range idx.DeviceIndex {
		newIdx.DeviceIndex[k] = v.Clone()
	}
	for k, v := range idx.KeywordIndex {
		newIdx.KeywordIndex[k] = v.Clone()
	}
	for k, v := range idx.TopicIndex {
		newIdx.TopicIndex[k] = v.Clone()
	}
	for k, v := range idx.EntityIndex {
		newIdx.EntityIndex[k] = v.Clone()
	}
	for k, v := range idx.Ads {
		newIdx.Ads[k] = v
	}
	return newIdx

}

func (idx *GlobalIndex) FindCandidates(requestContext contextextractor.RequestContext,
	pageCtx models.PageContext) map[uint32]*models.Ad {
	start := time.Now()
	ctx := context.Background()

	if idx == nil {
		observability.RecordIndexLookup(ctx, "find_candidates", 0, time.Since(start))
		return nil
	}

	var candidates *roaring.Bitmap
	if requestContext.Geo.Country != "" {
		candidates = idx.GeoIndex[requestContext.Geo.Country]
	}

	if candidates == nil {
		// No geo match or empty country — include all ads as candidates
		candidates = roaring.NewBitmap()
		for adID := range idx.Ads {
			candidates.Add(adID)
		}
	} else {
		// Clone to avoid modifying the original bitmap
		candidates = candidates.Clone()
	}

	if deviceBitmap := idx.DeviceIndex[requestContext.Device.Device]; deviceBitmap != nil {
		candidates.And(deviceBitmap)
	}

	contextMatches := roaring.NewBitmap()
	for kw := range pageCtx.Keywords {
		if kwBitmap, exists := idx.KeywordIndex[kw]; exists {
			contextMatches.Or(kwBitmap)
		}
	}

	for topicIdStr := range pageCtx.Topics {
		topicId, err := strconv.ParseInt(topicIdStr, 10, 32)
		if err != nil {
			continue
		}
		if topicBitmap, exists := idx.TopicIndex[int32(topicId)]; exists {
			contextMatches.Or(topicBitmap)
		}
	}

	for _, entity := range pageCtx.Entities {
		if entityBitmap, exists := idx.EntityIndex[entity.Text]; exists {
			contextMatches.Or(entityBitmap)
		}
	}

	candidates.And(contextMatches)
	resultAds := make(map[uint32]*models.Ad)
	it := candidates.Iterator()
	for it.HasNext() {
		adID := it.Next()
		if ad, exists := idx.Ads[adID]; exists {
			resultAds[adID] = ad
		}
	}

	observability.RecordIndexLookup(ctx, "find_candidates", len(resultAds), time.Since(start))
	return resultAds
}
