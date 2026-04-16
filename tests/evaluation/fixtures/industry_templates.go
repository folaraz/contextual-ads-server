package fixtures

type IndustryTemplate struct {
	Industry string

	Keywords []string

	TopicIDs []string

	TopicNames []string

	Entities []string

	EntityTypes []string

	HeadlineTemplates []string

	DescriptionTemplates []string
}

var Industries = []string{
	"e-commerce", "saas", "entertainment", "education", "finance",
	"healthcare", "travel", "automotive", "food-beverage", "technology",
	"fashion", "sports",
}

var IndustryTemplates = map[string]IndustryTemplate{
	"e-commerce": {
		Industry: "e-commerce",
		Keywords: []string{
			"shopping", "deals", "discount", "online store", "free shipping",
			"buy now", "sale", "coupon", "marketplace", "best price",
			"checkout", "cart", "retail", "product review", "comparison",
			"flash sale", "clearance", "bundle", "order tracking", "returns",
		},
		TopicIDs:    []string{"1046", "1047", "1048"},
		TopicNames:  []string{"Shopping", "Retail Stores", "Online Shopping"},
		Entities:    []string{"Amazon", "Shopify", "eBay", "Walmart", "Etsy", "Target"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "BRAND", "BRAND"},
		HeadlineTemplates: []string{
			"Shop the Best Deals Online",
			"Free Shipping on Orders Over $50",
			"Up to 70%% Off — Limited Time",
			"New Arrivals Just Dropped",
			"Your One-Stop Online Shop",
		},
		DescriptionTemplates: []string{
			"Discover unbeatable prices on thousands of products. Fast, free delivery.",
			"Shop top brands at discount prices. New deals every day.",
			"Compare prices across sellers and save big on every purchase.",
		},
	},
	"saas": {
		Industry: "saas",
		Keywords: []string{
			"software", "cloud", "SaaS", "enterprise", "API",
			"platform", "automation", "dashboard", "analytics", "integration",
			"productivity", "workflow", "collaboration", "deployment", "scalable",
			"subscription", "B2B", "CRM", "devops", "infrastructure",
		},
		TopicIDs:    []string{"1053", "1054"},
		TopicNames:  []string{"Software", "Technology & Computing"},
		Entities:    []string{"Salesforce", "HubSpot", "Slack", "Notion", "Datadog", "Snowflake"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "BRAND", "BRAND"},
		HeadlineTemplates: []string{
			"Scale Your Business with Cloud",
			"All-in-One Platform for Teams",
			"Automate Workflows in Minutes",
			"Enterprise-Grade Analytics",
			"Try Free for 14 Days",
		},
		DescriptionTemplates: []string{
			"The modern platform for growing teams. Integrates with your existing tools.",
			"Powerful analytics and automation. Trusted by 10,000+ companies.",
			"Build, deploy, and scale faster with our developer-first platform.",
		},
	},
	"entertainment": {
		Industry: "entertainment",
		Keywords: []string{
			"movies", "streaming", "TV shows", "music", "gaming",
			"concert", "festival", "podcast", "celebrity", "trailer",
			"box office", "binge-watch", "premiere", "entertainment news", "series",
			"documentary", "comedy", "drama", "animation", "blockbuster",
		},
		TopicIDs:    []string{"1016", "1017"},
		TopicNames:  []string{"Entertainment", "Movies"},
		Entities:    []string{"Netflix", "Disney+", "Spotify", "HBO Max", "YouTube", "Hulu"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "BRAND", "BRAND"},
		HeadlineTemplates: []string{
			"Stream the Latest Hits",
			"New Season Now Streaming",
			"Unlimited Entertainment Awaits",
			"Watch Anywhere, Anytime",
			"Exclusive Originals Only Here",
		},
		DescriptionTemplates: []string{
			"Thousands of movies, shows, and originals. Start your free trial today.",
			"The best in entertainment — from blockbusters to hidden gems.",
			"Live concerts, new releases, and exclusive content all in one place.",
		},
	},
	"education": {
		Industry: "education",
		Keywords: []string{
			"online courses", "learning", "certification", "education", "training",
			"university", "degree", "e-learning", "skills", "tutorial",
			"bootcamp", "scholarship", "student", "instructor", "curriculum",
			"exam prep", "professional development", "MOOC", "webinar", "mentorship",
		},
		TopicIDs:    []string{"1015"},
		TopicNames:  []string{"Education"},
		Entities:    []string{"Coursera", "Udemy", "Khan Academy", "edX", "LinkedIn Learning", "Skillshare"},
		EntityTypes: []string{"BRAND", "BRAND", "ORG", "BRAND", "BRAND", "BRAND"},
		HeadlineTemplates: []string{
			"Learn New Skills Online",
			"Get Certified in Weeks",
			"World-Class Courses from Top Universities",
			"Advance Your Career Today",
			"Free Courses for Beginners",
		},
		DescriptionTemplates: []string{
			"Flexible online learning from top instructors. Study at your own pace.",
			"Earn certificates recognized by leading employers worldwide.",
			"Join millions of learners gaining new skills every day.",
		},
	},
	"finance": {
		Industry: "finance",
		Keywords: []string{
			"investing", "stocks", "savings", "banking", "credit card",
			"mortgage", "insurance", "retirement", "financial planning", "crypto",
			"budget", "interest rate", "portfolio", "wealth management", "fintech",
			"loan", "tax", "trading", "gold", "economy",
		},
		TopicIDs:    []string{"1020", "1021"},
		TopicNames:  []string{"Finance", "Personal Finance"},
		Entities:    []string{"Goldman Sachs", "JPMorgan", "Robinhood", "Fidelity", "Charles Schwab", "Coinbase"},
		EntityTypes: []string{"ORG", "ORG", "BRAND", "BRAND", "BRAND", "BRAND"},
		HeadlineTemplates: []string{
			"Invest Smarter, Not Harder",
			"High-Yield Savings Account",
			"Your Money, Your Future",
			"Zero-Fee Trading Platform",
			"Financial Freedom Starts Here",
		},
		DescriptionTemplates: []string{
			"Start investing with as little as $1. Commission-free trades.",
			"Grow your wealth with expert-backed portfolios and low fees.",
			"Smart financial tools for budgeting, saving, and investing.",
		},
	},
	"healthcare": {
		Industry: "healthcare",
		Keywords: []string{
			"health", "wellness", "medical", "fitness", "nutrition",
			"mental health", "telehealth", "pharmacy", "insurance", "diagnosis",
			"therapy", "supplement", "exercise", "doctor", "clinical",
			"hospital", "prescription", "preventive care", "vaccine", "recovery",
		},
		TopicIDs:    []string{"1023", "1024"},
		TopicNames:  []string{"Health & Fitness", "Medical Health"},
		Entities:    []string{"CVS Health", "Peloton", "Headspace", "Teladoc", "Mayo Clinic", "Fitbit"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "ORG", "BRAND"},
		HeadlineTemplates: []string{
			"Your Health, Simplified",
			"Talk to a Doctor Online",
			"Wellness Made Easy",
			"Track Your Fitness Goals",
			"Mental Health Matters",
		},
		DescriptionTemplates: []string{
			"Access quality healthcare from the comfort of home. 24/7 telehealth.",
			"Personalized wellness plans backed by science and real doctors.",
			"Track, manage, and improve your health with our all-in-one app.",
		},
	},
	"travel": {
		Industry: "travel",
		Keywords: []string{
			"flights", "hotels", "vacation", "travel deals", "booking",
			"destination", "cruise", "resort", "airline", "road trip",
			"adventure", "tourism", "backpacking", "travel insurance", "itinerary",
			"all-inclusive", "beach", "mountain", "city break", "passport",
		},
		TopicIDs:    []string{"1055", "1056"},
		TopicNames:  []string{"Travel", "Hotels & Accommodations"},
		Entities:    []string{"Expedia", "Airbnb", "Booking.com", "Delta Airlines", "Marriott", "Tripadvisor"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "BRAND", "BRAND"},
		HeadlineTemplates: []string{
			"Book Your Dream Vacation",
			"Flights from $99",
			"Last-Minute Travel Deals",
			"Explore the World for Less",
			"Luxury Stays at Budget Prices",
		},
		DescriptionTemplates: []string{
			"Compare flights, hotels, and packages to save on your next trip.",
			"Over 2 million properties worldwide. Book now, pay later.",
			"Adventure awaits — discover top-rated destinations and hidden gems.",
		},
	},
	"automotive": {
		Industry: "automotive",
		Keywords: []string{
			"cars", "SUV", "electric vehicle", "EV", "auto loan",
			"test drive", "sedan", "truck", "hybrid", "dealership",
			"car insurance", "maintenance", "fuel efficiency", "safety rating", "horsepower",
			"lease", "trade-in", "new model", "performance", "charging station",
		},
		TopicIDs:    []string{"1003", "1004"},
		TopicNames:  []string{"Automotive", "Auto Parts"},
		Entities:    []string{"Tesla", "Toyota", "Ford", "BMW", "General Motors", "Rivian"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "ORG", "BRAND"},
		HeadlineTemplates: []string{
			"Drive the Future Today",
			"0%% APR on New Models",
			"All-Electric, All-Awesome",
			"Find Your Perfect Ride",
			"Trade In and Save Thousands",
		},
		DescriptionTemplates: []string{
			"Explore the latest models with cutting-edge technology and safety.",
			"Electric vehicles with 300+ mile range. Test drive today.",
			"Low monthly payments and flexible financing. Your dream car awaits.",
		},
	},
	"food-beverage": {
		Industry: "food-beverage",
		Keywords: []string{
			"recipes", "food delivery", "restaurant", "cooking", "healthy eating",
			"organic", "meal kit", "snacks", "beverages", "vegan",
			"gourmet", "fast food", "nutrition", "ingredients", "catering",
			"wine", "coffee", "brunch", "takeout", "farm-to-table",
		},
		TopicIDs:    []string{"1022"},
		TopicNames:  []string{"Food & Drink"},
		Entities:    []string{"DoorDash", "HelloFresh", "Starbucks", "Whole Foods", "Blue Apron", "Grubhub"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "BRAND", "BRAND"},
		HeadlineTemplates: []string{
			"Fresh Meals Delivered to You",
			"Cook Like a Chef at Home",
			"Order Now, Eat in Minutes",
			"Healthy Eating Made Simple",
			"Discover New Flavors Today",
		},
		DescriptionTemplates: []string{
			"Chef-curated recipes with pre-portioned ingredients. Skip the grocery store.",
			"From local favorites to global cuisines — delivered fast and fresh.",
			"Organic, sustainable, and delicious. Meal plans starting at $7.99/serving.",
		},
	},
	"technology": {
		Industry: "technology",
		Keywords: []string{
			"AI", "machine learning", "gadgets", "smartphones", "laptops",
			"cybersecurity", "5G", "IoT", "blockchain", "innovation",
			"robotics", "VR", "AR", "chip", "startup",
			"data science", "neural network", "quantum computing", "wearables", "tech news",
		},
		TopicIDs:    []string{"1053", "1054"},
		TopicNames:  []string{"Software", "Technology & Computing"},
		Entities:    []string{"Apple", "Google", "Microsoft", "NVIDIA", "OpenAI", "Meta"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "ORG", "BRAND"},
		HeadlineTemplates: []string{
			"The Future of AI Is Here",
			"Next-Gen Gadgets, Now Available",
			"Secure Your Digital Life",
			"Innovation at Your Fingertips",
			"Upgrade Your Tech Stack",
		},
		DescriptionTemplates: []string{
			"Cutting-edge technology products and services for the modern world.",
			"From AI assistants to smart home devices — explore what's next.",
			"Enterprise-grade security and performance. Built for tomorrow.",
		},
	},
	"fashion": {
		Industry: "fashion",
		Keywords: []string{
			"fashion", "clothing", "style", "designer", "trends",
			"accessories", "luxury", "outfit", "wardrobe", "apparel",
			"runway", "collection", "sustainable fashion", "streetwear", "haute couture",
			"beauty", "cosmetics", "skincare", "fragrance", "jewellery",
		},
		TopicIDs:    []string{"1051", "1052"},
		TopicNames:  []string{"Style & Fashion", "Clothing"},
		Entities:    []string{"Nike", "Zara", "Gucci", "H&M", "Sephora", "LVMH"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "BRAND", "ORG"},
		HeadlineTemplates: []string{
			"New Season, New Styles",
			"Luxury Fashion for Less",
			"Trending Now: Spring Collection",
			"Express Your Style",
			"Sustainable Fashion Forward",
		},
		DescriptionTemplates: []string{
			"Discover the latest trends from top designers. Free returns.",
			"From casual to couture — find your perfect look today.",
			"Sustainable, stylish, and affordable fashion for every occasion.",
		},
	},
	"sports": {
		Industry: "sports",
		Keywords: []string{
			"sports", "football", "basketball", "soccer", "tennis",
			"fitness", "athletic", "training", "NFL", "NBA",
			"championship", "league", "scores", "highlights", "gear",
			"workout", "marathon", "Olympics", "coaching", "stadium",
		},
		TopicIDs:    []string{"1050"},
		TopicNames:  []string{"Sports"},
		Entities:    []string{"Nike", "Adidas", "ESPN", "Under Armour", "Puma", "FIFA"},
		EntityTypes: []string{"BRAND", "BRAND", "BRAND", "BRAND", "BRAND", "ORG"},
		HeadlineTemplates: []string{
			"Gear Up for Game Day",
			"Train Like a Pro",
			"Live Sports, Every Game",
			"Performance Gear That Delivers",
			"Your Fitness Journey Starts Here",
		},
		DescriptionTemplates: []string{
			"Premium athletic gear for every sport. Built for performance.",
			"Stream live games, scores, and highlights — all in one app.",
			"From marathon training to weekend leagues — equip yourself to win.",
		},
	},
}

var ContentCategoryToIndustry = map[string]string{
	"finance":    "finance",
	"technology": "technology",
	"education":  "education",
	"automotive": "automotive",
	"travel":     "travel",

	"football":   "sports",
	"basketball": "sports",
	"soccer":     "sports",
	"tennis":     "sports",
	"sports":     "sports",

	"movies":        "entertainment",
	"music":         "entertainment",
	"entertainment": "entertainment",
	"gaming":        "entertainment",
	"books":         "entertainment",

	"lifestyle": "fashion",

	"food": "food-beverage",

	"health": "healthcare",

	"home":        "e-commerce",
	"pets":        "e-commerce",
	"real_estate": "e-commerce",

	"politics": "education",
	"news":     "education",
}
