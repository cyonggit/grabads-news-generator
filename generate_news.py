"""
GrabAds News Widget -- Weekly News Generator (Free RSS Version)
==============================================================
Pulls news from free RSS feeds. No API key or credits required.
Run by GitHub Actions every Monday. Outputs news.json for the widget.

Dependencies: feedparser, python-dateutil, requests
"""

import json
import os
import re
import hashlib
import requests
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser

# ── RSS feeds
RSS_FEEDS = [
    {"name": "Campaign Asia",         "url": "https://www.campaignasia.com/rss"},
    {"name": "Campaign Asia",         "url": "https://www.campaignasia.com/feed"},
    {"name": "Marketing Interactive", "url": "https://www.marketing-interactive.com/feed"},
    {"name": "Marketing Interactive", "url": "https://www.marketing-interactive.com/rss"},
    {"name": "The Drum",              "url": "https://www.thedrum.com/rss"},
    {"name": "The Drum",              "url": "https://www.thedrum.com/feed"},
    {"name": "Adweek",                "url": "https://www.adweek.com/feed/"},
    {"name": "Ad Age",                "url": "https://adage.com/rss"},
    {"name": "Ad Age",                "url": "https://adage.com/feed"},
    {"name": "Marketing Week",        "url": "https://www.marketingweek.com/feed/"},
    {"name": "MediaPost",             "url": "https://www.mediapost.com/rss/"},
    {"name": "Search Engine Land",    "url": "https://searchengineland.com/feed"},
    {"name": "Mumbrella",             "url": "https://mumbrella.com.au/feed"},
]

# ── STRICT ads/marketing relevance filter
# Articles must contain at least one of these to be included at all
ADS_RELEVANCE_KEYWORDS = [
    "advertis", "marketing", "agency", "brand", "campaign", "media buy",
    "programmatic", "ad tech", "adtech", "martech", "creative", "ad spend",
    "digital media", "social media", "influencer", "content marketing",
    "out-of-home", "ooh", "dooh", "retail media", "retail network",
    "ecommerce advertising", "search advertising", "display advertising",
    "media planning", "media agency", "ad network", "ad platform",
    "ad revenue", "ad market", "advertising industry", "media industry",
    "publisher", "broadcasting", "streaming ads", "connected tv", "ctv",
    "data-driven", "first-party data", "targeting", "audience",
    "grabads", "grab ads",
]

# ── Country keywords
COUNTRY_KEYWORDS = {
    "Singapore":   ["singapore", "singaporean"],
    "Philippines": ["philippines", "philippine", "filipino", "filipina", "manila", "cebu", "davao"],
    "Indonesia":   ["indonesia", "indonesian", "jakarta", "surabaya", "bandung", "bali"],
    "Thailand":    ["thailand", "thai", "bangkok", "phuket", "chiang mai"],
    "Vietnam":     ["vietnam", "vietnamese", "hanoi", "ho chi minh", "saigon", "hcmc"],
    "Malaysia":    ["malaysia", "malaysian", "kuala lumpur", "penang", "johor"],
    "Taiwan":      ["taiwan", "taiwanese", "taipei", "kaohsiung", "taichung"],
}

# ── Regional keywords for APAC-level articles
REGIONAL_KEYWORDS = [
    "southeast asia", "sea region", "apac", "asia pacific",
    "asia-pacific", "asean", "across asia", "asian market",
    "emerging markets",
]

# ── Category keywords
CATEGORY_KEYWORDS = {
    "digital": [
        "programmatic", "digital advertising", "social media", "performance marketing",
        "ad tech", "adtech", "google ads", "meta ads", "tiktok", "youtube ads",
        "search advertising", "display advertising", "rtb", "dsp", "ssp",
        "first-party data", "mobile advertising", "retail media", "retail media network",
        "ecommerce advertising", "connected tv", "ctv", "streaming ads",
        "shoppable", "commerce media", "data-driven advertising",
    ],
    "creative": [
        "creative campaign", "ad campaign", "cannes lions", "spikes asia",
        "award-winning", "ogilvy", "bbdo", "saatchi", "dentsu creative",
        "brand film", "viral campaign", "brand activation", "creative agency",
        "advertising award", "creative work", "brand storytelling",
    ],
    "media": [
        "media buying", "media planning", "streaming", "broadcast", "television",
        "out-of-home", "ooh advertising", "dooh", "digital out-of-home",
        "publishing", "newspaper", "print media", "podcast advertising",
        "connected tv", "linear tv", "media agency", "media owner",
    ],
    "industry": [
        "agency wins", "account win", "new business", "merger", "acquisition",
        "appoints", "new ceo", "new appointment", "brand launch", "rebranding",
        "partnership", "ad spend", "advertising revenue", "market share",
        "industry report", "ad market", "pitch win", "advertising agency",
    ],
}

