package fixtures

type TargetingData struct {
	Keywords []string
	Topics   []int32
	Entities []EntityData
}

type EntityData struct {
	Type string
	Name string
}

var TargetingByIndustry = map[string]TargetingData{
	"e-commerce": {
		Keywords: []string{
			"shopping", "deals", "discount", "sale", "buy", "purchase",
			"online shopping", "free shipping", "best price", "clearance",
			"new arrivals", "trending products", "gift ideas", "holiday deals",
		},
		Topics: []int32{434, 435, 436},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Amazon"},
			{Type: "BRAND", Name: "eBay"},
			{Type: "PRODUCT", Name: "electronics"},
			{Type: "PRODUCT", Name: "home goods"},
			{Type: "ORGANIZATION", Name: "retail store"},
			{Type: "PERSON", Name: "influencer"},
		},
	},
	"saas": {
		Keywords: []string{
			"software", "cloud", "enterprise", "productivity", "automation",
			"workflow", "integration", "api", "dashboard", "analytics",
			"collaboration", "project management", "crm", "erp",
		},
		Topics: []int32{602, 603, 604},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Salesforce"},
			{Type: "BRAND", Name: "Microsoft"},
			{Type: "PRODUCT", Name: "CRM software"},
			{Type: "PRODUCT", Name: "project management tool"},
			{Type: "ORGANIZATION", Name: "enterprise software company"},
			{Type: "PERSON", Name: "tech CEO"},
		},
	},
	"entertainment": {
		Keywords: []string{
			"movies", "streaming", "netflix", "gaming", "music",
			"concerts", "entertainment", "shows", "series", "binge watch",
			"new releases", "blockbuster", "comedy", "drama", "action",
		},
		Topics: []int32{203, 264, 392},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Netflix"},
			{Type: "BRAND", Name: "Disney"},
			{Type: "PRODUCT", Name: "streaming service"},
			{Type: "PRODUCT", Name: "video game"},
			{Type: "ORGANIZATION", Name: "movie studio"},
			{Type: "PERSON", Name: "actor"},
		},
	},
	"education": {
		Keywords: []string{
			"learning", "courses", "online education", "certification",
			"skills", "training", "tutorial", "degree", "university",
			"career development", "e-learning", "webinar", "workshop",
		},
		Topics: []int32{132, 133, 134},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Coursera"},
			{Type: "BRAND", Name: "Udemy"},
			{Type: "PRODUCT", Name: "online course"},
			{Type: "PRODUCT", Name: "certification program"},
			{Type: "ORGANIZATION", Name: "university"},
			{Type: "PERSON", Name: "instructor"},
		},
	},
	"finance": {
		Keywords: []string{
			"investing", "stocks", "crypto", "banking", "loans",
			"insurance", "retirement", "savings", "wealth", "financial planning",
			"credit card", "mortgage", "trading", "portfolio",
		},
		Topics: []int32{52, 53, 54},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Chase"},
			{Type: "BRAND", Name: "Fidelity"},
			{Type: "PRODUCT", Name: "credit card"},
			{Type: "PRODUCT", Name: "investment account"},
			{Type: "ORGANIZATION", Name: "bank"},
			{Type: "PERSON", Name: "financial advisor"},
		},
	},
	"healthcare": {
		Keywords: []string{
			"health", "wellness", "fitness", "medical", "doctor",
			"pharmacy", "supplements", "nutrition", "mental health",
			"exercise", "diet", "healthcare", "telemedicine", "insurance",
		},
		Topics: []int32{239, 240, 241},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Peloton"},
			{Type: "BRAND", Name: "CVS"},
			{Type: "PRODUCT", Name: "vitamin supplements"},
			{Type: "PRODUCT", Name: "fitness tracker"},
			{Type: "ORGANIZATION", Name: "healthcare provider"},
			{Type: "PERSON", Name: "fitness instructor"},
		},
	},
	"travel": {
		Keywords: []string{
			"travel", "vacation", "flights", "hotels", "booking",
			"destinations", "tourism", "adventure", "beach", "mountains",
			"cruise", "road trip", "backpacking", "luxury travel",
		},
		Topics: []int32{508, 509, 510},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Expedia"},
			{Type: "BRAND", Name: "Marriott"},
			{Type: "PRODUCT", Name: "flight booking"},
			{Type: "PRODUCT", Name: "vacation package"},
			{Type: "ORGANIZATION", Name: "airline"},
			{Type: "PERSON", Name: "travel blogger"},
		},
	},
	"automotive": {
		Keywords: []string{
			"cars", "auto", "vehicles", "electric cars", "SUV",
			"dealership", "test drive", "new car", "used cars", "EV",
			"car insurance", "auto parts", "maintenance", "luxury cars",
		},
		Topics: []int32{1, 2, 3},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Tesla"},
			{Type: "BRAND", Name: "Ford"},
			{Type: "PRODUCT", Name: "electric vehicle"},
			{Type: "PRODUCT", Name: "SUV"},
			{Type: "ORGANIZATION", Name: "auto manufacturer"},
			{Type: "PERSON", Name: "car reviewer"},
		},
	},
	"food-beverage": {
		Keywords: []string{
			"food", "recipes", "cooking", "restaurants", "delivery",
			"gourmet", "healthy eating", "fast food", "beverages", "wine",
			"meal prep", "dining", "takeout", "catering", "organic",
		},
		Topics: []int32{212, 213, 214},
		Entities: []EntityData{
			{Type: "BRAND", Name: "DoorDash"},
			{Type: "BRAND", Name: "HelloFresh"},
			{Type: "PRODUCT", Name: "meal kit"},
			{Type: "PRODUCT", Name: "food delivery app"},
			{Type: "ORGANIZATION", Name: "restaurant chain"},
			{Type: "PERSON", Name: "chef"},
		},
	},
	"technology": {
		Keywords: []string{
			"technology", "gadgets", "smartphones", "laptops", "AI",
			"tech news", "innovation", "devices", "wearables", "smart home",
			"5G", "cybersecurity", "programming", "startups",
		},
		Topics: []int32{602, 617, 618},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Apple"},
			{Type: "BRAND", Name: "Samsung"},
			{Type: "PRODUCT", Name: "smartphone"},
			{Type: "PRODUCT", Name: "laptop"},
			{Type: "ORGANIZATION", Name: "tech company"},
			{Type: "PERSON", Name: "tech reviewer"},
		},
	},
	"fashion": {
		Keywords: []string{
			"fashion", "clothing", "style", "trends", "designer",
			"shoes", "accessories", "jewelry", "handbags", "luxury",
			"streetwear", "sustainable fashion", "beauty", "makeup",
		},
		Topics: []int32{473, 474, 475},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Gucci"},
			{Type: "BRAND", Name: "Zara"},
			{Type: "PRODUCT", Name: "designer clothing"},
			{Type: "PRODUCT", Name: "luxury handbag"},
			{Type: "ORGANIZATION", Name: "fashion house"},
			{Type: "PERSON", Name: "fashion influencer"},
		},
	},
	"sports": {
		Keywords: []string{
			"sports", "fitness", "football", "basketball", "soccer",
			"workout", "gym", "athletes", "training", "equipment",
			"sports news", "fantasy sports", "outdoor activities", "running",
		},
		Topics: []int32{463, 464, 465},
		Entities: []EntityData{
			{Type: "BRAND", Name: "Nike"},
			{Type: "BRAND", Name: "Adidas"},
			{Type: "PRODUCT", Name: "sports equipment"},
			{Type: "PRODUCT", Name: "running shoes"},
			{Type: "ORGANIZATION", Name: "sports league"},
			{Type: "PERSON", Name: "professional athlete"},
		},
	},
}

