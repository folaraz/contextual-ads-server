package fixtures

import "github.com/folaraz/contextual-ads-server/tests/client"

type AdvertiserTemplate struct {
	NamePrefix string
	Industry   string
	Website    string
}

var AdvertiserTemplates = map[string][]AdvertiserTemplate{
	"e-commerce": {
		{NamePrefix: "ShopMax", Industry: "e-commerce", Website: "https://www.shopmax.com"},
		{NamePrefix: "BuyNow", Industry: "e-commerce", Website: "https://www.buynow.com"},
		{NamePrefix: "MegaStore", Industry: "e-commerce", Website: "https://www.megastore.com"},
		{NamePrefix: "QuickCart", Industry: "e-commerce", Website: "https://www.quickcart.com"},
		{NamePrefix: "DealHub", Industry: "e-commerce", Website: "https://www.dealhub.com"},
	},
	"saas": {
		{NamePrefix: "CloudSync", Industry: "saas", Website: "https://www.cloudsync.io"},
		{NamePrefix: "DataFlow", Industry: "saas", Website: "https://www.dataflow.io"},
		{NamePrefix: "TeamCollab", Industry: "saas", Website: "https://www.teamcollab.com"},
		{NamePrefix: "AutoScale", Industry: "saas", Website: "https://www.autoscale.io"},
		{NamePrefix: "DevOpsHub", Industry: "saas", Website: "https://www.devopshub.com"},
	},
	"entertainment": {
		{NamePrefix: "StreamFlix", Industry: "entertainment", Website: "https://www.streamflix.com"},
		{NamePrefix: "GameZone", Industry: "entertainment", Website: "https://www.gamezone.com"},
		{NamePrefix: "MusicWave", Industry: "entertainment", Website: "https://www.musicwave.com"},
		{NamePrefix: "MovieHub", Industry: "entertainment", Website: "https://www.moviehub.com"},
		{NamePrefix: "PlayNow", Industry: "entertainment", Website: "https://www.playnow.com"},
	},
	"education": {
		{NamePrefix: "LearnPro", Industry: "education", Website: "https://www.learnpro.com"},
		{NamePrefix: "EduPath", Industry: "education", Website: "https://www.edupath.com"},
		{NamePrefix: "SkillUp", Industry: "education", Website: "https://www.skillup.io"},
		{NamePrefix: "CourseHub", Industry: "education", Website: "https://www.coursehub.com"},
		{NamePrefix: "TutorNow", Industry: "education", Website: "https://www.tutornow.com"},
	},
	"finance": {
		{NamePrefix: "InvestSmart", Industry: "finance", Website: "https://www.investsmart.com"},
		{NamePrefix: "WealthBuilder", Industry: "finance", Website: "https://www.wealthbuilder.com"},
		{NamePrefix: "QuickLoan", Industry: "finance", Website: "https://www.quickloan.com"},
		{NamePrefix: "SecureBank", Industry: "finance", Website: "https://www.securebank.com"},
		{NamePrefix: "CryptoTrade", Industry: "finance", Website: "https://www.cryptotrade.io"},
	},
	"healthcare": {
		{NamePrefix: "HealthFirst", Industry: "healthcare", Website: "https://www.healthfirst.com"},
		{NamePrefix: "MediCare", Industry: "healthcare", Website: "https://www.medicare-plus.com"},
		{NamePrefix: "WellnessHub", Industry: "healthcare", Website: "https://www.wellnesshub.com"},
		{NamePrefix: "FitLife", Industry: "healthcare", Website: "https://www.fitlife.com"},
		{NamePrefix: "PharmaCare", Industry: "healthcare", Website: "https://www.pharmacare.com"},
	},
	"travel": {
		{NamePrefix: "TravelNow", Industry: "travel", Website: "https://www.travelnow.com"},
		{NamePrefix: "FlightDeals", Industry: "travel", Website: "https://www.flightdeals.com"},
		{NamePrefix: "HotelFinder", Industry: "travel", Website: "https://www.hotelfinder.com"},
		{NamePrefix: "VacationSpot", Industry: "travel", Website: "https://www.vacationspot.com"},
		{NamePrefix: "TourGuide", Industry: "travel", Website: "https://www.tourguide.com"},
	},
	"automotive": {
		{NamePrefix: "AutoMax", Industry: "automotive", Website: "https://www.automax.com"},
		{NamePrefix: "CarFinder", Industry: "automotive", Website: "https://www.carfinder.com"},
		{NamePrefix: "DriveNow", Industry: "automotive", Website: "https://www.drivenow.com"},
		{NamePrefix: "AutoParts", Industry: "automotive", Website: "https://www.autoparts.com"},
		{NamePrefix: "ElectricAuto", Industry: "automotive", Website: "https://www.electricauto.com"},
	},
	"food-beverage": {
		{NamePrefix: "FoodieHub", Industry: "food-beverage", Website: "https://www.foodiehub.com"},
		{NamePrefix: "QuickEats", Industry: "food-beverage", Website: "https://www.quickeats.com"},
		{NamePrefix: "GourmetBox", Industry: "food-beverage", Website: "https://www.gourmetbox.com"},
		{NamePrefix: "DrinkDeals", Industry: "food-beverage", Website: "https://www.drinkdeals.com"},
		{NamePrefix: "MealPrep", Industry: "food-beverage", Website: "https://www.mealprep.com"},
	},
	"technology": {
		{NamePrefix: "TechGiant", Industry: "technology", Website: "https://www.techgiant.com"},
		{NamePrefix: "GadgetWorld", Industry: "technology", Website: "https://www.gadgetworld.com"},
		{NamePrefix: "SmartDevices", Industry: "technology", Website: "https://www.smartdevices.com"},
		{NamePrefix: "AILabs", Industry: "technology", Website: "https://www.ailabs.io"},
		{NamePrefix: "RoboTech", Industry: "technology", Website: "https://www.robotech.com"},
	},
	"fashion": {
		{NamePrefix: "StyleHub", Industry: "fashion", Website: "https://www.stylehub.com"},
		{NamePrefix: "TrendyWear", Industry: "fashion", Website: "https://www.trendywear.com"},
		{NamePrefix: "LuxuryBrand", Industry: "fashion", Website: "https://www.luxurybrand.com"},
		{NamePrefix: "ShoePalace", Industry: "fashion", Website: "https://www.shoepalace.com"},
		{NamePrefix: "AccessoryBox", Industry: "fashion", Website: "https://www.accessorybox.com"},
	},
	"sports": {
		{NamePrefix: "SportsPro", Industry: "sports", Website: "https://www.sportspro.com"},
		{NamePrefix: "FitGear", Industry: "sports", Website: "https://www.fitgear.com"},
		{NamePrefix: "TeamJersey", Industry: "sports", Website: "https://www.teamjersey.com"},
		{NamePrefix: "OutdoorLife", Industry: "sports", Website: "https://www.outdoorlife.com"},
		{NamePrefix: "GymEquip", Industry: "sports", Website: "https://www.gymequip.com"},
	},
}

func GetAdvertiserTemplates(industry string) []AdvertiserTemplate {
	if templates, ok := AdvertiserTemplates[industry]; ok {
		return templates
	}
	return AdvertiserTemplates["e-commerce"]
}

func (t AdvertiserTemplate) ToCreateRequest(suffix string) client.CreateAdvertiserRequest {
	name := t.NamePrefix
	if suffix != "" {
		name = t.NamePrefix + " " + suffix
	}
	return client.CreateAdvertiserRequest{
		Name:    name,
		Website: t.Website,
	}
}
