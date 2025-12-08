import json
import random
from datetime import datetime, timedelta
from typing import List, Dict

# Advertisers organized by content category
ADVERTISERS = [
    # Fashion & Lifestyle
    {"name": "H&M", "industry": "Fashion Retail", "budget_range": (50000, 150000)},
    {"name": "Zara", "industry": "Fashion Retail", "budget_range": (55000, 165000)},
    {"name": "Sephora", "industry": "Beauty", "budget_range": (55000, 160000)},
    {"name": "Lululemon", "industry": "Athletic Wear", "budget_range": (50000, 145000)},
    {"name": "Warby Parker", "industry": "Fashion Accessories", "budget_range": (40000, 120000)},
    {"name": "Everlane", "industry": "Fashion Retail", "budget_range": (35000, 100000)},

    # Music & Entertainment
    {"name": "Spotify", "industry": "Music Streaming", "budget_range": (90000, 250000)},
    {"name": "Apple Music", "industry": "Music Streaming", "budget_range": (100000, 280000)},
    {"name": "Ticketmaster", "industry": "Event Tickets", "budget_range": (70000, 200000)},
    {"name": "Gibson", "industry": "Musical Instruments", "budget_range": (45000, 130000)},
    {"name": "Fender", "industry": "Musical Instruments", "budget_range": (45000, 130000)},

    # Movies & Streaming
    {"name": "Netflix", "industry": "Streaming", "budget_range": (120000, 350000)},
    {"name": "Disney+", "industry": "Streaming", "budget_range": (110000, 320000)},
    {"name": "HBO Max", "industry": "Streaming", "budget_range": (100000, 290000)},
    {"name": "AMC Theatres", "industry": "Movie Theaters", "budget_range": (60000, 180000)},
    {"name": "Paramount+", "industry": "Streaming", "budget_range": (85000, 240000)},

    # Finance & Investment
    {"name": "Fidelity", "industry": "Financial Services", "budget_range": (90000, 260000)},
    {"name": "Charles Schwab", "industry": "Financial Services", "budget_range": (85000, 250000)},
    {"name": "Robinhood", "industry": "Investment App", "budget_range": (70000, 200000)},
    {"name": "Coinbase", "industry": "Cryptocurrency", "budget_range": (75000, 220000)},
    {"name": "Mint", "industry": "Financial Planning", "budget_range": (50000, 150000)},
    {"name": "Credit Karma", "industry": "Financial Services", "budget_range": (60000, 175000)},

    # Sports - Basketball
    {"name": "NBA League Pass", "industry": "Sports Streaming", "budget_range": (80000, 230000)},
    {"name": "Nike Basketball", "industry": "Sports Apparel", "budget_range": (90000, 260000)},
    {"name": "Spalding", "industry": "Sports Equipment", "budget_range": (40000, 120000)},
    {"name": "Under Armour", "industry": "Sports Apparel", "budget_range": (70000, 200000)},

    # Sports - Football
    {"name": "NFL Sunday Ticket", "industry": "Sports Streaming", "budget_range": (100000, 290000)},
    {"name": "Nike Football", "industry": "Sports Apparel", "budget_range": (90000, 260000)},
    {"name": "Riddell", "industry": "Sports Equipment", "budget_range": (50000, 145000)},
    {"name": "Fanatics", "industry": "Sports Merchandise", "budget_range": (65000, 190000)},

    # Sports - Tennis
    {"name": "Wilson Tennis", "industry": "Sports Equipment", "budget_range": (45000, 130000)},
    {"name": "Tennis Warehouse", "industry": "Sports Retail", "budget_range": (40000, 115000)},

    # Sports - Soccer
    {"name": "Adidas Soccer", "industry": "Sports Apparel", "budget_range": (85000, 245000)},
    {"name": "Puma Soccer", "industry": "Sports Apparel", "budget_range": (70000, 200000)},
    {"name": "SoccerPro", "industry": "Sports Retail", "budget_range": (40000, 115000)},

    # Politics & News
    {"name": "The New York Times", "industry": "News Media", "budget_range": (80000, 230000)},
    {"name": "The Washington Post", "industry": "News Media", "budget_range": (75000, 215000)},
    {"name": "The Atlantic", "industry": "News Media", "budget_range": (55000, 160000)},
    {"name": "Audible", "industry": "Audiobooks", "budget_range": (70000, 200000)},

    # Technology
    {"name": "Apple", "industry": "Consumer Electronics", "budget_range": (150000, 400000)},
    {"name": "Samsung", "industry": "Consumer Electronics", "budget_range": (130000, 370000)},
    {"name": "Microsoft", "industry": "Software & Cloud", "budget_range": (140000, 380000)},
    {"name": "Adobe", "industry": "Software", "budget_range": (90000, 260000)},
    {"name": "Tesla", "industry": "Electric Vehicles", "budget_range": (110000, 320000)},
    {"name": "Google Pixel", "industry": "Consumer Electronics", "budget_range": (95000, 275000)},
    {"name": "Dell", "industry": "Computer Hardware", "budget_range": (80000, 230000)},
    {"name": "Lenovo", "industry": "Computer Hardware", "budget_range": (75000, 215000)},
]