var CreativeTemplates = map[string][]CreativeTemplate{
	"e-commerce": {
		{
			HeadlineTemplate:    "Shop the Best %s Deals Today",
			DescriptionTemplate: "Discover amazing deals on %s. Free shipping on orders over $50. Limited time offer!",
			CTAs:                []string{"Shop Now", "Get Deal", "Buy Now", "View Offers"},
		},
		{
			HeadlineTemplate:    "New Arrivals: %s Collection",
			DescriptionTemplate: "Explore our latest %s arrivals. Premium quality at unbeatable prices. Order today!",
			CTAs:                []string{"Explore Now", "Shop Collection", "See What's New"},
		},
	},
	"saas": {
		{
			HeadlineTemplate:    "Transform Your %s Workflow",
			DescriptionTemplate: "Boost productivity with our %s solution. Start your free trial today. No credit card required.",
			CTAs:                []string{"Start Free Trial", "Get Started", "Try Free", "Request Demo"},
		},
		{
			HeadlineTemplate:    "Scale Your %s Operations",
			DescriptionTemplate: "Enterprise-grade %s platform trusted by 10,000+ companies. See why teams love us.",
			CTAs:                []string{"Learn More", "See Plans", "Book Demo", "Get Pricing"},
		},
	},
	"entertainment": {
		{
			HeadlineTemplate:    "Stream %s Now",
			DescriptionTemplate: "Watch the latest %s content. Unlimited streaming. Cancel anytime. Start watching today!",
			CTAs:                []string{"Watch Now", "Start Streaming", "Play Now", "Subscribe"},
		},
		{
			HeadlineTemplate:    "New Release: %s",
			DescriptionTemplate: "Don't miss the most anticipated %s of the year. Available now on all devices.",
			CTAs:                []string{"Watch Trailer", "Get Access", "See Showtimes"},
		},
	},
	"education": {
		{
			HeadlineTemplate:    "Master %s Skills Today",
			DescriptionTemplate: "Learn %s from industry experts. Get certified. Advance your career. Enroll now!",
			CTAs:                []string{"Enroll Now", "Start Learning", "Get Certified", "View Courses"},
		},
		{
			HeadlineTemplate:    "Free %s Course",
			DescriptionTemplate: "Start your %s journey for free. Join millions of learners worldwide. Limited spots available.",
			CTAs:                []string{"Join Free", "Start Course", "Learn Free"},
		},
	},
	"finance": {
		{
			HeadlineTemplate:    "Smart %s Solutions",
			DescriptionTemplate: "Take control of your %s. Expert tools and guidance. Start building wealth today.",
			CTAs:                []string{"Get Started", "Open Account", "Learn More", "Calculate Now"},
		},
		{
			HeadlineTemplate:    "Invest in %s",
			DescriptionTemplate: "Secure your financial future with %s. Trusted by millions. Start with just $1.",
			CTAs:                []string{"Start Investing", "Sign Up", "View Options"},
		},
	},
	"healthcare": {
		{
			HeadlineTemplate:    "Your %s Journey Starts Here",
			DescriptionTemplate: "Transform your health with %s. Expert guidance. Proven results. Start today!",
			CTAs:                []string{"Get Started", "Learn More", "Start Free", "Book Consultation"},
		},
		{
			HeadlineTemplate:    "Premium %s Products",
			DescriptionTemplate: "Discover %s solutions backed by science. Free shipping on all orders.",
			CTAs:                []string{"Shop Now", "View Products", "Try Now"},
		},
	},
	"travel": {
		{
			HeadlineTemplate:    "Discover %s Destinations",
			DescriptionTemplate: "Book your dream %s vacation. Best prices guaranteed. Flexible cancellation.",
			CTAs:                []string{"Book Now", "Explore", "Plan Trip", "View Deals"},
		},
		{
			HeadlineTemplate:    "%s Travel Deals",
			DescriptionTemplate: "Unbeatable %s travel packages. Save up to 50%. Limited availability!",
			CTAs:                []string{"See Deals", "Book Today", "Get Quote"},
		},
	},
	"automotive": {
		{
			HeadlineTemplate:    "Drive the New %s",
			DescriptionTemplate: "Experience the latest %s models. Schedule a test drive today. Special financing available.",
			CTAs:                []string{"Schedule Test Drive", "View Inventory", "Get Quote", "Learn More"},
		},
		{
			HeadlineTemplate:    "%s Auto Deals",
			DescriptionTemplate: "Find your perfect %s. Best prices. Wide selection. Financing options available.",
			CTAs:                []string{"Search Inventory", "Get Pre-Approved", "View Specials"},
		},
	},
	"food-beverage": {
		{
			HeadlineTemplate:    "Delicious %s Delivered",
			DescriptionTemplate: "Order %s to your door. Fresh ingredients. Fast delivery. First order discount!",
			CTAs:                []string{"Order Now", "See Menu", "Get Delivery", "Try Now"},
		},
		{
			HeadlineTemplate:    "Taste the Best %s",
			DescriptionTemplate: "Experience premium %s. Made with love. Order online for pickup or delivery.",
			CTAs:                []string{"Order Online", "View Menu", "Find Location"},
		},
	},
	"technology": {
		{
			HeadlineTemplate:    "Next-Gen %s Technology",
			DescriptionTemplate: "Discover cutting-edge %s. Innovative features. Unmatched performance. Order now!",
			CTAs:                []string{"Shop Now", "Learn More", "Pre-Order", "Compare Models"},
		},
		{
			HeadlineTemplate:    "Upgrade to %s",
			DescriptionTemplate: "Experience the future with %s. Limited stock. Free shipping. 30-day returns.",
			CTAs:                []string{"Buy Now", "See Features", "Get Yours"},
		},
	},
	"fashion": {
		{
			HeadlineTemplate:    "New %s Collection",
			DescriptionTemplate: "Discover the latest %s trends. Premium quality. Free returns. Shop the collection!",
			CTAs:                []string{"Shop Now", "View Collection", "Explore Styles"},
		},
		{
			HeadlineTemplate:    "%s Style Sale",
			DescriptionTemplate: "Up to 60% off %s items. Limited time offer. Free shipping on $75+.",
			CTAs:                []string{"Shop Sale", "See Deals", "Get Discount"},
		},
	},
	"sports": {
		{
			HeadlineTemplate:    "Gear Up with %s",
			DescriptionTemplate: "Professional %s equipment. Used by champions. Free shipping on orders $50+.",
			CTAs:                []string{"Shop Now", "View Gear", "Get Equipped"},
		},
		{
			HeadlineTemplate:    "Train Like a Pro: %s",
			DescriptionTemplate: "Elevate your %s performance. Premium gear. Expert reviews. Shop today!",
			CTAs:                []string{"Shop Training Gear", "See Reviews", "Start Training"},
		},
	},
}

type CreativeTemplate struct {
	HeadlineTemplate    string
	DescriptionTemplate string
	CTAs                []string
}

func GetTargetingData(industry string) TargetingData {
	if data, ok := TargetingByIndustry[industry]; ok {
		return data
	}
	return TargetingByIndustry["e-commerce"]
}

func GetCreativeTemplates(industry string) []CreativeTemplate {
	if templates, ok := CreativeTemplates[industry]; ok {
		return templates
	}
	return CreativeTemplates["e-commerce"]
}
