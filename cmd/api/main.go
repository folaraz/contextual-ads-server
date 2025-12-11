package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/auction"
	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/storage"
	"github.com/folaraz/contextual-ads-server/internal/utils"
)

type AdRequest struct {
	SlotID      string  `json:"slotId"`
	PublisherID string  `json:"publisherId"`
	Sizes       [][]int `json:"sizes"`
	Context     Context `json:"context"`
	Device      Device  `json:"device"`
	Meta        Meta    `json:"meta"`
}

type Context struct {
	URL         string   `json:"url"`
	Keywords    []string `json:"keywords"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
}

type Device struct {
	Type      string `json:"type"`
	UserAgent string `json:"userAgent"`
	Language  string `json:"language"`
}

type Meta struct {
	Timestamp int64 `json:"timestamp"`
}

type EventPayload struct {
	AdID        string `json:"adId"`
	EventType   string `json:"eventType"`
	Timestamp   int64  `json:"timestamp"`
	URL         string `json:"url"`
	ClickURL    string `json:"clickUrl"`
	PublisherID string `json:"publisherId"`
}

type AdTestResponse struct {
	AdID     string `json:"adId"`
	Type     string `json:"type"`
	Creative string `json:"creative"`
	ClickURL string `json:"clickUrl"`
}

func init() {
	contextextractor.InitRequestExtractorDB()
	err := storage.LoadAdContentToProductMapping()
	if err != nil {
		return
	}
}

func GetAd(url string) models.AuctionResult {
	urlHash, _ := utils.GenerateHashAndURL(url)
	fmt.Println(urlHash)
	pageContext := storage.GetContext(urlHash)
	qualifiedAds := storage.QueryAds(pageContext)
	result := auction.RunAdAuction(qualifiedAds, pageContext)
	return result
}

func adHandler(w http.ResponseWriter, r *http.Request) {

	var adRequest AdRequest
	if err := json.NewDecoder(r.Body).Decode(&adRequest); err != nil {
		fmt.Printf("Error decoding request payload: %v\n", err)
		http.Error(w, fmt.Sprintf("Invalid request payload: %v", err), http.StatusBadRequest)
		return
	}

	fmt.Printf("Received AdRequest: %+v\n", adRequest)

	var matched []models.AdRankResult
	requestContext := contextextractor.RetrieveRequestContext(r)
	//fmt.Printf("Request Context: %+v\n", requestContext)
	_ = requestContext
	_ = matched
	fmt.Println(r)
	//matched = GetAd(url)

	//Ad_Response = {
	//ad_id: "ad_23456",
	//	creative: {
	//	title: "Monday.com - Work Management Made Easy",
	//		description: "Manage projects, track tasks...",
	//			image_url: "https://cdn.monday.com/ad_banner_123.jpg",
	//			click_url: "https://adserver.com/click?ad=23456&page=page_technews_12345",
	//			impression_url: "https://adserver.com/imp?ad=23456",
	//			cta: "Try Free"
	//	},
	//metadata: {
	//price_cpm: 3.81,
	//	relevance_score: 0.931
	//}
	//}

	//Event_Log.write({
	//event: "ad_served",
	//	ad_id: "ad_23456",
	//		page_id: "page_technews_12345",
	//		user_id: "user_98765",
	//		price: 3.81,
	//		timestamp: "2025-10-19T14:35:42Z",
	//		matching_details: {
	//	keyword_score: 0.92,
	//		topic_score: 0.95,
	//			similarity_score: 0.91,
	//			best_section: "Section 3: Project Management"
	//	}
	//})

	//var response []struct {
	//	ID          string          `json:"id"`
	//	Creative    models.Creative `json:"creative"`
	//	VectorScore float64         `json:"vector_score"`
	//}
	//for _, ad := range matched {
	//	response = append(response, struct {
	//		ID          string          `json:"id"`
	//		Creative    models.Creative `json:"creative"`
	//		VectorScore float64         `json:"vector_score"`
	//	}{
	//		ID:          ad.Ad.ID,
	//		Creative:    ad.Ad.Creative,
	//		VectorScore: ad.VectorScore,
	//	})
	//}

	response := AdTestResponse{
		AdID:     fmt.Sprintf("test-ad-%d", time.Now().UnixNano()),
		Type:     "html",
		Creative: `<div style="padding:40px;background:brown;color:white;text-align:center;border-radius:8px;"><h2>Test Ad</h2><p>Click tracking enabled</p></div>`,
		//Security (Signing the URL)
		ClickURL: "https://example.com",
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(response); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func clickEventHandler(w http.ResponseWriter, r *http.Request) {
	adID := r.URL.Query().Get("adId")
	clickURL := r.URL.Query().Get("clickUrl")
	pageURL := r.URL.Query().Get("pageUrl")

	eventPayload := EventPayload{
		AdID:      adID,
		EventType: "click",
		Timestamp: time.Now().Unix(),
		URL:       pageURL,
		//we should check the cache for the clickURL mapping to avoid open redirector attack
		ClickURL: clickURL,
	}
	// have a logic to determin if you want to record the event as it might have been recorded already.

	fmt.Printf("Received Event: %+v\n", eventPayload)

	//todo log the click event to storage or analytics system. Maybe some in memory queue system for batching.
	// Think about deduplication of clicks(idempotency). Maybe as part of the ad response payload create a unique id. Will think about it further later.

	http.Redirect(w, r, eventPayload.ClickURL, http.StatusFound)
}

func impressionEventHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Printf("Received impression event\n")

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

		// Handle preflight requests
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		// Call the next handler
		next.ServeHTTP(w, r)
	})
}

// request comes in with url and keywords.
// checks cache for embeddings and usese that to query for the ads from inventory
// matching engine for right ads to display
// todo expose api to get vector representation of url from storage
// run query to get the top k ads that matches the vector from the inventory
// run the matching engine to get the bid winner for the ad and return it to the client
func main() {
	mux := http.NewServeMux()

	//get user agent from request header
	mux.HandleFunc("POST /v1/ads", adHandler)
	mux.HandleFunc("POST /v1/events/impression", impressionEventHandler)
	mux.HandleFunc("GET /v1/events/click", clickEventHandler)

	// Wrap the mux with CORS middleware
	handler := corsMiddleware(mux)

	err := http.ListenAndServe(":8080", handler)
	if err != nil {
		fmt.Println(err)
	}
}
