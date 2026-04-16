package fixtures

import "github.com/folaraz/contextual-ads-server/tests/client"

type PublisherTemplate struct {
	NamePrefix string
	Domain     string
	Category   string
}

var PublisherTemplates = map[string][]PublisherTemplate{
	"news": {
		{NamePrefix: "Daily News", Domain: "dailynews.com", Category: "news"},
		{NamePrefix: "World Report", Domain: "worldreport.com", Category: "news"},
		{NamePrefix: "Breaking News Now", Domain: "breakingnewsnow.com", Category: "news"},
		{NamePrefix: "Global Times", Domain: "globaltimes.com", Category: "news"},
		{NamePrefix: "News Today", Domain: "newstoday.com", Category: "news"},
		{NamePrefix: "The Bulletin", Domain: "thebulletin.com", Category: "news"},
	},
	"blog": {
		{NamePrefix: "Tech Insights", Domain: "techinsights.blog", Category: "blog"},
		{NamePrefix: "Lifestyle Blog", Domain: "lifestyleblog.com", Category: "blog"},
		{NamePrefix: "Daily Thoughts", Domain: "dailythoughts.blog", Category: "blog"},
		{NamePrefix: "Creative Corner", Domain: "creativecorner.blog", Category: "blog"},
		{NamePrefix: "Digital Nomad", Domain: "digitalnomad.blog", Category: "blog"},
	},
	"e-commerce": {
		{NamePrefix: "Shop Central", Domain: "shopcentral.com", Category: "e-commerce"},
		{NamePrefix: "Deal Finder", Domain: "dealfinder.com", Category: "e-commerce"},
		{NamePrefix: "Best Buys", Domain: "bestbuys.shop", Category: "e-commerce"},
		{NamePrefix: "Online Mart", Domain: "onlinemart.com", Category: "e-commerce"},
		{NamePrefix: "Value Store", Domain: "valuestore.com", Category: "e-commerce"},
	},
	"entertainment": {
		{NamePrefix: "Movie Reviews", Domain: "moviereviews.com", Category: "entertainment"},
		{NamePrefix: "Gaming World", Domain: "gamingworld.com", Category: "entertainment"},
		{NamePrefix: "Music Central", Domain: "musiccentral.com", Category: "entertainment"},
		{NamePrefix: "Celebrity Watch", Domain: "celebritywatch.com", Category: "entertainment"},
		{NamePrefix: "Stream Guide", Domain: "streamguide.com", Category: "entertainment"},
	},
	"sports": {
		{NamePrefix: "Sports Daily", Domain: "sportsdaily.com", Category: "sports"},
		{NamePrefix: "Game Highlights", Domain: "gamehighlights.com", Category: "sports"},
		{NamePrefix: "Athlete Profiles", Domain: "athleteprofiles.com", Category: "sports"},
		{NamePrefix: "Fantasy League", Domain: "fantasyleague.com", Category: "sports"},
		{NamePrefix: "Fitness Zone", Domain: "fitnesszone.com", Category: "sports"},
	},
	"technology": {
		{NamePrefix: "Tech Crunch Daily", Domain: "techcrunchdaily.com", Category: "technology"},
		{NamePrefix: "Gadget Reviews", Domain: "gadgetreviews.tech", Category: "technology"},
		{NamePrefix: "AI News", Domain: "ainews.tech", Category: "technology"},
		{NamePrefix: "Dev Community", Domain: "devcommunity.io", Category: "technology"},
		{NamePrefix: "Startup Weekly", Domain: "startupweekly.com", Category: "technology"},
	},
	"lifestyle": {
		{NamePrefix: "Home Decor", Domain: "homedecor.com", Category: "lifestyle"},
		{NamePrefix: "Wellness Daily", Domain: "wellnessdaily.com", Category: "lifestyle"},
		{NamePrefix: "Beauty Insider", Domain: "beautyinsider.com", Category: "lifestyle"},
		{NamePrefix: "Fashion Forward", Domain: "fashionforward.com", Category: "lifestyle"},
		{NamePrefix: "Living Better", Domain: "livingbetter.com", Category: "lifestyle"},
	},
	"finance": {
		{NamePrefix: "Money Matters", Domain: "moneymatters.com", Category: "finance"},
		{NamePrefix: "Investment Weekly", Domain: "investmentweekly.com", Category: "finance"},
		{NamePrefix: "Crypto News", Domain: "cryptonews.finance", Category: "finance"},
		{NamePrefix: "Market Watch", Domain: "marketwatch-daily.com", Category: "finance"},
		{NamePrefix: "Personal Finance", Domain: "personalfinance.com", Category: "finance"},
	},
	"health": {
		{NamePrefix: "Health Tips", Domain: "healthtips.com", Category: "health"},
		{NamePrefix: "Medical News", Domain: "medicalnews.com", Category: "health"},
		{NamePrefix: "Nutrition Guide", Domain: "nutritionguide.com", Category: "health"},
		{NamePrefix: "Fitness Journal", Domain: "fitnessjournal.com", Category: "health"},
		{NamePrefix: "Mental Wellness", Domain: "mentalwellness.com", Category: "health"},
	},
	"travel": {
		{NamePrefix: "Travel Guide", Domain: "travelguide.com", Category: "travel"},
		{NamePrefix: "Destination Reviews", Domain: "destinationreviews.com", Category: "travel"},
		{NamePrefix: "Budget Traveler", Domain: "budgettraveler.com", Category: "travel"},
		{NamePrefix: "Adventure Seeker", Domain: "adventureseeker.com", Category: "travel"},
		{NamePrefix: "Luxury Travel", Domain: "luxurytravel.com", Category: "travel"},
	},
	"food": {
		{NamePrefix: "Recipe Hub", Domain: "recipehub.com", Category: "food"},
		{NamePrefix: "Food Critic", Domain: "foodcritic.com", Category: "food"},
		{NamePrefix: "Restaurant Reviews", Domain: "restaurantreviews.com", Category: "food"},
		{NamePrefix: "Cooking Tips", Domain: "cookingtips.com", Category: "food"},
		{NamePrefix: "Gourmet Guide", Domain: "gourmetguide.com", Category: "food"},
	},
	"automotive": {
		{NamePrefix: "Car Reviews", Domain: "carreviews.com", Category: "automotive"},
		{NamePrefix: "Auto News", Domain: "autonews.com", Category: "automotive"},
		{NamePrefix: "EV World", Domain: "evworld.com", Category: "automotive"},
		{NamePrefix: "Motor Trends", Domain: "motortrends.com", Category: "automotive"},
		{NamePrefix: "Auto Enthusiast", Domain: "autoenthusiast.com", Category: "automotive"},
	},
}

func GetPublisherTemplates(category string) []PublisherTemplate {
	if templates, ok := PublisherTemplates[category]; ok {
		return templates
	}
	return PublisherTemplates["news"]
}

func (t PublisherTemplate) ToCreateRequest(suffix string) client.CreatePublisherRequest {
	name := t.NamePrefix
	domain := "www." + t.Domain
	if suffix != "" {
		name = t.NamePrefix + " " + suffix
		domain = "www." + suffix + "." + t.Domain
	}
	return client.CreatePublisherRequest{
		Name:   name,
		Domain: domain,
	}
}
