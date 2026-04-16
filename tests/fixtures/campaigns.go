package fixtures

import "github.com/folaraz/contextual-ads-server/tests/client"

type CampaignTemplate struct {
	Industry     string
	CampaignName string
	Creative     CreativeData
	Targeting    TargetingData
}

type CreativeData struct {
	Headline       string
	Description    string
	ImageURL       string
	CallToAction   string
	LandingPageURL string
	CreativeType   string
}

var SampleImageURLs = map[string][]string{
	"e-commerce": {
		"https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1607082349566-187342175e2f?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1556742111-a301076d9d18?w=1200&h=630&fit=crop",
	},
	"saas": {
		"https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1551434678-e076c223a692?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=1200&h=630&fit=crop",
	},
	"entertainment": {
		"https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=1200&h=630&fit=crop",
	},
	"education": {
		"https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1427504494785-3a9ca7044f45?w=1200&h=630&fit=crop",
	},
	"finance": {
		"https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1579532537598-459ecdaf39cc?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1559526324-593bc073d938?w=1200&h=630&fit=crop",
	},
	"healthcare": {
		"https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?w=1200&h=630&fit=crop",
	},
	"travel": {
		"https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=1200&h=630&fit=crop",
	},
	"automotive": {
		"https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1542362567-b07e54358753?w=1200&h=630&fit=crop",
	},
	"food-beverage": {
		"https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=1200&h=630&fit=crop",
	},
	"technology": {
		"https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=1200&h=630&fit=crop",
	},
	"fashion": {
		"https://images.unsplash.com/photo-1445205170230-053b83016050?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1483985988355-763728e1935b?w=1200&h=630&fit=crop",
	},
	"sports": {
		"https://images.unsplash.com/photo-1461896836934- voices-7?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1517649763962-0c623066013b?w=1200&h=630&fit=crop",
		"https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=1200&h=630&fit=crop",
	},
}

func GetImageURLs(industry string) []string {
	if urls, ok := SampleImageURLs[industry]; ok {
		return urls
	}
	return SampleImageURLs["e-commerce"]
}

func BuildCampaignRequest(
	advertiserID int32,
	campaignName string,
	status string,
	budget float64,
	bidAmount float64,
	dailyBudget float64,
	pricingModel string,
	startDate string,
	endDate string,
	creative CreativeData,
	targeting TargetingData,
	countries []string,
	devices []string,
) client.CreateCampaignRequest {
	var entities []client.EntityInput
	for _, e := range targeting.Entities {
		entities = append(entities, client.EntityInput{
			Type: e.Type,
			Name: e.Name,
		})
	}

	return client.CreateCampaignRequest{
		AdvertiserID: advertiserID,
		Campaign: client.CampaignInput{
			Name:      campaignName,
			Status:    status,
			Budget:    budget,
			Currency:  "USD",
			StartDate: startDate,
			EndDate:   endDate,
		},
		AdSet: client.AdSetInput{
			Name:         campaignName + " Ad Set",
			BidAmount:    bidAmount,
			DailyBudget:  dailyBudget,
			PricingModel: pricingModel,
		},
		Creative: client.CreativeInput{
			Headline:       creative.Headline,
			Description:    creative.Description,
			ImageURL:       creative.ImageURL,
			CallToAction:   creative.CallToAction,
			LandingPageURL: creative.LandingPageURL,
			Status:         "ACTIVE",
			CreativeType:   creative.CreativeType,
		},
		Targeting: client.TargetingInput{
			Keywords:  targeting.Keywords,
			Topics:    targeting.Topics,
			Entities:  entities,
			Countries: countries,
			Devices:   devices,
		},
	}
}
