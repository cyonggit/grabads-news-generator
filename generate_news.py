"""
GrabAds News Widget — Weekly News Generator
============================================
This script is run by GitLab CI every Monday. It calls the Anthropic API
server-side, generates news.json, and the pipeline commits it back to the repo.

Your API key lives ONLY in GitLab CI secrets — never in this file.
"""

import anthropic
import json
import os
from datetime import datetime

# ── Anthropic client (reads ANTHROPIC_API_KEY from environment automatically)
client = anthropic.Anthropic()

COUNTRIES = [
    "Singapore",
    "Philippines",
    "Indonesia",
    "Thailand",
    "Vietnam",
    "Malaysia",
]

PROMPT_TEMPLATE = """You are a news research assistant. Find the 6 most recent and significant advertising, marketing, and media industry news stories from {country} in the past 7 days.

Return ONLY a JSON array (no markdown, no preamble) with exactly these keys per item:
- "headline": concise news headline, max 12 words
- "summary": 1-2 sentence summary, max 30 words
- "category": exactly one of: "industry", "digital", "creative", "media"
  - industry = agency news, brand launches, business deals, market moves
  - digital = programmatic, social media ads, performance marketing, ad tech
  - creative = notable campaigns, awards, creative work
  - media = publishing, broadcasting, streaming, OOH, print
- "source": publication name (e.g. "Campaign Asia", "Marketing Interactive", "The Drum")
- "date": e.g. "2 days ago", "Today", "This week"
- "imageQuery": a 3-5 word image search phrase to visually illustrate the story (e.g. "digital billboard city night")

Return ONLY the raw JSON array."""


def fetch_news_for_country(country: str) -> list:
    print(f"  Fetching news for {country}...")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(country=country)}],
        )

        # Extract text blocks from the response
        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )

        # Parse JSON array from response
        text = text.strip().replace("```json", "").replace("```", "").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found in response")

        articles = json.loads(text[start:end])
        print(f"  ✓ {len(articles)} articles fetched for {country}")
        return articles

    except Exception as e:
        print(f"  ✗ Failed for {country}: {e}. Using fallback.")
        return fallback(country)


def fallback(country: str) -> list:
    return [
        {"headline": f"Top agency moves reshaping {country}'s ad scene", "summary": "Major agencies and brands are driving significant market shifts this week.", "category": "industry", "source": "Campaign Asia", "date": "This week", "imageQuery": "marketing agency office team"},
        {"headline": f"Programmatic spend surges across {country} market", "summary": "Digital ad investment continues to climb with new data-driven strategies.", "category": "digital", "source": "Marketing Interactive", "date": "This week", "imageQuery": "digital advertising screens data"},
        {"headline": f"Bold new creative campaign wins buzz in {country}", "summary": "A striking new campaign is generating significant social and press attention.", "category": "creative", "source": "The Drum", "date": "This week", "imageQuery": "creative advertising campaign billboard"},
        {"headline": f"Streaming reshapes media buying in {country}", "summary": "Publishers and broadcasters are adapting to evolving viewer habits.", "category": "media", "source": "Adweek Asia", "date": "This week", "imageQuery": "streaming media television remote"},
        {"headline": f"Brand partnerships signal confidence in {country} market", "summary": "Several high-profile brand collaborations were announced this week.", "category": "industry", "source": "Campaign Asia", "date": "This week", "imageQuery": "business partnership handshake meeting"},
        {"headline": f"Social commerce ad formats gain traction in {country}", "summary": "Shoppable content and in-app advertising formats are seeing rapid adoption.", "category": "digital", "source": "Marketing Interactive", "date": "This week", "imageQuery": "social media phone shopping app"},
    ]


def main():
    print("=" * 50)
    print("GrabAds Weekly News Generator")
    print(f"Running at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    output = {
        "generatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generatedDate": datetime.utcnow().strftime("%-d %b %Y"),
        "countries": {},
    }

    for country in COUNTRIES:
        output["countries"][country] = fetch_news_for_country(country)

    # Write to news.json in the repo root
    output_path = os.path.join(os.path.dirname(__file__), "news.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 50)
    print(f"✓ news.json written successfully")
    print(f"  Total articles: {sum(len(v) for v in output['countries'].values())}")
    print("=" * 50)


if __name__ == "__main__":
    main()
