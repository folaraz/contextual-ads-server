package models

import "github.com/folaraz/contextual-ads-server/internal/publisher"

type AuctionCandidate struct {
	Ad             Ad
	PacingScore    float64
	Similarity     float64 // vector similarity score
	PredictedCTR   float64 // predicted click-through rate
	QualityScore   float64 // quality score based on relevance
	NormalizedBid  float64 // normalized bid amount
	EffectiveBid   float64 // eCPM (effective cost per mille)
	FinalRankScore float64 // final score used for ranking
}

type AuctionStats struct {
	TotalCandidates     int // Total ads considered initially
	FilteredByTargeting int // Ads filtered due to targeting mismatch
	FilteredByBudget    int // Ads filtered due to budget/pacing
	EligibleForAuction  int // Ads that entered the auction
}

type AuctionResult struct {
	Winner    *AuctionCandidate  // winning ad (nil if no winner)
	RunnerUps []AuctionCandidate // other candidates sorted by rank
	PricePaid float64            // clearing price (second-price auction)
	HasWinner bool
	PageHash  string
	AuctionID string
	Stats     AuctionStats // Filtering statistics
}

func (r *AuctionResult) Empty() bool {
	return !r.HasWinner
}

func (r *AuctionResult) AllCandidates() []AuctionCandidate {
	if !r.HasWinner {
		return r.RunnerUps
	}
	all := make([]AuctionCandidate, 0, 1+len(r.RunnerUps))
	all = append(all, *r.Winner)
	all = append(all, r.RunnerUps...)
	return all
}

func (r *AuctionResult) TopN(n int) []AuctionCandidate {
	all := r.AllCandidates()
	if n >= len(all) {
		return all
	}
	return all[:n]
}

func (r *AuctionResult) LengthOfCandidates() int {
	if r.HasWinner {
		return 1 + len(r.RunnerUps)
	}
	return len(r.RunnerUps)
}

func (r *AuctionResult) GetWinningAuctionCandidateForEvent() *publisher.AuctionCandidate {
	if r.Winner == nil {
		return nil
	}
	return &publisher.AuctionCandidate{
		AdID:           r.Winner.Ad.AdID,
		CampaignID:     r.Winner.Ad.CampaignID,
		PacingScore:    r.Winner.PacingScore,
		Similarity:     r.Winner.Similarity,
		QualityScore:   r.Winner.QualityScore,
		NormalizedBid:  r.Winner.NormalizedBid,
		EffectiveBid:   r.Winner.EffectiveBid,
		FinalRankScore: r.Winner.FinalRankScore,
	}
}

func (r *AuctionResult) GetRunnerUpAuctionCandidatesForEvent() []publisher.AuctionCandidate {
	candidates := make([]publisher.AuctionCandidate, 0, len(r.RunnerUps))
	for _, candidate := range r.RunnerUps {
		candidates = append(candidates, publisher.AuctionCandidate{
			AdID:           candidate.Ad.AdID,
			CampaignID:     candidate.Ad.CampaignID,
			PacingScore:    candidate.PacingScore,
			Similarity:     candidate.Similarity,
			QualityScore:   candidate.QualityScore,
			NormalizedBid:  candidate.NormalizedBid,
			EffectiveBid:   candidate.EffectiveBid,
			FinalRankScore: candidate.FinalRankScore,
		})
	}
	return candidates
}
