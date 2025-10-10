package main

import (
	"github.com/folaraz/contextual-ads-server/internal/storage"
	"github.com/folaraz/contextual-ads-server/internal/utils"
)

type Ad struct {
	ID       string   `json:"id"`
	Title    string   `json:"title"`
	Url      string   `json:"url"`
	Keywords []string `json:"keywords"`
	Bid      float64  `json:"bid"`
}

var ads = []Ad{
	{ID: "1", Title: "Buy Football Shoes", Url: "https://example.com/football", Keywords: []string{"football", "sports"}, Bid: 0.5},
	{ID: "2", Title: "Best Laptops 2025", Url: "https://example.com/laptops", Keywords: []string{"tech", "laptop"}, Bid: 0.8},
	{ID: "3", Title: "Healthy Recipes", Url: "https://example.com/recipes", Keywords: []string{"food", "health"}, Bid: 0.3},
}

func GetAd(url string, keyword []string) Ad {
	var matched Ad
	urlHash, _, _ := utils.GenerateHashAndURL(url)
	urlContext := storage.GetContext(urlHash)
	return matched
}