# Campaign templates by category
CAMPAIGN_TEMPLATES = {
    "Fashion Retail": ["Spring 2025 Collection", "New Arrivals Daily", "Seasonal Sale Event", "Fashion Week Exclusive"],
    "Beauty": ["Holiday Beauty Sets", "Skincare Revolution", "Beauty Insider Event", "New Launches"],
    "Athletic Wear": ["Performance Collection", "Yoga Essentials", "Running Gear Sale", "Activewear Trends"],
    "Fashion Accessories": ["Home Try-On Program", "New Frame Styles", "Spring Eyewear Collection", "Limited Edition Release"],
    "Music Streaming": ["Premium Trial Offer", "Discover Weekly Playlists", "Concert Livestreams", "Podcast Exclusives"],
    "Event Tickets": ["Concert Presale Access", "Live Events Near You", "Festival Season Passes", "Sports Tickets"],
    "Musical Instruments": ["Guitar Sale Event", "Professional Series", "Beginner Bundles", "Limited Edition Models"],
    "Streaming": ["Original Series Launch", "Binge-Worthy Content", "Family Plan Deals", "Free Trial Month"],
    "Movie Theaters": ["Opening Weekend Tickets", "Blockbuster Season", "Premium Experience", "Movie Membership"],
    "Financial Services": ["Smart Investing Tools", "Retirement Planning", "Zero Commission Trading", "Financial Freedom"],
    "Investment App": ["Start Investing Today", "Portfolio Diversification", "Fractional Shares", "Investment Education"],
    "Cryptocurrency": ["Crypto Made Simple", "Secure Trading Platform", "Earn Rewards Program", "Market Analysis Tools"],
    "Financial Planning": ["Budget Tracking App", "Credit Score Monitoring", "Financial Goals", "Debt Payoff Tools"],
    "Sports Streaming": ["Live Games All Season", "Multi-Device Streaming", "Game Replays & Highlights", "Playoff Coverage"],
    "Sports Apparel": ["Athlete Signature Line", "Performance Technology", "Team Spirit Collection", "Training Essentials"],
    "Sports Equipment": ["Professional Grade Gear", "Equipment Sale", "Youth Sports Program", "Championship Quality"],
    "Sports Merchandise": ["Official Team Gear", "Fan Favorites", "Limited Edition Jerseys", "Game Day Essentials"],
    "Sports Retail": ["Pro Shop Deals", "Equipment Experts", "Gear Up for Season", "Online Exclusive Offers"],
    "News Media": ["Digital Subscription", "Award-Winning Journalism", "Unlimited Access", "Breaking News Coverage"],
    "Audiobooks": ["Unlimited Listening", "Bestseller Collection", "Podcast Originals", "Free Trial Month"],
    "Consumer Electronics": ["Latest Innovation", "Trade-In Program", "Holiday Tech Deals", "Pre-Order Exclusive"],
    "Software & Cloud": ["Cloud Solutions", "Productivity Suite", "Business Tools", "Enterprise Solutions"],
    "Software": ["Creative Cloud", "Design Tools", "Professional Software", "Student Discount"],
    "Electric Vehicles": ["Test Drive Event", "Zero Emissions Future", "Advanced Autopilot", "EV Tax Credits"],
    "Computer Hardware": ["New Laptop Launch", "Gaming Workstations", "Business Solutions", "Back to School Sale"],
}

