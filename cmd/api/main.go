package main

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/storage"
	"github.com/folaraz/contextual-ads-server/internal/utils"
)

func GetAd(url string) []models.AdRankResult {
	urlHash, _ := utils.GenerateHashAndURL(url)
	fmt.Println(urlHash)
	pageContext := storage.GetContext(urlHash)
	qualifiedAds := storage.QueryAds(pageContext)
	return qualifiedAds
}

func adHandler(w http.ResponseWriter, r *http.Request) {
	url := r.URL.Query().Get("url")
	var matched []models.AdRankResult
	matched = GetAd(url)

	var response []struct {
		Creative    models.Creative `json:"creative"`
		VectorScore float64         `json:"vector_score"`
	}
	for _, ad := range matched {
		response = append(response, struct {
			Creative    models.Creative `json:"creative"`
			VectorScore float64         `json:"vector_score"`
		}{
			Creative:    ad.Ad.Creative,
			VectorScore: ad.VectorScore,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	err := json.NewEncoder(w).Encode(response)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func createAdInventory() {

}

// request comes in with url and keywords.
// checks cache for embeddings and usese that to query for the ads from inventory
// matching engine for right ads to display
// todo expose api to get vector representation of url from storage
// run query to get the top k ads that matches the vector from the inventory
// run the matching engine to get the bid winner for the ad and return it to the client
func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /ads", adHandler)

	err := http.ListenAndServe(":8080", mux)
	if err != nil {
		fmt.Println(err)
	}
}