COUNTRIES = list(COUNTRY_KEYWORDS.keys())


def is_ads_relevant(article: dict) -> bool:
    """Strictly filter to only ads/marketing related articles."""
    text = article["raw_text"]
    return any(kw in text for kw in ADS_RELEVANCE_KEYWORDS)


def fetch_all_articles() -> list:
    """Fetch RSS feeds, deduplicate, and filter to ads-relevant only."""
    seen_urls = set()
    seen_sources = set()
    all_articles = []

    for feed_info in RSS_FEEDS:
        source = feed_info["name"]
        if source in seen_sources:
            continue
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; GrabAds-NewsBot/1.0; +https://grab.com)"
            }
            response = requests.get(feed_info["url"], headers=headers, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            count = 0
            filtered = 0
            for entry in feed.entries:
                title   = entry.get("title", "").strip()
                url     = entry.get("link", "")
                summary = clean_html(entry.get("summary", entry.get("description", "")))

                if not title or not url or url in seen_urls:
                    continue

                article = {
                    "title":     title,
                    "summary":   summary,
                    "url":       url,
                    "source":    source,
                    "published": parse_date(entry),
                    "raw_text":  (title + " " + summary).lower(),
                }

                # Strict ads relevance filter
                if not is_ads_relevant(article):
                    filtered += 1
                    continue

                seen_urls.add(url)
                all_articles.append(article)
                count += 1

            if count > 0:
                seen_sources.add(source)
            print(f"    {count} ads-relevant articles from {source} ({filtered} filtered out)")

        except Exception as e:
            print(f"    Failed {source} ({feed_info['url']}): {e}")

    print(f"  Total ads-relevant articles: {len(all_articles)}")
    return all_articles


def is_country_match(article: dict, country: str) -> bool:
    text = article["raw_text"]
    return any(kw in text for kw in COUNTRY_KEYWORDS[country])


def is_regional_match(article: dict) -> bool:
    text = article["raw_text"]
    return any(kw in text for kw in REGIONAL_KEYWORDS)


def classify_category(article: dict) -> str:
    text = article["raw_text"]
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "industry"


def format_article(article: dict) -> dict:
    category = classify_category(article)
    summary  = article["summary"]
    if len(summary) > 180:
        summary = summary[:177] + "..."
    return {
        "headline":   article["title"],
        "summary":    summary if summary else "Click to read the full article.",
        "category":   category,
        "source":     article["source"],
        "date":       format_date(article["published"]),
        "url":        article["url"],
        "imageQuery": image_query_for(category),
    }


def build_country_news(country: str, all_articles: list) -> list:
    """
    Build up to 6 articles per country:
    1. Country-specific articles first
    2. Regional APAC articles to fill remaining slots
    3. Rotate general ads articles per country so each market gets different ones
    4. Fallback placeholders only if absolutely nothing found
    """
    # Priority 1: country-specific
    specific = [a for a in all_articles if is_country_match(a, country)]
    used_urls = {a["url"] for a in specific}

    # Priority 2: regional APAC articles
    regional = [a for a in all_articles
                if a["url"] not in used_urls and is_regional_match(a)]
    used_urls.update(a["url"] for a in regional)

    # Priority 3: remaining ads articles, rotated per country
    # Use a deterministic shuffle based on country name so each country
    # gets a different slice of the general pool
    general = [a for a in all_articles if a["url"] not in used_urls]

    # Rotate general pool differently per country using country name as seed
    country_seed = int(hashlib.md5(country.encode()).hexdigest(), 16) % max(len(general), 1)
    rotated_general = general[country_seed:] + general[:country_seed]

    print(f"    {country}: {len(specific)} specific, {len(regional)} regional, {len(general)} general available")

    # Combine in priority order
    combined = specific[:6]
    if len(combined) < 6:
        combined += regional[:(6 - len(combined))]
    if len(combined) < 6:
        combined += rotated_general[:(6 - len(combined))]

    # Sort by recency
    def sort_key(a):
        d = format_date(a["published"])
        return {"Today": 0, "Yesterday": 1}.get(d, 2)
    combined.sort(key=sort_key)

    result = [format_article(a) for a in combined[:6]]

    # Only pad with fallback if still under 6
    if len(result) < 6:
        print(f"    Padding {country} with {6 - len(result)} fallback articles")
        result += fallback(country)[:(6 - len(result))]

    return result


def format_date(published: datetime) -> str:
    if not published:
        return "This week"
    now = datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    delta = now - published
    if delta.days == 0:
        return "Today"
    elif delta.days == 1:
        return "Yesterday"
    elif delta.days <= 6:
        return f"{delta.days} days ago"
    else:
        return published.strftime("%-d %b")


def parse_date(entry) -> datetime:
    for field in ["published", "updated", "created"]:
        val = entry.get(field)
        if val:
            try:
                return dateparser.parse(val)
            except Exception:
                pass
    return None


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def image_query_for(category: str) -> str:
    return {
        "digital":  "digital advertising technology",
        "creative": "creative advertising campaign",
        "media":    "media broadcasting publishing",
        "industry": "marketing agency business",
    }.get(category, "advertising marketing")


def fallback(country: str) -> list:
    return [
        {"headline": f"Top agency moves reshaping {country}'s ad scene", "summary": "Major agencies and brands are driving significant market shifts this week.", "category": "industry", "source": "Campaign Asia", "date": "This week", "url": "", "imageQuery": "marketing agency office team"},
        {"headline": f"Programmatic spend surges across {country} market", "summary": "Digital ad investment continues to climb with new data-driven strategies.", "category": "digital", "source": "Marketing Interactive", "date": "This week", "url": "", "imageQuery": "digital advertising screens data"},
        {"headline": f"Bold new creative campaign wins buzz in {country}", "summary": "A striking campaign is generating significant social and press attention.", "category": "creative", "source": "The Drum", "date": "This week", "url": "", "imageQuery": "creative advertising campaign billboard"},
        {"headline": f"Retail media networks grow in {country}", "summary": "Retailers are increasingly launching ad platforms to monetise their audiences.", "category": "digital", "source": "Adweek", "date": "This week", "url": "", "imageQuery": "retail media network shopping"},
        {"headline": f"Streaming reshapes media buying in {country}", "summary": "Publishers and broadcasters are adapting to evolving viewer habits.", "category": "media", "source": "Adweek", "date": "This week", "url": "", "imageQuery": "streaming media television remote"},
        {"headline": f"Brand partnerships signal confidence in {country}", "summary": "Several high-profile brand collaborations were announced this week.", "category": "industry", "source": "Campaign Asia", "date": "This week", "url": "", "imageQuery": "business partnership handshake meeting"},
    ]


def main():
    print("=" * 50)
    print("GrabAds Weekly News Generator (RSS Edition)")
    print(f"Running at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    print("\nFetching RSS feeds...")
    all_articles = fetch_all_articles()

    print("\nMatching articles to markets...")
    output = {
        "generatedAt":   datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generatedDate": datetime.utcnow().strftime("%-d %b %Y"),
        "countries":     {},
    }

    for country in COUNTRIES:
        print(f"  Processing {country}...")
        output["countries"][country] = build_country_news(country, all_articles)
        print(f"    Final: {len(output['countries'][country])} articles for {country}")

    output_path = os.path.join(os.path.dirname(__file__), "news.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in output["countries"].values())
    print("\n" + "=" * 50)
    print(f"news.json written successfully")
    print(f"Total articles: {total}")
    print("=" * 50)


if __name__ == "__main__":
    main()