# IAB Content Categories mapped to industries
IAB_CATEGORIES = {
    "Fashion Retail": [
        {"name": "Clothing and Accessories", "iab_id": "1058", "tier": 1},
        {"name": "Retail", "iab_id": "1494", "tier": 1}
    ],
    "Beauty": [
        {"name": "Cosmetics", "iab_id": "1138", "tier": 2},
        {"name": "Cosmetic Services", "iab_id": "1088", "tier": 1}
    ],
    "Athletic Wear": [
        {"name": "Sportswear", "iab_id": "1063", "tier": 3},
        {"name": "Fitness Activities", "iab_id": "1510", "tier": 1}
    ],
    "Fashion Accessories": [
        {"name": "Clothing Accessories", "iab_id": "1068", "tier": 2},
        {"name": "Sunglasses", "iab_id": "1074", "tier": 2}
    ],
    "Music Streaming": [
        {"name": "Media", "iab_id": "1419", "tier": 1},
        {"name": "Music and Video Streaming Services", "iab_id": "1431", "tier": 2}
    ],
    "Event Tickets": [
        {"name": "Events and Performances", "iab_id": "1315", "tier": 1},
        {"name": "Concerts", "iab_id": "1319", "tier": 2}
    ],
    "Musical Instruments": [
        {"name": "Musical Instruments and Record Stores", "iab_id": "1503", "tier": 2}
    ],
    "Streaming": [
        {"name": "Media", "iab_id": "1419", "tier": 1},
        {"name": "Music and Video Streaming Services", "iab_id": "1431", "tier": 2}
    ],
    "Movie Theaters": [
        {"name": "Events and Performances", "iab_id": "1315", "tier": 1},
        {"name": "Cinemas and Movie Events", "iab_id": "1317", "tier": 2}
    ],
    "Financial Services": [
        {"name": "Finance and Insurance", "iab_id": "1335", "tier": 1},
        {"name": "Stocks and Investments", "iab_id": "1351", "tier": 2}
    ],
    "Investment App": [
        {"name": "Financial Investment and Management Applications", "iab_id": "1352", "tier": 2}
    ],
    "Cryptocurrency": [
        {"name": "Non-Fiat Currency", "iab_id": "1448", "tier": 1},
        {"name": "Cryptocurrency Exchanges", "iab_id": "1449", "tier": 2}
    ],
    "Financial Planning": [
        {"name": "Finance and Insurance", "iab_id": "1335", "tier": 1},
        {"name": "Financial Investment and Management Applications", "iab_id": "1352", "tier": 2}
    ],
    "Sports Streaming": [
        {"name": "Media", "iab_id": "1419", "tier": 1},
        {"name": "Sports", "iab_id": "1434", "tier": 2}
    ],
    "Sports Apparel": [
        {"name": "Sportswear", "iab_id": "1063", "tier": 3},
        {"name": "Sporting Goods", "iab_id": "1524", "tier": 1}
    ],
    "Sports Equipment": [
        {"name": "Sporting Goods", "iab_id": "1524", "tier": 1},
        {"name": "Athletics Equipment", "iab_id": "1525", "tier": 2}
    ],
    "Sports Merchandise": [
        {"name": "Sporting Goods", "iab_id": "1524", "tier": 1},
        {"name": "Sports Memorabilia and Trading Cards", "iab_id": "1080", "tier": 2}
    ],
    "Sports Retail": [
        {"name": "Retail", "iab_id": "1494", "tier": 1},
        {"name": "Sporting Goods Stores", "iab_id": "1508", "tier": 2}
    ],
    "News Media": [
        {"name": "Media", "iab_id": "1419", "tier": 1},
        {"name": "News and Analysis", "iab_id": "1432", "tier": 2}
    ],
    "Audiobooks": [
        {"name": "Media", "iab_id": "1419", "tier": 1},
        {"name": "Books and Audio Books", "iab_id": "1422", "tier": 2}
    ],
    "Consumer Electronics": [
        {"name": "Consumer Electronics", "iab_id": "1097", "tier": 1},
        {"name": "Mobile Phones and Accessories", "iab_id": "1114", "tier": 2}
    ],
    "Software & Cloud": [
        {"name": "Computer Software", "iab_id": "1082", "tier": 1},
        {"name": "Web Hosting and Cloud Computing", "iab_id": "1027", "tier": 3}
    ],
    "Software": [
        {"name": "Computer Software", "iab_id": "1082", "tier": 1},
        {"name": "Personal Computer Software", "iab_id": "1086", "tier": 2}
    ],
    "Electric Vehicles": [
        {"name": "Vehicles", "iab_id": "1551", "tier": 1},
        {"name": "Electric Vehicles", "iab_id": "1571", "tier": 3}
    ],
    "Computer Hardware": [
        {"name": "Consumer Electronics", "iab_id": "1097", "tier": 1},
        {"name": "Computers", "iab_id": "1106", "tier": 2}
    ],
}

