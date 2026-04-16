#!/usr/bin/env python3
"""
Bulk Ad Campaign Inventory Generator

Generates realistic ad campaign inventories at any scale (10k, 50k, 100k+) with:
- 400+ advertisers across 74 industries
- Full IAB taxonomy integration (1,179 content + 583 product categories)
- Typed entities (BRAND, PRODUCT, ORGANIZATION, PERSON)
- Weighted country/device distributions
- API-compatible output matching CreateCampaignHTTPRequest schema

All creative content (headlines, descriptions, CTAs) is sourced from the
creative bank (data/creative_bank.json). Run generate_creative_bank.py first
to generate rich, diverse creatives via Claude API.

The generator scales linearly: campaigns are distributed evenly across all
advertisers, so increasing --count simply gives each advertiser more campaigns.
No code changes needed for any count.

Usage:
    python bulk_ads_generator.py                        # 10k campaigns (default)
    python bulk_ads_generator.py --count 50000          # 50k campaigns
    python bulk_ads_generator.py --count 100000         # 100k campaigns
    python bulk_ads_generator.py --count 500 --seed 99  # 500 campaigns, custom seed

Output:
    data/campaign_requests_{count}.json   # e.g., campaign_requests_10k.json
    data/advertisers_list.json            # Advertiser reference list
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent.parent / "data"


COUNTRIES_WEIGHTED = [
    ("US", 10), ("CA", 10), ("GB", 60), ("DE", 8), ("FR", 7), ("AU", 5),
]

DEVICES = ["mobile", "desktop", "tablet"]

# Device distribution per industry type (mobile%, desktop%, tablet%)
DEVICE_WEIGHTS = {
    "entertainment": (55, 30, 15),
    "finance": (35, 55, 10),
    "b2b": (20, 70, 10),
    "ecommerce": (50, 35, 15),
    "sports": (55, 30, 15),
    "news": (50, 35, 15),
    "technology": (40, 50, 10),
    "lifestyle": (55, 30, 15),
    "education": (35, 45, 20),
    "health": (45, 40, 15),
    "default": (45, 40, 15),
}

CREATIVE_TYPES_WEIGHTED = [("banner", 100)]
PRICING_MODELS_WEIGHTED = [("CPM", 60), ("CPC", 40)]
CAMPAIGN_STATUS_WEIGHTED = [("ACTIVE", 99), ("PAUSED", 0.5), ("COMPLETED", 0.5)]
CREATIVE_STATUS_WEIGHTED = [('PENDING_ANALYSIS', 100)]


SAMPLE_IMAGES = [
    "https://images.unsplash.com/photo-1441986300917-64674bd600d8",
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30",
    "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f",
    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
    "https://images.unsplash.com/photo-1560343090-f0409e92791a",
    "https://images.unsplash.com/photo-1572635196237-14b3f281503f",
    "https://images.unsplash.com/photo-1556742400-b5b1b10f2c9e",
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff",
    "https://images.unsplash.com/photo-1491553895911-0055eca6402d",
    "https://images.unsplash.com/photo-1553062407-98eeb64c6a62",
    "https://images.unsplash.com/photo-1546868871-af0de0ae72be",
    "https://images.unsplash.com/photo-1498050108023-c5249f4df085",
    "https://images.unsplash.com/photo-1519389950473-47ba0277781c",
    "https://images.unsplash.com/photo-1460925895917-afdab827c52f",
    "https://images.unsplash.com/photo-1551288049-bebda4e38f71",
]


# Each industry has: type (for device/CTA weighting), content_categories, IAB product taxonomy IDs
INDUSTRIES = {
    # Fashion & Lifestyle
    "Fashion Retail": {"type": "ecommerce", "categories": ["lifestyle"], "product_iab_root": [1058, 1068]},
    "Beauty": {"type": "ecommerce", "categories": ["lifestyle"], "product_iab_root": [1088, 1138]},
    "Athletic Wear": {"type": "ecommerce", "categories": ["lifestyle", "sports"], "product_iab_root": [1063, 1510]},
    "Fashion Accessories": {"type": "ecommerce", "categories": ["lifestyle"], "product_iab_root": [1068, 1074]},
    "Luxury Goods": {"type": "ecommerce", "categories": ["lifestyle"], "product_iab_root": [1058, 1068, 1494]},
    # Entertainment
    "Music Streaming": {"type": "entertainment", "categories": ["music", "entertainment"], "product_iab_root": [1419, 1431]},
    "Event Tickets": {"type": "entertainment", "categories": ["music", "entertainment"], "product_iab_root": [1315, 1319]},
    "Musical Instruments": {"type": "ecommerce", "categories": ["music"], "product_iab_root": [1503]},
    "Streaming": {"type": "entertainment", "categories": ["movies", "entertainment"], "product_iab_root": [1419, 1431]},
    "Movie Theaters": {"type": "entertainment", "categories": ["movies"], "product_iab_root": [1315, 1317]},
    "Gaming": {"type": "entertainment", "categories": ["gaming", "technology"], "product_iab_root": [1097, 1082]},
    # Finance
    "Financial Services": {"type": "finance", "categories": ["finance"], "product_iab_root": [1335, 1351]},
    "Investment App": {"type": "finance", "categories": ["finance"], "product_iab_root": [1352]},
    "Cryptocurrency": {"type": "finance", "categories": ["finance", "technology"], "product_iab_root": [1448, 1449]},
    "Financial Planning": {"type": "finance", "categories": ["finance"], "product_iab_root": [1335, 1352]},
    "Insurance": {"type": "finance", "categories": ["finance"], "product_iab_root": [1335, 1351]},
    # Sports
    "Sports Streaming": {"type": "sports", "categories": ["basketball", "football", "tennis", "soccer", "sports"], "product_iab_root": [1419, 1434]},
    "Sports Apparel": {"type": "sports", "categories": ["basketball", "football", "tennis", "soccer", "sports"], "product_iab_root": [1063, 1524]},
    "Sports Equipment": {"type": "sports", "categories": ["basketball", "football", "tennis", "soccer", "sports"], "product_iab_root": [1524, 1525]},
    "Sports Merchandise": {"type": "sports", "categories": ["basketball", "football", "tennis", "soccer", "sports"], "product_iab_root": [1524, 1080]},
    "Sports Retail": {"type": "sports", "categories": ["basketball", "football", "tennis", "soccer", "sports"], "product_iab_root": [1494, 1508]},
    # Technology
    "Consumer Electronics": {"type": "technology", "categories": ["technology"], "product_iab_root": [1097, 1114]},
    "Software & Cloud": {"type": "b2b", "categories": ["technology"], "product_iab_root": [1082, 1027]},
    "Software": {"type": "technology", "categories": ["technology"], "product_iab_root": [1082, 1086]},
    "Electric Vehicles": {"type": "technology", "categories": ["technology", "automotive"], "product_iab_root": [1551, 1571]},
    "Computer Hardware": {"type": "technology", "categories": ["technology"], "product_iab_root": [1097, 1106]},
    "Telecom": {"type": "technology", "categories": ["technology"], "product_iab_root": [1097, 1082]},
    # News & Media
    "News Media": {"type": "news", "categories": ["politics", "news"], "product_iab_root": [1419, 1432]},
    "Audiobooks": {"type": "entertainment", "categories": ["books", "entertainment"], "product_iab_root": [1419, 1422]},
    # Real Estate
    "Real Estate": {"type": "finance", "categories": ["real_estate"], "product_iab_root": [1335]},
    # Pet Products
    "Pet Products": {"type": "ecommerce", "categories": ["lifestyle", "pets"], "product_iab_root": [1494]},
    # Home & Garden
    "Home & Garden": {"type": "ecommerce", "categories": ["lifestyle", "home"], "product_iab_root": [1494]},
    # Education
    "EdTech": {"type": "education", "categories": ["education", "technology"], "product_iab_root": [1082]},
    # Food & Beverage
    "Food Delivery": {"type": "ecommerce", "categories": ["food", "lifestyle"], "product_iab_root": [1494]},
    "Restaurants": {"type": "ecommerce", "categories": ["food", "lifestyle"], "product_iab_root": [1494]},
    "Craft Beer & Spirits": {"type": "ecommerce", "categories": ["food", "beverages"], "product_iab_root": [1494]},
    "Energy Drinks": {"type": "ecommerce", "categories": ["beverages", "sports"], "product_iab_root": [1494, 1510]},
    "Coffee & Tea": {"type": "ecommerce", "categories": ["food", "beverages"], "product_iab_root": [1494]},
    # Health & Wellness
    "Fitness & Wellness": {"type": "health", "categories": ["health", "lifestyle"], "product_iab_root": [1510]},
    "Healthcare": {"type": "health", "categories": ["health"], "product_iab_root": [1335]},
    "Pharmaceuticals": {"type": "health", "categories": ["health", "pharma"], "product_iab_root": [1335]},
    "Supplements & Nutrition": {"type": "health", "categories": ["health", "food"], "product_iab_root": [1510, 1494]},
    # Travel & Hospitality
    "Travel": {"type": "lifestyle", "categories": ["travel", "lifestyle"], "product_iab_root": [1494]},
    "Airlines": {"type": "lifestyle", "categories": ["travel"], "product_iab_root": [1494]},
    "Hotels & Resorts": {"type": "lifestyle", "categories": ["travel", "hospitality"], "product_iab_root": [1494]},
    "Cruises": {"type": "lifestyle", "categories": ["travel", "hospitality"], "product_iab_root": [1494]},
    # Automotive
    "Automotive": {"type": "technology", "categories": ["automotive", "technology"], "product_iab_root": [1551]},
    # B2B / SaaS / Professional Services
    "B2B SaaS": {"type": "b2b", "categories": ["technology"], "product_iab_root": [1082, 1010]},
    "Cybersecurity": {"type": "b2b", "categories": ["technology"], "product_iab_root": [1082]},
    "HR & Recruiting": {"type": "b2b", "categories": ["technology", "careers"], "product_iab_root": [1082, 1010]},
    "Accounting & Tax": {"type": "b2b", "categories": ["finance", "technology"], "product_iab_root": [1335, 1082]},
    "Legal Services": {"type": "b2b", "categories": ["legal", "technology"], "product_iab_root": [1335]},
    # Culture & Society
    "Culture": {"type": "lifestyle", "categories": ["culture", "entertainment"], "product_iab_root": [1315, 1319]},
    "Education": {"type": "education", "categories": ["education"], "product_iab_root": [1082]},
    "Non-Profit": {"type": "default", "categories": ["non_profit", "news"], "product_iab_root": [1335]},
    "Government": {"type": "default", "categories": ["government", "politics"], "product_iab_root": [1335]},
    "Politics": {"type": "news", "categories": ["politics", "news"], "product_iab_root": [1419, 1432]},
    # Social & Creator
    "Social Media": {"type": "technology", "categories": ["technology", "social_media"], "product_iab_root": [1082, 1419]},
    "Creator Economy": {"type": "technology", "categories": ["technology", "social_media"], "product_iab_root": [1082, 1419]},
    # Tech Verticals
    "Technology": {"type": "technology", "categories": ["technology", "ai"], "product_iab_root": [1082, 1097]},
    "AI": {"type": "technology", "categories": ["ai", "technology"], "product_iab_root": [1082]},
    "FinTech": {"type": "finance", "categories": ["finance", "technology"], "product_iab_root": [1335, 1082]},
    "HealthTech": {"type": "health", "categories": ["health", "technology"], "product_iab_root": [1335, 1082]},
    # E-commerce & Banking
    "E-commerce": {"type": "ecommerce", "categories": ["ecommerce", "technology"], "product_iab_root": [1494, 1082]},
    "Personal Banking": {"type": "finance", "categories": ["finance", "personal_banking"], "product_iab_root": [1335, 1351]},
    # Family
    "Baby & Parenting": {"type": "ecommerce", "categories": ["parenting", "lifestyle"], "product_iab_root": [1494]},
    "Kids & Family Entertainment": {"type": "entertainment", "categories": ["entertainment", "parenting"], "product_iab_root": [1315, 1419]},
    # Home Services & Utilities
    "Home Services": {"type": "ecommerce", "categories": ["home", "lifestyle"], "product_iab_root": [1494]},
    "Cleaning & Household": {"type": "ecommerce", "categories": ["home", "lifestyle"], "product_iab_root": [1494]},
    "Solar & Renewable Energy": {"type": "technology", "categories": ["sustainability", "technology"], "product_iab_root": [1082]},
    # Privacy & Security
    "Identity & Privacy": {"type": "technology", "categories": ["technology", "legal"], "product_iab_root": [1082]},
    # Weddings
    "Weddings": {"type": "lifestyle", "categories": ["lifestyle", "events"], "product_iab_root": [1494, 1315]},
    # Logistics
    "Logistics & Shipping": {"type": "b2b", "categories": ["logistics", "technology"], "product_iab_root": [1494, 1082]},
    # Sustainability
    "Sustainability": {"type": "lifestyle", "categories": ["sustainability", "lifestyle"], "product_iab_root": [1494]},
}

# 300+ advertisers across all industries
ADVERTISERS = [
    # Fashion Retail (15)
    {"name": "H&M", "industry": "Fashion Retail", "website": "https://www.hm.com", "budget_range": (5000, 15000)},
    {"name": "Zara", "industry": "Fashion Retail", "website": "https://www.zara.com", "budget_range": (5500, 16500)},
    {"name": "Everlane", "industry": "Fashion Retail", "website": "https://www.everlane.com", "budget_range": (3500, 10000)},
    {"name": "ASOS", "industry": "Fashion Retail", "website": "https://www.asos.com", "budget_range": (6000, 18000)},
    {"name": "Uniqlo", "industry": "Fashion Retail", "website": "https://www.uniqlo.com", "budget_range": (5500, 16000)},
    {"name": "Nordstrom", "industry": "Fashion Retail", "website": "https://www.nordstrom.com", "budget_range": (7000, 20000)},
    {"name": "Gap", "industry": "Fashion Retail", "website": "https://www.gap.com", "budget_range": (5000, 14500)},
    {"name": "J.Crew", "industry": "Fashion Retail", "website": "https://www.jcrew.com", "budget_range": (4500, 13000)},
    {"name": "Mango", "industry": "Fashion Retail", "website": "https://www.mango.com", "budget_range": (4500, 13500)},
    {"name": "Anthropologie", "industry": "Fashion Retail", "website": "https://www.anthropologie.com", "budget_range": (4000, 12000)},
    {"name": "Reformation", "industry": "Fashion Retail", "website": "https://www.thereformation.com", "budget_range": (3500, 10000)},
    {"name": "Stitch Fix", "industry": "Fashion Retail", "website": "https://www.stitchfix.com", "budget_range": (4000, 11500)},
    {"name": "Shein", "industry": "Fashion Retail", "website": "https://www.shein.com", "budget_range": (8000, 25000)},
    {"name": "ThredUp", "industry": "Fashion Retail", "website": "https://www.thredup.com", "budget_range": (3000, 9000)},
    {"name": "Revolve", "industry": "Fashion Retail", "website": "https://www.revolve.com", "budget_range": (4500, 13000)},
    # Beauty (10)
    {"name": "Sephora", "industry": "Beauty", "website": "https://www.sephora.com", "budget_range": (5500, 16000)},
    {"name": "Glossier", "industry": "Beauty", "website": "https://www.glossier.com", "budget_range": (4000, 12000)},
    {"name": "Ulta Beauty", "industry": "Beauty", "website": "https://www.ulta.com", "budget_range": (5000, 15000)},
    {"name": "Fenty Beauty", "industry": "Beauty", "website": "https://www.fentybeauty.com", "budget_range": (5500, 16500)},
    {"name": "The Ordinary", "industry": "Beauty", "website": "https://www.theordinary.com", "budget_range": (3000, 9000)},
    {"name": "MAC Cosmetics", "industry": "Beauty", "website": "https://www.maccosmetics.com", "budget_range": (5000, 15000)},
    {"name": "Clinique", "industry": "Beauty", "website": "https://www.clinique.com", "budget_range": (4500, 13500)},
    {"name": "Drunk Elephant", "industry": "Beauty", "website": "https://www.drunkelephant.com", "budget_range": (3500, 10500)},
    {"name": "Tatcha", "industry": "Beauty", "website": "https://www.tatcha.com", "budget_range": (3500, 10000)},
    {"name": "Charlotte Tilbury", "industry": "Beauty", "website": "https://www.charlottetilbury.com", "budget_range": (4500, 14000)},
    # Athletic Wear (8)
    {"name": "Lululemon", "industry": "Athletic Wear", "website": "https://www.lululemon.com", "budget_range": (5000, 14500)},
    {"name": "Nike Training", "industry": "Athletic Wear", "website": "https://www.nike.com/training", "budget_range": (7000, 20000)},
    {"name": "Gymshark", "industry": "Athletic Wear", "website": "https://www.gymshark.com", "budget_range": (4000, 12000)},
    {"name": "Athleta", "industry": "Athletic Wear", "website": "https://www.athleta.com", "budget_range": (4000, 11500)},
    {"name": "Alo Yoga", "industry": "Athletic Wear", "website": "https://www.aloyoga.com", "budget_range": (3500, 10000)},
    {"name": "Vuori", "industry": "Athletic Wear", "website": "https://www.vuoriclothing.com", "budget_range": (3000, 9000)},
    {"name": "Outdoor Voices", "industry": "Athletic Wear", "website": "https://www.outdoorvoices.com", "budget_range": (2500, 8000)},
    {"name": "Fabletics", "industry": "Athletic Wear", "website": "https://www.fabletics.com", "budget_range": (3500, 10500)},
    # Fashion Accessories (6)
    {"name": "Warby Parker", "industry": "Fashion Accessories", "website": "https://www.warbyparker.com", "budget_range": (4000, 12000)},
    {"name": "Ray-Ban", "industry": "Fashion Accessories", "website": "https://www.ray-ban.com", "budget_range": (5000, 15000)},
    {"name": "Coach", "industry": "Fashion Accessories", "website": "https://www.coach.com", "budget_range": (5500, 16500)},
    {"name": "Kate Spade", "industry": "Fashion Accessories", "website": "https://www.katespade.com", "budget_range": (4500, 13500)},
    {"name": "Fossil", "industry": "Fashion Accessories", "website": "https://www.fossil.com", "budget_range": (3500, 10000)},
    {"name": "Tiffany & Co", "industry": "Fashion Accessories", "website": "https://www.tiffany.com", "budget_range": (6000, 18000)},
    # Luxury Goods (6)
    {"name": "Louis Vuitton", "industry": "Luxury Goods", "website": "https://www.louisvuitton.com", "budget_range": (10000, 30000)},
    {"name": "Gucci", "industry": "Luxury Goods", "website": "https://www.gucci.com", "budget_range": (9000, 28000)},
    {"name": "Prada", "industry": "Luxury Goods", "website": "https://www.prada.com", "budget_range": (8500, 26000)},
    {"name": "Burberry", "industry": "Luxury Goods", "website": "https://www.burberry.com", "budget_range": (8000, 24000)},
    {"name": "Hermès", "industry": "Luxury Goods", "website": "https://www.hermes.com", "budget_range": (9500, 29000)},
    {"name": "Cartier", "industry": "Luxury Goods", "website": "https://www.cartier.com", "budget_range": (9000, 27000)},
    # Music Streaming (5)
    {"name": "Spotify", "industry": "Music Streaming", "website": "https://www.spotify.com", "budget_range": (9000, 25000)},
    {"name": "Apple Music", "industry": "Music Streaming", "website": "https://www.apple.com/apple-music", "budget_range": (10000, 28000)},
    {"name": "Tidal", "industry": "Music Streaming", "website": "https://www.tidal.com", "budget_range": (5000, 14000)},
    {"name": "Amazon Music", "industry": "Music Streaming", "website": "https://music.amazon.com", "budget_range": (8000, 23000)},
    {"name": "Deezer", "industry": "Music Streaming", "website": "https://www.deezer.com", "budget_range": (4500, 13000)},
    # Event Tickets (4)
    {"name": "Ticketmaster", "industry": "Event Tickets", "website": "https://www.ticketmaster.com", "budget_range": (7000, 20000)},
    {"name": "StubHub", "industry": "Event Tickets", "website": "https://www.stubhub.com", "budget_range": (5500, 16000)},
    {"name": "SeatGeek", "industry": "Event Tickets", "website": "https://www.seatgeek.com", "budget_range": (4500, 13000)},
    {"name": "Vivid Seats", "industry": "Event Tickets", "website": "https://www.vividseats.com", "budget_range": (4000, 11500)},
    # Musical Instruments (4)
    {"name": "Gibson", "industry": "Musical Instruments", "website": "https://www.gibson.com", "budget_range": (4500, 13000)},
    {"name": "Fender", "industry": "Musical Instruments", "website": "https://www.fender.com", "budget_range": (4500, 13000)},
    {"name": "Yamaha Music", "industry": "Musical Instruments", "website": "https://www.yamaha.com", "budget_range": (5000, 14500)},
    {"name": "Roland", "industry": "Musical Instruments", "website": "https://www.roland.com", "budget_range": (4000, 11500)},
    # Streaming (8)
    {"name": "Netflix", "industry": "Streaming", "website": "https://www.netflix.com", "budget_range": (12000, 35000)},
    {"name": "Disney+", "industry": "Streaming", "website": "https://www.disneyplus.com", "budget_range": (11000, 32000)},
    {"name": "HBO Max", "industry": "Streaming", "website": "https://www.hbomax.com", "budget_range": (10000, 29000)},
    {"name": "Paramount+", "industry": "Streaming", "website": "https://www.paramountplus.com", "budget_range": (8500, 24000)},
    {"name": "Hulu", "industry": "Streaming", "website": "https://www.hulu.com", "budget_range": (9000, 26000)},
    {"name": "Peacock", "industry": "Streaming", "website": "https://www.peacocktv.com", "budget_range": (7500, 22000)},
    {"name": "Apple TV+", "industry": "Streaming", "website": "https://tv.apple.com", "budget_range": (10000, 30000)},
    {"name": "Crunchyroll", "industry": "Streaming", "website": "https://www.crunchyroll.com", "budget_range": (4000, 12000)},
    # Movie Theaters (4)
    {"name": "AMC Theatres", "industry": "Movie Theaters", "website": "https://www.amctheatres.com", "budget_range": (6000, 18000)},
    {"name": "Regal Cinemas", "industry": "Movie Theaters", "website": "https://www.regmovies.com", "budget_range": (5000, 15000)},
    {"name": "Cinemark", "industry": "Movie Theaters", "website": "https://www.cinemark.com", "budget_range": (4500, 13500)},
    {"name": "Alamo Drafthouse", "industry": "Movie Theaters", "website": "https://www.drafthouse.com", "budget_range": (3000, 9000)},
    # Gaming (8)
    {"name": "PlayStation", "industry": "Gaming", "website": "https://www.playstation.com", "budget_range": (10000, 30000)},
    {"name": "Xbox", "industry": "Gaming", "website": "https://www.xbox.com", "budget_range": (10000, 30000)},
    {"name": "Nintendo", "industry": "Gaming", "website": "https://www.nintendo.com", "budget_range": (9000, 27000)},
    {"name": "Steam", "industry": "Gaming", "website": "https://store.steampowered.com", "budget_range": (7000, 20000)},
    {"name": "Epic Games", "industry": "Gaming", "website": "https://www.epicgames.com", "budget_range": (8000, 24000)},
    {"name": "Riot Games", "industry": "Gaming", "website": "https://www.riotgames.com", "budget_range": (7500, 22000)},
    {"name": "EA Sports", "industry": "Gaming", "website": "https://www.ea.com", "budget_range": (9000, 27000)},
    {"name": "Activision", "industry": "Gaming", "website": "https://www.activision.com", "budget_range": (8500, 25500)},
    # Financial Services (8)
    {"name": "Fidelity", "industry": "Financial Services", "website": "https://www.fidelity.com", "budget_range": (9000, 26000)},
    {"name": "Charles Schwab", "industry": "Financial Services", "website": "https://www.schwab.com", "budget_range": (8500, 25000)},
    {"name": "Vanguard", "industry": "Financial Services", "website": "https://www.vanguard.com", "budget_range": (8000, 24000)},
    {"name": "TD Ameritrade", "industry": "Financial Services", "website": "https://www.tdameritrade.com", "budget_range": (7500, 22000)},
    {"name": "E*TRADE", "industry": "Financial Services", "website": "https://www.etrade.com", "budget_range": (7000, 20000)},
    {"name": "Goldman Sachs", "industry": "Financial Services", "website": "https://www.goldmansachs.com", "budget_range": (10000, 30000)},
    {"name": "JP Morgan", "industry": "Financial Services", "website": "https://www.jpmorgan.com", "budget_range": (10000, 30000)},
    {"name": "Morgan Stanley", "industry": "Financial Services", "website": "https://www.morganstanley.com", "budget_range": (9000, 27000)},
    # Investment App (5)
    {"name": "Robinhood", "industry": "Investment App", "website": "https://www.robinhood.com", "budget_range": (7000, 20000)},
    {"name": "Acorns", "industry": "Investment App", "website": "https://www.acorns.com", "budget_range": (4000, 12000)},
    {"name": "Wealthfront", "industry": "Investment App", "website": "https://www.wealthfront.com", "budget_range": (4500, 13500)},
    {"name": "Betterment", "industry": "Investment App", "website": "https://www.betterment.com", "budget_range": (4500, 13000)},
    {"name": "SoFi", "industry": "Investment App", "website": "https://www.sofi.com", "budget_range": (5500, 16500)},
    # Cryptocurrency (5)
    {"name": "Coinbase", "industry": "Cryptocurrency", "website": "https://www.coinbase.com", "budget_range": (7500, 22000)},
    {"name": "Kraken", "industry": "Cryptocurrency", "website": "https://www.kraken.com", "budget_range": (6000, 17500)},
    {"name": "Gemini", "industry": "Cryptocurrency", "website": "https://www.gemini.com", "budget_range": (5500, 16000)},
    {"name": "Binance US", "industry": "Cryptocurrency", "website": "https://www.binance.us", "budget_range": (6500, 19000)},
    {"name": "Crypto.com", "industry": "Cryptocurrency", "website": "https://crypto.com", "budget_range": (7000, 20000)},
    # Financial Planning (4)
    {"name": "Mint", "industry": "Financial Planning", "website": "https://www.mint.com", "budget_range": (5000, 15000)},
    {"name": "Credit Karma", "industry": "Financial Planning", "website": "https://www.creditkarma.com", "budget_range": (6000, 17500)},
    {"name": "YNAB", "industry": "Financial Planning", "website": "https://www.ynab.com", "budget_range": (3000, 9000)},
    {"name": "Personal Capital", "industry": "Financial Planning", "website": "https://www.personalcapital.com", "budget_range": (4000, 12000)},
    # Insurance (6)
    {"name": "Geico", "industry": "Insurance", "website": "https://www.geico.com", "budget_range": (10000, 30000)},
    {"name": "Progressive", "industry": "Insurance", "website": "https://www.progressive.com", "budget_range": (9500, 28500)},
    {"name": "State Farm", "industry": "Insurance", "website": "https://www.statefarm.com", "budget_range": (9000, 27000)},
    {"name": "Allstate", "industry": "Insurance", "website": "https://www.allstate.com", "budget_range": (8500, 25500)},
    {"name": "Lemonade", "industry": "Insurance", "website": "https://www.lemonade.com", "budget_range": (5000, 15000)},
    {"name": "Root Insurance", "industry": "Insurance", "website": "https://www.joinroot.com", "budget_range": (4000, 12000)},
    # Sports (various sub-industries) (20)
    {"name": "NBA League Pass", "industry": "Sports Streaming", "website": "https://www.nba.com/watch", "budget_range": (8000, 23000)},
    {"name": "NFL Sunday Ticket", "industry": "Sports Streaming", "website": "https://www.nfl.com/watch", "budget_range": (10000, 29000)},
    {"name": "ESPN+", "industry": "Sports Streaming", "website": "https://www.espn.com/espnplus", "budget_range": (9000, 26000)},
    {"name": "DAZN", "industry": "Sports Streaming", "website": "https://www.dazn.com", "budget_range": (7000, 20000)},
    {"name": "Nike Basketball", "industry": "Sports Apparel", "website": "https://www.nike.com/basketball", "budget_range": (9000, 26000)},
    {"name": "Under Armour", "industry": "Sports Apparel", "website": "https://www.underarmour.com", "budget_range": (7000, 20000)},
    {"name": "Adidas Soccer", "industry": "Sports Apparel", "website": "https://www.adidas.com/soccer", "budget_range": (8500, 24500)},
    {"name": "Puma Soccer", "industry": "Sports Apparel", "website": "https://www.puma.com/soccer", "budget_range": (7000, 20000)},
    {"name": "Nike Football", "industry": "Sports Apparel", "website": "https://www.nike.com/football", "budget_range": (9000, 26000)},
    {"name": "New Balance Athletics", "industry": "Sports Apparel", "website": "https://www.newbalance.com", "budget_range": (6000, 17500)},
    {"name": "Spalding", "industry": "Sports Equipment", "website": "https://www.spalding.com", "budget_range": (4000, 12000)},
    {"name": "Riddell", "industry": "Sports Equipment", "website": "https://www.riddell.com", "budget_range": (5000, 14500)},
    {"name": "Wilson Tennis", "industry": "Sports Equipment", "website": "https://www.wilson.com/tennis", "budget_range": (4500, 13000)},
    {"name": "Callaway Golf", "industry": "Sports Equipment", "website": "https://www.callawaygolf.com", "budget_range": (5500, 16000)},
    {"name": "Titleist", "industry": "Sports Equipment", "website": "https://www.titleist.com", "budget_range": (5000, 14500)},
    {"name": "Fanatics", "industry": "Sports Merchandise", "website": "https://www.fanatics.com", "budget_range": (6500, 19000)},
    {"name": "NFL Shop", "industry": "Sports Merchandise", "website": "https://www.nflshop.com", "budget_range": (6000, 17500)},
    {"name": "Tennis Warehouse", "industry": "Sports Retail", "website": "https://www.tennis-warehouse.com", "budget_range": (4000, 11500)},
    {"name": "SoccerPro", "industry": "Sports Retail", "website": "https://www.soccerpro.com", "budget_range": (4000, 11500)},
    {"name": "Dick's Sporting Goods", "industry": "Sports Retail", "website": "https://www.dickssportinggoods.com", "budget_range": (7000, 20000)},
    # Technology (15)
    {"name": "Apple", "industry": "Consumer Electronics", "website": "https://www.apple.com", "budget_range": (15000, 40000)},
    {"name": "Samsung", "industry": "Consumer Electronics", "website": "https://www.samsung.com", "budget_range": (13000, 37000)},
    {"name": "Google Pixel", "industry": "Consumer Electronics", "website": "https://store.google.com/pixel", "budget_range": (9500, 27500)},
    {"name": "Sony Electronics", "industry": "Consumer Electronics", "website": "https://www.sony.com", "budget_range": (8000, 24000)},
    {"name": "Bose", "industry": "Consumer Electronics", "website": "https://www.bose.com", "budget_range": (6000, 18000)},
    {"name": "Microsoft", "industry": "Software & Cloud", "website": "https://www.microsoft.com", "budget_range": (14000, 38000)},
    {"name": "Salesforce", "industry": "Software & Cloud", "website": "https://www.salesforce.com", "budget_range": (10000, 30000)},
    {"name": "Adobe", "industry": "Software", "website": "https://www.adobe.com", "budget_range": (9000, 26000)},
    {"name": "Figma", "industry": "Software", "website": "https://www.figma.com", "budget_range": (5000, 15000)},
    {"name": "Notion", "industry": "Software", "website": "https://www.notion.so", "budget_range": (4000, 12000)},
    {"name": "Tesla", "industry": "Electric Vehicles", "website": "https://www.tesla.com", "budget_range": (11000, 32000)},
    {"name": "Rivian", "industry": "Electric Vehicles", "website": "https://www.rivian.com", "budget_range": (8000, 24000)},
    {"name": "Dell", "industry": "Computer Hardware", "website": "https://www.dell.com", "budget_range": (8000, 23000)},
    {"name": "Lenovo", "industry": "Computer Hardware", "website": "https://www.lenovo.com", "budget_range": (7500, 21500)},
    {"name": "HP", "industry": "Computer Hardware", "website": "https://www.hp.com", "budget_range": (7000, 20000)},
    {"name": "ASUS", "industry": "Computer Hardware", "website": "https://www.asus.com", "budget_range": (5500, 16500)},
    {"name": "Razer", "industry": "Computer Hardware", "website": "https://www.razer.com", "budget_range": (5000, 15000)},
    # Telecom (5)
    {"name": "Verizon", "industry": "Telecom", "website": "https://www.verizon.com", "budget_range": (10000, 30000)},
    {"name": "AT&T", "industry": "Telecom", "website": "https://www.att.com", "budget_range": (10000, 30000)},
    {"name": "T-Mobile", "industry": "Telecom", "website": "https://www.t-mobile.com", "budget_range": (9000, 27000)},
    {"name": "Mint Mobile", "industry": "Telecom", "website": "https://www.mintmobile.com", "budget_range": (5000, 15000)},
    {"name": "Google Fi", "industry": "Telecom", "website": "https://fi.google.com", "budget_range": (4500, 13500)},
    # News Media (6)
    {"name": "The New York Times", "industry": "News Media", "website": "https://www.nytimes.com", "budget_range": (8000, 23000)},
    {"name": "The Washington Post", "industry": "News Media", "website": "https://www.washingtonpost.com", "budget_range": (7500, 21500)},
    {"name": "The Atlantic", "industry": "News Media", "website": "https://www.theatlantic.com", "budget_range": (5500, 16000)},
    {"name": "Reuters", "industry": "News Media", "website": "https://www.reuters.com", "budget_range": (7000, 20000)},
    {"name": "Bloomberg", "industry": "News Media", "website": "https://www.bloomberg.com", "budget_range": (8500, 25000)},
    {"name": "The Economist", "industry": "News Media", "website": "https://www.economist.com", "budget_range": (6500, 19000)},
    # Audiobooks (4)
    {"name": "Audible", "industry": "Audiobooks", "website": "https://www.audible.com", "budget_range": (7000, 20000)},
    {"name": "Scribd", "industry": "Audiobooks", "website": "https://www.scribd.com", "budget_range": (4000, 12000)},
    {"name": "Libro.fm", "industry": "Audiobooks", "website": "https://www.libro.fm", "budget_range": (2500, 7500)},
    {"name": "Kobo", "industry": "Audiobooks", "website": "https://www.kobo.com", "budget_range": (3500, 10000)},
    # Real Estate (6)
    {"name": "Zillow", "industry": "Real Estate", "website": "https://www.zillow.com", "budget_range": (9000, 27000)},
    {"name": "Redfin", "industry": "Real Estate", "website": "https://www.redfin.com", "budget_range": (7000, 20000)},
    {"name": "Realtor.com", "industry": "Real Estate", "website": "https://www.realtor.com", "budget_range": (7500, 22000)},
    {"name": "Compass", "industry": "Real Estate", "website": "https://www.compass.com", "budget_range": (6000, 18000)},
    {"name": "Opendoor", "industry": "Real Estate", "website": "https://www.opendoor.com", "budget_range": (6500, 19000)},
    {"name": "Trulia", "industry": "Real Estate", "website": "https://www.trulia.com", "budget_range": (5500, 16000)},
    # Pet Products (6)
    {"name": "Chewy", "industry": "Pet Products", "website": "https://www.chewy.com", "budget_range": (7000, 20000)},
    {"name": "BarkBox", "industry": "Pet Products", "website": "https://www.barkbox.com", "budget_range": (4000, 12000)},
    {"name": "Petco", "industry": "Pet Products", "website": "https://www.petco.com", "budget_range": (6000, 17500)},
    {"name": "PetSmart", "industry": "Pet Products", "website": "https://www.petsmart.com", "budget_range": (5500, 16000)},
    {"name": "Rover", "industry": "Pet Products", "website": "https://www.rover.com", "budget_range": (3500, 10000)},
    {"name": "Ollie", "industry": "Pet Products", "website": "https://www.myollie.com", "budget_range": (3000, 9000)},
    # Home & Garden (6)
    {"name": "Wayfair", "industry": "Home & Garden", "website": "https://www.wayfair.com", "budget_range": (8000, 24000)},
    {"name": "West Elm", "industry": "Home & Garden", "website": "https://www.westelm.com", "budget_range": (5500, 16500)},
    {"name": "Pottery Barn", "industry": "Home & Garden", "website": "https://www.potterybarn.com", "budget_range": (6000, 18000)},
    {"name": "IKEA", "industry": "Home & Garden", "website": "https://www.ikea.com", "budget_range": (9000, 27000)},
    {"name": "Crate & Barrel", "industry": "Home & Garden", "website": "https://www.crateandbarrel.com", "budget_range": (5000, 15000)},
    {"name": "The Home Depot", "industry": "Home & Garden", "website": "https://www.homedepot.com", "budget_range": (10000, 30000)},
    # EdTech (8)
    {"name": "Coursera", "industry": "EdTech", "website": "https://www.coursera.org", "budget_range": (5000, 15000)},
    {"name": "Udemy", "industry": "EdTech", "website": "https://www.udemy.com", "budget_range": (4500, 13500)},
    {"name": "Khan Academy", "industry": "EdTech", "website": "https://www.khanacademy.org", "budget_range": (3500, 10000)},
    {"name": "Duolingo", "industry": "EdTech", "website": "https://www.duolingo.com", "budget_range": (6000, 18000)},
    {"name": "MasterClass", "industry": "EdTech", "website": "https://www.masterclass.com", "budget_range": (5500, 16500)},
    {"name": "Skillshare", "industry": "EdTech", "website": "https://www.skillshare.com", "budget_range": (3500, 10000)},
    {"name": "LinkedIn Learning", "industry": "EdTech", "website": "https://www.linkedin.com/learning", "budget_range": (7000, 20000)},
    {"name": "Codecademy", "industry": "EdTech", "website": "https://www.codecademy.com", "budget_range": (4000, 12000)},
    # Food Delivery (6)
    {"name": "DoorDash", "industry": "Food Delivery", "website": "https://www.doordash.com", "budget_range": (9000, 27000)},
    {"name": "Uber Eats", "industry": "Food Delivery", "website": "https://www.ubereats.com", "budget_range": (8500, 25500)},
    {"name": "Grubhub", "industry": "Food Delivery", "website": "https://www.grubhub.com", "budget_range": (7000, 20000)},
    {"name": "Instacart", "industry": "Food Delivery", "website": "https://www.instacart.com", "budget_range": (7500, 22000)},
    {"name": "HelloFresh", "industry": "Food Delivery", "website": "https://www.hellofresh.com", "budget_range": (6500, 19000)},
    {"name": "Blue Apron", "industry": "Food Delivery", "website": "https://www.blueapron.com", "budget_range": (4500, 13500)},
    # Restaurants (6)
    {"name": "Chipotle", "industry": "Restaurants", "website": "https://www.chipotle.com", "budget_range": (8000, 24000)},
    {"name": "Sweetgreen", "industry": "Restaurants", "website": "https://www.sweetgreen.com", "budget_range": (4500, 13500)},
    {"name": "Shake Shack", "industry": "Restaurants", "website": "https://www.shakeshack.com", "budget_range": (5500, 16500)},
    {"name": "Panera Bread", "industry": "Restaurants", "website": "https://www.panerabread.com", "budget_range": (6500, 19000)},
    {"name": "Starbucks", "industry": "Restaurants", "website": "https://www.starbucks.com", "budget_range": (10000, 30000)},
    {"name": "Domino's", "industry": "Restaurants", "website": "https://www.dominos.com", "budget_range": (7500, 22000)},
    # Fitness & Wellness (8)
    {"name": "Peloton", "industry": "Fitness & Wellness", "website": "https://www.onepeloton.com", "budget_range": (8000, 24000)},
    {"name": "ClassPass", "industry": "Fitness & Wellness", "website": "https://www.classpass.com", "budget_range": (5000, 15000)},
    {"name": "Calm", "industry": "Fitness & Wellness", "website": "https://www.calm.com", "budget_range": (5500, 16500)},
    {"name": "Headspace", "industry": "Fitness & Wellness", "website": "https://www.headspace.com", "budget_range": (5000, 15000)},
    {"name": "Noom", "industry": "Fitness & Wellness", "website": "https://www.noom.com", "budget_range": (6000, 18000)},
    {"name": "Mirror", "industry": "Fitness & Wellness", "website": "https://www.mirror.co", "budget_range": (4500, 13500)},
    {"name": "Whoop", "industry": "Fitness & Wellness", "website": "https://www.whoop.com", "budget_range": (4000, 12000)},
    {"name": "Fitbit", "industry": "Fitness & Wellness", "website": "https://www.fitbit.com", "budget_range": (5500, 16500)},
    # Healthcare (5)
    {"name": "Hims & Hers", "industry": "Healthcare", "website": "https://www.forhims.com", "budget_range": (6000, 18000)},
    {"name": "Roman", "industry": "Healthcare", "website": "https://www.getroman.com", "budget_range": (5000, 15000)},
    {"name": "Nurx", "industry": "Healthcare", "website": "https://www.nurx.com", "budget_range": (4000, 12000)},
    {"name": "GoodRx", "industry": "Healthcare", "website": "https://www.goodrx.com", "budget_range": (5500, 16500)},
    {"name": "Teladoc", "industry": "Healthcare", "website": "https://www.teladoc.com", "budget_range": (6500, 19000)},
    # Travel (8)
    {"name": "Airbnb", "industry": "Travel", "website": "https://www.airbnb.com", "budget_range": (10000, 30000)},
    {"name": "Booking.com", "industry": "Travel", "website": "https://www.booking.com", "budget_range": (11000, 33000)},
    {"name": "Expedia", "industry": "Travel", "website": "https://www.expedia.com", "budget_range": (9000, 27000)},
    {"name": "Vrbo", "industry": "Travel", "website": "https://www.vrbo.com", "budget_range": (7000, 20000)},
    {"name": "Tripadvisor", "industry": "Travel", "website": "https://www.tripadvisor.com", "budget_range": (6500, 19000)},
    {"name": "Kayak", "industry": "Travel", "website": "https://www.kayak.com", "budget_range": (5500, 16000)},
    {"name": "Hopper", "industry": "Travel", "website": "https://www.hopper.com", "budget_range": (4500, 13500)},
    {"name": "Hotels.com", "industry": "Travel", "website": "https://www.hotels.com", "budget_range": (7500, 22000)},
    # Airlines (5)
    {"name": "Delta Airlines", "industry": "Airlines", "website": "https://www.delta.com", "budget_range": (10000, 30000)},
    {"name": "United Airlines", "industry": "Airlines", "website": "https://www.united.com", "budget_range": (9500, 28500)},
    {"name": "Southwest Airlines", "industry": "Airlines", "website": "https://www.southwest.com", "budget_range": (8500, 25500)},
    {"name": "JetBlue", "industry": "Airlines", "website": "https://www.jetblue.com", "budget_range": (7000, 20000)},
    {"name": "Alaska Airlines", "industry": "Airlines", "website": "https://www.alaskaair.com", "budget_range": (6500, 19000)},
    # Automotive (6)
    {"name": "Toyota", "industry": "Automotive", "website": "https://www.toyota.com", "budget_range": (12000, 35000)},
    {"name": "Honda", "industry": "Automotive", "website": "https://www.honda.com", "budget_range": (11000, 32000)},
    {"name": "BMW", "industry": "Automotive", "website": "https://www.bmw.com", "budget_range": (13000, 38000)},
    {"name": "Mercedes-Benz", "industry": "Automotive", "website": "https://www.mercedes-benz.com", "budget_range": (13000, 38000)},
    {"name": "Ford", "industry": "Automotive", "website": "https://www.ford.com", "budget_range": (11000, 32000)},
    {"name": "Hyundai", "industry": "Automotive", "website": "https://www.hyundai.com", "budget_range": (9000, 27000)},
    # B2B SaaS (10)
    {"name": "Slack", "industry": "B2B SaaS", "website": "https://www.slack.com", "budget_range": (7000, 20000)},
    {"name": "Zoom", "industry": "B2B SaaS", "website": "https://www.zoom.us", "budget_range": (8000, 24000)},
    {"name": "HubSpot", "industry": "B2B SaaS", "website": "https://www.hubspot.com", "budget_range": (7500, 22000)},
    {"name": "Atlassian", "industry": "B2B SaaS", "website": "https://www.atlassian.com", "budget_range": (7000, 21000)},
    {"name": "Datadog", "industry": "B2B SaaS", "website": "https://www.datadog.com", "budget_range": (6000, 18000)},
    {"name": "Snowflake", "industry": "B2B SaaS", "website": "https://www.snowflake.com", "budget_range": (8000, 24000)},
    {"name": "Stripe", "industry": "B2B SaaS", "website": "https://www.stripe.com", "budget_range": (6500, 19500)},
    {"name": "Twilio", "industry": "B2B SaaS", "website": "https://www.twilio.com", "budget_range": (5500, 16500)},
    {"name": "MongoDB", "industry": "B2B SaaS", "website": "https://www.mongodb.com", "budget_range": (5000, 15000)},
    {"name": "Vercel", "industry": "B2B SaaS", "website": "https://www.vercel.com", "budget_range": (4000, 12000)},
    # Cybersecurity (5)
    {"name": "CrowdStrike", "industry": "Cybersecurity", "website": "https://www.crowdstrike.com", "budget_range": (7000, 21000)},
    {"name": "Palo Alto Networks", "industry": "Cybersecurity", "website": "https://www.paloaltonetworks.com", "budget_range": (8000, 24000)},
    {"name": "Okta", "industry": "Cybersecurity", "website": "https://www.okta.com", "budget_range": (6000, 18000)},
    {"name": "Zscaler", "industry": "Cybersecurity", "website": "https://www.zscaler.com", "budget_range": (5500, 16500)},
    {"name": "1Password", "industry": "Cybersecurity", "website": "https://www.1password.com", "budget_range": (4000, 12000)},
    # Culture (5)
    {"name": "Smithsonian", "industry": "Culture", "website": "https://www.si.edu", "budget_range": (4000, 12000)},
    {"name": "National Geographic", "industry": "Culture", "website": "https://www.nationalgeographic.com", "budget_range": (6000, 18000)},
    {"name": "The Met", "industry": "Culture", "website": "https://www.metmuseum.org", "budget_range": (3500, 10000)},
    {"name": "MoMA", "industry": "Culture", "website": "https://www.moma.org", "budget_range": (3500, 10000)},
    {"name": "PBS", "industry": "Culture", "website": "https://www.pbs.org", "budget_range": (5000, 15000)},
    # Education (6)
    {"name": "Harvard Online", "industry": "Education", "website": "https://www.harvardonline.harvard.edu", "budget_range": (6000, 18000)},
    {"name": "Stanford Online", "industry": "Education", "website": "https://online.stanford.edu", "budget_range": (6000, 18000)},
    {"name": "MIT OpenCourseWare", "industry": "Education", "website": "https://ocw.mit.edu", "budget_range": (4000, 12000)},
    {"name": "Pearson", "industry": "Education", "website": "https://www.pearson.com", "budget_range": (7000, 20000)},
    {"name": "McGraw-Hill", "industry": "Education", "website": "https://www.mheducation.com", "budget_range": (6500, 19000)},
    {"name": "Chegg", "industry": "Education", "website": "https://www.chegg.com", "budget_range": (5000, 15000)},
    # Non-Profit (5)
    {"name": "UNICEF", "industry": "Non-Profit", "website": "https://www.unicef.org", "budget_range": (3000, 10000)},
    {"name": "Red Cross", "industry": "Non-Profit", "website": "https://www.redcross.org", "budget_range": (3500, 11000)},
    {"name": "World Wildlife Fund", "industry": "Non-Profit", "website": "https://www.worldwildlife.org", "budget_range": (3000, 9500)},
    {"name": "Doctors Without Borders", "industry": "Non-Profit", "website": "https://www.msf.org", "budget_range": (3000, 10000)},
    {"name": "Habitat for Humanity", "industry": "Non-Profit", "website": "https://www.habitat.org", "budget_range": (2500, 8500)},
    # Government (4)
    {"name": "USA.gov", "industry": "Government", "website": "https://www.usa.gov", "budget_range": (5000, 15000)},
    {"name": "CDC", "industry": "Government", "website": "https://www.cdc.gov", "budget_range": (6000, 18000)},
    {"name": "NASA", "industry": "Government", "website": "https://www.nasa.gov", "budget_range": (5000, 15000)},
    {"name": "USPS", "industry": "Government", "website": "https://www.usps.com", "budget_range": (7000, 20000)},
    # Politics (4)
    {"name": "Politico", "industry": "Politics", "website": "https://www.politico.com", "budget_range": (5000, 15000)},
    {"name": "The Hill", "industry": "Politics", "website": "https://thehill.com", "budget_range": (4500, 13500)},
    {"name": "FiveThirtyEight", "industry": "Politics", "website": "https://fivethirtyeight.com", "budget_range": (3500, 10000)},
    {"name": "C-SPAN", "industry": "Politics", "website": "https://www.c-span.org", "budget_range": (3000, 9000)},
    # Technology (standalone) (5)
    {"name": "NVIDIA", "industry": "Technology", "website": "https://www.nvidia.com", "budget_range": (12000, 35000)},
    {"name": "Intel", "industry": "Technology", "website": "https://www.intel.com", "budget_range": (11000, 32000)},
    {"name": "AMD", "industry": "Technology", "website": "https://www.amd.com", "budget_range": (9000, 27000)},
    {"name": "Qualcomm", "industry": "Technology", "website": "https://www.qualcomm.com", "budget_range": (8000, 24000)},
    {"name": "Cisco", "industry": "Technology", "website": "https://www.cisco.com", "budget_range": (10000, 30000)},
    # AI (6)
    {"name": "OpenAI", "industry": "AI", "website": "https://www.openai.com", "budget_range": (10000, 30000)},
    {"name": "Anthropic", "industry": "AI", "website": "https://www.anthropic.com", "budget_range": (8000, 24000)},
    {"name": "Google DeepMind", "industry": "AI", "website": "https://deepmind.google", "budget_range": (9000, 27000)},
    {"name": "Hugging Face", "industry": "AI", "website": "https://huggingface.co", "budget_range": (5000, 15000)},
    {"name": "Stability AI", "industry": "AI", "website": "https://stability.ai", "budget_range": (5500, 16500)},
    {"name": "Cohere", "industry": "AI", "website": "https://cohere.com", "budget_range": (5000, 15000)},
    # FinTech (6)
    {"name": "Square", "industry": "FinTech", "website": "https://squareup.com", "budget_range": (8000, 24000)},
    {"name": "Plaid", "industry": "FinTech", "website": "https://plaid.com", "budget_range": (6000, 18000)},
    {"name": "Chime", "industry": "FinTech", "website": "https://www.chime.com", "budget_range": (7000, 20000)},
    {"name": "Revolut", "industry": "FinTech", "website": "https://www.revolut.com", "budget_range": (7500, 22000)},
    {"name": "Wise", "industry": "FinTech", "website": "https://wise.com", "budget_range": (6000, 18000)},
    {"name": "Affirm", "industry": "FinTech", "website": "https://www.affirm.com", "budget_range": (6500, 19000)},
    # HealthTech (5)
    {"name": "Zocdoc", "industry": "HealthTech", "website": "https://www.zocdoc.com", "budget_range": (5500, 16500)},
    {"name": "Ro", "industry": "HealthTech", "website": "https://ro.co", "budget_range": (5000, 15000)},
    {"name": "Cityblock Health", "industry": "HealthTech", "website": "https://www.cityblock.com", "budget_range": (4500, 13500)},
    {"name": "Tempus", "industry": "HealthTech", "website": "https://www.tempus.com", "budget_range": (5000, 15000)},
    {"name": "Oscar Health", "industry": "HealthTech", "website": "https://www.hioscar.com", "budget_range": (6000, 18000)},
    # E-commerce (6)
    {"name": "Shopify", "industry": "E-commerce", "website": "https://www.shopify.com", "budget_range": (9000, 27000)},
    {"name": "Etsy", "industry": "E-commerce", "website": "https://www.etsy.com", "budget_range": (7000, 20000)},
    {"name": "Amazon", "industry": "E-commerce", "website": "https://www.amazon.com", "budget_range": (15000, 40000)},
    {"name": "eBay", "industry": "E-commerce", "website": "https://www.ebay.com", "budget_range": (10000, 30000)},
    {"name": "Walmart Marketplace", "industry": "E-commerce", "website": "https://www.walmart.com", "budget_range": (12000, 35000)},
    {"name": "Wish", "industry": "E-commerce", "website": "https://www.wish.com", "budget_range": (5000, 15000)},
    # Personal Banking (6)
    {"name": "Chase", "industry": "Personal Banking", "website": "https://www.chase.com", "budget_range": (10000, 30000)},
    {"name": "Bank of America", "industry": "Personal Banking", "website": "https://www.bankofamerica.com", "budget_range": (10000, 30000)},
    {"name": "Wells Fargo", "industry": "Personal Banking", "website": "https://www.wellsfargo.com", "budget_range": (9000, 27000)},
    {"name": "Ally Bank", "industry": "Personal Banking", "website": "https://www.ally.com", "budget_range": (6000, 18000)},
    {"name": "Marcus by Goldman Sachs", "industry": "Personal Banking", "website": "https://www.marcus.com", "budget_range": (7000, 20000)},
    {"name": "Capital One", "industry": "Personal Banking", "website": "https://www.capitalone.com", "budget_range": (9000, 27000)},
    # Craft Beer & Spirits (5)
    {"name": "Heineken", "industry": "Craft Beer & Spirits", "website": "https://www.heineken.com", "budget_range": (8000, 24000)},
    {"name": "Diageo", "industry": "Craft Beer & Spirits", "website": "https://www.diageo.com", "budget_range": (10000, 30000)},
    {"name": "Anheuser-Busch", "industry": "Craft Beer & Spirits", "website": "https://www.anheuser-busch.com", "budget_range": (12000, 35000)},
    {"name": "Patrón", "industry": "Craft Beer & Spirits", "website": "https://www.patrontequila.com", "budget_range": (6000, 18000)},
    {"name": "Drizly", "industry": "Craft Beer & Spirits", "website": "https://www.drizly.com", "budget_range": (5000, 15000)},
    # Energy Drinks (5)
    {"name": "Red Bull", "industry": "Energy Drinks", "website": "https://www.redbull.com", "budget_range": (12000, 35000)},
    {"name": "Monster Energy", "industry": "Energy Drinks", "website": "https://www.monsterenergy.com", "budget_range": (10000, 30000)},
    {"name": "Celsius", "industry": "Energy Drinks", "website": "https://www.celsius.com", "budget_range": (7000, 20000)},
    {"name": "Ghost Energy", "industry": "Energy Drinks", "website": "https://www.ghostenergy.com", "budget_range": (5000, 15000)},
    {"name": "Prime", "industry": "Energy Drinks", "website": "https://drinkprime.com", "budget_range": (6000, 18000)},
    # Coffee & Tea (5)
    {"name": "Nespresso", "industry": "Coffee & Tea", "website": "https://www.nespresso.com", "budget_range": (8000, 24000)},
    {"name": "Blue Bottle Coffee", "industry": "Coffee & Tea", "website": "https://bluebottlecoffee.com", "budget_range": (4500, 13500)},
    {"name": "Illy", "industry": "Coffee & Tea", "website": "https://www.illy.com", "budget_range": (5000, 15000)},
    {"name": "Twinings", "industry": "Coffee & Tea", "website": "https://www.twinings.com", "budget_range": (5000, 15000)},
    {"name": "Trade Coffee", "industry": "Coffee & Tea", "website": "https://www.drinktrade.com", "budget_range": (3500, 10000)},
    # Pharmaceuticals (5)
    {"name": "Pfizer", "industry": "Pharmaceuticals", "website": "https://www.pfizer.com", "budget_range": (12000, 35000)},
    {"name": "Johnson & Johnson", "industry": "Pharmaceuticals", "website": "https://www.jnj.com", "budget_range": (12000, 35000)},
    {"name": "AbbVie", "industry": "Pharmaceuticals", "website": "https://www.abbvie.com", "budget_range": (10000, 30000)},
    {"name": "Moderna", "industry": "Pharmaceuticals", "website": "https://www.modernatx.com", "budget_range": (9000, 27000)},
    {"name": "Eli Lilly", "industry": "Pharmaceuticals", "website": "https://www.lilly.com", "budget_range": (10000, 30000)},
    # Supplements & Nutrition (5)
    {"name": "GNC", "industry": "Supplements & Nutrition", "website": "https://www.gnc.com", "budget_range": (6000, 18000)},
    {"name": "AG1", "industry": "Supplements & Nutrition", "website": "https://drinkag1.com", "budget_range": (7000, 20000)},
    {"name": "Huel", "industry": "Supplements & Nutrition", "website": "https://www.huel.com", "budget_range": (5000, 15000)},
    {"name": "Vital Proteins", "industry": "Supplements & Nutrition", "website": "https://www.vitalproteins.com", "budget_range": (5500, 16500)},
    {"name": "Optimum Nutrition", "industry": "Supplements & Nutrition", "website": "https://www.optimumnutrition.com", "budget_range": (5000, 15000)},
    # Hotels & Resorts (5)
    {"name": "Marriott", "industry": "Hotels & Resorts", "website": "https://www.marriott.com", "budget_range": (10000, 30000)},
    {"name": "Hilton", "industry": "Hotels & Resorts", "website": "https://www.hilton.com", "budget_range": (10000, 30000)},
    {"name": "Hyatt", "industry": "Hotels & Resorts", "website": "https://www.hyatt.com", "budget_range": (8000, 24000)},
    {"name": "IHG", "industry": "Hotels & Resorts", "website": "https://www.ihg.com", "budget_range": (8500, 25500)},
    {"name": "Four Seasons", "industry": "Hotels & Resorts", "website": "https://www.fourseasons.com", "budget_range": (9000, 27000)},
    # Cruises (4)
    {"name": "Royal Caribbean", "industry": "Cruises", "website": "https://www.royalcaribbean.com", "budget_range": (9000, 27000)},
    {"name": "Carnival Cruise Line", "industry": "Cruises", "website": "https://www.carnival.com", "budget_range": (8000, 24000)},
    {"name": "Norwegian Cruise Line", "industry": "Cruises", "website": "https://www.ncl.com", "budget_range": (7500, 22000)},
    {"name": "Celebrity Cruises", "industry": "Cruises", "website": "https://www.celebritycruises.com", "budget_range": (7000, 20000)},
    # HR & Recruiting (5)
    {"name": "LinkedIn", "industry": "HR & Recruiting", "website": "https://www.linkedin.com", "budget_range": (10000, 30000)},
    {"name": "Indeed", "industry": "HR & Recruiting", "website": "https://www.indeed.com", "budget_range": (9000, 27000)},
    {"name": "Glassdoor", "industry": "HR & Recruiting", "website": "https://www.glassdoor.com", "budget_range": (7000, 20000)},
    {"name": "Workday", "industry": "HR & Recruiting", "website": "https://www.workday.com", "budget_range": (8000, 24000)},
    {"name": "BambooHR", "industry": "HR & Recruiting", "website": "https://www.bamboohr.com", "budget_range": (5000, 15000)},
    # Accounting & Tax (5)
    {"name": "TurboTax", "industry": "Accounting & Tax", "website": "https://turbotax.intuit.com", "budget_range": (10000, 30000)},
    {"name": "H&R Block", "industry": "Accounting & Tax", "website": "https://www.hrblock.com", "budget_range": (8000, 24000)},
    {"name": "QuickBooks", "industry": "Accounting & Tax", "website": "https://quickbooks.intuit.com", "budget_range": (9000, 27000)},
    {"name": "FreshBooks", "industry": "Accounting & Tax", "website": "https://www.freshbooks.com", "budget_range": (5000, 15000)},
    {"name": "Xero", "industry": "Accounting & Tax", "website": "https://www.xero.com", "budget_range": (5500, 16500)},
    # Legal Services (5)
    {"name": "LegalZoom", "industry": "Legal Services", "website": "https://www.legalzoom.com", "budget_range": (7000, 20000)},
    {"name": "Rocket Lawyer", "industry": "Legal Services", "website": "https://www.rocketlawyer.com", "budget_range": (5500, 16500)},
    {"name": "Avvo", "industry": "Legal Services", "website": "https://www.avvo.com", "budget_range": (5000, 15000)},
    {"name": "FindLaw", "industry": "Legal Services", "website": "https://www.findlaw.com", "budget_range": (4500, 13500)},
    {"name": "LawDepot", "industry": "Legal Services", "website": "https://www.lawdepot.com", "budget_range": (4000, 12000)},
    # Social Media (5)
    {"name": "TikTok", "industry": "Social Media", "website": "https://www.tiktok.com", "budget_range": (12000, 35000)},
    {"name": "Snapchat", "industry": "Social Media", "website": "https://www.snapchat.com", "budget_range": (10000, 30000)},
    {"name": "Pinterest", "industry": "Social Media", "website": "https://www.pinterest.com", "budget_range": (8000, 24000)},
    {"name": "Reddit", "industry": "Social Media", "website": "https://www.reddit.com", "budget_range": (7000, 20000)},
    {"name": "Discord", "industry": "Social Media", "website": "https://www.discord.com", "budget_range": (6000, 18000)},
    # Creator Economy (5)
    {"name": "Patreon", "industry": "Creator Economy", "website": "https://www.patreon.com", "budget_range": (5000, 15000)},
    {"name": "Substack", "industry": "Creator Economy", "website": "https://substack.com", "budget_range": (4500, 13500)},
    {"name": "Gumroad", "industry": "Creator Economy", "website": "https://gumroad.com", "budget_range": (3500, 10000)},
    {"name": "Kajabi", "industry": "Creator Economy", "website": "https://www.kajabi.com", "budget_range": (5000, 15000)},
    {"name": "Teachable", "industry": "Creator Economy", "website": "https://teachable.com", "budget_range": (4500, 13500)},
    # Baby & Parenting (5)
    {"name": "Pampers", "industry": "Baby & Parenting", "website": "https://www.pampers.com", "budget_range": (9000, 27000)},
    {"name": "BabyCenter", "industry": "Baby & Parenting", "website": "https://www.babycenter.com", "budget_range": (5000, 15000)},
    {"name": "Nanit", "industry": "Baby & Parenting", "website": "https://www.nanit.com", "budget_range": (5500, 16500)},
    {"name": "Hatch", "industry": "Baby & Parenting", "website": "https://www.hatchwearable.com", "budget_range": (4500, 13500)},
    {"name": "Ergobaby", "industry": "Baby & Parenting", "website": "https://www.ergobaby.com", "budget_range": (4000, 12000)},
    # Kids & Family Entertainment (5)
    {"name": "Disney Junior", "industry": "Kids & Family Entertainment", "website": "https://disneyjunior.disney.com", "budget_range": (10000, 30000)},
    {"name": "Lego", "industry": "Kids & Family Entertainment", "website": "https://www.lego.com", "budget_range": (9000, 27000)},
    {"name": "Nickelodeon", "industry": "Kids & Family Entertainment", "website": "https://www.nick.com", "budget_range": (8000, 24000)},
    {"name": "PBS Kids", "industry": "Kids & Family Entertainment", "website": "https://pbskids.org", "budget_range": (5000, 15000)},
    {"name": "Mattel", "industry": "Kids & Family Entertainment", "website": "https://www.mattel.com", "budget_range": (8000, 24000)},
    # Home Services (5)
    {"name": "Angi", "industry": "Home Services", "website": "https://www.angi.com", "budget_range": (7000, 20000)},
    {"name": "Thumbtack", "industry": "Home Services", "website": "https://www.thumbtack.com", "budget_range": (6000, 18000)},
    {"name": "TaskRabbit", "industry": "Home Services", "website": "https://www.taskrabbit.com", "budget_range": (5000, 15000)},
    {"name": "Handy", "industry": "Home Services", "website": "https://www.handy.com", "budget_range": (4000, 12000)},
    {"name": "HomeAdvisor", "industry": "Home Services", "website": "https://www.homeadvisor.com", "budget_range": (6500, 19000)},
    # Cleaning & Household (5)
    {"name": "Procter & Gamble", "industry": "Cleaning & Household", "website": "https://www.pg.com", "budget_range": (12000, 35000)},
    {"name": "Clorox", "industry": "Cleaning & Household", "website": "https://www.clorox.com", "budget_range": (8000, 24000)},
    {"name": "Seventh Generation", "industry": "Cleaning & Household", "website": "https://www.seventhgeneration.com", "budget_range": (5000, 15000)},
    {"name": "Method", "industry": "Cleaning & Household", "website": "https://methodhome.com", "budget_range": (4500, 13500)},
    {"name": "Mrs. Meyer's", "industry": "Cleaning & Household", "website": "https://www.mrsmeyers.com", "budget_range": (4000, 12000)},
    # Solar & Renewable Energy (5)
    {"name": "SunPower", "industry": "Solar & Renewable Energy", "website": "https://www.sunpower.com", "budget_range": (7000, 20000)},
    {"name": "Sunrun", "industry": "Solar & Renewable Energy", "website": "https://www.sunrun.com", "budget_range": (7500, 22000)},
    {"name": "Tesla Energy", "industry": "Solar & Renewable Energy", "website": "https://www.tesla.com/energy", "budget_range": (9000, 27000)},
    {"name": "EnergySage", "industry": "Solar & Renewable Energy", "website": "https://www.energysage.com", "budget_range": (5000, 15000)},
    {"name": "Enphase Energy", "industry": "Solar & Renewable Energy", "website": "https://www.enphase.com", "budget_range": (6000, 18000)},
    # Identity & Privacy (5)
    {"name": "NordVPN", "industry": "Identity & Privacy", "website": "https://nordvpn.com", "budget_range": (7000, 20000)},
    {"name": "ExpressVPN", "industry": "Identity & Privacy", "website": "https://www.expressvpn.com", "budget_range": (7000, 20000)},
    {"name": "LifeLock", "industry": "Identity & Privacy", "website": "https://www.lifelock.com", "budget_range": (6000, 18000)},
    {"name": "DeleteMe", "industry": "Identity & Privacy", "website": "https://joindeleteme.com", "budget_range": (4000, 12000)},
    {"name": "Surfshark", "industry": "Identity & Privacy", "website": "https://surfshark.com", "budget_range": (5500, 16500)},
    # Weddings (5)
    {"name": "Zola", "industry": "Weddings", "website": "https://www.zola.com", "budget_range": (6000, 18000)},
    {"name": "The Knot", "industry": "Weddings", "website": "https://www.theknot.com", "budget_range": (7000, 20000)},
    {"name": "WeddingWire", "industry": "Weddings", "website": "https://www.weddingwire.com", "budget_range": (6000, 18000)},
    {"name": "Minted", "industry": "Weddings", "website": "https://www.minted.com", "budget_range": (5000, 15000)},
    {"name": "Joy", "industry": "Weddings", "website": "https://www.withjoy.com", "budget_range": (3500, 10000)},
    # Logistics & Shipping (5)
    {"name": "FedEx", "industry": "Logistics & Shipping", "website": "https://www.fedex.com", "budget_range": (10000, 30000)},
    {"name": "UPS", "industry": "Logistics & Shipping", "website": "https://www.ups.com", "budget_range": (10000, 30000)},
    {"name": "DHL", "industry": "Logistics & Shipping", "website": "https://www.dhl.com", "budget_range": (9000, 27000)},
    {"name": "ShipBob", "industry": "Logistics & Shipping", "website": "https://www.shipbob.com", "budget_range": (5000, 15000)},
    {"name": "Flexport", "industry": "Logistics & Shipping", "website": "https://www.flexport.com", "budget_range": (6000, 18000)},
    # Sustainability (5)
    {"name": "Patagonia", "industry": "Sustainability", "website": "https://www.patagonia.com", "budget_range": (7000, 20000)},
    {"name": "Allbirds", "industry": "Sustainability", "website": "https://www.allbirds.com", "budget_range": (5500, 16500)},
    {"name": "Oatly", "industry": "Sustainability", "website": "https://www.oatly.com", "budget_range": (6000, 18000)},
    {"name": "Beyond Meat", "industry": "Sustainability", "website": "https://www.beyondmeat.com", "budget_range": (7000, 20000)},
    {"name": "Tentree", "industry": "Sustainability", "website": "https://www.tentree.com", "budget_range": (4000, 12000)},
    # ── Boosted existing low-count industries ──────────────────────────────
    # Sports Merchandise (+3)
    {"name": "NBA Store", "industry": "Sports Merchandise", "website": "https://store.nba.com", "budget_range": (6000, 17500)},
    {"name": "MLB Shop", "industry": "Sports Merchandise", "website": "https://www.mlbshop.com", "budget_range": (5500, 16000)},
    {"name": "Mitchell & Ness", "industry": "Sports Merchandise", "website": "https://www.mitchellandness.com", "budget_range": (4500, 13000)},
    # Sports Retail (+3)
    {"name": "REI", "industry": "Sports Retail", "website": "https://www.rei.com", "budget_range": (7000, 20000)},
    {"name": "Academy Sports", "industry": "Sports Retail", "website": "https://www.academy.com", "budget_range": (6000, 18000)},
    {"name": "Bass Pro Shops", "industry": "Sports Retail", "website": "https://www.basspro.com", "budget_range": (7500, 22000)},
    # Software (+3)
    {"name": "Canva", "industry": "Software", "website": "https://www.canva.com", "budget_range": (6000, 18000)},
    {"name": "Sketch", "industry": "Software", "website": "https://www.sketch.com", "budget_range": (4000, 12000)},
    {"name": "Miro", "industry": "Software", "website": "https://miro.com", "budget_range": (5000, 15000)},
    # Software & Cloud (+3)
    {"name": "AWS", "industry": "Software & Cloud", "website": "https://aws.amazon.com", "budget_range": (14000, 40000)},
    {"name": "Google Cloud", "industry": "Software & Cloud", "website": "https://cloud.google.com", "budget_range": (13000, 38000)},
    {"name": "Oracle Cloud", "industry": "Software & Cloud", "website": "https://www.oracle.com/cloud", "budget_range": (10000, 30000)},
    # Electric Vehicles (+3)
    {"name": "Lucid Motors", "industry": "Electric Vehicles", "website": "https://www.lucidmotors.com", "budget_range": (8000, 24000)},
    {"name": "Polestar", "industry": "Electric Vehicles", "website": "https://www.polestar.com", "budget_range": (7500, 22000)},
    {"name": "VinFast", "industry": "Electric Vehicles", "website": "https://www.vinfast.com", "budget_range": (6000, 18000)},
    # ── Additional advertisers to reach 1000 total ──────────────────────────
    {"name": "Shein", "industry": "Fashion Retail", "website": "https://www.shein.com", "budget_range": (8000, 24000)},
    {"name": "Revolve", "industry": "Fashion Retail", "website": "https://www.revolve.com", "budget_range": (6000, 18000)},
    {"name": "Abercrombie & Fitch", "industry": "Fashion Retail", "website": "https://www.abercrombie.com", "budget_range": (5500, 16500)},
    {"name": "Banana Republic", "industry": "Fashion Retail", "website": "https://bananarepublic.gap.com", "budget_range": (5000, 15000)},
    {"name": "Express", "industry": "Fashion Retail", "website": "https://www.express.com", "budget_range": (4500, 13500)},
    {"name": "The Ordinary", "industry": "Beauty", "website": "https://theordinary.com", "budget_range": (4000, 12000)},
    {"name": "Drunk Elephant", "industry": "Beauty", "website": "https://www.drunkelephant.com", "budget_range": (5000, 15000)},
    {"name": "CeraVe", "industry": "Beauty", "website": "https://www.cerave.com", "budget_range": (6000, 18000)},
    {"name": "Olaplex", "industry": "Beauty", "website": "https://www.olaplex.com", "budget_range": (5000, 15000)},
    {"name": "Kiehl's", "industry": "Beauty", "website": "https://www.kiehls.com", "budget_range": (5500, 16500)},
    {"name": "On Running", "industry": "Athletic Wear", "website": "https://www.on.com", "budget_range": (5500, 16500)},
    {"name": "HOKA", "industry": "Athletic Wear", "website": "https://www.hoka.com", "budget_range": (6000, 18000)},
    {"name": "Brooks Running", "industry": "Athletic Wear", "website": "https://www.brooksrunning.com", "budget_range": (5500, 16500)},
    {"name": "Reebok", "industry": "Athletic Wear", "website": "https://www.reebok.com", "budget_range": (6000, 18000)},
    {"name": "New Balance", "industry": "Athletic Wear", "website": "https://www.newbalance.com", "budget_range": (6500, 19500)},
    {"name": "Asics", "industry": "Athletic Wear", "website": "https://www.asics.com", "budget_range": (5500, 16500)},
    {"name": "Ray-Ban", "industry": "Fashion Accessories", "website": "https://www.ray-ban.com", "budget_range": (6000, 18000)},
    {"name": "Pandora", "industry": "Fashion Accessories", "website": "https://www.pandora.net", "budget_range": (5500, 16500)},
    {"name": "Swarovski", "industry": "Fashion Accessories", "website": "https://www.swarovski.com", "budget_range": (6000, 18000)},
    {"name": "Fossil", "industry": "Fashion Accessories", "website": "https://www.fossil.com", "budget_range": (4500, 13500)},
    {"name": "Coach", "industry": "Fashion Accessories", "website": "https://www.coach.com", "budget_range": (6500, 19500)},
    {"name": "Kate Spade", "industry": "Fashion Accessories", "website": "https://www.katespade.com", "budget_range": (5500, 16500)},
    {"name": "Michael Kors", "industry": "Fashion Accessories", "website": "https://www.michaelkors.com", "budget_range": (6000, 18000)},
    {"name": "Tiffany & Co.", "industry": "Fashion Accessories", "website": "https://www.tiffany.com", "budget_range": (8000, 24000)},
    {"name": "Balenciaga", "industry": "Luxury Goods", "website": "https://www.balenciaga.com", "budget_range": (8000, 24000)},
    {"name": "Fendi", "industry": "Luxury Goods", "website": "https://www.fendi.com", "budget_range": (8000, 24000)},
    {"name": "Valentino", "industry": "Luxury Goods", "website": "https://www.valentino.com", "budget_range": (7500, 22500)},
    {"name": "Versace", "industry": "Luxury Goods", "website": "https://www.versace.com", "budget_range": (7500, 22500)},
    {"name": "Saint Laurent", "industry": "Luxury Goods", "website": "https://www.ysl.com", "budget_range": (8000, 24000)},
    {"name": "Bottega Veneta", "industry": "Luxury Goods", "website": "https://www.bottegaveneta.com", "budget_range": (7500, 22500)},
    {"name": "Omega", "industry": "Luxury Goods", "website": "https://www.omegawatches.com", "budget_range": (7000, 21000)},
    {"name": "Rolex", "industry": "Luxury Goods", "website": "https://www.rolex.com", "budget_range": (9000, 27000)},
    {"name": "Pandora Music", "industry": "Music Streaming", "website": "https://www.pandora.com", "budget_range": (5000, 15000)},
    {"name": "SoundCloud", "industry": "Music Streaming", "website": "https://soundcloud.com", "budget_range": (4500, 13500)},
    {"name": "iHeartRadio", "industry": "Music Streaming", "website": "https://www.iheart.com", "budget_range": (5500, 16500)},
    {"name": "Audiomack", "industry": "Music Streaming", "website": "https://audiomack.com", "budget_range": (3500, 10500)},
    {"name": "Qobuz", "industry": "Music Streaming", "website": "https://www.qobuz.com", "budget_range": (3000, 9000)},
    {"name": "Napster", "industry": "Music Streaming", "website": "https://www.napster.com", "budget_range": (3000, 9000)},
    {"name": "LiveOne", "industry": "Music Streaming", "website": "https://www.liveone.com", "budget_range": (3500, 10500)},
    {"name": "Mixcloud", "industry": "Music Streaming", "website": "https://www.mixcloud.com", "budget_range": (3000, 9000)},
    {"name": "Eventbrite", "industry": "Event Tickets", "website": "https://www.eventbrite.com", "budget_range": (6000, 18000)},
    {"name": "AXS", "industry": "Event Tickets", "website": "https://www.axs.com", "budget_range": (5000, 15000)},
    {"name": "SeatGeek", "industry": "Event Tickets", "website": "https://seatgeek.com", "budget_range": (5500, 16500)},
    {"name": "Vivid Seats", "industry": "Event Tickets", "website": "https://www.vividseats.com", "budget_range": (5000, 15000)},
    {"name": "Dice", "industry": "Event Tickets", "website": "https://dice.fm", "budget_range": (3500, 10500)},
    {"name": "Fever", "industry": "Event Tickets", "website": "https://ffrr.com", "budget_range": (4000, 12000)},
    {"name": "Bandsintown", "industry": "Event Tickets", "website": "https://www.bandsintown.com", "budget_range": (3500, 10500)},
    {"name": "TickPick", "industry": "Event Tickets", "website": "https://www.tickpick.com", "budget_range": (4000, 12000)},
    {"name": "Gametime", "industry": "Event Tickets", "website": "https://gametime.co", "budget_range": (4500, 13500)},
    {"name": "Sweetwater", "industry": "Musical Instruments", "website": "https://www.sweetwater.com", "budget_range": (6000, 18000)},
    {"name": "Guitar Center", "industry": "Musical Instruments", "website": "https://www.guitarcenter.com", "budget_range": (7000, 21000)},
    {"name": "Reverb", "industry": "Musical Instruments", "website": "https://reverb.com", "budget_range": (5000, 15000)},
    {"name": "Yamaha Music", "industry": "Musical Instruments", "website": "https://www.yamaha.com/en/musical_instruments", "budget_range": (6000, 18000)},
    {"name": "Roland", "industry": "Musical Instruments", "website": "https://www.roland.com", "budget_range": (5500, 16500)},
    {"name": "Steinway & Sons", "industry": "Musical Instruments", "website": "https://www.steinway.com", "budget_range": (7000, 21000)},
    {"name": "Korg", "industry": "Musical Instruments", "website": "https://www.korg.com", "budget_range": (4500, 13500)},
    {"name": "PRS Guitars", "industry": "Musical Instruments", "website": "https://www.prsguitars.com", "budget_range": (5000, 15000)},
    {"name": "Zildjian", "industry": "Musical Instruments", "website": "https://zildjian.com", "budget_range": (4500, 13500)},
    {"name": "Paramount+", "industry": "Streaming", "website": "https://www.paramountplus.com", "budget_range": (9000, 27000)},
    {"name": "Peacock", "industry": "Streaming", "website": "https://www.peacocktv.com", "budget_range": (8000, 24000)},
    {"name": "Discovery+", "industry": "Streaming", "website": "https://www.discoveryplus.com", "budget_range": (7000, 21000)},
    {"name": "Tubi", "industry": "Streaming", "website": "https://tubitv.com", "budget_range": (5000, 15000)},
    {"name": "Pluto TV", "industry": "Streaming", "website": "https://pluto.tv", "budget_range": (5000, 15000)},
    {"name": "Crunchyroll", "industry": "Streaming", "website": "https://www.crunchyroll.com", "budget_range": (5500, 16500)},
    {"name": "Cinemark", "industry": "Movie Theaters", "website": "https://www.cinemark.com", "budget_range": (5500, 16500)},
    {"name": "Alamo Drafthouse", "industry": "Movie Theaters", "website": "https://drafthouse.com", "budget_range": (4000, 12000)},
    {"name": "Landmark Theatres", "industry": "Movie Theaters", "website": "https://www.landmarktheatres.com", "budget_range": (3500, 10500)},
    {"name": "Harkins Theatres", "industry": "Movie Theaters", "website": "https://www.harkins.com", "budget_range": (3500, 10500)},
    {"name": "Showcase Cinemas", "industry": "Movie Theaters", "website": "https://www.showcasecinemas.com", "budget_range": (3500, 10500)},
    {"name": "Marcus Theatres", "industry": "Movie Theaters", "website": "https://www.marcustheatres.com", "budget_range": (3500, 10500)},
    {"name": "Studio Movie Grill", "industry": "Movie Theaters", "website": "https://www.studiomoviegrill.com", "budget_range": (3000, 9000)},
    {"name": "Angelika Film Center", "industry": "Movie Theaters", "website": "https://www.angelikafilmcenter.com", "budget_range": (3000, 9000)},
    {"name": "iPic Theaters", "industry": "Movie Theaters", "website": "https://www.ipic.com", "budget_range": (4000, 12000)},
    {"name": "Riot Games", "industry": "Gaming", "website": "https://www.riotgames.com", "budget_range": (9000, 27000)},
    {"name": "Ubisoft", "industry": "Gaming", "website": "https://www.ubisoft.com", "budget_range": (8000, 24000)},
    {"name": "Supercell", "industry": "Gaming", "website": "https://supercell.com", "budget_range": (7000, 21000)},
    {"name": "Valve", "industry": "Gaming", "website": "https://www.valvesoftware.com", "budget_range": (8000, 24000)},
    {"name": "Bungie", "industry": "Gaming", "website": "https://www.bungie.net", "budget_range": (6500, 19500)},
    {"name": "miHoYo", "industry": "Gaming", "website": "https://www.hoyoverse.com", "budget_range": (7000, 21000)},
    {"name": "Edward Jones", "industry": "Financial Services", "website": "https://www.edwardjones.com", "budget_range": (7000, 21000)},
    {"name": "T. Rowe Price", "industry": "Financial Services", "website": "https://www.troweprice.com", "budget_range": (7500, 22500)},
    {"name": "BlackRock", "industry": "Financial Services", "website": "https://www.blackrock.com", "budget_range": (9000, 27000)},
    {"name": "J.P. Morgan Wealth", "industry": "Financial Services", "website": "https://www.jpmorgan.com/wealth-management", "budget_range": (9000, 27000)},
    {"name": "Wealthfront", "industry": "Financial Services", "website": "https://www.wealthfront.com", "budget_range": (5500, 16500)},
    {"name": "Betterment", "industry": "Financial Services", "website": "https://www.betterment.com", "budget_range": (5500, 16500)},
    {"name": "Webull", "industry": "Investment App", "website": "https://www.webull.com", "budget_range": (5000, 15000)},
    {"name": "Wealthsimple", "industry": "Investment App", "website": "https://www.wealthsimple.com", "budget_range": (5000, 15000)},
    {"name": "eToro", "industry": "Investment App", "website": "https://www.etoro.com", "budget_range": (6000, 18000)},
    {"name": "Public.com", "industry": "Investment App", "website": "https://public.com", "budget_range": (4500, 13500)},
    {"name": "Moomoo", "industry": "Investment App", "website": "https://www.moomoo.com", "budget_range": (4500, 13500)},
    {"name": "Stash", "industry": "Investment App", "website": "https://www.stash.com", "budget_range": (4000, 12000)},
    {"name": "M1 Finance", "industry": "Investment App", "website": "https://m1.com", "budget_range": (4000, 12000)},
    {"name": "Fundrise", "industry": "Investment App", "website": "https://fundrise.com", "budget_range": (4500, 13500)},
    {"name": "Kraken", "industry": "Cryptocurrency", "website": "https://www.kraken.com", "budget_range": (7000, 21000)},
    {"name": "Binance", "industry": "Cryptocurrency", "website": "https://www.binance.com", "budget_range": (8000, 24000)},
    {"name": "Ledger", "industry": "Cryptocurrency", "website": "https://www.ledger.com", "budget_range": (5000, 15000)},
    {"name": "Phantom", "industry": "Cryptocurrency", "website": "https://phantom.app", "budget_range": (4000, 12000)},
    {"name": "OKX", "industry": "Cryptocurrency", "website": "https://www.okx.com", "budget_range": (6000, 18000)},
    {"name": "Uniswap", "industry": "Cryptocurrency", "website": "https://uniswap.org", "budget_range": (5000, 15000)},
    {"name": "BlockFi", "industry": "Cryptocurrency", "website": "https://blockfi.com", "budget_range": (4500, 13500)},
    {"name": "MetaMask", "industry": "Cryptocurrency", "website": "https://metamask.io", "budget_range": (4500, 13500)},
    {"name": "YNAB", "industry": "Financial Planning", "website": "https://www.ynab.com", "budget_range": (4000, 12000)},
    {"name": "Personal Capital", "industry": "Financial Planning", "website": "https://www.personalcapital.com", "budget_range": (5000, 15000)},
    {"name": "Rocket Money", "industry": "Financial Planning", "website": "https://www.rocketmoney.com", "budget_range": (4500, 13500)},
    {"name": "Copilot Money", "industry": "Financial Planning", "website": "https://copilot.money", "budget_range": (3500, 10500)},
    {"name": "Tiller Money", "industry": "Financial Planning", "website": "https://www.tillerhq.com", "budget_range": (3000, 9000)},
    {"name": "Simplifi", "industry": "Financial Planning", "website": "https://www.quicken.com/simplifi", "budget_range": (3500, 10500)},
    {"name": "Honeydue", "industry": "Financial Planning", "website": "https://www.honeydue.com", "budget_range": (3000, 9000)},
    {"name": "Monarch Money", "industry": "Financial Planning", "website": "https://www.monarchmoney.com", "budget_range": (3500, 10500)},
    {"name": "Goodbudget", "industry": "Financial Planning", "website": "https://goodbudget.com", "budget_range": (2500, 7500)},
    {"name": "Root Insurance", "industry": "Insurance", "website": "https://www.joinroot.com", "budget_range": (5000, 15000)},
    {"name": "Hippo Insurance", "industry": "Insurance", "website": "https://www.hippo.com", "budget_range": (5000, 15000)},
    {"name": "Policygenius", "industry": "Insurance", "website": "https://www.policygenius.com", "budget_range": (4500, 13500)},
    {"name": "USAA", "industry": "Insurance", "website": "https://www.usaa.com", "budget_range": (8000, 24000)},
    {"name": "Allstate", "industry": "Insurance", "website": "https://www.allstate.com", "budget_range": (9000, 27000)},
    {"name": "Liberty Mutual", "industry": "Insurance", "website": "https://www.libertymutual.com", "budget_range": (8000, 24000)},
    {"name": "Nationwide", "industry": "Insurance", "website": "https://www.nationwide.com", "budget_range": (7000, 21000)},
    {"name": "Fubo", "industry": "Sports Streaming", "website": "https://www.fubo.tv", "budget_range": (5500, 16500)},
    {"name": "DAZN", "industry": "Sports Streaming", "website": "https://www.dazn.com", "budget_range": (6000, 18000)},
    {"name": "NBC Sports", "industry": "Sports Streaming", "website": "https://www.nbcsports.com", "budget_range": (7000, 21000)},
    {"name": "Fox Sports", "industry": "Sports Streaming", "website": "https://www.foxsports.com", "budget_range": (7000, 21000)},
    {"name": "CBS Sports", "industry": "Sports Streaming", "website": "https://www.cbssports.com", "budget_range": (6500, 19500)},
    {"name": "FloSports", "industry": "Sports Streaming", "website": "https://www.flosports.tv", "budget_range": (4000, 12000)},
    {"name": "Bally Sports", "industry": "Sports Streaming", "website": "https://www.ballysports.com", "budget_range": (5000, 15000)},
    {"name": "Venu Sports", "industry": "Sports Streaming", "website": "https://www.venusports.com", "budget_range": (6000, 18000)},
    {"name": "Stadium", "industry": "Sports Streaming", "website": "https://watchstadium.com", "budget_range": (3500, 10500)},
    {"name": "Puma", "industry": "Sports Apparel", "website": "https://www.puma.com", "budget_range": (7000, 21000)},
    {"name": "Reebok", "industry": "Sports Apparel", "website": "https://www.reebok.com", "budget_range": (6500, 19500)},
    {"name": "Champion", "industry": "Sports Apparel", "website": "https://www.champion.com", "budget_range": (5500, 16500)},
    {"name": "Fila", "industry": "Sports Apparel", "website": "https://www.fila.com", "budget_range": (5000, 15000)},
    {"name": "2XU", "industry": "Sports Apparel", "website": "https://www.2xu.com", "budget_range": (4000, 12000)},
    {"name": "Salomon", "industry": "Sports Apparel", "website": "https://www.salomon.com", "budget_range": (5500, 16500)},
    {"name": "Ellesse", "industry": "Sports Apparel", "website": "https://www.ellesse.com", "budget_range": (4000, 12000)},
    {"name": "Callaway Golf", "industry": "Sports Equipment", "website": "https://www.callawaygolf.com", "budget_range": (6000, 18000)},
    {"name": "Titleist", "industry": "Sports Equipment", "website": "https://www.titleist.com", "budget_range": (5500, 16500)},
    {"name": "Yonex", "industry": "Sports Equipment", "website": "https://www.yonex.com", "budget_range": (4500, 13500)},
    {"name": "Ping", "industry": "Sports Equipment", "website": "https://ping.com", "budget_range": (5000, 15000)},
    {"name": "Babolat", "industry": "Sports Equipment", "website": "https://www.babolat.com", "budget_range": (4500, 13500)},
    {"name": "Easton", "industry": "Sports Equipment", "website": "https://www.easton.com", "budget_range": (4000, 12000)},
    {"name": "Mizuno", "industry": "Sports Equipment", "website": "https://www.mizuno.com", "budget_range": (5000, 15000)},
    {"name": "TaylorMade", "industry": "Sports Equipment", "website": "https://www.taylormadegolf.com", "budget_range": (5500, 16500)},
    {"name": "Fanatics", "industry": "Sports Merchandise", "website": "https://www.fanatics.com", "budget_range": (8000, 24000)},
    {"name": "NHL Shop", "industry": "Sports Merchandise", "website": "https://shop.nhl.com", "budget_range": (5500, 16500)},
    {"name": "MLS Store", "industry": "Sports Merchandise", "website": "https://www.mlsstore.com", "budget_range": (4500, 13500)},
    {"name": "New Era", "industry": "Sports Merchandise", "website": "https://www.neweracap.com", "budget_range": (5000, 15000)},
    {"name": "47 Brand", "industry": "Sports Merchandise", "website": "https://www.47brand.com", "budget_range": (4000, 12000)},
    {"name": "Lids", "industry": "Sports Merchandise", "website": "https://www.lids.com", "budget_range": (4500, 13500)},
    {"name": "Pro:Direct Sport", "industry": "Sports Merchandise", "website": "https://www.prodirectsport.com", "budget_range": (4000, 12000)},
    {"name": "Soccer.com", "industry": "Sports Merchandise", "website": "https://www.soccer.com", "budget_range": (3500, 10500)},
    {"name": "Cabela's", "industry": "Sports Retail", "website": "https://www.cabelas.com", "budget_range": (7000, 21000)},
    {"name": "Scheels", "industry": "Sports Retail", "website": "https://www.scheels.com", "budget_range": (5000, 15000)},
    {"name": "Decathlon", "industry": "Sports Retail", "website": "https://www.decathlon.com", "budget_range": (6000, 18000)},
    {"name": "Big 5 Sporting Goods", "industry": "Sports Retail", "website": "https://www.big5sportinggoods.com", "budget_range": (4500, 13500)},
    {"name": "Backcountry", "industry": "Sports Retail", "website": "https://www.backcountry.com", "budget_range": (5500, 16500)},
    {"name": "Sierra Trading Post", "industry": "Sports Retail", "website": "https://www.sierra.com", "budget_range": (4500, 13500)},
    {"name": "Moosejaw", "industry": "Sports Retail", "website": "https://www.moosejaw.com", "budget_range": (4000, 12000)},
    {"name": "Sony", "industry": "Consumer Electronics", "website": "https://www.sony.com", "budget_range": (10000, 30000)},
    {"name": "LG Electronics", "industry": "Consumer Electronics", "website": "https://www.lg.com", "budget_range": (8000, 24000)},
    {"name": "Bose", "industry": "Consumer Electronics", "website": "https://www.bose.com", "budget_range": (7000, 21000)},
    {"name": "Sonos", "industry": "Consumer Electronics", "website": "https://www.sonos.com", "budget_range": (6000, 18000)},
    {"name": "Garmin", "industry": "Consumer Electronics", "website": "https://www.garmin.com", "budget_range": (6000, 18000)},
    {"name": "JBL", "industry": "Consumer Electronics", "website": "https://www.jbl.com", "budget_range": (5500, 16500)},
    {"name": "Anker", "industry": "Consumer Electronics", "website": "https://www.anker.com", "budget_range": (5000, 15000)},
    {"name": "Logitech", "industry": "Consumer Electronics", "website": "https://www.logitech.com", "budget_range": (6000, 18000)},
    {"name": "IBM Cloud", "industry": "Software & Cloud", "website": "https://www.ibm.com/cloud", "budget_range": (10000, 30000)},
    {"name": "DigitalOcean", "industry": "Software & Cloud", "website": "https://www.digitalocean.com", "budget_range": (5000, 15000)},
    {"name": "Cloudflare", "industry": "Software & Cloud", "website": "https://www.cloudflare.com", "budget_range": (6000, 18000)},
    {"name": "Akamai", "industry": "Software & Cloud", "website": "https://www.akamai.com", "budget_range": (7000, 21000)},
    {"name": "VMware", "industry": "Software & Cloud", "website": "https://www.vmware.com", "budget_range": (8000, 24000)},
    {"name": "Red Hat", "industry": "Software & Cloud", "website": "https://www.redhat.com", "budget_range": (7000, 21000)},
    {"name": "Heroku", "industry": "Software & Cloud", "website": "https://www.heroku.com", "budget_range": (4000, 12000)},
    {"name": "Linode", "industry": "Software & Cloud", "website": "https://www.linode.com", "budget_range": (4000, 12000)},
    {"name": "Notion", "industry": "Software", "website": "https://www.notion.so", "budget_range": (5000, 15000)},
    {"name": "Airtable", "industry": "Software", "website": "https://www.airtable.com", "budget_range": (5000, 15000)},
    {"name": "InVision", "industry": "Software", "website": "https://www.invisionapp.com", "budget_range": (4500, 13500)},
    {"name": "Procreate", "industry": "Software", "website": "https://procreate.com", "budget_range": (4000, 12000)},
    {"name": "Affinity", "industry": "Software", "website": "https://affinity.serif.com", "budget_range": (4000, 12000)},
    {"name": "DaVinci Resolve", "industry": "Software", "website": "https://www.blackmagicdesign.com/products/davinciresolve", "budget_range": (5000, 15000)},
    {"name": "Loom", "industry": "Software", "website": "https://www.loom.com", "budget_range": (4000, 12000)},
    {"name": "BMW iX", "industry": "Electric Vehicles", "website": "https://www.bmwusa.com/vehicles/bmwix", "budget_range": (8000, 24000)},
    {"name": "Mercedes EQ", "industry": "Electric Vehicles", "website": "https://www.mbusa.com/en/eq", "budget_range": (8000, 24000)},
    {"name": "Hyundai IONIQ", "industry": "Electric Vehicles", "website": "https://www.hyundaiusa.com/ioniq", "budget_range": (6000, 18000)},
    {"name": "Kia EV", "industry": "Electric Vehicles", "website": "https://www.kia.com/ev", "budget_range": (5500, 16500)},
    {"name": "Fisker", "industry": "Electric Vehicles", "website": "https://www.fiskerinc.com", "budget_range": (5000, 15000)},
    {"name": "Canoo", "industry": "Electric Vehicles", "website": "https://www.canoo.com", "budget_range": (4500, 13500)},
    {"name": "Volvo EX", "industry": "Electric Vehicles", "website": "https://www.volvocars.com/electric", "budget_range": (7000, 21000)},
    {"name": "Ford Electric", "industry": "Electric Vehicles", "website": "https://www.ford.com/electric", "budget_range": (8000, 24000)},
    {"name": "Acer", "industry": "Computer Hardware", "website": "https://www.acer.com", "budget_range": (5000, 15000)},
    {"name": "MSI", "industry": "Computer Hardware", "website": "https://www.msi.com", "budget_range": (5500, 16500)},
    {"name": "Corsair", "industry": "Computer Hardware", "website": "https://www.corsair.com", "budget_range": (5000, 15000)},
    {"name": "Alienware", "industry": "Computer Hardware", "website": "https://www.dell.com/alienware", "budget_range": (6000, 18000)},
    {"name": "System76", "industry": "Computer Hardware", "website": "https://system76.com", "budget_range": (3500, 10500)},
    {"name": "Framework", "industry": "Computer Hardware", "website": "https://frame.work", "budget_range": (3500, 10500)},
    {"name": "Dynabook", "industry": "Computer Hardware", "website": "https://www.dynabook.com", "budget_range": (4000, 12000)},
    {"name": "Samsung PC", "industry": "Computer Hardware", "website": "https://www.samsung.com/us/computing", "budget_range": (6000, 18000)},
    {"name": "Xfinity Mobile", "industry": "Telecom", "website": "https://www.xfinity.com/mobile", "budget_range": (7000, 21000)},
    {"name": "US Cellular", "industry": "Telecom", "website": "https://www.uscellular.com", "budget_range": (5000, 15000)},
    {"name": "Visible", "industry": "Telecom", "website": "https://www.visible.com", "budget_range": (4000, 12000)},
    {"name": "Cricket Wireless", "industry": "Telecom", "website": "https://www.cricketwireless.com", "budget_range": (4500, 13500)},
    {"name": "Boost Mobile", "industry": "Telecom", "website": "https://www.boostmobile.com", "budget_range": (4500, 13500)},
    {"name": "Spectrum Mobile", "industry": "Telecom", "website": "https://www.spectrum.com/mobile", "budget_range": (5500, 16500)},
    {"name": "Straight Talk", "industry": "Telecom", "website": "https://www.straighttalk.com", "budget_range": (4000, 12000)},
    {"name": "Consumer Cellular", "industry": "Telecom", "website": "https://www.consumercellular.com", "budget_range": (4000, 12000)},
    {"name": "Wall Street Journal", "industry": "News Media", "website": "https://www.wsj.com", "budget_range": (8000, 24000)},
    {"name": "The Guardian", "industry": "News Media", "website": "https://www.theguardian.com", "budget_range": (6000, 18000)},
    {"name": "Financial Times", "industry": "News Media", "website": "https://www.ft.com", "budget_range": (7000, 21000)},
    {"name": "The Economist", "industry": "News Media", "website": "https://www.economist.com", "budget_range": (6500, 19500)},
    {"name": "Axios", "industry": "News Media", "website": "https://www.axios.com", "budget_range": (5000, 15000)},
    {"name": "Vox Media", "industry": "News Media", "website": "https://www.voxmedia.com", "budget_range": (5000, 15000)},
    {"name": "Vice News", "industry": "News Media", "website": "https://www.vice.com/en/section/news", "budget_range": (4500, 13500)},
    {"name": "Storytel", "industry": "Audiobooks", "website": "https://www.storytel.com", "budget_range": (4500, 13500)},
    {"name": "Chirp", "industry": "Audiobooks", "website": "https://www.chirpbooks.com", "budget_range": (3500, 10500)},
    {"name": "Hoopla", "industry": "Audiobooks", "website": "https://www.hoopladigital.com", "budget_range": (3500, 10500)},
    {"name": "Blinkist", "industry": "Audiobooks", "website": "https://www.blinkist.com", "budget_range": (4000, 12000)},
    {"name": "Libby", "industry": "Audiobooks", "website": "https://libbyapp.com", "budget_range": (3000, 9000)},
    {"name": "Podimo", "industry": "Audiobooks", "website": "https://podimo.com", "budget_range": (3500, 10500)},
    {"name": "NextoryAB", "industry": "Audiobooks", "website": "https://www.nextory.com", "budget_range": (3000, 9000)},
    {"name": "Everand", "industry": "Audiobooks", "website": "https://www.everand.com", "budget_range": (4000, 12000)},
    {"name": "Downpour", "industry": "Audiobooks", "website": "https://www.downpour.com", "budget_range": (3000, 9000)},
    {"name": "Compass", "industry": "Real Estate", "website": "https://www.compass.com", "budget_range": (7000, 21000)},
    {"name": "Offerpad", "industry": "Real Estate", "website": "https://www.offerpad.com", "budget_range": (5000, 15000)},
    {"name": "Homelight", "industry": "Real Estate", "website": "https://www.homelight.com", "budget_range": (5000, 15000)},
    {"name": "Knock", "industry": "Real Estate", "website": "https://www.knock.com", "budget_range": (4500, 13500)},
    {"name": "Rocket Homes", "industry": "Real Estate", "website": "https://www.rockethomes.com", "budget_range": (6000, 18000)},
    {"name": "Flyhomes", "industry": "Real Estate", "website": "https://www.flyhomes.com", "budget_range": (4500, 13500)},
    {"name": "Movoto", "industry": "Real Estate", "website": "https://www.movoto.com", "budget_range": (4000, 12000)},
    {"name": "BarkBox", "industry": "Pet Products", "website": "https://www.barkbox.com", "budget_range": (4500, 13500)},
    {"name": "Petco", "industry": "Pet Products", "website": "https://www.petco.com", "budget_range": (7000, 21000)},
    {"name": "PetSmart", "industry": "Pet Products", "website": "https://www.petsmart.com", "budget_range": (7000, 21000)},
    {"name": "The Farmer's Dog", "industry": "Pet Products", "website": "https://www.thefarmersdog.com", "budget_range": (5000, 15000)},
    {"name": "Nom Nom", "industry": "Pet Products", "website": "https://www.nomnomnow.com", "budget_range": (4500, 13500)},
    {"name": "Wisdom Panel", "industry": "Pet Products", "website": "https://www.wisdompanel.com", "budget_range": (4000, 12000)},
    {"name": "PetPlate", "industry": "Pet Products", "website": "https://www.petplate.com", "budget_range": (4000, 12000)},
    {"name": "Lowe's", "industry": "Home & Garden", "website": "https://www.lowes.com", "budget_range": (9000, 27000)},
    {"name": "Overstock", "industry": "Home & Garden", "website": "https://www.overstock.com", "budget_range": (5500, 16500)},
    {"name": "Article", "industry": "Home & Garden", "website": "https://www.article.com", "budget_range": (5000, 15000)},
    {"name": "Floyd", "industry": "Home & Garden", "website": "https://floydhome.com", "budget_range": (4000, 12000)},
    {"name": "Burrow", "industry": "Home & Garden", "website": "https://burrow.com", "budget_range": (4500, 13500)},
    {"name": "Ruggable", "industry": "Home & Garden", "website": "https://ruggable.com", "budget_range": (4500, 13500)},
    {"name": "Joybird", "industry": "Home & Garden", "website": "https://joybird.com", "budget_range": (5000, 15000)},
    {"name": "Pluralsight", "industry": "EdTech", "website": "https://www.pluralsight.com", "budget_range": (5000, 15000)},
    {"name": "Khan Academy", "industry": "EdTech", "website": "https://www.khanacademy.org", "budget_range": (4000, 12000)},
    {"name": "Codecademy", "industry": "EdTech", "website": "https://www.codecademy.com", "budget_range": (4500, 13500)},
    {"name": "DataCamp", "industry": "EdTech", "website": "https://www.datacamp.com", "budget_range": (4500, 13500)},
    {"name": "Brilliant", "industry": "EdTech", "website": "https://brilliant.org", "budget_range": (4000, 12000)},
    {"name": "Postmates", "industry": "Food Delivery", "website": "https://postmates.com", "budget_range": (6000, 18000)},
    {"name": "Instacart", "industry": "Food Delivery", "website": "https://www.instacart.com", "budget_range": (7000, 21000)},
    {"name": "Caviar", "industry": "Food Delivery", "website": "https://www.trycaviar.com", "budget_range": (5000, 15000)},
    {"name": "Gopuff", "industry": "Food Delivery", "website": "https://gopuff.com", "budget_range": (5000, 15000)},
    {"name": "Factor", "industry": "Food Delivery", "website": "https://www.factor75.com", "budget_range": (5500, 16500)},
    {"name": "Freshly", "industry": "Food Delivery", "website": "https://www.freshly.com", "budget_range": (5000, 15000)},
    {"name": "Hungryroot", "industry": "Food Delivery", "website": "https://www.hungryroot.com", "budget_range": (4500, 13500)},
    {"name": "Chick-fil-A", "industry": "Restaurants", "website": "https://www.chick-fil-a.com", "budget_range": (8000, 24000)},
    {"name": "Wingstop", "industry": "Restaurants", "website": "https://www.wingstop.com", "budget_range": (5500, 16500)},
    {"name": "Five Guys", "industry": "Restaurants", "website": "https://www.fiveguys.com", "budget_range": (5500, 16500)},
    {"name": "Nando's", "industry": "Restaurants", "website": "https://www.nandos.com", "budget_range": (5000, 15000)},
    {"name": "Cava", "industry": "Restaurants", "website": "https://www.cava.com", "budget_range": (4500, 13500)},
    {"name": "Portillo's", "industry": "Restaurants", "website": "https://www.portillos.com", "budget_range": (4500, 13500)},
    {"name": "Raising Cane's", "industry": "Restaurants", "website": "https://www.raisingcanes.com", "budget_range": (6000, 18000)},
    {"name": "Orangetheory", "industry": "Fitness & Wellness", "website": "https://www.orangetheory.com", "budget_range": (5500, 16500)},
    {"name": "CrossFit", "industry": "Fitness & Wellness", "website": "https://www.crossfit.com", "budget_range": (5000, 15000)},
    {"name": "Barry's", "industry": "Fitness & Wellness", "website": "https://www.barrys.com", "budget_range": (5000, 15000)},
    {"name": "SoulCycle", "industry": "Fitness & Wellness", "website": "https://www.soul-cycle.com", "budget_range": (4500, 13500)},
    {"name": "F45 Training", "industry": "Fitness & Wellness", "website": "https://f45training.com", "budget_range": (4500, 13500)},
    {"name": "Cerebral", "industry": "Healthcare", "website": "https://cerebral.com", "budget_range": (4500, 13500)},
    {"name": "Nurx", "industry": "Healthcare", "website": "https://www.nurx.com", "budget_range": (4000, 12000)},
    {"name": "Done", "industry": "Healthcare", "website": "https://www.donefirst.com", "budget_range": (4000, 12000)},
    {"name": "PlushCare", "industry": "Healthcare", "website": "https://plushcare.com", "budget_range": (4500, 13500)},
    {"name": "MDLive", "industry": "Healthcare", "website": "https://www.mdlive.com", "budget_range": (5000, 15000)},
    {"name": "Amwell", "industry": "Healthcare", "website": "https://www.amwell.com", "budget_range": (5000, 15000)},
    {"name": "98point6", "industry": "Healthcare", "website": "https://www.98point6.com", "budget_range": (3500, 10500)},
    {"name": "K Health", "industry": "Healthcare", "website": "https://khealth.com", "budget_range": (4000, 12000)},
    {"name": "Hopper", "industry": "Travel", "website": "https://www.hopper.com", "budget_range": (5000, 15000)},
    {"name": "Skyscanner", "industry": "Travel", "website": "https://www.skyscanner.com", "budget_range": (5500, 16500)},
    {"name": "Hotels.com", "industry": "Travel", "website": "https://www.hotels.com", "budget_range": (7000, 21000)},
    {"name": "Priceline", "industry": "Travel", "website": "https://www.priceline.com", "budget_range": (7000, 21000)},
    {"name": "Trivago", "industry": "Travel", "website": "https://www.trivago.com", "budget_range": (6000, 18000)},
    {"name": "Spirit Airlines", "industry": "Airlines", "website": "https://www.spirit.com", "budget_range": (5000, 15000)},
    {"name": "Frontier Airlines", "industry": "Airlines", "website": "https://www.flyfrontier.com", "budget_range": (4500, 13500)},
    {"name": "Hawaiian Airlines", "industry": "Airlines", "website": "https://www.hawaiianairlines.com", "budget_range": (5000, 15000)},
    {"name": "Allegiant Air", "industry": "Airlines", "website": "https://www.allegiantair.com", "budget_range": (4000, 12000)},
    {"name": "Breeze Airways", "industry": "Airlines", "website": "https://www.flybreeze.com", "budget_range": (3500, 10500)},
    {"name": "Sun Country Airlines", "industry": "Airlines", "website": "https://www.suncountry.com", "budget_range": (3500, 10500)},
    {"name": "Avelo Airlines", "industry": "Airlines", "website": "https://www.aveloair.com", "budget_range": (3000, 9000)},
    {"name": "JSX", "industry": "Airlines", "website": "https://www.jsx.com", "budget_range": (4500, 13500)},
    {"name": "Chevrolet", "industry": "Automotive", "website": "https://www.chevrolet.com", "budget_range": (9000, 27000)},
    {"name": "Nissan", "industry": "Automotive", "website": "https://www.nissanusa.com", "budget_range": (8000, 24000)},
    {"name": "Mazda", "industry": "Automotive", "website": "https://www.mazdausa.com", "budget_range": (6000, 18000)},
    {"name": "Subaru", "industry": "Automotive", "website": "https://www.subaru.com", "budget_range": (6500, 19500)},
    {"name": "Kia", "industry": "Automotive", "website": "https://www.kia.com", "budget_range": (6000, 18000)},
    {"name": "Volvo", "industry": "Automotive", "website": "https://www.volvocars.com", "budget_range": (7000, 21000)},
    {"name": "Jeep", "industry": "Automotive", "website": "https://www.jeep.com", "budget_range": (7000, 21000)},
    {"name": "Notion", "industry": "B2B SaaS", "website": "https://www.notion.so", "budget_range": (5000, 15000)},
    {"name": "Airtable", "industry": "B2B SaaS", "website": "https://www.airtable.com", "budget_range": (5000, 15000)},
    {"name": "Zapier", "industry": "B2B SaaS", "website": "https://zapier.com", "budget_range": (5500, 16500)},
    {"name": "Fortinet", "industry": "Cybersecurity", "website": "https://www.fortinet.com", "budget_range": (7000, 21000)},
    {"name": "SentinelOne", "industry": "Cybersecurity", "website": "https://www.sentinelone.com", "budget_range": (6000, 18000)},
    {"name": "Snyk", "industry": "Cybersecurity", "website": "https://snyk.io", "budget_range": (5000, 15000)},
    {"name": "Proofpoint", "industry": "Cybersecurity", "website": "https://www.proofpoint.com", "budget_range": (6000, 18000)},
    {"name": "Cloudflare Security", "industry": "Cybersecurity", "website": "https://www.cloudflare.com/security", "budget_range": (6000, 18000)},
    {"name": "Sophos", "industry": "Cybersecurity", "website": "https://www.sophos.com", "budget_range": (5500, 16500)},
    {"name": "Trend Micro", "industry": "Cybersecurity", "website": "https://www.trendmicro.com", "budget_range": (5500, 16500)},
    {"name": "KnowBe4", "industry": "Cybersecurity", "website": "https://www.knowbe4.com", "budget_range": (4500, 13500)},
    {"name": "Artsy", "industry": "Culture", "website": "https://www.artsy.net", "budget_range": (4000, 12000)},
    {"name": "British Museum", "industry": "Culture", "website": "https://www.britishmuseum.org", "budget_range": (3500, 10500)},
    {"name": "Guggenheim", "industry": "Culture", "website": "https://www.guggenheim.org", "budget_range": (3500, 10500)},
    {"name": "Lincoln Center", "industry": "Culture", "website": "https://www.lincolncenter.org", "budget_range": (4000, 12000)},
    {"name": "Carnegie Hall", "industry": "Culture", "website": "https://www.carnegiehall.org", "budget_range": (4000, 12000)},
    {"name": "Criterion Collection", "industry": "Culture", "website": "https://www.criterion.com", "budget_range": (3500, 10500)},
    {"name": "Sundance Institute", "industry": "Culture", "website": "https://www.sundance.org", "budget_range": (3500, 10500)},
    {"name": "TIFF", "industry": "Culture", "website": "https://www.tiff.net", "budget_range": (3500, 10500)},
    {"name": "Coursera", "industry": "Education", "website": "https://www.coursera.org", "budget_range": (6000, 18000)},
    {"name": "edX", "industry": "Education", "website": "https://www.edx.org", "budget_range": (5500, 16500)},
    {"name": "Scholastic", "industry": "Education", "website": "https://www.scholastic.com", "budget_range": (5500, 16500)},
    {"name": "Cengage", "industry": "Education", "website": "https://www.cengage.com", "budget_range": (5500, 16500)},
    {"name": "Kaplan", "industry": "Education", "website": "https://www.kaplan.com", "budget_range": (6000, 18000)},
    {"name": "Princeton Review", "industry": "Education", "website": "https://www.princetonreview.com", "budget_range": (5000, 15000)},
    {"name": "Houghton Mifflin", "industry": "Education", "website": "https://www.hmhco.com", "budget_range": (5500, 16500)},
    {"name": "Save the Children", "industry": "Non-Profit", "website": "https://www.savethechildren.org", "budget_range": (3000, 10000)},
    {"name": "Amnesty International", "industry": "Non-Profit", "website": "https://www.amnesty.org", "budget_range": (3000, 10000)},
    {"name": "Feeding America", "industry": "Non-Profit", "website": "https://www.feedingamerica.org", "budget_range": (3500, 11000)},
    {"name": "Greenpeace", "industry": "Non-Profit", "website": "https://www.greenpeace.org", "budget_range": (3000, 9500)},
    {"name": "The Nature Conservancy", "industry": "Non-Profit", "website": "https://www.nature.org", "budget_range": (3500, 11000)},
    {"name": "St. Jude", "industry": "Non-Profit", "website": "https://www.stjude.org", "budget_range": (4000, 12000)},
    {"name": "Oxfam", "industry": "Non-Profit", "website": "https://www.oxfam.org", "budget_range": (3000, 9500)},
    {"name": "Goodwill", "industry": "Non-Profit", "website": "https://www.goodwill.org", "budget_range": (3000, 9500)},
    {"name": "EPA", "industry": "Government", "website": "https://www.epa.gov", "budget_range": (5000, 15000)},
    {"name": "FEMA", "industry": "Government", "website": "https://www.fema.gov", "budget_range": (5000, 15000)},
    {"name": "SSA", "industry": "Government", "website": "https://www.ssa.gov", "budget_range": (5500, 16500)},
    {"name": "National Park Service", "industry": "Government", "website": "https://www.nps.gov", "budget_range": (4000, 12000)},
    {"name": "TSA", "industry": "Government", "website": "https://www.tsa.gov", "budget_range": (4500, 13500)},
    {"name": "SBA", "industry": "Government", "website": "https://www.sba.gov", "budget_range": (4500, 13500)},
    {"name": "VA", "industry": "Government", "website": "https://www.va.gov", "budget_range": (5000, 15000)},
    {"name": "NIH", "industry": "Government", "website": "https://www.nih.gov", "budget_range": (5500, 16500)},
    {"name": "DOE", "industry": "Government", "website": "https://www.energy.gov", "budget_range": (5000, 15000)},
    {"name": "Associated Press", "industry": "Politics", "website": "https://apnews.com", "budget_range": (5000, 15000)},
    {"name": "NPR Politics", "industry": "Politics", "website": "https://www.npr.org/sections/politics", "budget_range": (4500, 13500)},
    {"name": "ProPublica", "industry": "Politics", "website": "https://www.propublica.org", "budget_range": (4000, 12000)},
    {"name": "The Intercept", "industry": "Politics", "website": "https://theintercept.com", "budget_range": (3500, 10500)},
    {"name": "Ballotpedia", "industry": "Politics", "website": "https://ballotpedia.org", "budget_range": (3000, 9000)},
    {"name": "OpenSecrets", "industry": "Politics", "website": "https://www.opensecrets.org", "budget_range": (3000, 9000)},
    {"name": "Real Clear Politics", "industry": "Politics", "website": "https://www.realclearpolitics.com", "budget_range": (4000, 12000)},
    {"name": "Pew Research", "industry": "Politics", "website": "https://www.pewresearch.org", "budget_range": (4000, 12000)},
    {"name": "The Marshall Project", "industry": "Politics", "website": "https://www.themarshallproject.org", "budget_range": (3000, 9000)},
    {"name": "ARM", "industry": "Technology", "website": "https://www.arm.com", "budget_range": (8000, 24000)},
    {"name": "Broadcom", "industry": "Technology", "website": "https://www.broadcom.com", "budget_range": (8000, 24000)},
    {"name": "Texas Instruments", "industry": "Technology", "website": "https://www.ti.com", "budget_range": (7000, 21000)},
    {"name": "Micron", "industry": "Technology", "website": "https://www.micron.com", "budget_range": (7000, 21000)},
    {"name": "Western Digital", "industry": "Technology", "website": "https://www.westerndigital.com", "budget_range": (6000, 18000)},
    {"name": "Seagate", "industry": "Technology", "website": "https://www.seagate.com", "budget_range": (6000, 18000)},
    {"name": "NetApp", "industry": "Technology", "website": "https://www.netapp.com", "budget_range": (6500, 19500)},
    {"name": "HPE", "industry": "Technology", "website": "https://www.hpe.com", "budget_range": (8000, 24000)},
    {"name": "Mistral AI", "industry": "AI", "website": "https://mistral.ai", "budget_range": (6000, 18000)},
    {"name": "Perplexity", "industry": "AI", "website": "https://www.perplexity.ai", "budget_range": (5000, 15000)},
    {"name": "Jasper AI", "industry": "AI", "website": "https://www.jasper.ai", "budget_range": (4500, 13500)},
    {"name": "Runway ML", "industry": "AI", "website": "https://runwayml.com", "budget_range": (4500, 13500)},
    {"name": "Scale AI", "industry": "AI", "website": "https://scale.com", "budget_range": (6000, 18000)},
    {"name": "Weights & Biases", "industry": "AI", "website": "https://wandb.ai", "budget_range": (4000, 12000)},
    {"name": "Replicate", "industry": "AI", "website": "https://replicate.com", "budget_range": (3500, 10500)},
    {"name": "Klarna", "industry": "FinTech", "website": "https://www.klarna.com", "budget_range": (7000, 21000)},
    {"name": "Marqeta", "industry": "FinTech", "website": "https://www.marqeta.com", "budget_range": (5000, 15000)},
    {"name": "Brex", "industry": "FinTech", "website": "https://www.brex.com", "budget_range": (5500, 16500)},
    {"name": "Ramp", "industry": "FinTech", "website": "https://ramp.com", "budget_range": (5000, 15000)},
    {"name": "Mercury", "industry": "FinTech", "website": "https://mercury.com", "budget_range": (4500, 13500)},
    {"name": "Dave", "industry": "FinTech", "website": "https://www.dave.com", "budget_range": (4000, 12000)},
    {"name": "Current", "industry": "FinTech", "website": "https://current.com", "budget_range": (4000, 12000)},
    {"name": "Headspace Health", "industry": "HealthTech", "website": "https://www.headspace.com", "budget_range": (5500, 16500)},
    {"name": "Included Health", "industry": "HealthTech", "website": "https://www.includedhealth.com", "budget_range": (5000, 15000)},
    {"name": "Hinge Health", "industry": "HealthTech", "website": "https://www.hingehealth.com", "budget_range": (5000, 15000)},
    {"name": "Noom", "industry": "HealthTech", "website": "https://www.noom.com", "budget_range": (6000, 18000)},
    {"name": "Virta Health", "industry": "HealthTech", "website": "https://www.virtahealth.com", "budget_range": (4500, 13500)},
    {"name": "Color Health", "industry": "HealthTech", "website": "https://www.color.com", "budget_range": (4500, 13500)},
    {"name": "Omada Health", "industry": "HealthTech", "website": "https://www.omadahealth.com", "budget_range": (4500, 13500)},
    {"name": "Spring Health", "industry": "HealthTech", "website": "https://www.springhealth.com", "budget_range": (4500, 13500)},
    {"name": "Mercari", "industry": "E-commerce", "website": "https://www.mercari.com", "budget_range": (5000, 15000)},
    {"name": "Poshmark", "industry": "E-commerce", "website": "https://poshmark.com", "budget_range": (5000, 15000)},
    {"name": "ThredUp", "industry": "E-commerce", "website": "https://www.thredup.com", "budget_range": (4500, 13500)},
    {"name": "StockX", "industry": "E-commerce", "website": "https://stockx.com", "budget_range": (5500, 16500)},
    {"name": "Depop", "industry": "E-commerce", "website": "https://www.depop.com", "budget_range": (4000, 12000)},
    {"name": "Temu", "industry": "E-commerce", "website": "https://www.temu.com", "budget_range": (8000, 24000)},
    {"name": "Faire", "industry": "E-commerce", "website": "https://www.faire.com", "budget_range": (5000, 15000)},
    {"name": "Citi", "industry": "Personal Banking", "website": "https://www.citi.com", "budget_range": (9000, 27000)},
    {"name": "US Bank", "industry": "Personal Banking", "website": "https://www.usbank.com", "budget_range": (8000, 24000)},
    {"name": "PNC", "industry": "Personal Banking", "website": "https://www.pnc.com", "budget_range": (7000, 21000)},
    {"name": "TD Bank", "industry": "Personal Banking", "website": "https://www.td.com", "budget_range": (7000, 21000)},
    {"name": "Discover Bank", "industry": "Personal Banking", "website": "https://www.discover.com/online-banking", "budget_range": (6000, 18000)},
    {"name": "SoFi Banking", "industry": "Personal Banking", "website": "https://www.sofi.com/banking", "budget_range": (5500, 16500)},
    {"name": "Wealthfront Cash", "industry": "Personal Banking", "website": "https://www.wealthfront.com/cash", "budget_range": (4500, 13500)},
    {"name": "BrewDog", "industry": "Craft Beer & Spirits", "website": "https://www.brewdog.com", "budget_range": (5000, 15000)},
    {"name": "Stone Brewing", "industry": "Craft Beer & Spirits", "website": "https://www.stonebrewing.com", "budget_range": (4500, 13500)},
    {"name": "Lagunitas", "industry": "Craft Beer & Spirits", "website": "https://lagunitas.com", "budget_range": (5000, 15000)},
    {"name": "Hendrick's Gin", "industry": "Craft Beer & Spirits", "website": "https://www.hendricksgin.com", "budget_range": (5500, 16500)},
    {"name": "Bulleit Bourbon", "industry": "Craft Beer & Spirits", "website": "https://www.bulleit.com", "budget_range": (5000, 15000)},
    {"name": "Casamigos", "industry": "Craft Beer & Spirits", "website": "https://www.casamigos.com", "budget_range": (6000, 18000)},
    {"name": "Aviation Gin", "industry": "Craft Beer & Spirits", "website": "https://www.aviationgin.com", "budget_range": (5000, 15000)},
    {"name": "Athletic Brewing", "industry": "Craft Beer & Spirits", "website": "https://athleticbrewing.com", "budget_range": (4000, 12000)},
    {"name": "Liquid Death", "industry": "Energy Drinks", "website": "https://liquiddeath.com", "budget_range": (6000, 18000)},
    {"name": "ZOA Energy", "industry": "Energy Drinks", "website": "https://zoaenergy.com", "budget_range": (5000, 15000)},
    {"name": "Alani Nu", "industry": "Energy Drinks", "website": "https://www.alaninu.com", "budget_range": (5000, 15000)},
    {"name": "Reign", "industry": "Energy Drinks", "website": "https://www.reignbodyfuel.com", "budget_range": (5000, 15000)},
    {"name": "Bang Energy", "industry": "Energy Drinks", "website": "https://bangenergy.com", "budget_range": (5500, 16500)},
    {"name": "C4 Energy", "industry": "Energy Drinks", "website": "https://cellucor.com/c4-energy", "budget_range": (4500, 13500)},
    {"name": "Guayaki", "industry": "Energy Drinks", "website": "https://guayaki.com", "budget_range": (3500, 10500)},
    {"name": "Nuun", "industry": "Energy Drinks", "website": "https://nuunlife.com", "budget_range": (3500, 10500)},
    {"name": "Stumptown Coffee", "industry": "Coffee & Tea", "website": "https://www.stumptowncoffee.com", "budget_range": (4000, 12000)},
    {"name": "Counter Culture", "industry": "Coffee & Tea", "website": "https://counterculturecoffee.com", "budget_range": (3500, 10500)},
    {"name": "Intelligentsia", "industry": "Coffee & Tea", "website": "https://www.intelligentsia.com", "budget_range": (4000, 12000)},
    {"name": "La Colombe", "industry": "Coffee & Tea", "website": "https://www.lacolombe.com", "budget_range": (4500, 13500)},
    {"name": "Peet's Coffee", "industry": "Coffee & Tea", "website": "https://www.peets.com", "budget_range": (5000, 15000)},
    {"name": "Rishi Tea", "industry": "Coffee & Tea", "website": "https://www.rishi-tea.com", "budget_range": (3000, 9000)},
    {"name": "DAVIDsTEA", "industry": "Coffee & Tea", "website": "https://www.davidstea.com", "budget_range": (3500, 10500)},
    {"name": "Keurig", "industry": "Coffee & Tea", "website": "https://www.keurig.com", "budget_range": (6000, 18000)},
    {"name": "Merck", "industry": "Pharmaceuticals", "website": "https://www.merck.com", "budget_range": (10000, 30000)},
    {"name": "Bristol-Myers Squibb", "industry": "Pharmaceuticals", "website": "https://www.bms.com", "budget_range": (9000, 27000)},
    {"name": "Novartis", "industry": "Pharmaceuticals", "website": "https://www.novartis.com", "budget_range": (9000, 27000)},
    {"name": "AstraZeneca", "industry": "Pharmaceuticals", "website": "https://www.astrazeneca.com", "budget_range": (9000, 27000)},
    {"name": "Roche", "industry": "Pharmaceuticals", "website": "https://www.roche.com", "budget_range": (9000, 27000)},
    {"name": "Sanofi", "industry": "Pharmaceuticals", "website": "https://www.sanofi.com", "budget_range": (8000, 24000)},
    {"name": "GSK", "industry": "Pharmaceuticals", "website": "https://www.gsk.com", "budget_range": (8000, 24000)},
    {"name": "Amgen", "industry": "Pharmaceuticals", "website": "https://www.amgen.com", "budget_range": (8000, 24000)},
    {"name": "Garden of Life", "industry": "Supplements & Nutrition", "website": "https://www.gardenoflife.com", "budget_range": (4500, 13500)},
    {"name": "Nature's Way", "industry": "Supplements & Nutrition", "website": "https://www.naturesway.com", "budget_range": (4000, 12000)},
    {"name": "MusclePharm", "industry": "Supplements & Nutrition", "website": "https://www.musclepharm.com", "budget_range": (4000, 12000)},
    {"name": "Orgain", "industry": "Supplements & Nutrition", "website": "https://www.orgain.com", "budget_range": (4500, 13500)},
    {"name": "Athletic Greens", "industry": "Supplements & Nutrition", "website": "https://athleticgreens.com", "budget_range": (5500, 16500)},
    {"name": "Ritual", "industry": "Supplements & Nutrition", "website": "https://ritual.com", "budget_range": (4500, 13500)},
    {"name": "Momentous", "industry": "Supplements & Nutrition", "website": "https://www.livemomentous.com", "budget_range": (4500, 13500)},
    {"name": "OWYN", "industry": "Supplements & Nutrition", "website": "https://liveowyn.com", "budget_range": (3500, 10500)},
    {"name": "Accor", "industry": "Hotels & Resorts", "website": "https://www.accor.com", "budget_range": (8000, 24000)},
    {"name": "Wyndham", "industry": "Hotels & Resorts", "website": "https://www.wyndhamhotels.com", "budget_range": (7000, 21000)},
    {"name": "Best Western", "industry": "Hotels & Resorts", "website": "https://www.bestwestern.com", "budget_range": (6000, 18000)},
    {"name": "Radisson", "industry": "Hotels & Resorts", "website": "https://www.radissonhotels.com", "budget_range": (6000, 18000)},
    {"name": "Rosewood Hotels", "industry": "Hotels & Resorts", "website": "https://www.rosewoodhotels.com", "budget_range": (7000, 21000)},
    {"name": "Aman Resorts", "industry": "Hotels & Resorts", "website": "https://www.aman.com", "budget_range": (7500, 22500)},
    {"name": "W Hotels", "industry": "Hotels & Resorts", "website": "https://www.marriott.com/w-hotels", "budget_range": (7000, 21000)},
    {"name": "Kimpton Hotels", "industry": "Hotels & Resorts", "website": "https://www.ihg.com/kimptonhotels", "budget_range": (6000, 18000)},
    {"name": "MSC Cruises", "industry": "Cruises", "website": "https://www.msccruises.com", "budget_range": (7000, 21000)},
    {"name": "Disney Cruise Line", "industry": "Cruises", "website": "https://disneycruise.disney.go.com", "budget_range": (8000, 24000)},
    {"name": "Viking Cruises", "industry": "Cruises", "website": "https://www.vikingcruises.com", "budget_range": (7000, 21000)},
    {"name": "Princess Cruises", "industry": "Cruises", "website": "https://www.princess.com", "budget_range": (6500, 19500)},
    {"name": "Holland America", "industry": "Cruises", "website": "https://www.hollandamerica.com", "budget_range": (6500, 19500)},
    {"name": "Silversea", "industry": "Cruises", "website": "https://www.silversea.com", "budget_range": (7500, 22500)},
    {"name": "Cunard", "industry": "Cruises", "website": "https://www.cunard.com", "budget_range": (7000, 21000)},
    {"name": "Windstar Cruises", "industry": "Cruises", "website": "https://www.windstarcruises.com", "budget_range": (6000, 18000)},
    {"name": "Azamara", "industry": "Cruises", "website": "https://www.azamara.com", "budget_range": (6000, 18000)},
    {"name": "ZipRecruiter", "industry": "HR & Recruiting", "website": "https://www.ziprecruiter.com", "budget_range": (6000, 18000)},
    {"name": "Lever", "industry": "HR & Recruiting", "website": "https://www.lever.co", "budget_range": (4500, 13500)},
    {"name": "Greenhouse", "industry": "HR & Recruiting", "website": "https://www.greenhouse.com", "budget_range": (5000, 15000)},
    {"name": "Gusto", "industry": "HR & Recruiting", "website": "https://gusto.com", "budget_range": (5000, 15000)},
    {"name": "Rippling", "industry": "HR & Recruiting", "website": "https://www.rippling.com", "budget_range": (5500, 16500)},
    {"name": "Lattice", "industry": "HR & Recruiting", "website": "https://lattice.com", "budget_range": (4500, 13500)},
    {"name": "Deel", "industry": "HR & Recruiting", "website": "https://www.deel.com", "budget_range": (5000, 15000)},
    {"name": "Remote.com", "industry": "HR & Recruiting", "website": "https://remote.com", "budget_range": (4500, 13500)},
    {"name": "Sage", "industry": "Accounting & Tax", "website": "https://www.sage.com", "budget_range": (6000, 18000)},
    {"name": "Bench", "industry": "Accounting & Tax", "website": "https://bench.co", "budget_range": (4000, 12000)},
    {"name": "Pilot", "industry": "Accounting & Tax", "website": "https://pilot.com", "budget_range": (4500, 13500)},
    {"name": "TaxJar", "industry": "Accounting & Tax", "website": "https://www.taxjar.com", "budget_range": (4000, 12000)},
    {"name": "TaxAct", "industry": "Accounting & Tax", "website": "https://www.taxact.com", "budget_range": (5000, 15000)},
    {"name": "FreeTaxUSA", "industry": "Accounting & Tax", "website": "https://www.freetaxusa.com", "budget_range": (3500, 10500)},
    {"name": "Zoho Books", "industry": "Accounting & Tax", "website": "https://www.zoho.com/books", "budget_range": (4000, 12000)},
    {"name": "NetSuite", "industry": "Accounting & Tax", "website": "https://www.netsuite.com", "budget_range": (8000, 24000)},
    {"name": "Clio", "industry": "Legal Services", "website": "https://www.clio.com", "budget_range": (4500, 13500)},
    {"name": "DocuSign Legal", "industry": "Legal Services", "website": "https://www.docusign.com", "budget_range": (5500, 16500)},
    {"name": "Nolo", "industry": "Legal Services", "website": "https://www.nolo.com", "budget_range": (3500, 10500)},
    {"name": "US Legal Forms", "industry": "Legal Services", "website": "https://www.uslegalforms.com", "budget_range": (3500, 10500)},
    {"name": "LegalShield", "industry": "Legal Services", "website": "https://www.legalshield.com", "budget_range": (4000, 12000)},
    {"name": "DoNotPay", "industry": "Legal Services", "website": "https://donotpay.com", "budget_range": (3500, 10500)},
    {"name": "Justia", "industry": "Legal Services", "website": "https://www.justia.com", "budget_range": (3500, 10500)},
    {"name": "UpCounsel", "industry": "Legal Services", "website": "https://www.upcounsel.com", "budget_range": (3500, 10500)},
    {"name": "Threads", "industry": "Social Media", "website": "https://www.threads.net", "budget_range": (8000, 24000)},
    {"name": "LinkedIn Social", "industry": "Social Media", "website": "https://www.linkedin.com", "budget_range": (9000, 27000)},
    {"name": "BeReal", "industry": "Social Media", "website": "https://bereal.com", "budget_range": (5000, 15000)},
    {"name": "Mastodon", "industry": "Social Media", "website": "https://joinmastodon.org", "budget_range": (3000, 9000)},
    {"name": "Bluesky", "industry": "Social Media", "website": "https://bsky.app", "budget_range": (4000, 12000)},
    {"name": "Lemon8", "industry": "Social Media", "website": "https://www.lemon8-app.com", "budget_range": (4000, 12000)},
    {"name": "Nextdoor", "industry": "Social Media", "website": "https://www.nextdoor.com", "budget_range": (5000, 15000)},
    {"name": "Clubhouse", "industry": "Social Media", "website": "https://www.clubhouse.com", "budget_range": (3500, 10500)},
    {"name": "Stan Store", "industry": "Creator Economy", "website": "https://www.stan.store", "budget_range": (3000, 9000)},
    {"name": "Beehiiv", "industry": "Creator Economy", "website": "https://www.beehiiv.com", "budget_range": (3500, 10500)},
    {"name": "ConvertKit", "industry": "Creator Economy", "website": "https://convertkit.com", "budget_range": (4000, 12000)},
    {"name": "Fourthwall", "industry": "Creator Economy", "website": "https://fourthwall.com", "budget_range": (3000, 9000)},
    {"name": "Podia", "industry": "Creator Economy", "website": "https://www.podia.com", "budget_range": (3500, 10500)},
    {"name": "Circle", "industry": "Creator Economy", "website": "https://circle.so", "budget_range": (3500, 10500)},
    {"name": "Linktree", "industry": "Creator Economy", "website": "https://linktr.ee", "budget_range": (3500, 10500)},
    {"name": "Spring", "industry": "Creator Economy", "website": "https://www.spri.ng", "budget_range": (3000, 9000)},
    {"name": "UPPAbaby", "industry": "Baby & Parenting", "website": "https://uppababy.com", "budget_range": (5000, 15000)},
    {"name": "Snoo", "industry": "Baby & Parenting", "website": "https://www.happiestbaby.com", "budget_range": (5000, 15000)},
    {"name": "Babylist", "industry": "Baby & Parenting", "website": "https://www.babylist.com", "budget_range": (4500, 13500)},
    {"name": "Owlet", "industry": "Baby & Parenting", "website": "https://www.owletcare.com", "budget_range": (4000, 12000)},
    {"name": "Lovevery", "industry": "Baby & Parenting", "website": "https://lovevery.com", "budget_range": (4500, 13500)},
    {"name": "Tubby Todd", "industry": "Baby & Parenting", "website": "https://tubbytodd.com", "budget_range": (3500, 10500)},
    {"name": "Newton Baby", "industry": "Baby & Parenting", "website": "https://www.newtonbaby.com", "budget_range": (3500, 10500)},
    {"name": "Graco", "industry": "Baby & Parenting", "website": "https://www.gracobaby.com", "budget_range": (5000, 15000)},
    {"name": "Hasbro", "industry": "Kids & Family Entertainment", "website": "https://www.hasbro.com", "budget_range": (7000, 21000)},
    {"name": "VTech", "industry": "Kids & Family Entertainment", "website": "https://www.vtechkids.com", "budget_range": (5000, 15000)},
    {"name": "Melissa & Doug", "industry": "Kids & Family Entertainment", "website": "https://www.melissaanddoug.com", "budget_range": (4500, 13500)},
    {"name": "Fisher-Price", "industry": "Kids & Family Entertainment", "website": "https://www.fisher-price.com", "budget_range": (6000, 18000)},
    {"name": "Bluey (BBC)", "industry": "Kids & Family Entertainment", "website": "https://www.bluey.tv", "budget_range": (5000, 15000)},
    {"name": "Hot Wheels", "industry": "Kids & Family Entertainment", "website": "https://www.hotwheels.com", "budget_range": (5000, 15000)},
    {"name": "National Geographic Kids", "industry": "Kids & Family Entertainment", "website": "https://kids.nationalgeographic.com", "budget_range": (4000, 12000)},
    {"name": "KiwiCo", "industry": "Kids & Family Entertainment", "website": "https://www.kiwico.com", "budget_range": (4500, 13500)},
    {"name": "Porch", "industry": "Home Services", "website": "https://porch.com", "budget_range": (5000, 15000)},
    {"name": "Yelp Home", "industry": "Home Services", "website": "https://www.yelp.com", "budget_range": (5500, 16500)},
    {"name": "Houzz", "industry": "Home Services", "website": "https://www.houzz.com", "budget_range": (5500, 16500)},
    {"name": "Networx", "industry": "Home Services", "website": "https://www.networx.com", "budget_range": (4000, 12000)},
    {"name": "Pro Referral", "industry": "Home Services", "website": "https://www.proreferral.com", "budget_range": (3500, 10500)},
    {"name": "Bark", "industry": "Home Services", "website": "https://www.bark.com", "budget_range": (3500, 10500)},
    {"name": "Fixd Repair", "industry": "Home Services", "website": "https://www.fixdrepair.com", "budget_range": (3500, 10500)},
    {"name": "Hometree", "industry": "Home Services", "website": "https://www.hometree.co.uk", "budget_range": (4000, 12000)},
    {"name": "SC Johnson", "industry": "Cleaning & Household", "website": "https://www.scjohnson.com", "budget_range": (8000, 24000)},
    {"name": "Arm & Hammer", "industry": "Cleaning & Household", "website": "https://www.armandhammer.com", "budget_range": (5500, 16500)},
    {"name": "Blueland", "industry": "Cleaning & Household", "website": "https://www.blueland.com", "budget_range": (4000, 12000)},
    {"name": "Dropps", "industry": "Cleaning & Household", "website": "https://www.dropps.com", "budget_range": (3500, 10500)},
    {"name": "Grove Collaborative", "industry": "Cleaning & Household", "website": "https://www.grove.co", "budget_range": (4500, 13500)},
    {"name": "Tide", "industry": "Cleaning & Household", "website": "https://tide.com", "budget_range": (7000, 21000)},
    {"name": "OxiClean", "industry": "Cleaning & Household", "website": "https://www.oxiclean.com", "budget_range": (5000, 15000)},
    {"name": "Swiffer", "industry": "Cleaning & Household", "website": "https://swiffer.com", "budget_range": (5500, 16500)},
    {"name": "Vivint Solar", "industry": "Solar & Renewable Energy", "website": "https://www.vivintsolar.com", "budget_range": (6000, 18000)},
    {"name": "Palmetto", "industry": "Solar & Renewable Energy", "website": "https://palmetto.com", "budget_range": (5000, 15000)},
    {"name": "SolarEdge", "industry": "Solar & Renewable Energy", "website": "https://www.solaredge.com", "budget_range": (5500, 16500)},
    {"name": "Freedom Solar", "industry": "Solar & Renewable Energy", "website": "https://freedomsolarpower.com", "budget_range": (4500, 13500)},
    {"name": "Momentum Solar", "industry": "Solar & Renewable Energy", "website": "https://momentumsolar.com", "budget_range": (5000, 15000)},
    {"name": "Trinity Solar", "industry": "Solar & Renewable Energy", "website": "https://www.trinitysolar.com", "budget_range": (4500, 13500)},
    {"name": "Blue Raven Solar", "industry": "Solar & Renewable Energy", "website": "https://blueravensolar.com", "budget_range": (4500, 13500)},
    {"name": "Generac", "industry": "Solar & Renewable Energy", "website": "https://www.generac.com", "budget_range": (6000, 18000)},
    {"name": "Bitwarden", "industry": "Identity & Privacy", "website": "https://bitwarden.com", "budget_range": (4000, 12000)},
    {"name": "ProtonVPN", "industry": "Identity & Privacy", "website": "https://protonvpn.com", "budget_range": (4500, 13500)},
    {"name": "Dashlane", "industry": "Identity & Privacy", "website": "https://www.dashlane.com", "budget_range": (4500, 13500)},
    {"name": "Aura", "industry": "Identity & Privacy", "website": "https://www.aura.com", "budget_range": (5500, 16500)},
    {"name": "IDShield", "industry": "Identity & Privacy", "website": "https://www.idshield.com", "budget_range": (4000, 12000)},
    {"name": "Privacy.com", "industry": "Identity & Privacy", "website": "https://privacy.com", "budget_range": (3500, 10500)},
    {"name": "Keeper Security", "industry": "Identity & Privacy", "website": "https://www.keepersecurity.com", "budget_range": (4500, 13500)},
    {"name": "Private Internet Access", "industry": "Identity & Privacy", "website": "https://www.privateinternetaccess.com", "budget_range": (4000, 12000)},
    {"name": "David's Bridal", "industry": "Weddings", "website": "https://www.davidsbridal.com", "budget_range": (6000, 18000)},
    {"name": "Shutterfly", "industry": "Weddings", "website": "https://www.shutterfly.com", "budget_range": (5000, 15000)},
    {"name": "Vistaprint Weddings", "industry": "Weddings", "website": "https://www.vistaprint.com/wedding", "budget_range": (4500, 13500)},
    {"name": "Paperless Post", "industry": "Weddings", "website": "https://www.paperlesspost.com", "budget_range": (4000, 12000)},
    {"name": "Azazie", "industry": "Weddings", "website": "https://www.azazie.com", "budget_range": (5000, 15000)},
    {"name": "BHLDN", "industry": "Weddings", "website": "https://www.bhldn.com", "budget_range": (5000, 15000)},
    {"name": "Honeyfund", "industry": "Weddings", "website": "https://www.honeyfund.com", "budget_range": (3000, 9000)},
    {"name": "AllSeated", "industry": "Weddings", "website": "https://www.allseated.com", "budget_range": (3500, 10500)},
    {"name": "Maersk", "industry": "Logistics & Shipping", "website": "https://www.maersk.com", "budget_range": (9000, 27000)},
    {"name": "XPO Logistics", "industry": "Logistics & Shipping", "website": "https://www.xpo.com", "budget_range": (7000, 21000)},
    {"name": "Shippo", "industry": "Logistics & Shipping", "website": "https://goshippo.com", "budget_range": (4500, 13500)},
    {"name": "EasyShip", "industry": "Logistics & Shipping", "website": "https://www.easyship.com", "budget_range": (4000, 12000)},
    {"name": "Pitney Bowes", "industry": "Logistics & Shipping", "website": "https://www.pitneybowes.com", "budget_range": (6000, 18000)},
    {"name": "Stamps.com", "industry": "Logistics & Shipping", "website": "https://www.stamps.com", "budget_range": (4500, 13500)},
    {"name": "ShipStation", "industry": "Logistics & Shipping", "website": "https://www.shipstation.com", "budget_range": (4500, 13500)},
    {"name": "Sendle", "industry": "Logistics & Shipping", "website": "https://www.sendle.com", "budget_range": (3500, 10500)},
    {"name": "Reformation", "industry": "Sustainability", "website": "https://www.thereformation.com", "budget_range": (5000, 15000)},
    {"name": "Girlfriend Collective", "industry": "Sustainability", "website": "https://www.girlfriend.com", "budget_range": (4000, 12000)},
    {"name": "Who Gives A Crap", "industry": "Sustainability", "website": "https://www.whogivesacrap.org", "budget_range": (4000, 12000)},
    {"name": "Pela Case", "industry": "Sustainability", "website": "https://www.pelacase.com", "budget_range": (3500, 10500)},
    {"name": "Bite Toothpaste", "industry": "Sustainability", "website": "https://www.bitetoothpastebits.com", "budget_range": (3000, 9000)},
    {"name": "Stasher", "industry": "Sustainability", "website": "https://www.stasherbag.com", "budget_range": (3500, 10500)},
    {"name": "Pangaia", "industry": "Sustainability", "website": "https://thepangaia.com", "budget_range": (4500, 13500)},
    {"name": "Cotopaxi", "industry": "Sustainability", "website": "https://www.cotopaxi.com", "budget_range": (4500, 13500)},
    {"name": "Bandcamp", "industry": "Music Streaming", "website": "https://bandcamp.com", "budget_range": (3500, 10500)},
    {"name": "Universe", "industry": "Event Tickets", "website": "https://www.universe.com", "budget_range": (4000, 12000)},
    {"name": "Taylor Guitars", "industry": "Musical Instruments", "website": "https://www.taylorguitars.com", "budget_range": (5000, 15000)},
    {"name": "Cinépolis", "industry": "Movie Theaters", "website": "https://www.cinepolis.com", "budget_range": (4500, 13500)},
    {"name": "Saxo Bank", "industry": "Investment App", "website": "https://www.home.saxo", "budget_range": (6000, 18000)},
    {"name": "Trezor", "industry": "Cryptocurrency", "website": "https://trezor.io", "budget_range": (4500, 13500)},
    {"name": "Quicken", "industry": "Financial Planning", "website": "https://www.quicken.com", "budget_range": (4500, 13500)},
    {"name": "Alto Insurance", "industry": "Insurance", "website": "https://www.altoinsurance.com", "budget_range": (4000, 12000)},
    {"name": "Sling TV", "industry": "Sports Streaming", "website": "https://www.sling.com", "budget_range": (5500, 16500)},
    {"name": "Arc'teryx", "industry": "Sports Apparel", "website": "https://arcteryx.com", "budget_range": (6000, 18000)},
    {"name": "HEAD", "industry": "Sports Equipment", "website": "https://www.head.com", "budget_range": (5000, 15000)},
    {"name": "Rally House", "industry": "Sports Merchandise", "website": "https://www.rallyhouse.com", "budget_range": (4000, 12000)},
    {"name": "Nothing Phone", "industry": "Consumer Electronics", "website": "https://nothing.tech", "budget_range": (5000, 15000)},
    {"name": "Render", "industry": "Software & Cloud", "website": "https://render.com", "budget_range": (4500, 13500)},
    {"name": "Scout Motors", "industry": "Electric Vehicles", "website": "https://www.scoutmotors.com", "budget_range": (7000, 21000)},
    {"name": "NZXT", "industry": "Computer Hardware", "website": "https://nzxt.com", "budget_range": (4500, 13500)},
    {"name": "Republic Wireless", "industry": "Telecom", "website": "https://republicwireless.com", "budget_range": (3500, 10500)},
    {"name": "Rest of World", "industry": "News Media", "website": "https://restofworld.org", "budget_range": (3500, 10500)},
    {"name": "Audm", "industry": "Audiobooks", "website": "https://www.audm.com", "budget_range": (3500, 10500)},
    {"name": "Sundae", "industry": "Real Estate", "website": "https://sundae.com", "budget_range": (4500, 13500)},
    {"name": "Spot & Tango", "industry": "Pet Products", "website": "https://www.spotandtango.com", "budget_range": (4000, 12000)},
    {"name": "Talkiatry", "industry": "Healthcare", "website": "https://www.talkiatry.com", "budget_range": (4500, 13500)},
    {"name": "CB2", "industry": "Home & Garden", "website": "https://www.cb2.com", "budget_range": (5000, 15000)},
]

# ─── Campaign Name Templates by Industry ─────────────────────────────────────
# Each industry has multiple campaign name templates used for naming campaigns.
# Actual creative content (headlines, descriptions, CTAs) comes from the creative bank.

CAMPAIGN_TEMPLATES = {
    "Fashion Retail": ["Spring Collection", "New Arrivals", "Seasonal Sale", "Fashion Week", "Summer Styles", "Winter Clearance", "Holiday Collection", "Back to School"],
    "Beauty": ["Beauty Sets", "Skincare Launch", "Beauty Event", "New Launches", "Glow Up Sale", "Holiday Glam", "Clean Beauty", "Summer Glow"],
    "Athletic Wear": ["Performance Collection", "Yoga Essentials", "Running Gear", "Activewear Trends", "Training Series", "Outdoor Collection", "Recovery Wear", "Studio Line"],
    "Fashion Accessories": ["New Frames", "Spring Eyewear", "Limited Edition", "Holiday Gift Guide", "Signature Collection", "Summer Styles", "Classic Revival"],
    "Luxury Goods": ["Maison Collection", "Heritage Line", "Resort Collection", "Artisan Series", "Limited Edition", "Holiday Luxury", "Signature Pieces"],
    "Music Streaming": ["Premium Trial", "Discover Weekly", "Concert Streams", "Podcast Launch", "Year in Review", "Family Plan", "Student Deal"],
    "Event Tickets": ["Concert Presale", "Live Events", "Festival Passes", "Sports Tickets", "VIP Access", "Early Bird Deals", "Summer Concerts"],
    "Musical Instruments": ["Guitar Sale", "Pro Series", "Beginner Bundles", "Limited Models", "Studio Gear", "Holiday Deals", "Artist Series"],
    "Streaming": ["Original Series", "Binge Content", "Family Plan", "Free Trial", "New Releases", "Award Winners", "Exclusive Premiere"],
    "Movie Theaters": ["Opening Weekend", "Blockbuster Season", "Premium Experience", "Movie Club", "IMAX Events", "Date Night Deal", "Family Matinee"],
    "Gaming": ["New Release", "Season Pass", "Esports League", "Free Play Weekend", "Expansion Launch", "Holiday Sale", "Beta Access", "Championship Series"],
    "Financial Services": ["Smart Investing", "Retirement Plan", "Zero Commission", "Financial Freedom", "Wealth Building", "Tax Season", "Market Insights"],
    "Investment App": ["Start Investing", "Portfolio Builder", "Fractional Shares", "Invest Education", "Crypto Trading", "Automated Investing", "Goal Tracking"],
    "Cryptocurrency": ["Crypto Simple", "Secure Trading", "Earn Rewards", "Market Tools", "DeFi Launch", "Staking Promo", "New Coins"],
    "Financial Planning": ["Budget Tracker", "Credit Monitor", "Financial Goals", "Debt Payoff", "Savings Plan", "Tax Optimizer", "Net Worth Tracker"],
    "Insurance": ["Save on Insurance", "Bundle Deal", "Free Quote", "Claims Simplified", "Coverage Review", "New Customer Deal", "Family Protection"],
    "Sports Streaming": ["Live Season", "Multi-Device", "Game Replays", "Playoff Coverage", "All Access Pass", "Sunday Special", "Championship Live"],
    "Sports Apparel": ["Athlete Line", "Performance Tech", "Team Collection", "Training Essentials", "Game Day Gear", "Pro Endorsed", "Limited Drop"],
    "Sports Equipment": ["Pro Grade Gear", "Equipment Sale", "Youth Program", "Championship Line", "Training Tools", "Season Starter", "Expert Pick"],
    "Sports Merchandise": ["Team Gear", "Fan Favorites", "Limited Jerseys", "Game Day", "Championship Merch", "Draft Collection", "Vintage Series"],
    "Sports Retail": ["Pro Shop Deals", "Expert Picks", "Gear Up Season", "Online Exclusive", "Clearance Event", "New Arrivals", "Bundle Deals"],
    "Consumer Electronics": ["Latest Innovation", "Trade-In Deal", "Holiday Tech", "Pre-Order Now", "Launch Event", "Ecosystem Bundle", "Upgrade Program"],
    "Software & Cloud": ["Cloud Solutions", "Productivity Suite", "Business Tools", "Enterprise Plan", "Migration Special", "Partner Program", "Security Update"],
    "Software": ["Creative Cloud", "Design Tools", "Pro Software", "Student Discount", "New Features", "Team License", "Plugin Launch"],
    "Electric Vehicles": ["Test Drive", "Zero Emissions", "Advanced Tech", "EV Credits", "Charging Network", "Model Launch", "Sustainability Drive"],
    "Computer Hardware": ["Laptop Launch", "Gaming Setup", "Business PCs", "Back to School", "Custom Build", "Workstation Pro", "Upgrade Sale"],
    "Telecom": ["Unlimited Plan", "5G Launch", "Family Bundle", "Switch & Save", "Holiday Promo", "Trade-In Deal", "Coverage Expansion"],
    "News Media": ["Digital Access", "Quality Journalism", "Unlimited Reading", "Breaking Coverage", "Opinion Access", "Newsletter Launch", "Archive Access"],
    "Audiobooks": ["Unlimited Listening", "Bestsellers", "Podcast Originals", "Free Trial", "Annual Deal", "Kids Collection", "New Releases"],
    "Real Estate": ["Home Search", "Market Report", "Instant Offer", "Virtual Tours", "New Listings", "Neighborhood Guide", "Mortgage Rates"],
    "Pet Products": ["Pet Essentials", "Subscription Box", "Vet Approved", "New Arrivals", "Holiday Treats", "Breed Specific", "Wellness Line"],
    "Home & Garden": ["Home Refresh", "Spring Sale", "Design Services", "Outdoor Living", "Kitchen Update", "Holiday Decor", "Storage Solutions"],
    "EdTech": ["Learn New Skills", "Certificate Program", "Free Course", "Career Boost", "Language Learning", "Pro Certification", "Summer Learning"],
    "Food Delivery": ["Free Delivery", "New Restaurants", "Meal Plans", "Grocery Delivery", "Party Catering", "Weekly Special", "First Order Deal"],
    "Restaurants": ["New Menu", "Loyalty Rewards", "Mobile Order", "Catering Special", "Seasonal Menu", "Happy Hour", "Family Meal Deal"],
    "Craft Beer & Spirits": ["Limited Release", "Seasonal Brew", "Tasting Event", "New Distillery", "Holiday Collection", "Craft Series", "Mixology Kit"],
    "Energy Drinks": ["Extreme Challenge", "New Flavor Launch", "Athlete Sponsorship", "Festival Promo", "Zero Sugar Line", "Limited Edition", "Summer Energy"],
    "Coffee & Tea": ["Morning Ritual", "New Roast", "Subscription Launch", "Seasonal Blend", "Holiday Gift Set", "Single Origin", "Brewing Guide"],
    # Health & Wellness
    "Fitness & Wellness": ["Fitness Challenge", "Home Workout", "Mindfulness App", "New Year Goals", "Summer Body", "Recovery Tools", "Community Class"],
    "Healthcare": ["Online Consultation", "Prescription Delivery", "Health Plan", "Wellness Check", "Telehealth Launch", "Savings Program", "Annual Checkup"],
    "Pharmaceuticals": ["New Treatment", "Clinical Results", "Patient Support", "Awareness Campaign", "Research Update", "Wellness Program", "Healthcare Partner"],
    "Supplements & Nutrition": ["New Formula", "Protein Launch", "Vitamin Pack", "Subscription Deal", "Athlete Endorsed", "Clean Label", "Bundle Sale"],
    # Travel & Hospitality
    "Travel": ["Dream Vacation", "Last Minute Deals", "Summer Getaway", "Loyalty Program", "Adventure Travel", "Weekend Escape", "Luxury Stay"],
    "Airlines": ["Flight Deals", "Loyalty Miles", "Business Class", "New Routes", "Holiday Travel", "Upgrade Offer", "Bundle & Save"],
    "Hotels & Resorts": ["Summer Getaway", "Loyalty Program", "Suite Upgrade", "Resort Package", "Weekend Deal", "Business Travel", "Honeymoon Special"],
    "Cruises": ["Maiden Voyage", "Caribbean Special", "Alaska Season", "Family Cruise", "All-Inclusive Deal", "Mediterranean Tour", "Last Minute Sailing"],
    "Automotive": ["New Model Launch", "Test Drive Event", "Lease Special", "Certified Pre-Owned", "Service Special", "Trade-In Deal", "Safety Features"],
    "B2B SaaS": ["Platform Launch", "Enterprise Trial", "Integration Suite", "Scaling Tools", "Developer API", "Team Collaboration", "Analytics Dashboard"],
    "Cybersecurity": ["Threat Protection", "Zero Trust Launch", "Security Audit", "Compliance Suite", "Incident Response", "Cloud Security", "Identity Protection"],
    "HR & Recruiting": ["Talent Platform", "Job Fair", "Enterprise HR", "Hiring Sprint", "Culture Report", "Workforce Analytics", "Recruiter Suite"],
    "Accounting & Tax": ["Tax Season", "New Features", "Small Business", "Year-End Prep", "Quarterly Filing", "Integration Launch", "Free Trial"],
    "Legal Services": ["Document Builder", "Business Formation", "Free Consultation", "Legal Plan", "Trademark Filing", "Estate Planning", "Small Claims"],
    "Culture": ["Art Exhibition", "Cultural Festival", "Heritage Month", "Gallery Opening", "Museum Event", "Documentary Premiere", "Cultural Exchange"],
    "Education": ["Fall Enrollment", "Summer Program", "Scholarship Drive", "Campus Tour", "New Courses", "Faculty Spotlight", "Alumni Event"],
    "Non-Profit": ["Annual Campaign", "Giving Tuesday", "Volunteer Drive", "Awareness Month", "Fundraiser Gala", "Community Impact", "Year-End Appeal"],
    "Government": ["Public Service", "Census Drive", "Safety Campaign", "Health Advisory", "Tax Season", "Community Program", "Emergency Preparedness"],
    "Politics": ["Election Coverage", "Policy Analysis", "Debate Watch", "Voter Guide", "Legislative Tracker", "Primary Season", "Town Hall"],
    "Social Media": ["Feature Launch", "Creator Fund", "Safety Update", "Community Event", "Trending Campaign", "Ad Platform", "New Tools"],
    "Creator Economy": ["Platform Launch", "Creator Spotlight", "Monetization Tools", "Course Builder", "Community Launch", "Payout Milestone", "Creator Summit"],
    "Technology": ["Product Launch", "Innovation Summit", "Tech Preview", "Developer Conference", "Benchmark Release", "Partner Program", "Next-Gen Platform"],
    "AI": ["Model Launch", "API Release", "Research Paper", "Enterprise AI", "AI Safety", "Developer Tools", "Partnership Announcement"],
    "FinTech": ["Product Launch", "Feature Release", "Partnership Deal", "Expansion Market", "Security Update", "User Milestone", "Regulatory Approval"],
    "HealthTech": ["Platform Launch", "Telehealth Expansion", "Provider Network", "Wellness Program", "Patient Portal", "Clinical Trial", "Partnership"],
    "E-commerce": ["Mega Sale", "Flash Deals", "Seller Spotlight", "Holiday Shopping", "Prime Day", "Free Shipping Week", "New Marketplace"],
    "Personal Banking": ["New Account", "Savings Rate", "Credit Card Launch", "Mobile Banking", "Rewards Program", "Financial Literacy", "Home Loan"],
    "Baby & Parenting": ["New Baby Essentials", "Registry Launch", "Safety Recall", "Milestone Tracker", "Nursery Collection", "Back to School", "Holiday Gift Guide"],
    "Kids & Family Entertainment": ["Summer Fun", "Holiday Special", "New Show Launch", "Birthday Party", "Educational Series", "Character Collection", "Family Weekend"],
    "Home Services": ["Spring Cleaning", "Emergency Repair", "Renovation Season", "Free Estimate", "Referral Bonus", "New Service Area", "Holiday Prep"],
    "Cleaning & Household": ["New Product Launch", "Spring Clean", "Eco-Friendly Line", "Bundle Deal", "Subscription Plan", "Seasonal Scent", "Back to School"],
    "Solar & Renewable Energy": ["Free Assessment", "Federal Credits", "Battery Launch", "Community Solar", "Rate Lock", "Spring Installation", "Energy Independence"],
    "Identity & Privacy": ["Security Suite", "Privacy Check", "Holiday Sale", "Family Plan", "Business VPN", "Data Breach Alert", "Annual Deal"],
    "Weddings": ["Planning Season", "Registry Launch", "Vendor Showcase", "Spring Collection", "Budget Tools", "Honeymoon Guide", "Save the Date"],
    "Logistics & Shipping": ["Peak Season", "Small Business", "Global Expansion", "Rate Comparison", "Holiday Shipping", "Same Day Launch", "Green Shipping"],
    "Sustainability": ["Earth Day", "New Launch", "Impact Report", "B-Corp Campaign", "Recycled Collection", "Carbon Neutral", "Holiday Gifts"],
}



ENTITY_BANKS = {
    "Fashion Retail": {
        "BRAND": ["Zara", "H&M", "Gap", "Uniqlo", "ASOS", "Nordstrom", "J.Crew", "Mango", "Shein", "Revolve"],
        "PRODUCT": ["dresses", "jeans", "jackets", "sneakers", "handbags", "t-shirts", "blazers", "skirts", "boots", "sweaters"],
        "ORGANIZATION": ["Fashion Week", "Vogue", "CFDA", "WWD", "Sustainable Apparel Coalition"],
        "PERSON": ["Anna Wintour", "Virgil Abloh", "Tommy Hilfiger", "Ralph Lauren", "Stella McCartney"],
    },
    "Beauty": {
        "BRAND": ["Sephora", "Glossier", "Ulta", "Fenty Beauty", "MAC", "Clinique", "Tatcha", "Charlotte Tilbury"],
        "PRODUCT": ["moisturizer", "serum", "foundation", "lipstick", "mascara", "cleanser", "sunscreen", "primer"],
        "ORGANIZATION": ["Allure", "Beauty Counter", "FDA", "EWG", "Leaping Bunny"],
        "PERSON": ["Rihanna", "Huda Kattan", "Charlotte Tilbury", "Bobbi Brown", "Pat McGrath"],
    },
    "Athletic Wear": {
        "BRAND": ["Lululemon", "Nike", "Gymshark", "Athleta", "Alo Yoga", "Vuori", "Fabletics"],
        "PRODUCT": ["leggings", "sports bras", "running shoes", "yoga mats", "training shorts", "compression tights"],
        "ORGANIZATION": ["CrossFit", "Yoga Alliance", "ACE Fitness", "NASM"],
        "PERSON": ["Simone Biles", "Serena Williams", "LeBron James", "Naomi Osaka"],
    },
    "Luxury Goods": {
        "BRAND": ["Louis Vuitton", "Gucci", "Prada", "Burberry", "Hermès", "Cartier", "Chanel", "Dior"],
        "PRODUCT": ["handbag", "watch", "jewelry", "perfume", "silk scarf", "leather goods", "sunglasses"],
        "ORGANIZATION": ["LVMH", "Kering", "Richemont", "Sotheby's", "Christie's"],
        "PERSON": ["Bernard Arnault", "Alessandro Michele", "Miuccia Prada", "Karl Lagerfeld"],
    },
    "Music Streaming": {
        "BRAND": ["Spotify", "Apple Music", "Tidal", "Amazon Music", "Deezer", "YouTube Music"],
        "PRODUCT": ["playlists", "podcasts", "lossless audio", "spatial audio", "radio stations"],
        "ORGANIZATION": ["Grammy Awards", "Billboard", "RIAA", "Spotify for Artists"],
        "PERSON": ["Taylor Swift", "Drake", "Beyoncé", "Bad Bunny", "The Weeknd"],
    },
    "Streaming": {
        "BRAND": ["Netflix", "Disney+", "HBO Max", "Hulu", "Peacock", "Apple TV+", "Paramount+"],
        "PRODUCT": ["original series", "documentaries", "movies", "live TV", "kids content"],
        "ORGANIZATION": ["Academy Awards", "Emmy Awards", "SAG-AFTRA", "Sundance"],
        "PERSON": ["Martin Scorsese", "Ava DuVernay", "Ryan Murphy", "Shonda Rhimes"],
    },
    "Gaming": {
        "BRAND": ["PlayStation", "Xbox", "Nintendo", "Steam", "Epic Games", "EA", "Activision"],
        "PRODUCT": ["console", "controller", "headset", "game pass", "VR headset", "gaming mouse"],
        "ORGANIZATION": ["ESL Gaming", "Riot Games", "Game Awards", "PAX", "E3"],
        "PERSON": ["Ninja", "Pokimane", "Shroud", "PewDiePie", "Hideo Kojima"],
    },
    "Financial Services": {
        "BRAND": ["Fidelity", "Schwab", "Vanguard", "Goldman Sachs", "JP Morgan", "Morgan Stanley"],
        "PRODUCT": ["mutual funds", "ETFs", "bonds", "IRA", "401k", "brokerage account"],
        "ORGANIZATION": ["SEC", "FINRA", "NYSE", "NASDAQ", "Federal Reserve"],
        "PERSON": ["Warren Buffett", "Ray Dalio", "Jamie Dimon", "Janet Yellen"],
    },
    "Cryptocurrency": {
        "BRAND": ["Coinbase", "Kraken", "Gemini", "Binance", "Crypto.com", "MetaMask"],
        "PRODUCT": ["Bitcoin", "Ethereum", "stablecoins", "NFTs", "DeFi protocols", "staking"],
        "ORGANIZATION": ["CoinDesk", "Chainalysis", "Ethereum Foundation", "Bitcoin Foundation"],
        "PERSON": ["Vitalik Buterin", "Brian Armstrong", "Changpeng Zhao", "Sam Bankman-Fried"],
    },
    "Consumer Electronics": {
        "BRAND": ["Apple", "Samsung", "Google", "Sony", "Bose", "LG", "OnePlus"],
        "PRODUCT": ["smartphone", "tablet", "laptop", "earbuds", "smartwatch", "speaker"],
        "ORGANIZATION": ["CES", "Apple Park", "Consumer Reports", "CNET", "The Verge"],
        "PERSON": ["Tim Cook", "Sundar Pichai", "Jensen Huang", "Lisa Su"],
    },
    "Software & Cloud": {
        "BRAND": ["Microsoft", "Salesforce", "AWS", "Google Cloud", "Oracle", "SAP"],
        "PRODUCT": ["CRM", "ERP", "cloud storage", "API gateway", "serverless functions"],
        "ORGANIZATION": ["Gartner", "Forrester", "IDC", "Cloud Native Computing Foundation"],
        "PERSON": ["Satya Nadella", "Marc Benioff", "Andy Jassy", "Thomas Kurian"],
    },
    "Electric Vehicles": {
        "BRAND": ["Tesla", "Rivian", "Lucid", "Polestar", "BMW i", "Mercedes EQ"],
        "PRODUCT": ["electric sedan", "electric SUV", "home charger", "supercharger", "battery pack"],
        "ORGANIZATION": ["EPA", "NHTSA", "ChargePoint", "Electrify America"],
        "PERSON": ["Elon Musk", "RJ Scaringe", "Mary Barra", "Carlos Tavares"],
    },
    "Real Estate": {
        "BRAND": ["Zillow", "Redfin", "Realtor.com", "Compass", "Opendoor", "Trulia"],
        "PRODUCT": ["homes", "condos", "townhouses", "apartments", "commercial property"],
        "ORGANIZATION": ["NAR", "MLS", "Fannie Mae", "Freddie Mac", "HUD"],
        "PERSON": ["Barbara Corcoran", "Ryan Serhant", "Fredrik Eklund"],
    },
    "Travel": {
        "BRAND": ["Airbnb", "Booking.com", "Expedia", "Vrbo", "Tripadvisor", "Kayak"],
        "PRODUCT": ["vacation rentals", "hotels", "flights", "car rentals", "cruises", "travel insurance"],
        "ORGANIZATION": ["IATA", "World Tourism Organization", "AAA", "Lonely Planet"],
        "PERSON": ["Anthony Bourdain", "Rick Steves", "Samantha Brown"],
    },
    "EdTech": {
        "BRAND": ["Coursera", "Udemy", "Duolingo", "Khan Academy", "MasterClass", "Codecademy"],
        "PRODUCT": ["online courses", "certificates", "bootcamps", "language lessons", "tutorials"],
        "ORGANIZATION": ["MIT OpenCourseWare", "Stanford Online", "edX", "Google Career Certificates"],
        "PERSON": ["Sal Khan", "Andrew Ng", "Sebastian Thrun"],
    },
    "Food Delivery": {
        "BRAND": ["DoorDash", "Uber Eats", "Grubhub", "Instacart", "HelloFresh", "Blue Apron"],
        "PRODUCT": ["meal kits", "grocery delivery", "restaurant delivery", "catering", "snack boxes"],
        "ORGANIZATION": ["National Restaurant Association", "Food Network", "James Beard Foundation"],
        "PERSON": ["Gordon Ramsay", "Guy Fieri", "Ina Garten"],
    },
    "Fitness & Wellness": {
        "BRAND": ["Peloton", "ClassPass", "Calm", "Headspace", "Fitbit", "Whoop"],
        "PRODUCT": ["spin bike", "meditation app", "fitness tracker", "yoga classes", "protein supplements"],
        "ORGANIZATION": ["ACE", "NASM", "ACSM", "WHO", "NIH"],
        "PERSON": ["Jillian Michaels", "Tony Horton", "Kayla Itsines", "Chris Hemsworth"],
    },
    "B2B SaaS": {
        "BRAND": ["Slack", "Zoom", "HubSpot", "Atlassian", "Datadog", "Snowflake", "Stripe"],
        "PRODUCT": ["CRM", "project management", "CI/CD pipeline", "data warehouse", "payment processing"],
        "ORGANIZATION": ["Y Combinator", "TechCrunch", "SaaStr", "Gartner"],
        "PERSON": ["Stewart Butterfield", "Eric Yuan", "Patrick Collison", "Dharmesh Shah"],
    },
    "Cybersecurity": {
        "BRAND": ["CrowdStrike", "Palo Alto Networks", "Okta", "Zscaler", "1Password"],
        "PRODUCT": ["endpoint protection", "SIEM", "zero trust", "identity management", "firewall"],
        "ORGANIZATION": ["NIST", "CISA", "OWASP", "RSA Conference", "Black Hat"],
        "PERSON": ["Kevin Mandia", "George Kurtz", "Nikesh Arora"],
    },
    "Fashion Accessories": {
        "BRAND": ["Warby Parker", "Ray-Ban", "Coach", "Kate Spade", "Fossil", "Tiffany & Co", "Oakley"],
        "PRODUCT": ["sunglasses", "watches", "handbags", "jewelry", "wallets", "belts", "scarves"],
        "ORGANIZATION": ["GIA", "Luxottica", "Swatch Group"],
        "PERSON": ["Michael Kors", "Tory Burch", "Kate Spade"],
    },
    "Event Tickets": {
        "BRAND": ["Ticketmaster", "StubHub", "SeatGeek", "Vivid Seats", "AXS"],
        "PRODUCT": ["concert tickets", "sports tickets", "festival passes", "VIP packages", "season tickets"],
        "ORGANIZATION": ["Live Nation", "AEG Presents", "Coachella", "Bonnaroo"],
        "PERSON": ["Taylor Swift", "Beyoncé", "Ed Sheeran", "Travis Scott"],
    },
    "Musical Instruments": {
        "BRAND": ["Gibson", "Fender", "Yamaha", "Roland", "Taylor Guitars", "Martin"],
        "PRODUCT": ["electric guitar", "acoustic guitar", "drums", "keyboard", "amplifier", "pedals"],
        "ORGANIZATION": ["NAMM", "Guitar Center", "Musicians Institute"],
        "PERSON": ["Jimi Hendrix", "Eric Clapton", "John Mayer", "Billie Eilish"],
    },
    "Movie Theaters": {
        "BRAND": ["AMC", "Regal", "Cinemark", "Alamo Drafthouse", "IMAX", "Dolby Cinema"],
        "PRODUCT": ["movie tickets", "popcorn", "IMAX experience", "reserved seating", "gift cards"],
        "ORGANIZATION": ["Motion Picture Association", "Academy Awards", "Sundance"],
        "PERSON": ["Steven Spielberg", "Christopher Nolan", "Greta Gerwig"],
    },
    "Investment App": {
        "BRAND": ["Robinhood", "Acorns", "Wealthfront", "Betterment", "SoFi", "Stash"],
        "PRODUCT": ["fractional shares", "robo-advisor", "IRA", "crypto trading", "ETFs"],
        "ORGANIZATION": ["SEC", "FINRA", "SIPC"],
        "PERSON": ["Vlad Tenev", "Warren Buffett", "Cathie Wood"],
    },
    "Financial Planning": {
        "BRAND": ["Mint", "Credit Karma", "YNAB", "Personal Capital", "NerdWallet"],
        "PRODUCT": ["budget tracker", "credit score", "net worth calculator", "debt payoff planner"],
        "ORGANIZATION": ["CFPB", "FICO", "Experian", "TransUnion", "Equifax"],
        "PERSON": ["Dave Ramsey", "Suze Orman", "Robert Kiyosaki"],
    },
    "Insurance": {
        "BRAND": ["Geico", "Progressive", "State Farm", "Allstate", "Lemonade", "Liberty Mutual"],
        "PRODUCT": ["auto insurance", "home insurance", "renters insurance", "life insurance", "pet insurance"],
        "ORGANIZATION": ["NAIC", "Insurance Information Institute", "AM Best"],
        "PERSON": ["Warren Buffett", "Flo from Progressive"],
    },
    "Sports Streaming": {
        "BRAND": ["ESPN+", "NFL Sunday Ticket", "NBA League Pass", "DAZN", "Peacock Sports"],
        "PRODUCT": ["live games", "replays", "highlights", "multi-view", "fantasy integration"],
        "ORGANIZATION": ["NFL", "NBA", "MLB", "NHL", "FIFA", "UEFA"],
        "PERSON": ["LeBron James", "Patrick Mahomes", "Lionel Messi", "Serena Williams"],
    },
    "Sports Apparel": {
        "BRAND": ["Nike", "Under Armour", "Adidas", "Puma", "New Balance", "Reebok"],
        "PRODUCT": ["jerseys", "sneakers", "cleats", "compression gear", "training shorts"],
        "ORGANIZATION": ["NFL Players Association", "NBA", "Olympic Committee"],
        "PERSON": ["LeBron James", "Serena Williams", "Cristiano Ronaldo", "Stephen Curry"],
    },
    "Sports Equipment": {
        "BRAND": ["Wilson", "Spalding", "Riddell", "Callaway", "Titleist", "Head"],
        "PRODUCT": ["footballs", "basketballs", "tennis racquets", "golf clubs", "helmets", "bats"],
        "ORGANIZATION": ["NFL", "NBA", "PGA Tour", "ATP", "WTA"],
        "PERSON": ["Tiger Woods", "Roger Federer", "Tom Brady"],
    },
    "Sports Merchandise": {
        "BRAND": ["Fanatics", "NFL Shop", "NBA Store", "Mitchell & Ness", "New Era"],
        "PRODUCT": ["jerseys", "hats", "t-shirts", "memorabilia", "autographed items"],
        "ORGANIZATION": ["NFL", "NBA", "MLB", "NHL", "MLS"],
        "PERSON": ["Michael Jordan", "Tom Brady", "LeBron James", "Patrick Mahomes"],
    },
    "Sports Retail": {
        "BRAND": ["Dick's Sporting Goods", "REI", "Academy Sports", "Tennis Warehouse", "SoccerPro"],
        "PRODUCT": ["sports equipment", "athletic shoes", "camping gear", "training aids"],
        "ORGANIZATION": ["Sporting Goods Manufacturers Association"],
        "PERSON": ["Roger Federer", "Rory McIlroy"],
    },
    "Software": {
        "BRAND": ["Adobe", "Figma", "Notion", "Canva", "Sketch", "InVision"],
        "PRODUCT": ["Photoshop", "Illustrator", "design tools", "prototyping", "collaboration"],
        "ORGANIZATION": ["AIGA", "Dribbble", "Behance", "Product Hunt"],
        "PERSON": ["Dylan Field", "Ivan Zhao", "Scott Belsky"],
    },
    "Computer Hardware": {
        "BRAND": ["Dell", "Lenovo", "HP", "ASUS", "Acer", "MSI", "Razer"],
        "PRODUCT": ["laptops", "desktops", "monitors", "keyboards", "mice", "docking stations"],
        "ORGANIZATION": ["Intel", "AMD", "NVIDIA", "CES"],
        "PERSON": ["Lisa Su", "Pat Gelsinger", "Jensen Huang"],
    },
    "Telecom": {
        "BRAND": ["Verizon", "AT&T", "T-Mobile", "Mint Mobile", "Google Fi"],
        "PRODUCT": ["5G plans", "unlimited data", "family plans", "home internet", "hotspot"],
        "ORGANIZATION": ["FCC", "CTIA", "GSMA"],
        "PERSON": ["Ryan Reynolds", "John Legere"],
    },
    "News Media": {
        "BRAND": ["New York Times", "Washington Post", "The Atlantic", "Reuters", "Bloomberg"],
        "PRODUCT": ["digital subscription", "newsletters", "podcasts", "investigations"],
        "ORGANIZATION": ["Pulitzer Prize", "Associated Press", "Reuters Institute"],
        "PERSON": ["Bob Woodward", "Maggie Haberman", "Kara Swisher"],
    },
    "Audiobooks": {
        "BRAND": ["Audible", "Scribd", "Libro.fm", "Kobo", "Google Play Books"],
        "PRODUCT": ["audiobooks", "podcasts", "e-books", "originals", "sleep stories"],
        "ORGANIZATION": ["Audio Publishers Association", "Goodreads"],
        "PERSON": ["Stephen King", "Michelle Obama", "Matthew McConaughey"],
    },
    "Pet Products": {
        "BRAND": ["Chewy", "BarkBox", "Petco", "PetSmart", "Rover", "Ollie"],
        "PRODUCT": ["dog food", "cat food", "pet toys", "grooming supplies", "pet beds"],
        "ORGANIZATION": ["ASPCA", "AKC", "Humane Society"],
        "PERSON": ["Cesar Millan", "Jackson Galaxy"],
    },
    "Home & Garden": {
        "BRAND": ["Wayfair", "IKEA", "West Elm", "Pottery Barn", "Home Depot", "Crate & Barrel"],
        "PRODUCT": ["furniture", "rugs", "lighting", "planters", "kitchen appliances", "bedding"],
        "ORGANIZATION": ["HGTV", "Architectural Digest", "Better Homes & Gardens"],
        "PERSON": ["Joanna Gaines", "Martha Stewart", "Nate Berkus"],
    },
    "Restaurants": {
        "BRAND": ["Chipotle", "Starbucks", "Shake Shack", "Panera", "Sweetgreen", "Domino's"],
        "PRODUCT": ["burritos", "coffee", "salads", "pizza", "meal deals", "rewards"],
        "ORGANIZATION": ["National Restaurant Association", "Michelin Guide", "James Beard Foundation"],
        "PERSON": ["Gordon Ramsay", "Guy Fieri", "David Chang"],
    },
    "Healthcare": {
        "BRAND": ["Hims & Hers", "GoodRx", "Teladoc", "Roman", "Nurx", "One Medical"],
        "PRODUCT": ["telehealth visits", "prescriptions", "lab tests", "therapy", "wellness plans"],
        "ORGANIZATION": ["FDA", "CDC", "WHO", "AMA"],
        "PERSON": ["Dr. Fauci", "Dr. Oz", "Dr. Sanjay Gupta"],
    },
    "Airlines": {
        "BRAND": ["Delta", "United", "Southwest", "JetBlue", "Alaska Airlines", "American Airlines"],
        "PRODUCT": ["flights", "miles", "business class", "lounge access", "companion pass"],
        "ORGANIZATION": ["FAA", "IATA", "TSA"],
        "PERSON": ["Ed Bastian", "Scott Kirby"],
    },
    "Automotive": {
        "BRAND": ["Toyota", "Honda", "BMW", "Mercedes-Benz", "Ford", "Tesla", "Hyundai"],
        "PRODUCT": ["sedan", "SUV", "truck", "electric car", "hybrid", "lease deals"],
        "ORGANIZATION": ["NHTSA", "EPA", "J.D. Power", "IIHS"],
        "PERSON": ["Elon Musk", "Mary Barra", "Akio Toyoda"],
    },
    "Culture": {
        "BRAND": ["Smithsonian", "National Geographic", "The Met", "MoMA", "PBS", "BBC Culture"],
        "PRODUCT": ["exhibitions", "documentaries", "art prints", "memberships", "guided tours"],
        "ORGANIZATION": ["NEA", "UNESCO", "National Endowment for the Arts", "Smithsonian Institution"],
        "PERSON": ["Ken Burns", "David Attenborough", "Lin-Manuel Miranda", "Ai Weiwei"],
    },
    "Education": {
        "BRAND": ["Harvard", "Stanford", "MIT", "Pearson", "McGraw-Hill", "Chegg"],
        "PRODUCT": ["textbooks", "online courses", "degree programs", "tutoring", "study guides"],
        "ORGANIZATION": ["Department of Education", "College Board", "ACT", "AACSB"],
        "PERSON": ["Sal Khan", "Angela Duckworth", "Howard Gardner"],
    },
    "Non-Profit": {
        "BRAND": ["UNICEF", "Red Cross", "WWF", "Doctors Without Borders", "Habitat for Humanity"],
        "PRODUCT": ["donations", "volunteer programs", "awareness campaigns", "grants", "sponsorships"],
        "ORGANIZATION": ["United Nations", "World Bank", "Gates Foundation", "Ford Foundation"],
        "PERSON": ["Bill Gates", "Melinda French Gates", "Malala Yousafzai", "Greta Thunberg"],
    },
    "Government": {
        "BRAND": ["USA.gov", "CDC", "NASA", "USPS", "IRS"],
        "PRODUCT": ["public services", "health advisories", "tax filing", "benefits enrollment", "civic resources"],
        "ORGANIZATION": ["White House", "Congress", "Supreme Court", "Federal Reserve"],
        "PERSON": ["President", "Secretary of State", "NASA Administrator"],
    },
    "Politics": {
        "BRAND": ["Politico", "The Hill", "FiveThirtyEight", "C-SPAN", "Roll Call"],
        "PRODUCT": ["news subscriptions", "newsletters", "polling data", "analysis reports", "podcasts"],
        "ORGANIZATION": ["DNC", "RNC", "FEC", "Brookings Institution", "Heritage Foundation"],
        "PERSON": ["Nate Silver", "Rachel Maddow", "Jake Tapper", "Anderson Cooper"],
    },
    "Technology": {
        "BRAND": ["NVIDIA", "Intel", "AMD", "Qualcomm", "Cisco", "IBM"],
        "PRODUCT": ["GPUs", "CPUs", "chipsets", "networking equipment", "servers", "accelerators"],
        "ORGANIZATION": ["CES", "IEEE", "ACM", "W3C", "Linux Foundation"],
        "PERSON": ["Jensen Huang", "Lisa Su", "Pat Gelsinger", "Satya Nadella"],
    },
    "AI": {
        "BRAND": ["OpenAI", "Anthropic", "Google DeepMind", "Hugging Face", "Stability AI", "Cohere"],
        "PRODUCT": ["LLMs", "API access", "fine-tuning", "embeddings", "image generation", "chatbots"],
        "ORGANIZATION": ["Partnership on AI", "AI Safety Institute", "NIST AI", "Stanford HAI"],
        "PERSON": ["Sam Altman", "Dario Amodei", "Demis Hassabis", "Yann LeCun", "Fei-Fei Li"],
    },
    "FinTech": {
        "BRAND": ["Square", "Plaid", "Chime", "Revolut", "Wise", "Affirm"],
        "PRODUCT": ["payment processing", "banking app", "money transfers", "BNPL", "open banking API"],
        "ORGANIZATION": ["CFPB", "OCC", "Federal Reserve", "Financial Stability Board"],
        "PERSON": ["Jack Dorsey", "Patrick Collison", "Max Levchin"],
    },
    "HealthTech": {
        "BRAND": ["Zocdoc", "Ro", "Oscar Health", "Tempus", "Cityblock Health"],
        "PRODUCT": ["telehealth platform", "health records", "appointment booking", "diagnostics", "care coordination"],
        "ORGANIZATION": ["FDA", "CMS", "ONC", "HIMSS", "HL7"],
        "PERSON": ["Anne Wojcicki", "Ali Parsa", "Glen Tullman"],
    },
    "E-commerce": {
        "BRAND": ["Shopify", "Etsy", "Amazon", "eBay", "Walmart Marketplace", "Wish"],
        "PRODUCT": ["online store", "marketplace", "seller tools", "fulfillment", "payment gateway"],
        "ORGANIZATION": ["NRF", "Internet Retailer", "Shopify Partners", "Amazon Sellers"],
        "PERSON": ["Jeff Bezos", "Tobias Lütke", "Andy Jassy"],
    },
    "Personal Banking": {
        "BRAND": ["Chase", "Bank of America", "Wells Fargo", "Ally Bank", "Capital One", "Marcus"],
        "PRODUCT": ["checking account", "savings account", "credit card", "mortgage", "auto loan", "CD"],
        "ORGANIZATION": ["FDIC", "Federal Reserve", "OCC", "NCUA"],
        "PERSON": ["Jamie Dimon", "Brian Moynihan", "Charlie Scharf"],
    },
    "Craft Beer & Spirits": {
        "BRAND": ["Heineken", "Diageo", "Patrón", "Drizly", "BrewDog", "Stone Brewing"],
        "PRODUCT": ["craft beer", "IPA", "whiskey", "tequila", "vodka", "cocktail kits"],
        "ORGANIZATION": ["Brewers Association", "TTB", "Beer Judge Certification"],
        "PERSON": ["Sam Calagione", "Jim Koch", "Garrett Oliver"],
    },
    "Energy Drinks": {
        "BRAND": ["Red Bull", "Monster", "Celsius", "Ghost", "Prime", "Rockstar"],
        "PRODUCT": ["energy drink", "pre-workout", "zero sugar", "electrolytes", "caffeine"],
        "ORGANIZATION": ["X Games", "UFC", "Red Bull Racing", "Monster Energy Cup"],
        "PERSON": ["Felix Baumgartner", "Travis Pastrana", "Logan Paul"],
    },
    "Coffee & Tea": {
        "BRAND": ["Nespresso", "Blue Bottle", "Illy", "Twinings", "Trade Coffee", "Stumptown"],
        "PRODUCT": ["espresso", "cold brew", "matcha", "loose leaf tea", "coffee pods", "grinder"],
        "ORGANIZATION": ["Specialty Coffee Association", "World Barista Championship"],
        "PERSON": ["James Hoffmann", "George Clooney"],
    },
    "Pharmaceuticals": {
        "BRAND": ["Pfizer", "Johnson & Johnson", "AbbVie", "Moderna", "Eli Lilly", "Merck"],
        "PRODUCT": ["prescription medication", "vaccine", "clinical trial", "biologic", "OTC medicine"],
        "ORGANIZATION": ["FDA", "WHO", "NIH", "CDC", "EMA"],
        "PERSON": ["Albert Bourla", "Stéphane Bancel"],
    },
    "Supplements & Nutrition": {
        "BRAND": ["GNC", "AG1", "Huel", "Vital Proteins", "Optimum Nutrition", "Garden of Life"],
        "PRODUCT": ["protein powder", "multivitamin", "creatine", "collagen", "greens powder", "omega-3"],
        "ORGANIZATION": ["NSF International", "Informed Sport", "FDA"],
        "PERSON": ["Andrew Huberman", "Layne Norton", "Dr. Rhonda Patrick"],
    },
    "Hotels & Resorts": {
        "BRAND": ["Marriott", "Hilton", "Hyatt", "IHG", "Four Seasons", "Ritz-Carlton"],
        "PRODUCT": ["hotel room", "suite", "loyalty points", "resort package", "spa", "conference venue"],
        "ORGANIZATION": ["AAA", "Forbes Travel Guide", "Condé Nast Traveler"],
        "PERSON": ["Anthony Capuano", "Christopher Nassetta"],
    },
    "Cruises": {
        "BRAND": ["Royal Caribbean", "Carnival", "Norwegian", "Celebrity Cruises", "MSC", "Disney Cruise"],
        "PRODUCT": ["cruise package", "shore excursion", "drink package", "suite", "all-inclusive"],
        "ORGANIZATION": ["CLIA", "Maritime Authority", "CDC Vessel Sanitation"],
        "PERSON": ["Jason Liberty", "Josh Weinstein"],
    },
    "HR & Recruiting": {
        "BRAND": ["LinkedIn", "Indeed", "Glassdoor", "Workday", "BambooHR", "ADP"],
        "PRODUCT": ["job posting", "ATS", "HR platform", "payroll", "talent analytics", "onboarding"],
        "ORGANIZATION": ["SHRM", "CIPD", "ATD", "WorldatWork"],
        "PERSON": ["Ryan Roslansky", "Aneel Bhusri"],
    },
    "Accounting & Tax": {
        "BRAND": ["TurboTax", "H&R Block", "QuickBooks", "FreshBooks", "Xero", "Wave"],
        "PRODUCT": ["tax filing", "bookkeeping", "invoicing", "payroll", "expense tracking", "tax refund"],
        "ORGANIZATION": ["IRS", "AICPA", "FASB", "CPA"],
        "PERSON": ["Sasan Goodarzi"],
    },
    "Legal Services": {
        "BRAND": ["LegalZoom", "Rocket Lawyer", "Avvo", "FindLaw", "LawDepot"],
        "PRODUCT": ["LLC formation", "trademark", "will", "contract", "legal advice", "legal plan"],
        "ORGANIZATION": ["ABA", "State Bar", "Legal Aid"],
        "PERSON": ["Brian Liu", "Charley Moore"],
    },
    "Social Media": {
        "BRAND": ["TikTok", "Snapchat", "Pinterest", "Reddit", "Discord", "Threads"],
        "PRODUCT": ["social feed", "stories", "reels", "live streaming", "ad platform", "messaging"],
        "ORGANIZATION": ["FTC", "EU Digital Services Act", "Internet Society"],
        "PERSON": ["Shou Zi Chew", "Evan Spiegel", "Steve Huffman"],
    },
    "Creator Economy": {
        "BRAND": ["Patreon", "Substack", "Gumroad", "Kajabi", "Teachable", "Ko-fi"],
        "PRODUCT": ["membership platform", "newsletter", "online course", "digital downloads", "merch store"],
        "ORGANIZATION": ["Creator Economy Council", "Influencer Marketing Hub"],
        "PERSON": ["Jack Conte", "Chris Best", "Sahil Lavingia"],
    },
    "Baby & Parenting": {
        "BRAND": ["Pampers", "BabyCenter", "Nanit", "Hatch", "Ergobaby", "UPPAbaby"],
        "PRODUCT": ["diapers", "baby monitor", "stroller", "car seat", "formula", "baby carrier"],
        "ORGANIZATION": ["AAP", "CPSC", "La Leche League"],
        "PERSON": ["Dr. Harvey Karp", "Emily Oster"],
    },
    "Kids & Family Entertainment": {
        "BRAND": ["Disney", "Lego", "Nickelodeon", "PBS Kids", "Mattel", "Hasbro"],
        "PRODUCT": ["toys", "games", "kids shows", "educational apps", "playsets", "action figures"],
        "ORGANIZATION": ["Toy Association", "Common Sense Media", "KidScreen"],
        "PERSON": ["Bob Iger", "Niels Christiansen"],
    },
    "Home Services": {
        "BRAND": ["Angi", "Thumbtack", "TaskRabbit", "HomeAdvisor", "Handy"],
        "PRODUCT": ["plumbing", "electrician", "painting", "HVAC", "cleaning", "handyman"],
        "ORGANIZATION": ["Better Business Bureau", "HomeStars", "National Association of Home Builders"],
        "PERSON": ["Joey Levin", "Marco Zappacosta"],
    },
    "Cleaning & Household": {
        "BRAND": ["P&G", "Clorox", "Seventh Generation", "Method", "Mrs. Meyer's", "Lysol"],
        "PRODUCT": ["dish soap", "laundry detergent", "disinfectant", "paper towels", "trash bags"],
        "ORGANIZATION": ["EPA Safer Choice", "Green Seal", "Consumer Reports"],
        "PERSON": ["Jon Moeller"],
    },
    "Solar & Renewable Energy": {
        "BRAND": ["SunPower", "Sunrun", "Tesla Energy", "EnergySage", "Enphase"],
        "PRODUCT": ["solar panels", "home battery", "solar roof", "EV charger", "energy monitoring"],
        "ORGANIZATION": ["SEIA", "DOE", "IRENA", "Solar Energy International"],
        "PERSON": ["Elon Musk", "Mary Powell"],
    },
    "Identity & Privacy": {
        "BRAND": ["NordVPN", "ExpressVPN", "LifeLock", "DeleteMe", "Surfshark", "1Password"],
        "PRODUCT": ["VPN", "identity monitoring", "password manager", "data removal", "encrypted email"],
        "ORGANIZATION": ["EFF", "NIST", "IAPP", "Privacy International"],
        "PERSON": ["Edward Snowden", "Tim Cook"],
    },
    "Weddings": {
        "BRAND": ["Zola", "The Knot", "WeddingWire", "Minted", "Joy"],
        "PRODUCT": ["wedding registry", "invitations", "vendor booking", "wedding website", "seating chart"],
        "ORGANIZATION": ["Association of Bridal Consultants", "NACE"],
        "PERSON": ["David Tutera", "Mindy Weiss"],
    },
    "Logistics & Shipping": {
        "BRAND": ["FedEx", "UPS", "DHL", "ShipBob", "Flexport", "USPS"],
        "PRODUCT": ["overnight shipping", "freight", "last mile delivery", "fulfillment", "tracking"],
        "ORGANIZATION": ["IMO", "DOT", "World Shipping Council"],
        "PERSON": ["Carol Tomé", "Raj Subramaniam", "Ryan Petersen"],
    },
    "Sustainability": {
        "BRAND": ["Patagonia", "Allbirds", "Oatly", "Beyond Meat", "Tentree"],
        "PRODUCT": ["recycled materials", "carbon offsets", "plant-based", "reusable products", "eco-packaging"],
        "ORGANIZATION": ["B Corp", "1% for the Planet", "EPA", "UN Global Compact"],
        "PERSON": ["Yvon Chouinard", "Rose Marcario", "Ethan Brown"],
    },
}

DEFAULT_ENTITY_BANK = {
    "BRAND": ["BrandX", "ProLine", "EliteChoice", "TopTier", "PrimePick"],
    "PRODUCT": ["premium product", "subscription service", "mobile app", "platform", "solution"],
    "ORGANIZATION": ["Industry Association", "Standards Board", "Consumer Federation"],
    "PERSON": ["Industry Expert", "CEO", "Founder"],
}


KEYWORDS_BY_CATEGORY = {
    "lifestyle": [
        "fashion", "style", "trends", "lifestyle", "beauty", "wellness", "shopping", "home decor",
        "self-care", "luxury", "design", "aesthetics", "wardrobe", "skincare", "makeup",
        "accessories", "sustainability", "organic", "minimalism", "curated", "artisan",
        "handmade", "vintage", "modern", "elegant", "chic", "boutique", "collection",
        "seasonal", "editorial", "brand", "designer", "premium", "exclusive", "bespoke",
        "contemporary", "refined", "sophisticated", "effortless", "timeless", "iconic",
        "capsule wardrobe", "athleisure", "streetwear", "personal styling", "color palette",
        "pattern", "textile", "fabric", "silhouette", "resort wear", "evening wear",
        "casual chic", "layering", "statement piece", "wardrobe essentials", "seasonal refresh",
    ],
    "music": [
        "music", "concert", "artist", "album", "streaming", "live performance", "entertainment",
        "playlist", "podcast", "vinyl", "beats", "rhythm", "melody", "lyrics", "guitar",
        "drums", "bass", "vocals", "recording", "studio", "producer", "DJ", "festival",
        "hip hop", "rock", "pop", "jazz", "classical", "indie", "electronic", "R&B",
        "country", "Latin", "world music", "new releases", "charts", "top hits",
        "music video", "mixtape", "acoustic", "songwriting", "music theory", "karaoke",
        "headphones", "speakers", "amplifier", "synthesizer", "turntable", "audio engineering",
        "Grammy", "Billboard", "concert tour", "backstage", "setlist", "music discovery",
    ],
    "movies": [
        "movies", "film", "cinema", "streaming", "entertainment", "box office", "premiere",
        "series", "documentary", "thriller", "comedy", "drama", "action", "horror",
        "sci-fi", "animation", "director", "actor", "screenplay", "Oscar", "Emmy",
        "binge watch", "original content", "sequel", "franchise", "blockbuster",
        "indie film", "foreign film", "film festival", "limited series", "miniseries",
        "cinematography", "special effects", "CGI", "film score", "casting", "film review",
        "red carpet", "movie trailer", "post-production", "film editing", "stunt work",
        "streaming wars", "content library", "watch party", "movie marathon", "cult classic",
    ],
    "entertainment": [
        "entertainment", "shows", "streaming", "gaming", "events", "live", "content",
        "viral", "trending", "celebrity", "pop culture", "fan", "experience", "immersive",
        "interactive", "virtual reality", "augmented reality", "esports", "cosplay",
        "anime", "manga", "comic books", "conventions", "theme parks", "attractions",
        "talent show", "reality TV", "late night", "stand-up comedy", "improv", "podcast",
        "influencer", "content creator", "TikTok", "YouTube", "social media", "meme",
        "fan fiction", "merchandise", "collectibles", "trivia", "awards show", "premiere",
    ],
    "finance": [
        "finance", "investing", "stock market", "economy", "trading", "money", "wealth",
        "retirement", "savings", "portfolio", "dividends", "bonds", "mutual funds", "ETF",
        "financial planning", "tax", "insurance", "banking", "credit", "loans",
        "interest rates", "inflation", "GDP", "Federal Reserve", "Wall Street",
        "cryptocurrency", "blockchain", "DeFi", "fintech", "robo-advisor",
        "asset allocation", "risk management", "compound interest", "capital gains",
        "fiduciary", "estate planning", "annuity", "hedge fund", "private equity",
        "venture capital", "IPO", "stock options", "dollar cost averaging", "passive income",
        "financial literacy", "budgeting", "emergency fund", "credit score", "debt management",
        "401k", "IRA", "Roth IRA", "social security", "pension", "index fund",
    ],
    "basketball": [
        "basketball", "NBA", "sports", "hoops", "playoffs", "team", "athlete",
        "slam dunk", "three pointer", "point guard", "shooting guard", "center",
        "rebounds", "assists", "MVP", "all-star", "draft", "trade", "free agency",
        "March Madness", "championship", "court", "sneakers", "jersey",
        "fast break", "pick and roll", "crossover", "layup", "free throw",
        "double dribble", "traveling", "technical foul", "buzzer beater", "overtime",
        "conference finals", "NBA Finals", "rookie", "hall of fame", "triple double",
    ],
    "football": [
        "football", "NFL", "sports", "touchdown", "game day", "playoffs", "super bowl",
        "quarterback", "wide receiver", "running back", "defense", "offense",
        "field goal", "interception", "fumble", "sack", "fantasy football",
        "draft", "combine", "training camp", "tailgate", "helmet", "jersey",
        "red zone", "two minute warning", "onside kick", "hail mary", "blitz",
        "scramble", "audible", "end zone", "punt", "kickoff", "halftime",
        "Pro Bowl", "Monday Night Football", "Thursday Night Football", "wild card",
    ],
    "tennis": [
        "tennis", "tournament", "grand slam", "racquet", "match", "athlete",
        "Wimbledon", "US Open", "French Open", "Australian Open", "serve",
        "volley", "baseline", "forehand", "backhand", "deuce", "ace",
        "clay court", "grass court", "hard court", "doubles", "singles",
        "tiebreak", "match point", "set point", "break point", "love game",
        "drop shot", "lob", "rally", "net play", "slice", "topspin",
        "ATP", "WTA", "seeded player", "qualifier", "Davis Cup", "Fed Cup",
    ],
    "soccer": [
        "soccer", "football", "world cup", "league", "match", "goal", "team",
        "Champions League", "Premier League", "La Liga", "Serie A", "Bundesliga",
        "striker", "midfielder", "defender", "goalkeeper", "penalty", "free kick",
        "transfer", "derby", "stadium", "cleats", "jersey", "VAR",
        "corner kick", "offside", "yellow card", "red card", "hat trick",
        "nutmeg", "bicycle kick", "header", "dribble", "assist", "clean sheet",
        "MLS", "Europa League", "relegation", "promotion", "injury time", "stoppage time",
    ],
    "sports": [
        "sports", "athletic", "competition", "championship", "tournament", "league",
        "athlete", "training", "fitness", "performance", "game", "score", "victory",
        "season", "playoffs", "draft", "roster", "coach", "stadium", "arena",
        "sportsmanship", "record", "medal", "Olympic", "world record", "qualifier",
        "exhibition", "preseason", "postseason", "rivalry", "dynasty", "underdog",
        "comeback", "highlight reel", "play of the day", "sports analytics", "sabermetrics",
    ],
    "politics": [
        "politics", "government", "policy", "election", "news", "current events",
        "legislation", "congress", "senate", "democracy", "voting", "campaign",
        "debate", "immigration", "healthcare policy", "foreign policy", "economy",
        "bipartisan", "executive order", "judicial", "supreme court",
        "ballot", "caucus", "primary", "swing state", "electoral college", "gerrymandering",
        "filibuster", "lobbyist", "PAC", "grassroots", "political action", "referendum",
        "town hall", "constituent", "political polling", "midterm elections", "inauguration",
        "political party", "independent", "progressive", "conservative", "moderate",
    ],
    "news": [
        "breaking news", "analysis", "investigation", "reporting", "journalism",
        "editorial", "opinion", "fact check", "global affairs", "domestic policy",
        "business news", "tech news", "science", "environment", "climate",
        "exclusive report", "live coverage", "developing story", "press conference",
        "source", "correspondent", "headline", "byline", "newsroom", "deadline",
        "media", "broadcast", "print journalism", "digital media", "press freedom",
        "accountability", "transparency", "whistleblower", "public interest", "data journalism",
    ],
    "technology": [
        "technology", "tech", "innovation", "gadgets", "AI", "software", "devices",
        "machine learning", "cloud computing", "cybersecurity", "blockchain", "5G",
        "IoT", "robotics", "automation", "data science", "SaaS", "startup",
        "venture capital", "silicon valley", "programming", "API", "open source",
        "developer", "engineering", "computing", "digital transformation",
        "quantum computing", "edge computing", "microservices", "containers",
        "semiconductor", "chip design", "neural network", "GPU computing", "inference",
        "natural language processing", "computer vision", "deep learning", "reinforcement learning",
        "tech stack", "full stack", "DevOps", "CI/CD", "infrastructure", "scalability",
        "low-code", "no-code", "augmented reality", "mixed reality", "spatial computing",
        "Web3", "decentralized", "metaverse", "digital twin", "autonomous systems",
    ],
    "gaming": [
        "gaming", "video games", "esports", "console", "PC gaming", "mobile gaming",
        "multiplayer", "RPG", "FPS", "strategy", "indie games", "AAA titles",
        "game pass", "VR gaming", "cloud gaming", "streaming", "Twitch",
        "speedrun", "modding", "game development", "early access", "DLC",
        "battle royale", "sandbox", "open world", "loot box", "microtransaction",
        "game engine", "Unity", "Unreal Engine", "pixel art", "retro gaming",
        "co-op", "PvP", "PvE", "MMORPG", "roguelike", "metroidvania",
        "game soundtrack", "character design", "game narrative", "achievement", "leaderboard",
    ],
    "automotive": [
        "cars", "automotive", "vehicles", "SUV", "truck", "sedan", "electric vehicle",
        "hybrid", "luxury car", "test drive", "lease", "financing", "trade-in",
        "safety features", "autonomous driving", "connected car", "fuel efficiency",
        "horsepower", "torque", "all-wheel drive", "MPG", "EV charging",
        "dashboard", "infotainment", "adaptive cruise control", "lane assist", "blind spot",
        "turbocharger", "transmission", "suspension", "aerodynamics", "towing capacity",
        "car insurance", "vehicle inspection", "car maintenance", "road trip", "garage",
        "supercar", "crossover", "minivan", "convertible", "off-road", "four-wheel drive",
    ],
    "real_estate": [
        "real estate", "homes", "property", "mortgage", "listings", "buy a home",
        "sell a home", "rent", "apartment", "condo", "townhouse", "neighborhood",
        "school district", "home value", "interest rates", "down payment",
        "open house", "virtual tour", "home inspection", "closing costs",
        "property tax", "HOA", "escrow", "appraisal", "title insurance", "pre-approval",
        "fixed rate", "adjustable rate", "refinance", "home equity", "HELOC",
        "real estate agent", "broker", "MLS listing", "curb appeal", "staging",
        "commercial real estate", "investment property", "rental income", "cap rate",
    ],
    "pets": [
        "pets", "dogs", "cats", "pet food", "pet health", "veterinary", "grooming",
        "pet supplies", "dog training", "cat toys", "puppy", "kitten", "adoption",
        "rescue", "pet insurance", "pet wellness", "organic pet food",
        "dog walking", "pet sitting", "kennel", "leash", "collar", "harness",
        "breed", "mixed breed", "senior pet", "pet nutrition", "raw diet",
        "aquarium", "fish", "bird", "reptile", "small animals", "exotic pets",
        "pet behavior", "separation anxiety", "crate training", "socialization",
    ],
    "home": [
        "home decor", "furniture", "interior design", "kitchen", "bathroom",
        "bedroom", "living room", "outdoor", "garden", "DIY", "renovation",
        "smart home", "lighting", "storage", "organization", "appliances",
        "home improvement", "landscaping", "patio", "deck", "fence",
        "paint colors", "wallpaper", "flooring", "tile", "countertop", "cabinet",
        "home automation", "security system", "doorbell camera", "thermostat",
        "energy efficiency", "solar panels", "insulation", "HVAC", "plumbing",
        "home staging", "open floor plan", "accent wall", "farmhouse style", "modern design",
    ],
    "education": [
        "education", "online learning", "courses", "skills", "career development",
        "certification", "training", "university", "coding", "data science",
        "language learning", "professional development", "e-learning", "MOOC",
        "bootcamp", "degree", "scholarship", "tuition", "student",
        "curriculum", "pedagogy", "assessment", "accreditation", "GPA",
        "SAT", "ACT", "GRE", "GMAT", "TOEFL", "IELTS",
        "study abroad", "distance learning", "hybrid learning", "classroom", "lecture",
        "research", "thesis", "dissertation", "academic journal", "peer review",
        "STEM", "liberal arts", "vocational training", "apprenticeship", "continuing education",
    ],
    "food": [
        "food", "cooking", "recipes", "restaurants", "delivery", "meal prep",
        "healthy eating", "organic", "vegan", "gluten-free", "keto", "paleo",
        "dining", "brunch", "takeout", "catering", "chef", "cuisine",
        "ingredients", "nutrition", "calories", "meal kit", "grocery",
        "farm to table", "sustainable food", "food truck", "street food", "comfort food",
        "baking", "pastry", "sourdough", "fermentation", "spices", "seasoning",
        "wine pairing", "craft beer", "cocktails", "barista", "coffee",
        "food photography", "food blog", "restaurant review", "Michelin star", "culinary arts",
    ],
    "health": [
        "health", "wellness", "fitness", "nutrition", "mental health", "meditation",
        "yoga", "exercise", "diet", "vitamins", "supplements", "sleep",
        "stress management", "healthcare", "telemedicine", "prescription",
        "therapy", "mindfulness", "workout", "recovery", "preventive care",
        "physical therapy", "chiropractic", "acupuncture", "holistic health", "naturopathy",
        "blood pressure", "cholesterol", "diabetes", "heart health", "immune system",
        "gut health", "probiotics", "hormone balance", "anti-aging", "longevity",
        "clinical trial", "FDA approved", "medical device", "health screening", "annual checkup",
        "wearable health", "biometrics", "health data", "patient portal", "EHR",
    ],
    "travel": [
        "travel", "vacation", "flights", "hotels", "booking", "destination",
        "adventure", "beach", "mountain", "city break", "road trip", "cruise",
        "resort", "backpacking", "luxury travel", "budget travel",
        "travel insurance", "passport", "itinerary", "tourism",
        "solo travel", "group travel", "family vacation", "honeymoon", "anniversary trip",
        "travel hacking", "frequent flyer", "travel rewards", "airline miles", "hotel points",
        "Airbnb", "hostel", "glamping", "villa rental", "all-inclusive",
        "visa", "customs", "jet lag", "layover", "connecting flight", "direct flight",
        "travel photography", "travel blog", "bucket list", "hidden gem", "off the beaten path",
    ],
    "books": [
        "books", "reading", "audiobooks", "bestsellers", "fiction", "non-fiction",
        "mystery", "thriller", "romance", "science fiction", "biography",
        "self-help", "business books", "book club", "kindle", "e-reader",
        "library", "author", "publishing", "literary",
        "memoir", "poetry", "graphic novel", "young adult", "children's books",
        "historical fiction", "fantasy", "dystopian", "true crime", "philosophy",
        "book review", "book recommendation", "reading list", "bookshelf", "bookstore",
        "literary award", "Pulitzer", "Booker Prize", "National Book Award", "debut novel",
    ],
    "culture": [
        "culture", "art", "museum", "gallery", "exhibition", "heritage", "history",
        "performing arts", "theater", "opera", "ballet", "symphony", "orchestra",
        "visual arts", "sculpture", "painting", "photography", "installation art",
        "cultural identity", "diversity", "inclusion", "multicultural", "tradition",
        "folklore", "mythology", "anthropology", "archaeology", "civilization",
        "cultural exchange", "arts funding", "public art", "street art", "graffiti",
        "film festival", "literary festival", "music festival", "dance", "choreography",
        "cultural preservation", "UNESCO", "world heritage", "indigenous", "diaspora",
    ],
    "non_profit": [
        "non-profit", "charity", "donation", "volunteer", "fundraising", "philanthropy",
        "social impact", "community service", "advocacy", "awareness", "cause",
        "humanitarian", "relief", "disaster response", "food bank", "homeless shelter",
        "education access", "clean water", "environmental conservation", "animal welfare",
        "social justice", "equity", "empowerment", "grassroots", "campaign",
        "grant", "endowment", "foundation", "corporate giving", "matching gifts",
        "tax deductible", "501c3", "annual report", "impact report", "transparency",
        "beneficiary", "program evaluation", "capacity building", "sustainability", "outreach",
    ],
    "government": [
        "government", "public service", "civic", "federal", "state", "local",
        "public policy", "regulation", "compliance", "census", "infrastructure",
        "public health", "emergency services", "law enforcement", "fire department",
        "public education", "transportation", "urban planning", "zoning",
        "social security", "Medicare", "Medicaid", "veterans affairs", "defense",
        "public safety", "environmental protection", "energy policy", "trade policy",
        "diplomatic relations", "immigration policy", "tax reform", "budget",
        "public records", "FOIA", "transparency", "accountability", "citizen engagement",
    ],
    "ai": [
        "artificial intelligence", "AI", "machine learning", "deep learning", "neural network",
        "large language model", "LLM", "GPT", "transformer", "natural language processing",
        "computer vision", "generative AI", "AI safety", "AI ethics", "AI alignment",
        "prompt engineering", "fine-tuning", "RAG", "retrieval augmented generation",
        "reinforcement learning", "supervised learning", "unsupervised learning",
        "AI agent", "autonomous AI", "multimodal AI", "foundation model", "open source AI",
        "AI research", "AI governance", "AI regulation", "responsible AI", "explainable AI",
        "inference", "training", "model evaluation", "benchmark", "parameter",
        "diffusion model", "image generation", "text-to-image", "speech recognition",
        "chatbot", "conversational AI", "AI assistant", "copilot", "AI productivity",
        "edge AI", "on-device AI", "AI chip", "tensor processing", "GPU cluster",
    ],
    "ecommerce": [
        "e-commerce", "online shopping", "marketplace", "seller", "buyer", "checkout",
        "cart", "wishlist", "product listing", "product review", "rating",
        "free shipping", "same-day delivery", "return policy", "refund",
        "flash sale", "discount code", "coupon", "promo", "loyalty program",
        "dropshipping", "fulfillment", "warehouse", "inventory", "supply chain",
        "payment gateway", "digital wallet", "buy now pay later", "BNPL", "subscription box",
        "cross-sell", "upsell", "personalization", "recommendation engine", "conversion rate",
        "shopping cart abandonment", "customer retention", "lifetime value", "average order value",
        "social commerce", "live shopping", "influencer marketing", "affiliate marketing",
    ],
    "personal_banking": [
        "personal banking", "checking account", "savings account", "credit card", "debit card",
        "mortgage", "home loan", "auto loan", "personal loan", "line of credit",
        "interest rate", "APY", "APR", "FDIC insured", "direct deposit",
        "mobile banking", "online banking", "ATM", "branch", "bank statement",
        "overdraft protection", "minimum balance", "monthly fee", "no-fee banking",
        "wire transfer", "ACH transfer", "Zelle", "Venmo", "peer-to-peer payment",
        "credit score", "credit report", "credit building", "secured credit card",
        "certificate of deposit", "CD", "money market account", "high-yield savings",
        "financial advisor", "wealth management", "trust", "estate planning", "beneficiary",
    ],
    "beverages": [
        "craft beer", "IPA", "lager", "stout", "ale", "brewing", "distillery",
        "whiskey", "bourbon", "tequila", "vodka", "gin", "rum", "cocktail",
        "energy drink", "caffeine", "electrolytes", "pre-workout", "hydration",
        "coffee", "espresso", "cold brew", "latte", "cappuccino", "matcha",
        "tea", "herbal tea", "green tea", "chai", "oolong", "kombucha",
        "wine", "champagne", "spirits", "mixology", "bartender", "sommelier",
        "tasting notes", "vintage", "barrel aged", "small batch", "limited release",
        "zero sugar", "low calorie", "organic", "fair trade", "single origin",
        "subscription", "delivery", "happy hour", "pairing", "flavor profile",
    ],
    "pharma": [
        "pharmaceutical", "medication", "prescription", "drug", "treatment", "therapy",
        "clinical trial", "FDA approved", "generic", "brand name", "dosage",
        "vaccine", "immunization", "booster", "antibody", "antiviral",
        "side effects", "drug interaction", "pharmacy", "pharmacist", "refill",
        "biologic", "biosimilar", "gene therapy", "precision medicine", "oncology",
        "cardiology", "neurology", "immunology", "dermatology", "endocrinology",
        "patient assistance", "copay card", "insurance coverage", "formulary",
        "research", "peer review", "clinical data", "Phase 3", "regulatory approval",
        "OTC", "over the counter", "supplement", "wellness", "chronic condition",
    ],
    "hospitality": [
        "hotel", "resort", "suite", "check-in", "concierge", "room service",
        "spa", "pool", "fitness center", "business center", "conference room",
        "loyalty program", "points", "elite status", "upgrade", "complimentary",
        "all-inclusive", "bed and breakfast", "boutique hotel", "luxury resort",
        "cruise", "cabin", "deck", "excursion", "port of call", "itinerary",
        "buffet", "fine dining", "entertainment", "casino", "water park",
        "honeymoon", "family vacation", "business travel", "group booking",
        "pet-friendly", "accessibility", "late checkout", "early boarding",
        "travel rewards", "hotel chain", "independent hotel", "villa", "private island",
    ],
    "careers": [
        "job search", "career", "resume", "interview", "hiring", "recruitment",
        "talent acquisition", "job posting", "applicant tracking", "onboarding",
        "employee engagement", "company culture", "remote work", "hybrid work",
        "salary", "benefits", "PTO", "health insurance", "401k match",
        "professional development", "promotion", "performance review", "mentorship",
        "LinkedIn", "networking", "headhunter", "recruiter", "staffing agency",
        "HR", "human resources", "payroll", "compliance", "labor law",
        "diversity", "inclusion", "equity", "DEI", "employee experience",
        "gig economy", "freelance", "contract", "internship", "entry level",
    ],
    "legal": [
        "legal", "lawyer", "attorney", "law firm", "legal advice", "consultation",
        "contract", "agreement", "terms of service", "privacy policy",
        "LLC", "incorporation", "business formation", "trademark", "patent",
        "copyright", "intellectual property", "litigation", "dispute resolution",
        "family law", "divorce", "custody", "estate planning", "will", "trust",
        "personal injury", "workers compensation", "employment law", "immigration",
        "real estate law", "landlord tenant", "eviction", "lease agreement",
        "criminal defense", "DUI", "traffic ticket", "small claims", "mediation",
        "legal document", "notary", "power of attorney", "affidavit", "deposition",
    ],
    "social_media": [
        "social media", "social network", "content creation", "influencer", "followers",
        "likes", "shares", "comments", "engagement", "algorithm", "feed",
        "stories", "reels", "short form video", "live streaming", "TikTok",
        "Instagram", "YouTube", "Twitter", "Reddit", "Discord", "Snapchat",
        "hashtag", "trending", "viral", "meme", "content creator", "UGC",
        "social commerce", "shoppable posts", "creator fund", "monetization",
        "community management", "brand ambassador", "collaboration", "sponsorship",
        "analytics", "reach", "impressions", "click-through rate", "conversion",
        "social listening", "sentiment analysis", "brand reputation", "crisis management",
    ],
    "parenting": [
        "parenting", "baby", "toddler", "newborn", "pregnancy", "maternity",
        "breastfeeding", "formula", "diaper", "nursery", "crib", "stroller",
        "car seat", "baby monitor", "baby food", "milestone", "development",
        "sleep training", "potty training", "daycare", "preschool", "playdate",
        "family", "kids", "children", "teenager", "school", "homework",
        "screen time", "safety", "childproofing", "pediatrician", "vaccination",
        "birthday party", "toy", "game", "activity", "outdoor play",
        "parenting advice", "mom", "dad", "work-life balance", "family time",
    ],
    "logistics": [
        "shipping", "delivery", "logistics", "freight", "supply chain", "warehouse",
        "fulfillment", "last mile", "tracking", "courier", "package",
        "overnight shipping", "express delivery", "ground shipping", "international",
        "customs", "duty", "import", "export", "trade", "tariff",
        "inventory management", "order fulfillment", "pick and pack", "returns",
        "3PL", "third party logistics", "cold chain", "perishable", "fragile",
        "fleet management", "route optimization", "real-time tracking", "proof of delivery",
        "e-commerce fulfillment", "dropship", "cross-docking", "palletization",
        "sustainability", "green logistics", "carbon neutral shipping", "EV fleet",
    ],
    "sustainability": [
        "sustainability", "eco-friendly", "green", "carbon neutral", "carbon footprint",
        "renewable", "recycled", "biodegradable", "compostable", "zero waste",
        "climate change", "global warming", "greenhouse gas", "emissions", "net zero",
        "solar", "wind", "clean energy", "renewable energy", "EV",
        "organic", "non-toxic", "chemical-free", "plant-based", "vegan",
        "fair trade", "ethical sourcing", "supply chain transparency", "B Corp",
        "circular economy", "upcycling", "reuse", "reduce", "repair",
        "ESG", "impact investing", "social responsibility", "corporate sustainability",
        "conservation", "biodiversity", "reforestation", "ocean cleanup", "wildlife protection",
    ],
    "events": [
        "wedding", "engagement", "bridal", "registry", "venue", "caterer",
        "florist", "photographer", "videographer", "DJ", "band", "reception",
        "ceremony", "rehearsal dinner", "save the date", "invitation", "RSVP",
        "bridesmaid", "groomsman", "maid of honor", "best man", "flower girl",
        "wedding dress", "tuxedo", "bouquet", "centerpiece", "seating chart",
        "honeymoon", "destination wedding", "elopement", "micro wedding",
        "party planning", "event coordinator", "decoration", "theme", "favor",
        "anniversary", "birthday", "graduation", "baby shower", "bachelorette",
    ],
}


class TaxonomyLoader:
    """Loads and indexes IAB taxonomy data for realistic topic assignment."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.product_taxonomy: List[Dict] = []
        self.content_taxonomy: List[Dict] = []
        self.product_by_parent: Dict[Optional[str], List[Dict]] = {}
        self.content_by_parent: Dict[Optional[str], List[Dict]] = {}
        self.product_by_id: Dict[str, Dict] = {}
        self.content_by_id: Dict[str, Dict] = {}

    def load(self):
        product_path = self.data_dir / "iab_product_taxonomy_flat.json"
        content_path = self.data_dir / "iab_content_taxonomy_flat.json"

        if product_path.exists():
            with open(product_path) as f:
                self.product_taxonomy = json.load(f)
            for item in self.product_taxonomy:
                parent = item.get("parent_id")
                self.product_by_parent.setdefault(parent, []).append(item)
                self.product_by_id[str(item["id"])] = item

        if content_path.exists():
            with open(content_path) as f:
                self.content_taxonomy = json.load(f)
            for item in self.content_taxonomy:
                parent = item.get("parent_id")
                self.content_by_parent.setdefault(parent, []).append(item)
                self.content_by_id[str(item["id"])] = item

    def get_related_topics(self, root_ids: List[int], count: int = 5) -> List[Dict]:
        """Get a mix of topic IDs related to the given root IDs from the product taxonomy."""
        candidates = []
        for root_id in root_ids:
            root_str = str(root_id)
            if root_str in self.product_by_id:
                candidates.append(self.product_by_id[root_str])
            # Add children
            children = self.product_by_parent.get(root_str, [])
            candidates.extend(children)
            # Add grandchildren
            for child in children:
                grandchildren = self.product_by_parent.get(str(child["id"]), [])
                candidates.extend(grandchildren)

        if not candidates:
            # Fallback to random product taxonomy entries
            candidates = random.sample(self.product_taxonomy, min(20, len(self.product_taxonomy)))

        # Deduplicate candidates by topic ID to avoid unique constraint violations
        seen_ids = set()
        unique_candidates = []
        for c in candidates:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique_candidates.append(c)

        selected = random.sample(unique_candidates, min(count, len(unique_candidates)))
        return [{"iab_id": str(t["id"]), "name": t["name"], "tier": t["tier"]} for t in selected]



