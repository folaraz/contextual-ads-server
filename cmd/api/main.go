package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/models/request"
	"github.com/folaraz/contextual-ads-server/internal/storage"
)

func init() {
	contextextractor.InitRequestExtractorDB()
	err := storage.LoadAdContentToProductMapping()
	if err != nil {
		return
	}
}

func adHandler(w http.ResponseWriter, r *http.Request) {

	var adRequest request.AdRequest
	if err := json.NewDecoder(r.Body).Decode(&adRequest); err != nil {
		fmt.Printf("Error decoding request payload: %v\n", err)
		http.Error(w, fmt.Sprintf("Invalid request payload: %v", err), http.StatusBadRequest)
		return
	}
	requestContext := contextextractor.RetrieveRequestContext(r)

	fmt.Printf("Received AdRequest: %+v\n", adRequest)

	var matched []models.AdRankResult
	requestContext := contextextractor.RetrieveRequestContext(r)
	fmt.Printf("Request Context: %+v\n", requestContext)
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

	response := AdResponse{
		AdID:        fmt.Sprintf("test-ad-%d", time.Now().UnixNano()),
		PublisherID: "publisher-123",
		Type:        "html",
		Creative:    `<div style="padding:40px;background:brown;color:white;text-align:center;border-radius:8px;"><h2>Test Ad</h2><p>Click tracking enabled</p></div>`,
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

	_ = pageURL  // to avoid unused variable warning if not used later
	_ = adID     // to avoid unused variable warning if not used later
	_ = clickURL // to avoid unused variable warning if not used later

	// have a logic to determin if you want to record the event as it might have been recorded already.

	fmt.Printf("Received Event: %+v\n", "testing")

	//todo log the click event to storage or analytics system. Maybe some in memory queue system for batching.
	// Think about deduplication of clicks(idempotency). Maybe as part of the ad response payload create a unique id. Will think about it further later.

	http.Redirect(w, r, "testing", http.StatusFound)
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