# Content keywords by category
CONTENT_KEYWORDS = {
    "lifestyle": ["fashion", "style", "trends", "lifestyle", "beauty", "wellness", "shopping"],
    "music": ["music", "concert", "artist", "album", "streaming", "live performance", "entertainment"],
    "movies": ["movies", "film", "cinema", "streaming", "entertainment", "box office", "premiere"],
    "finance": ["finance", "investing", "stock market", "economy", "trading", "money", "wealth"],
    "basketball": ["basketball", "NBA", "sports", "hoops", "playoffs", "team", "athlete"],
    "football": ["football", "NFL", "sports", "touchdown", "game day", "playoffs", "super bowl"],
    "tennis": ["tennis", "tournament", "grand slam", "racquet", "match", "athlete"],
    "soccer": ["soccer", "football", "world cup", "league", "match", "goal", "team"],
    "politics": ["politics", "government", "policy", "election", "news", "current events"],
    "technology": ["technology", "tech", "innovation", "gadgets", "AI", "software", "devices"]
}

# Headlines and descriptions by industry
AD_CONTENT = {
    "Fashion Retail": {
        "headlines": [
            "Spring 2025 Fashion Trends Are Here",
            "Discover Your New Style This Season",
            "Shop the Latest Fashion Collection",
            "Trending Styles for Every Occasion"
        ],
        "descriptions": [
            "Explore spring's hottest trends with our new collection. From soft power dressing to statement pieces, find your perfect look today.",
            "Shop curated fashion picks from our editors. Discover timeless pieces and modern essentials for your wardrobe.",
            "Get free shipping on orders over $50. Browse our latest arrivals and refresh your style for the new season."
        ]
    },
    "Beauty": {
        "headlines": [
            "Elevate Your Beauty Routine",
            "Shop Award-Winning Skincare",
            "Discover Your Perfect Match",
            "Beauty Trends for 2025"
        ],
        "descriptions": [
            "Explore our collection of premium beauty products. From skincare to makeup, find everything you need for your wellness journey.",
            "Join Beauty Insider and earn rewards on every purchase. Get exclusive access to new launches and beauty events.",
            "Shop the latest in beauty innovation. Free samples with every order and expert advice from our beauty advisors."
        ]
    },
    "Music Streaming": {
        "headlines": [
            "Your Soundtrack to Life Awaits",
            "Discover New Music Every Day",
            "Stream Without Limits",
            "Listen to Millions of Songs Free"
        ],
        "descriptions": [
            "Get 3 months of Premium free. Enjoy ad-free music, offline listening, and unlimited skips on all your devices.",
            "Discover new artists and exclusive content. Create playlists, follow your favorite musicians, and explore curated collections.",
            "Stream the latest albums and classic hits. Join millions of listeners enjoying personalized music recommendations."
        ]
    },
    "Streaming": {
        "headlines": [
            "Binge-Worthy Content Awaits",
            "Stream Your Next Obsession",
            "Award-Winning Shows & Movies",
            "Entertainment for Everyone"
        ],
        "descriptions": [
            "Watch thousands of movies and TV shows including exclusive originals. Start your free trial and stream on any device.",
            "New releases every week. From blockbusters to critically acclaimed series, discover your next favorite show.",
            "Get unlimited entertainment for the whole family. Stream on up to 4 devices with our premium plan."
        ]
    },
    "Financial Services": {
        "headlines": [
            "Invest in Your Financial Future",
            "Smart Investing Made Simple",
            "Zero Commission Trading",
            "Build Your Wealth Today"
        ],
        "descriptions": [
            "Start investing with confidence. Get expert guidance, powerful tools, and zero commission trades on stocks and ETFs.",
            "Plan for retirement with our comprehensive financial solutions. Speak with advisors and access educational resources.",
            "Open an account in minutes. Trade stocks, bonds, and funds with award-winning research and customer service."
        ]
    },
    "Investment App": {
        "headlines": [
            "Invest Spare Change Automatically",
            "Start Investing with Just $1",
            "Build Wealth Your Way",
            "Investing for Everyone"
        ],
        "descriptions": [
            "Invest commission-free with fractional shares. Start building your portfolio today with no account minimums.",
            "Join millions of investors growing their wealth. Get real-time market data, research tools, and educational content.",
            "Download the app and start investing in minutes. Buy stocks, ETFs, and crypto all in one place."
        ]
    },
    "Cryptocurrency": {
        "headlines": [
            "Trade Crypto with Confidence",
            "Secure Cryptocurrency Exchange",
            "Start Your Crypto Journey",
            "Buy, Sell, Store Digital Assets"
        ],
        "descriptions": [
            "Trade Bitcoin, Ethereum, and 200+ cryptocurrencies. Industry-leading security and easy-to-use platform.",
            "Earn rewards on your crypto. Stake your assets and earn up to 5% APY on select cryptocurrencies.",
            "Get started with just $10. Sign up today and receive $10 in Bitcoin when you complete your first trade."
        ]
    },
    "Sports Streaming": {
        "headlines": [
            "Watch Every Game Live",
            "Stream Your Team All Season",
            "Never Miss a Moment",
            "Live Sports Streaming"
        ],
        "descriptions": [
            "Watch every game live and on-demand. Get access to exclusive content, replays, and highlights all season long.",
            "Stream on any device. Follow your favorite teams with multi-game viewing and real-time stats.",
            "Subscribe today and watch live games, classic matches, and exclusive behind-the-scenes content."
        ]
    },
    "Sports Apparel": {
        "headlines": [
            "Gear Up for Game Day",
            "Performance Meets Style",
            "Official Athlete Collection",
            "Engineered for Athletes"
        ],
        "descriptions": [
            "Shop the latest performance gear worn by professional athletes. Advanced fabrics keep you comfortable and dry.",
            "Get free shipping on orders over $50. Browse our collection of jerseys, shoes, and training equipment.",
            "Join our rewards program and earn points on every purchase. Get exclusive access to limited edition releases."
        ]
    },
    "Sports Equipment": {
        "headlines": [
            "Professional Grade Equipment",
            "Gear for Champions",
            "Upgrade Your Game",
            "Quality Sports Equipment"
        ],
        "descriptions": [
            "Shop equipment trusted by professional athletes. From training gear to game-day essentials, we have everything you need.",
            "Get expert advice from our team. Find the perfect equipment for your skill level and sport.",
            "Free shipping on all orders. Browse our selection of balls, protective gear, and training accessories."
        ]
    },
    "News Media": {
        "headlines": [
            "Stay Informed with Quality Journalism",
            "Award-Winning News Coverage",
            "Subscribe to Unlimited Access",
            "In-Depth Analysis & Reporting"
        ],
        "descriptions": [
            "Get unlimited access to breaking news, analysis, and investigative reporting. Subscribe today for just $1/week.",
            "Read award-winning journalism from our team of expert reporters. Digital subscription includes newsletters and podcasts.",
            "Stay ahead of the news with real-time updates and comprehensive coverage of politics, business, and culture."
        ]
    },
    "Consumer Electronics": {
        "headlines": [
            "Innovation in Your Hands",
            "Experience the Latest Technology",
            "Pre-Order the Newest Release",
            "Revolutionary Tech Awaits"
        ],
        "descriptions": [
            "Discover cutting-edge technology designed to enhance your life. Shop online with free delivery and easy returns.",
            "Trade in your old device for instant credit. Upgrade to the latest model with flexible payment options.",
            "Pre-order now and be first to experience next-gen innovation. Get exclusive launch day delivery and bonuses."
        ]
    },
    "Software": {
        "headlines": [
            "Create Without Limits",
            "Professional Creative Tools",
            "Transform Your Workflow",
            "Industry-Standard Software"
        ],
        "descriptions": [
            "Access powerful creative apps and cloud services. Start your free trial and bring your ideas to life.",
            "Join millions of creatives using professional design tools. Get tutorials, templates, and cloud storage included.",
            "Students save 60% on Creative Cloud. Get access to Photoshop, Illustrator, and more with educational pricing."
        ]
    },
    "Electric Vehicles": {
        "headlines": [
            "Drive the Future of Transportation",
            "Zero Emissions, Maximum Performance",
            "Schedule Your Test Drive",
            "Experience Electric Innovation"
        ],
        "descriptions": [
            "Discover electric vehicles that combine luxury, performance, and sustainability. Schedule a test drive today.",
            "Learn about federal tax credits and incentives. Configure your dream EV and see your estimated savings.",
            "Advanced autopilot and cutting-edge technology. Experience the most advanced electric vehicles on the road."
        ]
    },
    "Movie Theaters": {
        "headlines": [
            "See It on the Big Screen",
            "Opening Weekend Tickets",
            "Premium Movie Experience",
            "Join Our Movie Club"
        ],
        "descriptions": [
            "Get tickets to the biggest movies of the year. Reserve your seats online for weekend showtimes.",
            "Join our membership program for discounted tickets, free upgrades, and exclusive screenings.",
            "Experience movies the way they were meant to be seen. Premium seating, sound, and picture quality."
        ]
    },
    "Audiobooks": {
        "headlines": [
            "Listen to Unlimited Audiobooks",
            "Your Next Great Listen Awaits",
            "Thousands of Titles Available",
            "Start Your Free Trial"
        ],
        "descriptions": [
            "Get unlimited access to audiobooks, podcasts, and Audible Originals. Try free for 30 days.",
            "Listen anywhere with our mobile app. Download titles and enjoy offline listening on all your devices.",
            "Discover bestsellers, new releases, and exclusive content. Plus members get special discounts and credits."
        ]
    },
    "Sports Merchandise": {
        "headlines": [
            "Official Team Merchandise",
            "Rep Your Team with Pride",
            "Game Day Essentials",
            "Limited Edition Jerseys"
        ],
        "descriptions": [
            "Shop authentic team gear and fan favorites. Get free shipping on orders over $50.",
            "Browse our collection of jerseys, hats, and accessories. Support your team in official merchandise.",
            "New arrivals daily. Find exclusive items and limited edition releases you can't get anywhere else."
        ]
    },
    "Computer Hardware": {
        "headlines": [
            "Power Your Productivity",
            "High-Performance Computing",
            "Shop Business Solutions",
            "Gaming Workstations Available"
        ],
        "descriptions": [
            "Discover laptops and desktops built for performance. Configure your perfect system with expert guidance.",
            "Get special pricing for students and educators. Browse our back-to-school deals on PCs and accessories.",
            "Free shipping and returns. Shop our latest models with powerful processors and stunning displays."
        ]
    },
    "Sports Retail": {
        "headlines": [
            "Everything for Your Sport",
            "Expert Gear Advice",
            "Shop Pro-Level Equipment",
            "Online Exclusive Deals"
        ],
        "descriptions": [
            "Find equipment for every sport and skill level. Get expert advice from our knowledgeable staff.",
            "Shop the latest gear from top brands. Free shipping on all orders with our rewards program.",
            "Browse racquets, apparel, and accessories. Quality equipment at competitive prices."
        ]
    },
    "Fashion Accessories": {
        "headlines": [
            "Find Your Perfect Frames",
            "Home Try-On Available",
            "Designer Eyewear Online",
            "Prescription Glasses from $95"
        ],
        "descriptions": [
            "Shop hundreds of styles online. Try 5 frames at home for free before you buy.",
            "Get designer frames at revolutionary prices. Every pair includes anti-reflective lenses and UV protection.",
            "Buy a pair, give a pair. For every pair sold, we distribute glasses to someone in need."
        ]
    },
    "Event Tickets": {
        "headlines": [
            "Get Tickets to Live Events",
            "Concert Presale Access",
            "Your Event Marketplace",
            "Sports & Concert Tickets"
        ],
        "descriptions": [
            "Find tickets to concerts, sports, theater, and more. Verified tickets with buyer guarantee.",
            "Get presale access and exclusive deals. Download our app for mobile ticket delivery.",
            "Sell your tickets safely and easily. Set your price and reach millions of fans."
        ]
    },
    "Musical Instruments": {
        "headlines": [
            "Play Like the Legends",
            "Professional Instruments",
            "Limited Edition Collection",
            "Beginner to Professional"
        ],
        "descriptions": [
            "Shop guitars, drums, and accessories from iconic brands. Find instruments for every skill level and budget.",
            "Get free shipping on all orders. Browse our collection of electric, acoustic, and bass guitars.",
            "Limited edition models available now. Crafted with premium materials and legendary tone."
        ]
    },
    "Software & Cloud": {
        "headlines": [
            "Cloud Solutions for Business",
            "Boost Team Productivity",
            "Enterprise-Grade Security",
            "Transform Your Workplace"
        ],
        "descriptions": [
            "Access powerful cloud tools for collaboration and productivity. Try Microsoft 365 free for 30 days.",
            "Get email, storage, and Office apps. Enterprise-grade security and 99.9% uptime guarantee.",
            "Connect your team from anywhere. Video conferencing, file sharing, and real-time collaboration."
        ]
    },
    "Financial Planning": {
        "headlines": [
            "Take Control of Your Finances",
            "Track Spending Automatically",
            "Improve Your Credit Score",
            "Free Budget Planning Tools"
        ],
        "descriptions": [
            "Get a complete view of your finances in one place. Track spending, create budgets, and achieve your goals.",
            "Monitor your credit score for free. Get personalized tips to improve your financial health.",
            "Completely free with no ads. Connect your accounts and see all your money in one dashboard."
        ]
    }
}

