package internal

import (
	"fmt"

	"github.com/folaraz/contextual-ads-server/internal/auction"
	"github.com/folaraz/contextual-ads-server/internal/contextextractor"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/storage"
	"github.com/folaraz/contextual-ads-server/internal/utils"
)

func GetAdRankResults(url string, requestContext contextextractor.RequestContext) models.AuctionResult {
	urlHash, _ := utils.GenerateHashAndURL(url)
	fmt.Println(urlHash)
	pageContext, err := storage.GetPageContext(urlHash)
	if err != nil {
		fmt.Printf("Error retrieving page context: %v\n", err)
		//todo needs updating can't just return empty
		return models.AuctionResult{}
	}
	qualifiedAds := storage.QueryAds(pageContext)
	result := auction.RunAdAuction(qualifiedAds, pageContext)
	return result
}
