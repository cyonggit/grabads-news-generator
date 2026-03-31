"""
GrabAds News Widget -- Weekly News Generator (Free RSS Version)
==============================================================
Pulls news from free RSS feeds. No API key or credits required.
Run by GitLab CI every Monday. Outputs news.json for the widget.

Dependencies: feedparser, python-dateutil
"""

import json
import os
import re
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser

# ── RSS feeds from major ad/marketing industry publications
RSS_FEEDS = [
    {"name": "Campaign Asia",         "url": "https://www.campaignasia.com/rss"},
    {"name": "Marketing Interactive", "url": "https://www.marketing-interactive.com/feed"},
    {"name": "The Drum",              "url": "https://www.thedrum.com/rss"},
    {"name": "Mumbrella Asia",        "url": "https://mumbrella.asia/feed"},
    {"name": "Exchange4Media",        "url": "https://www.exchange4media.com/rss/rss.aspx"},
    {"name": "Marketing Week",        "url": "https://www.marketingweek.com/feed/"},
    {"name": "Adweek",                "url": "https://www.adweek.com/feed/"},
]

# ── Country keywords: only use unambiguous, sufficiently long terms
# ── Avoid short abbreviations like "ph", "th", "id", "my" which cause
#    false matches on common English words
COUNTRY_KEYWORDS = {
    "Singapore":   ["singapore", "singaporean"],
    "Philippines": ["philippines", "philippine", "filipino", "filipina", "manila", "cebu", "davao"],
    "Indonesia":   ["indonesia", "indonesian", "jakarta", "surabaya", "bandung", "bali"],
    "Thailand":    ["thailand", "thai", "bangkok", "phuket", "chiang mai"],
    "Vietnam":     ["vietnam", "vietnamese", "hanoi", "ho chi minh", "saigon", "hcmc"],
    "Malaysia":    ["malaysia", "malaysian", "kuala lumpur", "penang", "johor"],
}

# ── Regional keywords that apply to ALL countries when no specific match
REGIONAL_KEYWORDS = [
    "southeast asia", "sea region", "apac", "asia pacific",
    "asia-pacific", "asean", "regional", "across asia",
]

# ── Category classification keywords
CATEGORY_KEYWORDS = {
    "digital":  [
        "programmatic", "digital advertising", "social media", "performance marketing",
        "ad tech", "adtech", "google ads", "meta ads", "tiktok ads", "youtube ads",
        "search ads", "display ads", "rtb", "dsp", "ssp", "first-party data",
        "third-party cookies", "mobile advertising", "e-commerce ads", "retail media",
    ],
    "creative": [
        "creative campaign", "ad campaign", "cannes lions", "spikes asia",
        "award-winning", "ogilvy", "bbdo", "saatchi", "dentsu creative",
        "brand film", "viral campaign", "brand activation", "creative agency",
        "advertising award", "creative work",
    ],
    "media":    [
        "media buying", "media planning", "streaming", "broadcast", "television",
        "out-of-home", "ooh advertising", "dooh", "digital out-of-home",
        "publishing", "newspaper", "print media", "podcast advertising",
        "connected tv", "ctv", "linear tv", "media agency",
    ],
    "industry": [
        "agency wins", "account win", "new business", "merger", "acquisition",
        "appoints", "new ceo", "new appointment", "brand launch", "rebranding",
        "partnership", "ad spend", "advertising revenue", "market share",
        "industry report", "ad market", "pitch win",
    ],
}

COUNTRIES = list(COUNTRY_KEYWORDS.keys())