# Landing pages
LANDING_PAGES = {
    "H&M": "https://www.hm.com",
    "Zara": "https://www.zara.com",
    "Sephora": "https://www.sephora.com",
    "Lululemon": "https://www.lululemon.com",
    "Warby Parker": "https://www.warbyparker.com",
    "Everlane": "https://www.everlane.com",
    "Spotify": "https://www.spotify.com",
    "Apple Music": "https://www.apple.com/apple-music",
    "Ticketmaster": "https://www.ticketmaster.com",
    "Gibson": "https://www.gibson.com",
    "Fender": "https://www.fender.com",
    "Netflix": "https://www.netflix.com",
    "Disney+": "https://www.disneyplus.com",
    "HBO Max": "https://www.hbomax.com",
    "AMC Theatres": "https://www.amctheatres.com",
    "Paramount+": "https://www.paramountplus.com",
    "Fidelity": "https://www.fidelity.com",
    "Charles Schwab": "https://www.schwab.com",
    "Robinhood": "https://www.robinhood.com",
    "Coinbase": "https://www.coinbase.com",
    "Mint": "https://www.mint.com",
    "Credit Karma": "https://www.creditkarma.com",
    "NBA League Pass": "https://www.nba.com/watch",
    "Nike Basketball": "https://www.nike.com/basketball",
    "Spalding": "https://www.spalding.com",
    "Under Armour": "https://www.underarmour.com",
    "NFL Sunday Ticket": "https://www.nfl.com/watch",
    "Nike Football": "https://www.nike.com/football",
    "Riddell": "https://www.riddell.com",
    "Fanatics": "https://www.fanatics.com",
    "Wilson Tennis": "https://www.wilson.com/tennis",
    "Tennis Warehouse": "https://www.tennis-warehouse.com",
    "Adidas Soccer": "https://www.adidas.com/soccer",
    "Puma Soccer": "https://www.puma.com/soccer",
    "SoccerPro": "https://www.soccerpro.com",
    "The New York Times": "https://www.nytimes.com",
    "The Washington Post": "https://www.washingtonpost.com",
    "The Atlantic": "https://www.theatlantic.com",
    "Audible": "https://www.audible.com",
    "Apple": "https://www.apple.com",
    "Samsung": "https://www.samsung.com",
    "Microsoft": "https://www.microsoft.com",
    "Adobe": "https://www.adobe.com",
    "Tesla": "https://www.tesla.com",
    "Google Pixel": "https://store.google.com/pixel",
    "Dell": "https://www.dell.com",
    "Lenovo": "https://www.lenovo.com",
}