def load_creative_bank(data_dir: Path) -> Optional[Dict]:
    """Load the LLM-generated creative bank (required for rich creatives).

    The creative bank is the primary source of headlines, descriptions, and CTAs.
    If missing, the generator will use minimal fallback text. Run
    generate_creative_bank.py first to produce data/creative_bank.json.
    """
    bank_path = data_dir / "creative_bank.json"
    if bank_path.exists():
        with open(bank_path) as f:
            bank = json.load(f)
        industries_count = len(bank.get("industries", {}))
        print(f"  Creative bank loaded: {industries_count} industries from {bank_path}")
        return bank
    print(f"  WARNING: Creative bank not found at {bank_path}")
    print(f"           Run generate_creative_bank.py first for rich creatives.")
    print(f"           Falling back to minimal placeholder text.")
    return None


# ─── Weighted Random Selection ───────────────────────────────────────────────

def weighted_choice(options: List[Tuple[str, int]]) -> str:
    """Select from weighted options. Each option is (value, weight)."""
    values, weights = zip(*options)
    return random.choices(values, weights=weights, k=1)[0]


def weighted_sample(items: List[str], weights: Tuple[int, ...], count: int) -> List[str]:
    """Sample multiple items with weights."""
    return random.choices(items, weights=weights, k=count)



