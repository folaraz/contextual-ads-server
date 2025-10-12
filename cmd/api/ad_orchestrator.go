package main

import (
	"fmt"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/storage"
	"github.com/folaraz/contextual-ads-server/internal/utils"
)

func GetAd(url string, keyword []string) models.Ad {
	var matched models.Ad
	urlHash, _, _ := utils.GenerateHashAndURL(url)
	pageContext := storage.GetContext(urlHash)
	qualifiedAds := storage.QueryAds(pageContext)
	fmt.Println(qualifiedAds)
	return matched
}