CTA_OPTIONS = ["Shop Now", "Learn More", "Subscribe", "Get Started", "Try Free", "Book Now", "Sign Up", "Watch Now", "Download", "Pre-Order"]

SAMPLE_IMAGES = [
    "https://images.unsplash.com/photo-1441986300917-64674bd600d8",
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30",
    "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f",
    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
    "https://images.unsplash.com/photo-1560343090-f0409e92791a",
    "https://images.unsplash.com/photo-1572635196237-14b3f281503f",
    "https://images.unsplash.com/photo-1556742400-b5b1b10f2c9e",
]

def generate_ad(ad_id: int, advertiser_data: Dict, campaign_name: str, content_category: str) -> Dict:
    """Generate a single realistic ad"""
    industry = advertiser_data["industry"]
    advertiser_name = advertiser_data["name"]
    budget_range = advertiser_data["budget_range"]

    # Generate dates
    start_date = datetime.now() - timedelta(days=random.randint(0, 90))
    end_date = start_date + timedelta(days=random.randint(30, 180))

    # Generate budget
    total_budget = random.randint(budget_range[0], budget_range[1])
    daily_budget = round(total_budget / ((end_date - start_date).days), 2)
    days_elapsed = (datetime.now() - start_date).days
    spent = min(days_elapsed * daily_budget, total_budget)
    remaining = max(0, total_budget - spent)

    # Get IAB categories
    topics = IAB_CATEGORIES.get(industry, [{"name": "General", "iab_id": "1000"}])

    # Get content keywords
    keywords = CONTENT_KEYWORDS.get(content_category, ["general"])

    # Get ad content
    ad_content = AD_CONTENT.get(industry, {
        "headlines": ["Discover Something New"],
        "descriptions": ["Explore our latest offerings and find what you need today."]
    })

    headline = random.choice(ad_content["headlines"])
    description = random.choice(ad_content["descriptions"])

    # Select CTA
    cta = random.choice(CTA_OPTIONS)

    # Get landing page
    landing_page = LANDING_PAGES.get(advertiser_name, "https://www.example.com")

    status_options = ["active", "active", "active", "paused", "completed"]

    ad = {
        "id": f"{ad_id:03d}",
        "advertiser": {
            "name": advertiser_name,
            "budget": total_budget,
            "currency": "USD"
        },
        "campaign": {
            "name": campaign_name
        },
        "creative": {
            "headline": headline,
            "description": description,
            "image_url": random.choice(SAMPLE_IMAGES) + f"?w=1200&h=630&fit=crop&q=80&ad={ad_id}",
            "call_to_action": cta,
            "landing_page_url": landing_page
        },
        "targeting": {
            "keywords": random.sample(keywords, k=min(len(keywords), random.randint(3, 5))),
            "topics": topics,
            "entities": [advertiser_name, industry],
            "countries": ["US"],
            "languages": ["en"]
        },
        "content_category": content_category,
        "daily_budget": daily_budget,
        "remaining_budget": round(remaining, 2),
        "status": random.choice(status_options),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "created_at": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "impressions": random.randint(10000, 500000) if days_elapsed > 0 else 0,
        "clicks": random.randint(100, 10000) if days_elapsed > 0 else 0,
        "spend": round(spent, 2)
    }

    return ad