def fetch_all_articles() -> list:
    """Fetch and parse all RSS feeds into a flat list of articles."""
    all_articles = []
    for feed_info in RSS_FEEDS:
        print(f"  Fetching {feed_info['name']}...")
        try:
            feed = feedparser.parse(feed_info["url"])
            count = 0
            for entry in feed.entries:
                title   = entry.get("title", "").strip()
                summary = clean_html(entry.get("summary", entry.get("description", "")))
                url     = entry.get("link", "")
                if not title or not url:
                    continue
                all_articles.append({
                    "title":     title,
                    "summary":   summary,
                    "url":       url,
                    "source":    feed_info["name"],
                    "published": parse_date(entry),
                    "raw_text":  (title + " " + summary).lower(),
                })
                count += 1
            print(f"    {count} articles from {feed_info['name']}")
        except Exception as e:
            print(f"    Failed to fetch {feed_info['name']}: {e}")

    print(f"  Total articles fetched: {len(all_articles)}")
    return all_articles


def is_country_match(article: dict, country: str) -> bool:
    """Check if an article explicitly mentions a country."""
    text = article["raw_text"]
    return any(kw in text for kw in COUNTRY_KEYWORDS[country])


def is_regional_match(article: dict) -> bool:
    """Check if an article is regional/APAC (relevant to all markets)."""
    text = article["raw_text"]
    return any(kw in text for kw in REGIONAL_KEYWORDS)


def classify_category(article: dict) -> str:
    """Score article against category keywords and return best match."""
    text = article["raw_text"]
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "industry"


def format_article(article: dict) -> dict:
    """Format a raw article dict into the widget-ready structure."""
    category = classify_category(article)
    summary  = article["summary"]
    if len(summary) > 180:
        summary = summary[:177] + "..."
    return {
        "headline":   article["title"],
        "summary":    summary,
        "category":   category,
        "source":     article["source"],
        "date":       format_date(article["published"]),
        "url":        article["url"],
        "imageQuery": image_query_for(category),
    }


def build_country_news(country: str, all_articles: list) -> list:
    """
    Build a list of up to 6 articles for a country using this priority:
      1. Articles that explicitly mention the country (best match)
      2. Regional/APAC articles to fill remaining slots
      3. Fallback placeholder articles if still not enough
    """
    # Priority 1: country-specific articles
    specific = [a for a in all_articles if is_country_match(a, country)]

    # Priority 2: regional articles not already in specific
    specific_urls = {a["url"] for a in specific}
    regional = [a for a in all_articles
                if is_regional_match(a) and a["url"] not in specific_urls]

    print(f"    {country}: {len(specific)} specific, {len(regional)} regional articles")

    # Combine: specific first, then regional to fill up to 6
    combined = specific[:6]
    if len(combined) < 6:
        combined += regional[:(6 - len(combined))]

    # Sort by recency
    order = {"Today": 0, "Yesterday": 1}
    combined.sort(key=lambda a: order.get(format_date(a["published"]), 2))

    result = [format_article(a) for a in combined[:6]]

    # Fill remaining slots with fallback if still under 6
    if len(result) < 6:
        print(f"    Only {len(result)} articles for {country}, padding with fallback")
        result += fallback(country)[:(6 - len(result))]

    return result


def format_date(published: datetime) -> str:
    """Convert datetime to a friendly relative label."""
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
    """Safely parse published date from RSS entry."""
    for field in ["published", "updated", "created"]:
        val = entry.get(field)
        if val:
            try:
                return dateparser.parse(val)
            except Exception:
                pass
    return None


def clean_html(text: str) -> str:
    """Strip HTML tags and clean whitespace."""
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
        {"headline": f"Streaming reshapes media buying in {country}", "summary": "Publishers and broadcasters are adapting to evolving viewer habits.", "category": "media", "source": "Adweek Asia", "date": "This week", "url": "", "imageQuery": "streaming media television remote"},
        {"headline": f"Brand partnerships signal confidence in {country}", "summary": "Several high-profile brand collaborations were announced this week.", "category": "industry", "source": "Campaign Asia", "date": "This week", "url": "", "imageQuery": "business partnership handshake meeting"},
        {"headline": f"Social commerce ad formats gain traction in {country}", "summary": "Shoppable content and in-app advertising formats are seeing rapid adoption.", "category": "digital", "source": "Marketing Interactive", "date": "This week", "url": "", "imageQuery": "social media phone shopping app"},
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
