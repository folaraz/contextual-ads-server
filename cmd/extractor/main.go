package main

//
//import (
//	"encoding/json"
//	"fmt"
//	"log"
//	"math"
//	"math/rand"
//	"sort"
//	"time"
//)
//
//// ------------------------- Data models -------------------------
//
//type Advertiser struct {
//	ID       string
//	Name     string
//	Budget   float64 // total remaining budget (USD)
//	Currency string
//}
//
//type Campaign struct {
//	ID          string
//	Name        string
//	Start       time.Time
//	End         time.Time
//	DailyBudget float64
//	Status      string // "active", "paused", "ended"
//}
//
//type Ad struct {
//	ID            string
//	AdvertiserID  string
//	CampaignID    string
//	Title         string
//	LandingURL    string
//	IABCategories []string
//	Keywords      []string
//	Embedding     []float64
//	BidCPC        float64 // advertiser bid per click in USD
//	QualityScore  float64 // 0..1 (or >1 scaling). We'll keep 0..2
//	// Historical metrics for priors
//	Impressions int
//	Clicks      int
//	CreatedAt   time.Time
//	// Runtime fields not persisted:
//	Active bool
//}
//
//// AuctionCandidate: ad + runtime scores
//type AuctionCandidate struct {
//	Ad
//	Similarity     float64
//	PredictedCTR   float64
//	EffectiveBid   float64 // bid * predicted_ctr * quality
//	FinalRankScore float64 // same as EffectiveBid (alias) - helps clarity
//}
//
//// AuctionResult for one slot
//type AuctionResult struct {
//	SlotIndex int
//	Winner    AuctionCandidate
//	PricePaid float64 // price per click (CPC), computed via second-price rule
//}
//
//// ------------------------- Helpers -------------------------
//
//// cosineSimilarity computes cosine similarity of two vectors of equal length.
//func cosineSimilarity(a, b []float64) float64 {
//	if len(a) == 0 || len(b) == 0 || len(a) != len(b) {
//		return 0.0
//	}
//	var dot, na, nb float64
//	for i := range a {
//		dot += a[i] * b[i]
//		na += a[i] * a[i]
//		nb += b[i] * b[i]
//	}
//	if na == 0 || nb == 0 {
//		return 0
//	}
//	return dot / (math.Sqrt(na) * math.Sqrt(nb))
//}
//
//// clamp keeps value between min and max.
//func clamp(val, min, max float64) float64 {
//	if val < min {
//		return min
//	}
//	if val > max {
//		return max
//	}
//	return val
//}
//
//// nowISO helper
//func nowISO() string {
//	return time.Now().UTC().Format(time.RFC3339)
//}
//
//// ------------------------- Auction logic -------------------------
//
//// BayesianSmoothedCTR returns a smoothed CTR estimate using Beta/Bayesian smoothing.
//// alpha: pseudo-clicks, beta: pseudo-impressions. Typical alpha=1, beta=100 => prior=0.01
//func BayesianSmoothedCTR(clicks, impressions int, alpha, beta float64) float64 {
//	return (float64(clicks) + alpha) / (float64(impressions) + beta)
//}
//
//// selectCandidates applies filters and returns candidates limited by maxCandidates.
//// Filters: similarity threshold, iab matching (if any), active status, campaign status, budget > minBid*someFactor.
//func selectCandidates(ads []Ad, pageEmbedding []float64, pageIAB []string, minSimilarity float64, maxCandidates int, advertisers map[string]*Advertiser, campaigns map[string]*Campaign, minBid float64, now time.Time) []AuctionCandidate {
//	cands := make([]AuctionCandidate, 0, len(ads))
//	iabSet := make(map[string]struct{})
//	for _, t := range pageIAB {
//		iabSet[t] = struct{}{}
//	}
//
//	for _, ad := range ads {
//		// active/campaign checks
//		if !ad.Active {
//			continue
//		}
//		camp, ok := campaigns[ad.CampaignID]
//		if !ok || camp.Status != "active" {
//			continue
//		}
//		adv, ok := advertisers[ad.AdvertiserID]
//		if !ok || adv.Budget <= 0.0 {
//			continue
//		}
//		// Check campaign date range
//		if now.Before(camp.Start) || now.After(camp.End) {
//			continue
//		}
//		// Bid floor
//		if ad.BidCPC < minBid {
//			continue
//		}
//
//		// similarity
//		sim := cosineSimilarity(pageEmbedding, ad.Embedding)
//		if sim < minSimilarity {
//			// fallback: allow if IAB matches strongly - (tunable)
//			matchIAB := false
//			if len(iabSet) > 0 {
//				for _, cat := range ad.IABCategories {
//					if _, ok := iabSet[cat]; ok {
//						matchIAB = true
//						break
//					}
//				}
//			}
//			if !matchIAB {
//				continue
//			}
//		}
//
//		cands = append(cands, AuctionCandidate{
//			Ad:         ad,
//			Similarity: sim,
//		})
//	}
//
//	// if too many, keep top-K by similarity as a simple pruning strategy
//	if len(cands) > maxCandidates {
//		sort.Slice(cands, func(i, j int) bool {
//			return cands[i].Similarity > cands[j].Similarity
//		})
//		cands = cands[:maxCandidates]
//	}
//	return cands
//}
//
//// scoreCandidates fills PredictedCTR and EffectiveBid fields.
//// predicted CTR uses Bayesian smoothing on historical clicks/impressions and optionally a "cold-start" prior.
//func scoreCandidates(cands []AuctionCandidate, alpha, beta float64) []AuctionCandidate {
//	for i := range cands {
//		// compute smoothed CTR prior
//		smoothed := BayesianSmoothedCTR(cands[i].Clicks, cands[i].Impressions, alpha, beta)
//		// incorporate similarity into predicted CTR — this is a simple approach:
//		// predicted_ctr = smoothedCTR * (0.6) + similarity * 0.4 * baseFactor
//		// We normalize similarity (it is between -1 and 1 but for embeddings usually 0..1)
//		simFactor := clamp(cands[i].Similarity, 0.0, 1.0)
//		// base awake: small factor to allow similarity to matter even for cold ads
//		predicted := 0.6*smoothed + 0.4*(0.01+0.99*simFactor) // blend prior with similarity-derived proxy
//		// clamp to safe bounds
//		predicted = clamp(predicted, 0.0001, 0.5) // avoid zero or huge values
//		cands[i].PredictedCTR = predicted
//
//		// effective bid = bidCPC * predictedCTR * qualityScore
//		// ensure quality score exists
//		qs := clamp(cands[i].QualityScore, 0.01, 2.0)
//		cands[i].EffectiveBid = cands[i].BidCPC * cands[i].PredictedCTR * qs
//		cands[i].FinalRankScore = cands[i].EffectiveBid
//	}
//	return cands
//}
//
//// runSecondPriceAuction takes scored candidates and returns winners for `slots` slots.
//// Pricing: for single slot it charges (secondScore / winner.predictedCTR). For multiple slots we use a simple iterative second-price:
//// winner pays enough to beat the next advertiser's effective bid adjusted by CTR; for slot i paying price = (nextCandidate.EffectiveBid / winner.PredictedCTR).
//// We also ensure a reserve price (minimum price per click).
//func runSecondPriceAuction(cands []AuctionCandidate, slots int, reservePrice float64, frequencyCaps map[string]map[string]int, userID string, freqCapPerAd int, advertisers map[string]*Advertiser) []AuctionResult {
//	// sort descending by effective bid
//	sort.Slice(cands, func(i, j int) bool {
//		return cands[i].FinalRankScore > cands[j].FinalRankScore
//	})
//	results := []AuctionResult{}
//
//	usedAdvertisers := map[string]struct{}{}
//	i := 0
//	for slot := 0; slot < slots && i < len(cands); i++ {
//		c := cands[i]
//
//		// skip advertiser duplicates for separate slots (common rule)
//		if _, used := usedAdvertisers[c.AdvertiserID]; used {
//			continue
//		}
//
//		// frequency cap check per user (simple)
//		if freqCapPerAd > 0 && userID != "" {
//			if freqMap, ok := frequencyCaps[userID]; ok {
//				count := freqMap[c.ID]
//				if count >= freqCapPerAd {
//					continue // skip this ad
//				}
//			}
//		}
//
//		// determine next highest candidate (j = next index after i that is from different advertiser)
//		nextIdx := -1
//		for j := i + 1; j < len(cands); j++ {
//			if cands[j].AdvertiserID != c.AdvertiserID {
//				nextIdx = j
//				break
//			}
//		}
//
//		price := reservePrice // default
//		if nextIdx >= 0 {
//			// second-price formula: price (CPC) = next.EffectiveBid / winner.predictedCTR
//			// ensure winner.predictedCTR > 0 to avoid divide by zero
//			if c.PredictedCTR > 0 {
//				rawPrice := cands[nextIdx].EffectiveBid / c.PredictedCTR
//				price = math.Max(price, rawPrice)
//			}
//		} else {
//			// no next bidder -> pay reserve or minimal
//			if c.PredictedCTR > 0 {
//				// fallback: price = reserve or small fraction of bid
//				price = math.Max(price, 0.5*c.BidCPC) // heuristic
//			}
//		}
//
//		// clamp price to not exceed winner's bid (seller rule)
//		price = math.Min(price, c.BidCPC)
//
//		// budget check and deduction (deduct expected cost by floor estimate; here we just check if advertiser has budget >= price)
//		adv := advertisers[c.AdvertiserID]
//		if adv == nil {
//			continue
//		}
//		if adv.Budget < price {
//			// skip if budget insufficient
//			continue
//		}
//
//		// allocate
//		result := AuctionResult{
//			SlotIndex: slot,
//			Winner:    c,
//			PricePaid: price,
//		}
//		results = append(results, result)
//
//		// Deduct budget conservatively: advertisers are charged on click, not impression.
//		// But to pace budget, we can deduct an expected small amount (e.g., price * predicted_ctr) or reserve budget for impression.
//		expectedCost := price * c.PredictedCTR // expected spend per impression
//		adv.Budget = adv.Budget - expectedCost
//		if adv.Budget < 0 {
//			adv.Budget = 0
//		}
//
//		// update frequency cap
//		if userID != "" {
//			if _, ok := frequencyCaps[userID]; !ok {
//				frequencyCaps[userID] = map[string]int{}
//			}
//			frequencyCaps[userID][c.ID] = frequencyCaps[userID][c.ID] + 1
//		}
//
//		usedAdvertisers[c.AdvertiserID] = struct{}{}
//		slot++
//	}
//	return results
//}
//
//// ------------------------- Example dataset & driver -------------------------
//
//// randVector returns a normalized random vector of dim length.
//func randVector(dim int) []float64 {
//	v := make([]float64, dim)
//	var sum float64
//	for i := 0; i < dim; i++ {
//		val := rand.NormFloat64()
//		v[i] = val
//		sum += val * val
//	}
//	norm := math.Sqrt(sum)
//	if norm == 0 {
//		norm = 1.0
//	}
//	for i := range v {
//		v[i] = v[i] / norm
//	}
//	return v
//}
//
//func makeSampleAds(n int, dim int) ([]Ad, map[string]*Advertiser, map[string]*Campaign) {
//	ads := make([]Ad, 0, n)
//	advertisers := make(map[string]*Advertiser)
//	campaigns := make(map[string]*Campaign)
//	now := time.Now()
//
//	// make 10 advertisers
//	for i := 0; i < 10; i++ {
//		id := fmt.Sprintf("adv_%02d", i+1)
//		advertisers[id] = &Advertiser{
//			ID:       id,
//			Name:     fmt.Sprintf("Adv %02d", i+1),
//			Budget:   100.0 + float64(rand.Intn(400)), // $100..$500
//			Currency: "USD",
//		}
//	}
//
//	// one campaign per adv
//	for _, adv := range advertisers {
//		cid := "camp_" + adv.ID
//		campaigns[cid] = &Campaign{
//			ID:          cid,
//			Name:        fmt.Sprintf("Camp for %s", adv.Name),
//			Start:       now.Add(-24 * time.Hour),
//			End:         now.Add(30 * 24 * time.Hour),
//			DailyBudget: 50.0,
//			Status:      "active",
//		}
//	}
//
//	iabSamples := [][]string{
//		{"Technology"},
//		{"Sports"},
//		{"Travel"},
//		{"Entertainment"},
//		{"Finance"},
//		{"Health"},
//		{"Autos"},
//		{"Food"},
//		{"Education"},
//		{"Shopping"},
//	}
//	keywordSamples := [][]string{
//		{"golang", "programming"},
//		{"football", "match"},
//		{"vacation", "resort"},
//		{"music", "streaming"},
//		{"credit card", "loans"},
//		{"fitness", "workout"},
//		{"cars", "sedan"},
//		{"recipes", "cooking"},
//		{"university", "course"},
//		{"sale", "discount"},
//	}
//
//	rand.Seed(time.Now().UnixNano())
//	for i := 0; i < n; i++ {
//		advIdx := (i % len(advertisers)) + 1
//		advID := fmt.Sprintf("adv_%02d", advIdx)
//		campID := "camp_" + advID
//		iab := iabSamples[i%len(iabSamples)]
//		kw := keywordSamples[i%len(keywordSamples)]
//
//		ad := Ad{
//			ID:            fmt.Sprintf("ad_%04d", i+1),
//			AdvertiserID:  advID,
//			CampaignID:    campID,
//			Title:         fmt.Sprintf("Ad %04d headline about %s", i+1, kw[0]),
//			LandingURL:    fmt.Sprintf("https://example.com/%d", i+1),
//			IABCategories: iab,
//			Keywords:      kw,
//			Embedding:     randVector(dim),
//			BidCPC:        0.05 + rand.Float64()*2.0, // 0.05..2.05
//			QualityScore:  0.6 + rand.Float64()*0.9,  // 0.6..1.5
//			Impressions:   rand.Intn(1000),
//			Clicks:        rand.Intn(50),
//			CreatedAt:     now.Add(-time.Duration(rand.Intn(1000)) * time.Hour),
//			Active:        true,
//		}
//		ads = append(ads, ad)
//	}
//
//	return ads, advertisers, campaigns
//}
//
//func prettyPrint(v interface{}) {
//	b, _ := json.MarshalIndent(v, "", "  ")
//	fmt.Println(string(b))
//}
//
//// ------------------------- main -------------------------
//
//func main() {
//	// config / thresholds
//	minSimilarity := 0.25 // low-ish for recall; tune up to 0.6 for stricter relevance
//	maxCandidates := 200
//	minBid := 0.02       // ignore ads below this bid
//	alpha := 1.0         // bayesian smoothing alpha
//	beta := 100.0        // beta -> prior ~ 1%
//	reservePrice := 0.01 // minimum CPC seller wants
//	slots := 3           // number of ad slots on page
//	freqCapPerAd := 3    // impressions per user per ad per day
//
//	// bootstrap dataset
//	dim := 64
//	ads, advertisers, campaigns := makeSampleAds(120, dim)
//
//	// simulate a page request
//	pageEmbedding := randVector(dim)
//	pageIAB := []string{"Technology"} // page IAB classification
//	userID := "user_abc_123"
//	now := time.Now()
//
//	// frequency map user->ad->count (normally stored in Redis)
//	frequencyCaps := map[string]map[string]int{}
//
//	// Step 1: Candidate selection (filtering)
//	cands := selectCandidates(ads, pageEmbedding, pageIAB, minSimilarity, maxCandidates, advertisers, campaigns, minBid, now)
//	log.Printf("candidates selected: %d\n", len(cands))
//
//	// Step 2: Scoring (predict CTR, effective bid)
//	cands = scoreCandidates(cands, alpha, beta)
//
//	// Step 3: Auction run
//	results := runSecondPriceAuction(cands, slots, reservePrice, frequencyCaps, userID, freqCapPerAd, advertisers)
//
//	// Output results
//	fmt.Printf("AUCTION RUN @ %s\n", nowISO())
//	fmt.Printf("Page IAB: %v\n", pageIAB)
//	fmt.Printf("Slots: %d\n", slots)
//	fmt.Println("---- WINNERS ----")
//	for _, r := range results {
//		fmt.Printf("Slot %d: Ad %s (Adv %s) | Similarity %.4f | PredCTR %.5f | Bid $%.3f | PricePaid $%.4f | RemainingAdvBudget $%.2f\n",
//			r.SlotIndex+1,
//			r.Winner.ID,
//			r.Winner.AdvertiserID,
//			r.Winner.Similarity,
//			r.Winner.PredictedCTR,
//			r.Winner.BidCPC,
//			r.PricePaid,
//			advertisers[r.Winner.AdvertiserID].Budget,
//		)
//	}
//	if len(results) == 0 {
//		fmt.Println("No winners (no eligible ads matched).")
//	}
//
//	// small audit: print top 5 candidates by EffectiveBid
//	sort.Slice(cands, func(i, j int) bool {
//		return cands[i].FinalRankScore > cands[j].FinalRankScore
//	})
//	fmt.Println("\nTop 5 candidates by EffectiveBid:")
//	for i := 0; i < 5 && i < len(cands); i++ {
//		c := cands[i]
//		fmt.Printf("%d) Ad %s | EffBid %.8f | Bid %.3f | PredCTR %.5f | Quality %.3f | Sim %.4f\n",
//			i+1, c.ID, c.EffectiveBid, c.BidCPC, c.PredictedCTR, c.QualityScore, c.Similarity)
//	}
//}