def generate_ad_inventory(num_ads: int = 10) -> List[Dict]:
    """Generate a complete ad inventory with diverse content categories"""
    ads = []

    # Content categories from URLs
    content_categories = [
        "lifestyle", "music", "movies", "finance",
        "basketball", "football", "tennis", "soccer",
        "politics", "technology"
    ]

    # Map industries to content categories
    industry_to_category = {
        "Fashion Retail": "lifestyle",
        "Beauty": "lifestyle",
        "Athletic Wear": "lifestyle",
        "Fashion Accessories": "lifestyle",
        "Music Streaming": "music",
        "Event Tickets": "music",
        "Musical Instruments": "music",
        "Streaming": "movies",
        "Movie Theaters": "movies",
        "Financial Services": "finance",
        "Investment App": "finance",
        "Cryptocurrency": "finance",
        "Financial Planning": "finance",
        "Sports Streaming": ["basketball", "football", "tennis", "soccer"],
        "Sports Apparel": ["basketball", "football", "tennis", "soccer"],
        "Sports Equipment": ["basketball", "football", "tennis", "soccer"],
        "Sports Merchandise": ["basketball", "football", "tennis", "soccer"],
        "Sports Retail": ["basketball", "football", "tennis", "soccer"],
        "News Media": "politics",
        "Audiobooks": "politics",
        "Consumer Electronics": "technology",
        "Software & Cloud": "technology",
        "Software": "technology",
        "Electric Vehicles": "technology",
        "Computer Hardware": "technology",
    }

    for i in range(num_ads):
        # Select random advertiser
        advertiser = random.choice(ADVERTISERS)
        industry = advertiser["industry"]

        # Get content category for this industry
        category_mapping = industry_to_category.get(industry, "lifestyle")
        if isinstance(category_mapping, list):
            content_category = random.choice(category_mapping)
        else:
            content_category = category_mapping

        # Select random campaign
        campaign_templates = CAMPAIGN_TEMPLATES.get(industry, ["General Campaign"])
        campaign_name = random.choice(campaign_templates)

        # Generate ad
        ad = generate_ad(i + 1, advertiser, campaign_name, content_category)
        ads.append(ad)

    return ads

