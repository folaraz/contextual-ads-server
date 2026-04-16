#!/usr/bin/env python3
"""
Generate Creative Bank using Claude API (One-Time Script)

Generates diverse ad creatives (headlines, descriptions, CTAs) for 70+ industry
verticals using Claude API. Output is saved as a static JSON file that the
bulk_ads_generator.py uses for creative content.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python generate_creative_bank.py [--output ../data/creative_bank.json]

This script runs ONCE and produces a static file. After generation, there is
no runtime API dependency - the bulk generator uses the file if present,
falls back to built-in templates otherwise.

"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR.parent.parent / "data" / "creative_bank.json"

INDUSTRIES = [
    # Fashion & Lifestyle
    "Fashion Retail", "Beauty", "Athletic Wear", "Fashion Accessories", "Luxury Goods",
    # Entertainment
    "Music Streaming", "Event Tickets", "Musical Instruments", "Streaming", "Movie Theaters",
    "Gaming",
    # Finance
    "Financial Services", "Investment App", "Cryptocurrency", "Financial Planning",
    "Insurance", "FinTech", "Personal Banking",
    # Sports
    "Sports Streaming", "Sports Apparel", "Sports Equipment", "Sports Merchandise",
    # Technology
    "Consumer Electronics", "Software & Cloud", "Software", "Electric Vehicles", "Computer Hardware",
    "Telecom", "Technology", "AI", "Cybersecurity",
    # News & Media
    "News Media", "Audiobooks",
    # Real Estate & Home
    "Real Estate", "Home & Garden",
    # Education
    "EdTech", "Education",
    # Food & Beverage
    "Food Delivery", "Restaurants", "Craft Beer & Spirits", "Energy Drinks", "Coffee & Tea",
    # Health & Wellness
    "Fitness & Wellness", "Healthcare", "HealthTech", "Pharmaceuticals", "Supplements & Nutrition",
    # Travel & Hospitality
    "Travel", "Airlines", "Hotels & Resorts", "Cruises",
    # Automotive
    "Automotive",
    # B2B / SaaS
    "B2B SaaS", "HR & Recruiting", "Accounting & Tax",
    # E-commerce
    "E-commerce",
    # Pets
    "Pet Products",
    # Culture & Society
    "Culture", "Non-Profit", "Government", "Politics",
    # Social & Creator
    "Social Media", "Creator Economy",
    # Professional Services
    "Legal Services",
    # Family
    "Baby & Parenting", "Kids & Family Entertainment",
    # Home Services & Utilities
    "Home Services", "Cleaning & Household", "Solar & Renewable Energy",
    # Privacy & Security
    "Identity & Privacy",
    # Weddings
    "Weddings",
    # Logistics
    "Logistics & Shipping",
    # Sustainability
    "Sustainability",
]

SYSTEM_PROMPT = """You are an expert advertising copywriter. Generate realistic, diverse ad creatives
for the given industry. Return valid JSON only, no markdown."""

# Separate prompts for each creative type to keep responses small and reliable
HEADLINES_PROMPT = """Generate 100 unique ad headlines for the "{industry}" industry.

Return a JSON object: {{"headlines": ["headline1", "headline2", ...]}}

Requirements:
- Under 100 characters each
- Concise, punchy, action-oriented
- Varied angles: urgency, value, emotion, curiosity, social proof
- No placeholder text like %s or {{{{}}}}
- Sound like actual ads from real {industry} companies"""

DESCRIPTIONS_PROMPT = """Generate 75 unique ad descriptions for the "{industry}" industry.

Return a JSON object: {{"descriptions": ["desc1", "desc2", ...]}}

Requirements:
- 2-4 sentences each, under 400 characters
- Benefit-focused, sell the value
- Varied tones: professional, friendly, urgent, aspirational
- No placeholder text like %s or {{{{}}}}
- Sound like actual ads from real {industry} companies"""

CTAS_PROMPT = """Generate 50 unique call-to-action buttons for the "{industry}" industry.

Return a JSON object: {{"ctas": ["cta1", "cta2", ...]}}

Requirements:
- 2-3 words max each
- Action-oriented
- No placeholder text like %s or {{{{}}}}
- Sound like actual CTAs from real {industry} companies"""


def extract_json(text: str) -> dict:
    """Extract and parse JSON from a response that may contain markdown fences."""
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    return json.loads(text)


def api_call_with_retries(client, model: str, prompt: str, max_retries: int = 3) -> dict:
    """Make a single Claude API call with retries and JSON extraction."""
    for attempt in range(1, max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            if message.stop_reason != "end_turn":
                print(f"      ⚠ Response truncated (stop_reason={message.stop_reason}), retrying...")
                if attempt < max_retries:
                    time.sleep(2)
                    continue

            return extract_json(response_text)
        except json.JSONDecodeError as e:
            print(f"      ⚠ JSON parse error on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(2)
            else:
                raise
        except Exception as e:
            print(f"      ⚠ API error on attempt {attempt}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(2)
            else:
                raise


def generate_for_industry(client, industry: str, model: str) -> dict:
    """Generate creatives for a single industry using 3 smaller API calls."""
    result = {}

    print(f"headlines...")
    data = api_call_with_retries(client, model, HEADLINES_PROMPT.format(industry=industry))
    result["headlines"] = data.get("headlines", [])

    print(f"descriptions...")
    data = api_call_with_retries(client, model, DESCRIPTIONS_PROMPT.format(industry=industry))
    result["descriptions"] = data.get("descriptions", [])

    print(f"ctas...")
    data = api_call_with_retries(client, model, CTAS_PROMPT.format(industry=industry))
    result["ctas"] = data.get("ctas", [])

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate creative bank using Claude API")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="Output file path")
    parser.add_argument("--model", type=str, default="claude-haiku-4-5-20251001", help="Claude model to use")
    parser.add_argument("--industries", type=str, nargs="+", help="Specific industries to generate (default: all)")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed.")
        print("  pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    target_industries = args.industries or INDUSTRIES

    output_path = Path(args.output)
    existing_bank = {"industries": {}}
    if output_path.exists():
        with open(output_path) as f:
            existing_bank = json.load(f)
        print(f"Loaded existing bank with {len(existing_bank.get('industries', {}))} industries")

    bank = existing_bank
    total = len(target_industries)

    for i, industry in enumerate(target_industries, 1):
        if industry in bank.get("industries", {}) and industry not in (args.industries or []):
            print(f"  [{i}/{total}] {industry} - already exists, skipping")
            continue

        print(f"  [{i}/{total}] Generating creatives for {industry}...")
        try:
            result = generate_for_industry(client, industry, args.model)
            bank.setdefault("industries", {})[industry] = result
            print(f"    -> {len(result.get('headlines', []))} headlines, "
                  f"{len(result.get('descriptions', []))} descriptions, "
                  f"{len(result.get('ctas', []))} CTAs")
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=2, ensure_ascii=False)

    total_headlines = sum(len(v.get("headlines", [])) for v in bank["industries"].values())
    total_descriptions = sum(len(v.get("descriptions", [])) for v in bank["industries"].values())
    total_ctas = sum(len(v.get("ctas", [])) for v in bank["industries"].values())

    print(f"\nCreative bank saved to {output_path}")
    print(f"  Industries: {len(bank['industries'])}")
    print(f"  Total headlines: {total_headlines}")
    print(f"  Total descriptions: {total_descriptions}")
    print(f"  Total CTAs: {total_ctas}")


if __name__ == "__main__":
    main()