class BulkAdsGenerator:
    def __init__(self, count: int = 10000, seed: int = 42, data_dir: Optional[Path] = None):
        self.count = count
        self.rng = random.Random(seed)
        random.seed(seed)
        self.data_dir = data_dir or DATA_DIR
        self.taxonomy = TaxonomyLoader(self.data_dir)
        self.taxonomy.load()
        self.creative_bank = load_creative_bank(self.data_dir)
        self.used_combos: Set[str] = set()
        self.advertiser_index: Dict[str, int] = {}  # name -> assigned advertiser_id

    def _pick_countries(self) -> List[str]:
        """Pick 1-3 countries with weighted distribution."""
        n = random.choices([1, 2, 3], weights=[50, 35, 15], k=1)[0]
        countries = []
        for _ in range(n):
            c = weighted_choice(COUNTRIES_WEIGHTED)
            if c not in countries:
                countries.append(c)
        return countries if countries else ["US"]

    def _pick_devices(self, industry_type: str) -> List[str]:
        """Pick 1-3 devices weighted by industry type."""
        weights = DEVICE_WEIGHTS.get(industry_type, DEVICE_WEIGHTS["default"])
        n = random.choices([1, 2, 3], weights=[20, 40, 40], k=1)[0]
        selected = set()
        for _ in range(n):
            d = random.choices(DEVICES, weights=weights, k=1)[0]
            selected.add(d)
        return list(selected) if selected else ["desktop"]

    def _pick_entities(self, industry: str, advertiser_name: str) -> List[Dict[str, str]]:
        """Generate 3-6 unique typed entities for a campaign."""
        bank = ENTITY_BANKS.get(industry, DEFAULT_ENTITY_BANK)
        entities = []
        # Track seen (type, lowered_name) to avoid duplicates that would violate
        # the DB unique constraint on (ad_id, entity_id, entity_type)
        seen = set()

        def _add(entity_type: str, name: str):
            key = (entity_type, name.lower())
            if key not in seen:
                seen.add(key)
                entities.append({"type": entity_type, "name": name})

        # Always include the advertiser as a BRAND
        _add("BRAND", advertiser_name)

        # Add 1-2 more brands
        for brand in random.sample(bank["BRAND"], min(2, len(bank["BRAND"]))):
            _add("BRAND", brand)

        # Add 1-2 products
        for product in random.sample(bank["PRODUCT"], min(2, len(bank["PRODUCT"]))):
            _add("PRODUCT", product)

        # Add 0-1 organization
        if random.random() > 0.4 and bank["ORGANIZATION"]:
            _add("ORGANIZATION", random.choice(bank["ORGANIZATION"]))

        # Add 0-1 person
        if random.random() > 0.6 and bank["PERSON"]:
            _add("PERSON", random.choice(bank["PERSON"]))

        return entities[:6]

    def _pick_keywords(self, categories: List[str]) -> List[str]:
        """Pick 5-12 unique keywords from the content categories."""
        all_keywords = set()
        for cat in categories:
            all_keywords.update(KEYWORDS_BY_CATEGORY.get(cat, []))
        if not all_keywords:
            all_keywords = set(KEYWORDS_BY_CATEGORY["technology"])
        all_keywords = list(all_keywords)
        n = random.randint(5, 12)
        return random.sample(all_keywords, min(n, len(all_keywords)))

    def _get_headline(self, industry: str) -> str:
        """Get a headline from the creative bank."""
        if self.creative_bank and industry in self.creative_bank.get("industries", {}):
            headlines = self.creative_bank["industries"][industry].get("headlines", [])
            if headlines:
                return random.choice(headlines)
        # Minimal fallback if creative bank missing for this industry
        return f"Discover {industry} Today"

    def _get_description(self, industry: str) -> str:
        """Get a description from the creative bank."""
        if self.creative_bank and industry in self.creative_bank.get("industries", {}):
            descriptions = self.creative_bank["industries"][industry].get("descriptions", [])
            if descriptions:
                return random.choice(descriptions)
        # Minimal fallback if creative bank missing for this industry
        return f"Explore the latest in {industry}. Find what you need and get started today."

    def _get_cta(self, industry: str, industry_type: str) -> str:
        """Get a CTA from the creative bank, looked up by industry name."""
        if self.creative_bank and industry in self.creative_bank.get("industries", {}):
            ctas = self.creative_bank["industries"][industry].get("ctas", [])
            if ctas:
                return random.choice(ctas)
        # Minimal fallback by industry type
        fallback_ctas = {
            "ecommerce": "Shop Now", "entertainment": "Watch Now", "finance": "Get Started",
            "b2b": "Request Demo", "sports": "Shop Now", "news": "Subscribe Now",
            "technology": "Learn More", "lifestyle": "Discover More",
            "education": "Enroll Now", "health": "Get Started",
        }
        return fallback_ctas.get(industry_type, "Learn More")

    def _pick_campaign_duration(self) -> int:
        """Pick a campaign duration (in days) using a weighted distribution.

        Distribution:
            20% → 1–2 days   (short blitz campaigns)
            40% → 3–15 days  (standard campaigns)
            20% → 16–25 days (extended campaigns)
            20% → 26–30 days (month-long campaigns)
        """
        roll = random.random()
        if roll < 0.20:
            return random.randint(1, 2)
        elif roll < 0.60:
            return random.randint(3, 15)
        elif roll < 0.80:
            return random.randint(16, 25)
        else:
            return random.randint(26, 30)

    def generate_api_request(self, advertiser_id: int, advertiser: Dict, campaign_name: str, industry_meta: Dict) -> Dict:
        """Generate a campaign in API-compatible format (matches CreateCampaignHTTPRequest)."""
        industry = advertiser["industry"]
        industry_type = industry_meta["type"]
        categories = industry_meta["categories"]

        # Dates — start today (with a small random past offset of 0-5 days)
        start_date = datetime.now() - timedelta(days=random.randint(0, 5))
        end_date = start_date + timedelta(days=self._pick_campaign_duration())

        # Budget
        budget = random.randint(advertiser["budget_range"][0], advertiser["budget_range"][1])
        pricing_model = weighted_choice(PRICING_MODELS_WEIGHTED)
        bid_amount = round(random.uniform(1.0, 8.0) if pricing_model == "CPM" else random.uniform(0.5, 3.0), 2)
        daily_budget_val = round(budget / max((end_date - start_date).days, 1), 2)

        # Creative
        headline = self._get_headline(industry)
        description = self._get_description(industry)
        cta = self._get_cta(industry, industry_type)
        creative_type = weighted_choice(CREATIVE_TYPES_WEIGHTED)

        # Targeting
        root_ids = industry_meta.get("product_iab_root", [])
        topics = self.taxonomy.get_related_topics(root_ids, count=random.randint(2, 6))
        topic_ids = [int(t["iab_id"]) for t in topics]
        keywords = self._pick_keywords(categories)
        entities = self._pick_entities(industry, advertiser["name"])
        countries = self._pick_countries()
        devices = self._pick_devices(industry_type)

        campaign_status = weighted_choice(CAMPAIGN_STATUS_WEIGHTED)
        creative_status = weighted_choice(CREATIVE_STATUS_WEIGHTED)

        return {
            "advertiser_id": advertiser_id,
            "campaign": {
                "name": campaign_name,
                "status": campaign_status,
                "budget": float(budget),
                "currency": "USD",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "ad_set": {
                "name": f"{campaign_name} - Ad Set",
                "bid_amount": bid_amount,
                "daily_budget": daily_budget_val,
                "pricing_model": pricing_model
            },
            "creative": {
                "headline": headline,
                "description": description,
                "image_url": random.choice(SAMPLE_IMAGES) + f"?w=1200&h=630&fit=crop&q=80",
                "call_to_action": cta,
                "landing_page_url": advertiser["website"],
                "status": creative_status,
                "creative_type": creative_type
            },
            "targeting": {
                "keywords": keywords,
                "topics": topic_ids,
                "entities": entities,
                "countries": countries,
                "devices": devices
            }
        }

    def generate(self) -> List[Dict]:
        """Generate all campaign requests in API-compatible format."""
        api_requests = []

        # Assign advertiser IDs (simulating sequential creation)
        for i, adv in enumerate(ADVERTISERS):
            self.advertiser_index[adv["name"]] = i + 1

        # Calculate campaigns per advertiser
        num_advertisers = len(ADVERTISERS)
        base_per_adv = self.count // num_advertisers
        remainder = self.count % num_advertisers

        ad_id = 1
        for adv_idx, advertiser in enumerate(ADVERTISERS):
            industry = advertiser["industry"]
            industry_meta = INDUSTRIES.get(industry)
            if not industry_meta:
                continue

            # How many campaigns for this advertiser
            num_campaigns = base_per_adv + (1 if adv_idx < remainder else 0)
            if num_campaigns == 0:
                continue

            campaign_templates = CAMPAIGN_TEMPLATES.get(industry, ["Campaign"])
            advertiser_id = self.advertiser_index[advertiser["name"]]

            for camp_idx in range(num_campaigns):
                # Pick campaign name (cycle through templates, add suffix for uniqueness)
                template = campaign_templates[camp_idx % len(campaign_templates)]
                suffix = f" #{camp_idx // len(campaign_templates) + 1}" if camp_idx >= len(campaign_templates) else ""
                campaign_name = f"{template}{suffix}"

                api_req = self.generate_api_request(advertiser_id, advertiser, campaign_name, industry_meta)
                api_requests.append(api_req)
                ad_id += 1

                if ad_id % 1000 == 0:
                    print(f"  Generated {ad_id}/{self.count} campaigns...")

        return api_requests

    def to_inventory_format(self, api_req: Dict, ad_id: int) -> Dict:
        """Convert an API-format request to ads_inventory.json format.

        The inventory format is what generate_eval_fixtures.py and the Go
        evaluation framework (ad_generator.go) expect.
        """
        advertiser_id = api_req["advertiser_id"]
        # Look up advertiser name from index (reverse lookup)
        advertiser_name = ""
        for name, aid in self.advertiser_index.items():
            if aid == advertiser_id:
                advertiser_name = name
                break

        campaign = api_req["campaign"]
        creative = api_req["creative"]
        targeting = api_req["targeting"]
        ad_set = api_req["ad_set"]

        budget = campaign["budget"]
        start_date = campaign["start_date"]
        end_date = campaign["end_date"]
        daily_budget_val = ad_set["daily_budget"]

        # Simulate runtime stats
        days_active = max((datetime.strptime(end_date, "%Y-%m-%d") -
                          datetime.strptime(start_date, "%Y-%m-%d")).days, 1)
        impressions = random.randint(50000, 500000)
        ctr = random.uniform(0.005, 0.02)
        clicks = int(impressions * ctr)
        spend = round(daily_budget_val * days_active * random.uniform(0.4, 0.9), 2)
        remaining_budget = round(max(budget - spend, 0), 2)

        # Convert topic IDs (ints) to topic objects {name, iab_id, tier}
        topic_objects = []
        for topic_id in targeting.get("topics", []):
            tid_str = str(topic_id)
            if tid_str in self.taxonomy.product_by_id:
                t = self.taxonomy.product_by_id[tid_str]
                topic_objects.append({
                    "name": t["name"],
                    "iab_id": tid_str,
                    "tier": t["tier"],
                })
            else:
                topic_objects.append({
                    "name": f"Topic {topic_id}",
                    "iab_id": tid_str,
                    "tier": 1,
                })

        # Convert entity objects [{type, name}] to plain string list
        entity_names = [e["name"] for e in targeting.get("entities", [])]

        # Derive content_category from industry
        industry_name = ""
        for adv in ADVERTISERS:
            if adv["name"] == advertiser_name:
                industry_name = adv["industry"]
                break
        industry_meta = INDUSTRIES.get(industry_name, {})
        content_category = industry_meta.get("categories", ["lifestyle"])[0]

        return {
            "id": f"{ad_id:03d}",
            "advertiser": {
                "name": advertiser_name,
                "budget": budget,
                "currency": "USD",
            },
            "campaign": {
                "name": campaign["name"],
            },
            "creative": {
                "headline": creative["headline"],
                "description": creative["description"],
                "image_url": creative.get("image_url", ""),
                "call_to_action": creative.get("call_to_action", "Learn More"),
                "landing_page_url": creative["landing_page_url"],
            },
            "targeting": {
                "keywords": targeting["keywords"],
                "topics": topic_objects,
                "entities": entity_names,
                "countries": targeting.get("countries", ["US"]),
                "languages": ["en"],
            },
            "content_category": content_category,
            "daily_budget": daily_budget_val,
            "remaining_budget": remaining_budget,
            "status": campaign.get("status", "ACTIVE").lower(),
            "start_date": start_date,
            "end_date": end_date,
            "created_at": datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
        }

    def generate_inventory(self) -> List[Dict]:
        """Generate ads directly in ads_inventory.json format."""
        api_requests = self.generate()
        inventory_ads = []
        for i, api_req in enumerate(api_requests):
            ad_id = i + 1
            inventory_ads.append(self.to_inventory_format(api_req, ad_id))
        return inventory_ads

    def print_stats(self, requests: List[Dict]):
        """Print inventory statistics from API-format requests."""
        print(f"\n{'='*60}")
        print(f"INVENTORY STATISTICS")
        print(f"{'='*60}")
        print(f"Total campaigns: {len(requests)}")

        # Unique advertisers
        adv_ids = set(req["advertiser_id"] for req in requests)
        print(f"Unique advertiser IDs: {len(adv_ids)}")

        # Status breakdown
        statuses = {}
        for req in requests:
            s = req["campaign"]["status"]
            statuses[s] = statuses.get(s, 0) + 1
        print(f"\n--- Status Breakdown ---")
        for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
            print(f"  {status}: {count} ({count/len(requests)*100:.1f}%)")

        # Industry breakdown (via advertiser_id -> ADVERTISERS lookup)
        id_to_industry = {i + 1: a["industry"] for i, a in enumerate(ADVERTISERS)}
        industries = {}
        for req in requests:
            ind = id_to_industry.get(req["advertiser_id"], "unknown")
            industries[ind] = industries.get(ind, 0) + 1
        print(f"\n--- Industry Breakdown (top 20) ---")
        for ind, count in sorted(industries.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"  {ind}: {count} ({count/len(requests)*100:.1f}%)")

        # Creative type breakdown
        creative_types = {}
        for req in requests:
            ct = req["creative"]["creative_type"]
            creative_types[ct] = creative_types.get(ct, 0) + 1
        print(f"\n--- Creative Type Breakdown ---")
        for ct, count in sorted(creative_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {ct}: {count} ({count/len(requests)*100:.1f}%)")

        # Pricing model breakdown
        pricing = {}
        for req in requests:
            pm = req["ad_set"]["pricing_model"]
            pricing[pm] = pricing.get(pm, 0) + 1
        print(f"\n--- Pricing Model Breakdown ---")
        for pm, count in sorted(pricing.items(), key=lambda x: x[1], reverse=True):
            print(f"  {pm}: {count} ({count/len(requests)*100:.1f}%)")

        # IAB topic coverage
        all_topic_ids = set()
        for req in requests:
            for topic_id in req["targeting"]["topics"]:
                all_topic_ids.add(topic_id)
        print(f"\n--- IAB Topic Coverage ---")
        print(f"  Unique IAB topic IDs used: {len(all_topic_ids)}")
        print(f"  Product taxonomy size: {len(self.taxonomy.product_taxonomy)}")
        if self.taxonomy.product_taxonomy:
            print(f"  Coverage: {len(all_topic_ids)/len(self.taxonomy.product_taxonomy)*100:.1f}%")

        # Entity type distribution
        entity_types = {}
        for req in requests:
            for e in req["targeting"]["entities"]:
                t = e["type"]
                entity_types[t] = entity_types.get(t, 0) + 1
        print(f"\n--- Entity Type Distribution ---")
        for t, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {t}: {count}")

        # Country distribution
        country_counts = {}
        for req in requests:
            for c in req["targeting"]["countries"]:
                country_counts[c] = country_counts.get(c, 0) + 1
        print(f"\n--- Country Distribution ---")
        for c, count in sorted(country_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {c}: {count}")

        # Device distribution
        device_counts = {}
        for req in requests:
            for d in req["targeting"]["devices"]:
                device_counts[d] = device_counts.get(d, 0) + 1
        print(f"\n--- Device Distribution ---")
        for d, count in sorted(device_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {d}: {count}")

        # Budget stats
        budgets = [req["campaign"]["budget"] for req in requests]
        print(f"\n--- Budget Statistics ---")
        print(f"  Total budget: ${sum(budgets):,.2f}")
        print(f"  Average budget: ${sum(budgets)/len(budgets):,.2f}")
        print(f"  Min budget: ${min(budgets):,.2f}")
        print(f"  Max budget: ${max(budgets):,.2f}")

        # Keyword diversity
        all_keywords = set()
        for req in requests:
            all_keywords.update(req["targeting"]["keywords"])
        print(f"\n--- Keyword Diversity ---")
        print(f"  Unique keywords: {len(all_keywords)}")
        print(f"  Avg keywords per campaign: {sum(len(req['targeting']['keywords']) for req in requests)/len(requests):.1f}")


def validate_api_requests(requests: List[Dict]) -> List[str]:
    """Validate all API requests have required fields populated."""
    errors = []
    for i, req in enumerate(requests):
        prefix = f"Request {i+1}"
        if not req.get("advertiser_id"):
            errors.append(f"{prefix}: missing advertiser_id")
        camp = req.get("campaign", {})
        if not camp.get("name"):
            errors.append(f"{prefix}: missing campaign.name")
        if not camp.get("start_date"):
            errors.append(f"{prefix}: missing campaign.start_date")
        creative = req.get("creative", {})
        if not creative.get("headline"):
            errors.append(f"{prefix}: missing creative.headline")
        if not creative.get("landing_page_url"):
            errors.append(f"{prefix}: missing creative.landing_page_url")
        targeting = req.get("targeting", {})
        if not targeting.get("keywords"):
            errors.append(f"{prefix}: empty targeting.keywords")
        if not targeting.get("topics"):
            errors.append(f"{prefix}: empty targeting.topics")
        if not targeting.get("entities"):
            errors.append(f"{prefix}: empty targeting.entities")
        if not targeting.get("countries"):
            errors.append(f"{prefix}: empty targeting.countries")
        if not targeting.get("devices"):
            errors.append(f"{prefix}: empty targeting.devices")
        # Validate entity types
        for entity in targeting.get("entities", []):
            if entity.get("type") not in ("BRAND", "PRODUCT", "ORGANIZATION", "PERSON"):
                errors.append(f"{prefix}: invalid entity type '{entity.get('type')}'")
        # Validate pricing model
        ad_set = req.get("ad_set", {})
        if ad_set.get("pricing_model") not in ("CPM", "CPC"):
            errors.append(f"{prefix}: invalid pricing_model '{ad_set.get('pricing_model')}'")
        # Validate creative type
        if creative.get("creative_type") not in ("banner", "native", "video"):
            errors.append(f"{prefix}: invalid creative_type '{creative.get('creative_type')}'")
    return errors


def _format_count(n: int) -> str:
    """Format count for filenames: 10000 -> 10k, 100000 -> 100k, 5000 -> 5k."""
    if n >= 1000 and n % 1000 == 0:
        return f"{n // 1000}k"
    return str(n)


def main():
    parser = argparse.ArgumentParser(
        description="Generate realistic ad campaign inventories for testing.",
        epilog="""
Examples:
  python bulk_ads_generator.py                                # 10k campaigns, API format
  python bulk_ads_generator.py --count 500 --format inventory # 500 ads → ads_inventory.json
  python bulk_ads_generator.py --count 50000                  # 50k campaigns, API format
  python bulk_ads_generator.py --count 500 --seed 99          # 500 campaigns, custom seed
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--count", type=int, default=10000,
                        help="Number of ads to generate (default: 10000).")
    parser.add_argument("--output-dir", type=str, default=str(DATA_DIR),
                        help="Output directory for generated files")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--no-validate", action="store_true",
                        help="Skip validation step (faster for very large counts)")
    parser.add_argument("--no-stats", action="store_true",
                        help="Skip stats printing (faster for very large counts)")
    parser.add_argument("--format", choices=["api", "inventory", "both"], default="api",
                        help="Output format: 'api' (CreateCampaignHTTPRequest, default), "
                             "'inventory' (writes data/ads_inventory.json), or "
                             "'both' (generates both API + inventory in one pass)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    count_label = _format_count(args.count)

    print(f"Generating {args.count:,} ad campaign inventories...")
    print(f"  Advertisers: {len(ADVERTISERS)}")
    print(f"  Industries: {len(INDUSTRIES)}")
    print(f"  Campaigns per advertiser (avg): ~{args.count // len(ADVERTISERS)}")
    print(f"  Output directory: {output_dir}")
    print(f"  Random seed: {args.seed}")
    print(f"  Format: {args.format}")

    generator = BulkAdsGenerator(
        count=args.count,
        seed=args.seed,
        data_dir=Path(args.output_dir) if args.output_dir != str(DATA_DIR) else DATA_DIR,
    )

    def _write_inventory(gen, out_dir):
        """Generate and write ads_inventory.json."""
        inventory_ads = gen.generate_inventory()
        inv_path = out_dir / "ads_inventory.json"
        with open(inv_path, "w", encoding="utf-8") as f:
            json.dump(inventory_ads, f, indent=2, ensure_ascii=False)
        size_mb = inv_path.stat().st_size / 1024 / 1024
        print(f"\nWrote {len(inventory_ads)} ads ({size_mb:.1f} MB) to {inv_path}")
        cats = {}
        for ad in inventory_ads:
            c = ad.get("content_category", "unknown")
            cats[c] = cats.get(c, 0) + 1
        print(f"\n--- Content Category Distribution ---")
        for c, n in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"  {c}: {n} ({n/len(inventory_ads)*100:.1f}%)")
        return inv_path

    def _write_api(gen, out_dir, clabel, validate, stats):
        """Generate and write campaign_requests + advertisers_list."""
        api_requests = gen.generate()
        api_path = out_dir / f"campaign_requests_{clabel}.json"
        print(f"\nWriting campaign requests to {api_path}...")
        with open(api_path, "w", encoding="utf-8") as f:
            json.dump(api_requests, f, indent=2, ensure_ascii=False)
        size_mb = api_path.stat().st_size / 1024 / 1024
        print(f"  Wrote {len(api_requests):,} requests ({size_mb:.1f} MB)")

        if validate:
            print("\nValidating API requests...")
            errors = validate_api_requests(api_requests)
            if errors:
                print(f"  VALIDATION ERRORS ({len(errors)}):")
                for err in errors[:20]:
                    print(f"    - {err}")
                if len(errors) > 20:
                    print(f"    ... and {len(errors) - 20} more")
            else:
                print(f"  All {len(api_requests):,} requests passed validation!")

        if stats:
            gen.print_stats(api_requests)

        advertisers_path = out_dir / "advertisers_list.json"
        advertisers_list = [
            {"id": gen.advertiser_index[a["name"]], "name": a["name"],
             "website": a["website"], "industry": a["industry"]}
            for a in ADVERTISERS
        ]
        with open(advertisers_path, "w", encoding="utf-8") as f:
            json.dump(advertisers_list, f, indent=2, ensure_ascii=False)
        print(f"\nWrote advertisers list to {advertisers_path} ({len(advertisers_list)} advertisers)")
        print(f"\nTo seed into the server:")
        print(f"  go run ./tests/cmd/seed --from-file={api_path} --workers=10")
        return api_path

    if args.format == "inventory":
        _write_inventory(generator, output_dir)
    elif args.format == "both":
        print("\n═══ Generating API format ═══")
        api_path = _write_api(generator, output_dir, count_label,
                              not args.no_validate, not args.no_stats)
        print("\n═══ Generating inventory format ═══")
        # Re-create generator with same seed for deterministic inventory
        inv_generator = BulkAdsGenerator(
            count=args.count,
            seed=args.seed,
            data_dir=Path(args.output_dir) if args.output_dir != str(DATA_DIR) else DATA_DIR,
        )
        _write_inventory(inv_generator, output_dir)
        print(f"\n✅ Both formats generated. Next steps:")
        print(f"  1. Seed DB:    go run ./tests/cmd/seed --from-file={api_path} --workers=10")
        print(f"  2. Preprocess: cd python && python3 scripts/preprocess_all.py --fast --workers 4")
        print(f"  3. Simulate:   make simulate")
    else:
        _write_api(generator, output_dir, count_label,
                   not args.no_validate, not args.no_stats)


if __name__ == "__main__":
    main()