def main():
    print("Generating 500 contextually relevant ads...")
    print("Categories: lifestyle, music, movies, finance, basketball, football, tennis, soccer, politics, technology\n")

    # Generate ads
    ads = generate_ad_inventory(50)

    # Save to JSON file
    output_file = "../data/ads_inventory.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ads, f, indent=2, ensure_ascii=False)

    print(f"✓ Successfully generated {len(ads)} ads")
    print(f"✓ Saved to: {output_file}")
    print(f"\nSample ad preview:")
    print(json.dumps(ads[0], indent=2))

    print(f"\n--- Inventory Statistics ---")
    print(f"Total ads: {len(ads)}")
    print(f"Unique advertisers: {len(set(ad['advertiser']['name'] for ad in ads))}")
    print(f"Active ads: {sum(1 for ad in ads if ad['status'] == 'active')}")
    print(f"Total budget: ${sum(ad['advertiser']['budget'] for ad in ads):,.2f}")

    # Content category breakdown
    categories = {}
    for ad in ads:
        category = ad.get('content_category', 'unknown')
        categories[category] = categories.get(category, 0) + 1

    print(f"\n--- Content Category Breakdown ---")
    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"{category}: {count} ads")

    # Industry breakdown
    industries = {}
    for ad in ads:
        advertiser = next(a for a in ADVERTISERS if a['name'] == ad['advertiser']['name'])
        industry = advertiser['industry']
        industries[industry] = industries.get(industry, 0) + 1

    print(f"\n--- Industry Breakdown ---")
    for industry, count in sorted(industries.items(), key=lambda x: x[1], reverse=True):
        print(f"{industry}: {count} ads")

    print(f"\n--- Top Advertisers ---")
    advertiser_counts = {}
    for ad in ads:
        name = ad['advertiser']['name']
        advertiser_counts[name] = advertiser_counts.get(name, 0) + 1

    for name, count in sorted(advertiser_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"{name}: {count} ads")

if __name__ == "__main__":
    main()