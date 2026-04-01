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
import requests
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser

# ── RSS feeds -- using multiple URL formats per source for reliability
RSS_FEEDS = [
    # Campaign Asia -- try multiple URL formats
    {"name": "Campaign Asia",         "url": "https://www.campaignasia.com/rss"},
    {"name": "Campaign Asia",         "url": "https://www.campaignasia.com/feed"},
    # Marketing Interactive
    {"name": "Marketing Interactive", "url": "https://www.marketing-interactive.com/feed"},
    {"name": "Marketing Interactive", "url": "https://www.marketing-interactive.com/rss"},
    # The Drum
    {"name": "The Drum",              "url": "https://www.thedrum.com/rss"},
    {"name": "The Drum",              "url": "https://www.thedrum.com/feed"},
    # Adweek -- confirmed working
    {"name": "Adweek",                "url": "https://www.adweek.com/feed/"},
    # AdAge
    {"name": "Ad Age",                "url": "https://adage.com/rss"},
    {"name": "Ad Age",                "url": "https://adage.com/feed"},
    # Marketing Week
    {"name": "Marketing Week",        "url": "https://www.marketingweek.com/feed/"},
    # PR Newswire -- Asia marketing press releases
    {"name": "PR Newswire Asia",      "url": "https://www.prnewswire.com/rss/news-releases-list.rss"},
    # Business Wire
    {"name": "Business Wire",         "url": "https://feed.businesswire.com/rss/home/?rss=G22"},
    # MediaPost
    {"name": "MediaPost",             "url": "https://www.mediapost.com/rss/"},
    # Marketing Land / Search Engine Land
    {"name": "Search Engine Land",    "url": "https://searchengineland.com/feed"},
    # Mumbrella
    {"name": "Mumbrella",             "url": "https://mumbrella.com.au/feed"},
]

# ── Country-specific keywords (unambiguous, full words only)
COUNTRY_KEYWORDS = {
    "Singapore":   ["singapore", "singaporean"],
    "Philippines": ["philippines", "philippine", "filipino", "filipina", "manila", "cebu", "davao"],
    "Indonesia":   ["indonesia", "indonesian", "jakarta", "surabaya", "bandung", "bali"],
    "Thailand":    ["thailand", "thai", "bangkok", "phuket", "chiang mai"],
    "Vietnam":     ["vietnam", "vietnamese", "hanoi", "ho chi minh", "saigon", "hcmc"],
    "Malaysia":    ["malaysia", "malaysian", "kuala lumpur", "penang", "johor"],
}

# ── Regional keywords -- articles with these go to ALL countries
REGIONAL_KEYWORDS = [
    "southeast asia", "sea region", "apac", "asia pacific",
    "asia-pacific", "asean", "across asia", "asian market",
    "emerging markets", "digital advertising", "programmatic",
    "ad tech", "adtech", "marketing technology", "martech",
    "social media marketing", "influencer marketing",
    "brand marketing", "advertising industry", "media buying",
    "ad spend", "advertising spend", "creative campaign",
    "marketing campaign", "brand campaign",
]

# ── Category keywords
CATEGORY_KEYWORDS = {
    "digital":  [
        "programmatic", "digital advertising", "social media", "performance marketing",
        "ad tech", "adtech", "google ads", "meta ads", "tiktok", "youtube ads",
        "search advertising", "display advertising", "rtb", "dsp", "ssp",
        "first-party data", "mobile advertising", "retail media", "ecommerce",
        "connected tv", "ctv", "streaming ads",
    ],
    "creative": [
        "creative campaign", "ad campaign", "cannes lions", "spikes asia",
        "award-winning", "ogilvy", "bbdo", "saatchi", "dentsu creative",
        "brand film", "viral campaign", "brand activation", "creative agency",
        "advertising award", "creative work", "brand storytelling",
    ],
    "media":    [
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


def fetch_all_articles() -> list:
    """Fetch and parse all RSS feeds, deduplicating by URL."""
    seen_urls = set()
    all_articles = []
    seen_sources = set()

    for feed_info in RSS_FEEDS:
        # Skip duplicate sources we already got articles from
        source = feed_info["name"]
        if source in seen_sources:
            continue

        try:
            # Use requests with a browser-like User-Agent to avoid blocks
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; GrabAds-NewsBot/1.0; +https://grab.com)"
            }
            response = requests.get(feed_info["url"], headers=headers, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            count = 0
            for entry in feed.entries:
                title   = entry.get("title", "").strip()
                url     = entry.get("link", "")
                summary = clean_html(entry.get("summary", entry.get("description", "")))

                if not title or not url or url in seen_urls:
                    continue

                seen_urls.add(url)
                all_articles.append({
                    "title":     title,
                    "summary":   summary,
                    "url":       url,
                    "source":    source,
                    "published": parse_date(entry),
                    "raw_text":  (title + " " + summary).lower(),
                })
                count += 1

            if count > 0:
                seen_sources.add(source)
            print(f"    {count} articles from {source} ({feed_info['url']})")

        except Exception as e:
            print(f"    Failed {source} ({feed_info['url']}): {e}")

    print(f"  Total unique articles fetched: {len(all_articles)}")
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
    2. Regional/industry articles to fill remaining slots
    3. Fallback placeholders only if absolutely nothing found
    """
    specific = [a for a in all_articles if is_country_match(a, country)]
    specific_urls = {a["url"] for a in specific}

    # ALL remaining articles count as regional fill
    # (since we're an ads industry widget, all ad industry news is relevant)
    regional = [a for a in all_articles
                if a["url"] not in specific_urls and
                (is_regional_match(a) or True)]  # use all articles as fill

    print(f"    {country}: {len(specific)} specific articles, {len(all_articles) - len(specific)} available as fill")

    # Combine specific first, then fill
    combined = specific[:6]
    if len(combined) < 6:
        combined += regional[:(6 - len(combined))]

    # Sort by recency
    def sort_key(a):
        d = format_date(a["published"])
        return {"Today": 0, "Yesterday": 1}.get(d, 2)
    combined.sort(key=sort_key)

    result = [format_article(a) for a in combined[:6]]

    # Only use fallback if we have nothing at all
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
