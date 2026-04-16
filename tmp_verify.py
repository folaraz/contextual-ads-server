#!/usr/bin/env python3
import json

iab_map = {
    "Sports": "sports", "News and Politics": "education",
    "Business and Finance": "finance", "Personal Finance": "finance",
    "Technology & Computing": "technology", "Medical Health": "healthcare",
    "Healthy Living": "healthcare", "Travel": "travel",
    "Education": "education", "Food & Drink": "food-beverage",
    "Television": "entertainment", "Movies": "entertainment",
    "Music and Audio": "entertainment", "Pop Culture": "entertainment",
    "Video Gaming": "entertainment", "Hobbies & Interests": "e-commerce",
    "Careers": "education", "Family and Relationships": "e-commerce",
    "Fine Art": "entertainment", "Science": "technology",
    "Events and Attractions": "entertainment", "Religion & Spirituality": "education",
    "Soccer": "sports", "Tennis": "sports", "Basketball": "sports",
    "Football": "sports", "Olympic Sports": "sports", "Sporting Events": "sports",
    "Summer Olympic Sports": "sports", "Swimming": "sports",
    "Politics": "education", "International News": "education",
    "Crime": "education", "Law": "education",
    "Economy": "finance", "Business": "finance",
    "Financial Assistance": "finance", "Frugal Living": "finance",
    "Computing": "technology", "Artificial Intelligence": "technology",
    "Pharmaceutical Drugs": "healthcare", "Diseases and Conditions": "healthcare",
    "Senior Health": "healthcare", "Wellness": "healthcare",
    "Travel Locations": "travel", "Travel Type": "travel",
    "Environment": "technology", "Biological Sciences": "technology",
    "Drama TV": "entertainment", "Disabled Sports": "sports", "Extreme Sports": "sports",
}

theme_map = {
    "finance": "finance", "technology": "technology", "education": "education",
    "automotive": "automotive", "travel": "travel",
    "football": "sports", "basketball": "sports", "soccer": "sports",
    "tennis": "sports", "sports": "sports",
    "movies": "entertainment", "music": "entertainment",
    "entertainment": "entertainment", "gaming": "entertainment", "books": "entertainment",
    "lifestyle": "fashion", "food": "food-beverage", "health": "healthcare",
    "home": "e-commerce", "pets": "e-commerce", "real_estate": "e-commerce",
    "politics": "education", "news": "education",
}

with open("data/eval/nlp_page_contexts.json") as f:
    pages = json.load(f)

categories = {}
uncategorized = 0

for p in pages:
    theme = p.get("theme", "")
    industry = theme_map.get(theme, "")
    if not industry:
        best_score = -1
        for t in p.get("topics", {}).values():
            ind = iab_map.get(t.get("name", ""))
            if ind and t.get("score", 0) > best_score:
                best_score = t["score"]
                industry = ind
    if industry:
        categories[industry] = categories.get(industry, 0) + 1
    else:
        uncategorized += 1
        title = p.get("meta_data", {}).get("title", "")[:60]
        topics = [t.get("name", "") for t in p.get("topics", {}).values()]
        print(f"  UNCATEGORIZED: {title}")
        print(f"    Topics: {topics}")

print()
print("Category distribution after fix:")
for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f"  {cat:20s} {count}")
print(f"  {'(uncategorized)':20s} {uncategorized}")
print(f"Total: {sum(categories.values()) + uncategorized}")

