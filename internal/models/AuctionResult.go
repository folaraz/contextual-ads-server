package models

type AuctionCandidate struct {
	Ad             Ad
	Similarity     float64
	PredictedCTR   float64 // predicted click-through rate
	QualityScore   float64 // quality score based on relevance
	NormalizedBid  float64 // normalized bid amount
	EffectiveBid   float64 // bid * predicted_ctr * quality
	FinalRankScore float64 // final score used for ranking in the auction
}

type AuctionResult struct {
	Winner    AuctionCandidate
	PricePaid float64 // price per click (CPC), computed via second-price rule, CVR * CPM, etc.
}
