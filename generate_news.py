"""
GrabAds News Widget -- Weekly News Generator (NewsAPI Version)
==============================================================
Fetches SEA + global ad industry news from NewsAPI.
No RSS feeds required.

Run by GitHub Actions every Monday.
Outputs news.json for the widget.

Dependencies: requests
"""

import json
import os
import re
import hashlib
import random
import requests
from datetime import datetime, timezone, timedelta


NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"

# ── Search queries -- all geo-anchored to SEA/APAC
# Two sets: SEA-specific and global industry movements worth flagging
SEARCH_QUERIES = [
    # SEA market-specific
    "advertising marketing Singapore",
    "advertising marketing Malaysia",
    "advertising marketing Indonesia",
    "advertising marketing Philippines",
    "advertising marketing Thailand Vietnam",
    "advertising marketing Taiwan",
    "digital marketing APAC Southeast Asia",
    "media agency APAC campaign",
    # Global industry movements always relevant to SEA sales teams
    "advertising agency account win Southeast Asia",
    "brand campaign launch Asia Pacific",
    "retail media network Asia",
    "programmatic advertising Southeast Asia",
    "ad tech adtech Asia Pacific",
    "social media advertising Asia TikTok Meta",
]

# ── Trusted ad industry sources to prioritise
TRUSTED_SOURCES = [
    "adweek.com",
    "thedrum.com",
    "campaignasia.com",
    "marketing-interactive.com",
    "marketingdive.com",
    "socialmediatoday.com",
    "mumbrella.com.au",
    "adage.com",
    "campaignlive.co.uk",
    "mediapost.com",
    "digiday.com",
    "businessinsider.com",
    "reuters.com",
    "bloomberg.com",
]

# ── SEA/Taiwan relevance keywords
SEA_KEYWORDS = [
    "singapore", "singaporean",
    "philippines", "philippine", "filipino", "manila",
    "indonesia", "indonesian", "jakarta",
    "thailand", "thai", "bangkok",
    "vietnam", "vietnamese", "hanoi", "ho chi minh",
    "malaysia", "malaysian", "kuala lumpur",
    "taiwan", "taiwanese", "taipei",
    "southeast asia", "sea region", "apac", "asia pacific",
    "asia-pacific", "asean",
]

# ── Industry movement keywords
INDUSTRY_MOVEMENT_KEYWORDS = [
    "account win", "agency win", "pitch win", "wins account",
    "wins pitch", "appointed", "appoints", "new ceo", "new chief",
    "merger", "acquisition", "acquires", "acquired by",
    "rebranding", "rebrand", "launches", "expands into",
    "partnership", "joint venture", "investment", "funding",
]

# ── Strict ads relevance filter
ADS_RELEVANCE_KEYWORDS = [
    "advertis", "marketing", "agency", "brand", "campaign", "media buy",
    "programmatic", "ad tech", "adtech", "martech", "creative", "ad spend",
    "digital media", "social media marketing", "influencer", "content marketing",
    "out-of-home", "ooh", "dooh", "retail media",
    "ecommerce advertising", "search advertising", "display advertising",
    "media planning", "media agency", "ad network", "ad platform",
    "ad revenue", "ad market", "advertising industry",
    "publisher", "streaming ads", "connected tv", "ctv",
    "first-party data", "targeting", "audience data",
]

# ── Category keywords
CATEGORY_KEYWORDS = {
    "digital": [
        "programmatic", "digital advertising", "social media", "performance marketing",
        "ad tech", "adtech", "google ads", "meta ads", "tiktok", "youtube ads",
        "search advertising", "display advertising", "rtb", "dsp", "ssp",
        "first-party data", "mobile advertising", "retail media", "retail media network",
        "ecommerce advertising", "connected tv", "ctv", "streaming ads",
        "shoppable", "commerce media",
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
    "retail": [
        "retail media", "retail media network", "commerce media", "shoppable",
        "in-store advertising", "shopper marketing", "ecommerce ads",
        "retail advertising", "grocery media",
    ],
    "industry": [
        "agency wins", "account win", "new business", "merger", "acquisition",
        "appoints", "new ceo", "new appointment", "brand launch", "rebranding",
        "partnership", "ad spend", "advertising revenue", "market share",
        "industry report", "ad market", "pitch win", "advertising agency",
    ],
}

# ── Rule-based talking point templates
TALKING_POINT_TEMPLATES = {
    "digital": [
        "Digital channels are evolving fast — brands that invest in data-driven targeting now will have a significant edge.",
        "Performance marketing in SEA is increasingly driven by first-party data — how are you leveraging yours?",
        "As programmatic matures across the region, brands that move beyond last-click attribution will see clearer ROI.",
        "Mobile-first audiences in SEA expect relevant, personalised ads — precision targeting is now table stakes.",
        "The shift to cookieless identity is accelerating — first-party data partnerships are becoming a competitive moat.",
        "Social commerce is growing rapidly across SEA — shoppable ad formats are closing the gap between discovery and purchase.",
    ],
    "creative": [
        "Creative effectiveness is increasingly measurable — brands investing in strong storytelling are seeing higher engagement.",
        "Award-winning work in APAC shows that culturally resonant campaigns outperform generic global adaptations.",
        "With attention spans shrinking, the brands that win are those that lead with emotion before product.",
        "Creative quality directly impacts media efficiency — strong creatives lower CPMs and boost conversion rates.",
        "Localised creative beats globalised templates in SEA — consumers respond to brands that speak their language.",
    ],
    "media": [
        "Fragmented media consumption means brands need to show up across multiple touchpoints to build effective reach.",
        "Streaming adoption in SEA is accelerating — connected TV is opening new premium inventory for brands.",
        "Out-of-home is experiencing a digital renaissance — DOOH formats now offer the targeting precision of digital.",
        "Audio advertising is underutilised in SEA relative to consumption — an opportunity for brands to own the space.",
        "The line between media and commerce is blurring — media owners who offer closed-loop measurement are winning budgets.",
    ],
    "retail": [
        "Retail media networks offer brands unmatched purchase-intent signals — your ads reach consumers when they're ready to buy.",
        "Closed-loop retail media measurement finally connects ad spend directly to sales.",
        "As e-commerce grows across SEA, brands that build retail media expertise now will have a lasting advantage.",
        "First-party shopper data from retail platforms is among the most valuable targeting asset available today.",
        "Retail media is the fastest-growing ad channel globally — brands not investing risk ceding ground to competitors.",
    ],
    "industry": [
        "Agency consolidation signals brands are seeking more integrated partners who can connect media, data, and creative.",
        "Account moves often signal a brand is ready to rethink its media strategy — an opportunity to present new solutions.",
        "When brands change agencies, they're typically open to trying new platforms and channels — timing is everything.",
        "Industry shifts like this show how quickly the competitive landscape is evolving.",
        "Leadership changes at brands often accelerate marketing transformation — a great moment to open new conversations.",
    ],
}

TOPIC_TALKING_POINTS = {
    "tiktok":        "TikTok's explosive growth across SEA makes short-form video a must-have in any brand's media mix.",
    "influencer":    "Influencer marketing in SEA is maturing — brands are shifting from reach to engagement and conversion metrics.",
    "retail media":  "Retail media is the fastest-growing ad channel globally — brands not investing risk ceding ground to competitors.",
    "programmatic":  "Programmatic efficiency is improving rapidly — smarter bidding and better data are reducing wasted impressions.",
    "first-party":   "First-party data is the new currency of digital advertising — brands building their data assets now are ahead.",
    "connected tv":  "CTV adoption in SEA is accelerating — premium video inventory is now accessible to performance marketers.",
    "out-of-home":   "Digital OOH in SEA is growing fast — contextual, location-based placements are driving real-world outcomes.",
    "social media":  "Social platforms in SEA have among the highest engagement rates globally — critical for brand building.",
    "ai":            "AI is reshaping how ads are created, targeted, and measured — brands embracing it early are seeing efficiency gains.",
    "e-commerce":    "SEA's e-commerce boom is creating new advertising opportunities at the point of purchase intent.",
    "streaming":     "Streaming audiences in SEA are growing rapidly — ad-supported tiers are opening new premium placements.",
    "data":          "Data-driven decision making is separating top-performing brands from those still relying on gut instinct.",
    "measurement":   "As attribution models evolve, brands investing in robust measurement frameworks will have clearer proof of impact.",
}


def fetch_articles_for_query(query: str, from_date: str) -> list:
    """Fetch articles from NewsAPI for a single query."""
    try:
        params = {
            "q":          query,
            "from":       from_date,
            "language":   "en",
            "sortBy":     "publishedAt",
            "pageSize":   20,
            "apiKey":     NEWS_API_KEY,
        }
        resp = requests.get(NEWS_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except Exception as e:
        print(f"    Failed query '{query}': {e}")
        return []


def fetch_all_articles() -> list:
    """Run all search queries and return deduplicated, filtered articles."""
    seen_urls    = set()
    all_articles = []

    # Only fetch articles from the past 7 days
    from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

    for query in SEARCH_QUERIES:
        print(f"  Querying: '{query}'...")
        raw = fetch_articles_for_query(query, from_date)
        count    = 0
        filtered = 0

        for item in raw:
            url     = item.get("url", "")
            title   = (item.get("title") or "").strip()
            summary = clean_html(item.get("description") or item.get("content") or "")
            source  = item.get("source", {}).get("name", "Unknown")
            pub_at  = item.get("publishedAt", "")

            # Skip removed articles, duplicates, missing titles
            if not title or not url or url in seen_urls:
                continue
            if "[Removed]" in title or title == "":
                continue

            raw_text = (title + " " + summary).lower()
            article  = {
                "title":     title,
                "summary":   summary,
                "url":       url,
                "source":    source,
                "published": parse_date(pub_at),
                "raw_text":  raw_text,
                "image":     item.get("urlToImage", ""),
            }

            # Apply ads relevance filter
            if not is_ads_relevant(article):
                filtered += 1
                continue

            seen_urls.add(url)
            all_articles.append(article)
            count += 1

        print(f"    {count} relevant articles ({filtered} filtered out)")

    print(f"  Total unique relevant articles: {len(all_articles)}")
    return all_articles


def is_ads_relevant(article: dict) -> bool:
    return any(kw in article["raw_text"] for kw in ADS_RELEVANCE_KEYWORDS)


def is_sea_relevant(article: dict) -> bool:
    return any(kw in article["raw_text"] for kw in SEA_KEYWORDS)


def is_industry_movement(article: dict) -> bool:
    return any(kw in article["raw_text"] for kw in INDUSTRY_MOVEMENT_KEYWORDS)


def classify_category(article: dict) -> str:
    text   = article["raw_text"]
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "industry"


def generate_talking_points(article: dict) -> list:
    """Generate 2-3 talking points using rule-based keyword matching."""
    text     = article["raw_text"]
    category = article.get("category", "industry")
    points   = []

    # Topic-specific points first
    for keyword, point in TOPIC_TALKING_POINTS.items():
        if keyword in text and point not in points:
            points.append(point)
        if len(points) >= 2:
            break

    # Fill with category templates
    seed      = int(hashlib.md5((article.get("url", "") + article.get("title", "")).encode()).hexdigest(), 16)
    rng       = random.Random(seed)
    templates = TALKING_POINT_TEMPLATES.get(category, TALKING_POINT_TEMPLATES["industry"])[:]
    rng.shuffle(templates)

    for t in templates:
        if t not in points:
            points.append(t)
        if len(points) >= 3:
            break

    return points[:3]


def select_top_articles(all_articles: list, max_articles: int = 12) -> list:
    """
    Only include:
    1. Articles that explicitly mention SEA/APAC markets
    2. Global industry movements (account wins, mergers etc) as they
       are always relevant talking points for SEA sales teams
    No generic global ads news unless it mentions SEA/APAC.
    """
    sea       = [a for a in all_articles if is_sea_relevant(a)]
    movements = [a for a in all_articles
                 if is_industry_movement(a) and not is_sea_relevant(a)]

    print(f"  SEA-specific: {len(sea)}")
    print(f"  Global industry movements: {len(movements)}")

    # SEA articles first, then industry movements to fill
    combined = sea[:max_articles]
    if len(combined) < max_articles:
        combined += movements[:(max_articles - len(combined))]

    # Sort by recency
    combined.sort(
        key=lambda a: a["published"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )

    return combined[:max_articles]


def format_article(article: dict) -> dict:
    category = classify_category(article)
    article["category"] = category
    summary  = article["summary"]
    if len(summary) > 200:
        summary = summary[:197] + "..."

    # Use real image from NewsAPI if available, else fall back to Picsum
    seed     = int(hashlib.md5(article.get("url", "").encode()).hexdigest(), 16) % 1000
    image    = article.get("image") or f"https://picsum.photos/seed/{seed}/600/280"

    return {
        "headline":      article["title"],
        "summary":       summary if summary else "Click to read the full article.",
        "category":      category,
        "source":        article["source"],
        "date":          format_date(article["published"]),
        "url":           article["url"],
        "image":         image,
        "talkingPoints": generate_talking_points(article),
        "isMovement":    is_industry_movement(article),
    }


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


def parse_date(date_str: str) -> datetime:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fallback() -> list:
    return [
        {"headline": "Programmatic spend surges across SEA markets", "summary": "Digital ad investment continues to climb with new data-driven strategies across Southeast Asia.", "category": "digital", "source": "Campaign Asia", "date": "This week", "url": "", "image": "https://picsum.photos/seed/1/600/280", "talkingPoints": ["Performance marketing in SEA is increasingly driven by first-party data.", "Programmatic efficiency is improving rapidly across the region."], "isMovement": False},
        {"headline": "Retail media networks gain momentum in APAC", "summary": "Retailers across Asia Pacific are launching ad networks to monetise their audiences.", "category": "retail", "source": "Marketing Dive", "date": "This week", "url": "", "image": "https://picsum.photos/seed/2/600/280", "talkingPoints": ["Retail media lets brands reach consumers closest to the point of purchase.", "Closed-loop measurement connects ad spend directly to sales."], "isMovement": False},
        {"headline": "Agency account moves signal shifting brand priorities", "summary": "Several major advertisers have consolidated their media buying with new agency partners.", "category": "industry", "source": "Adweek", "date": "This week", "url": "", "image": "https://picsum.photos/seed/3/600/280", "talkingPoints": ["Account moves signal brands are seeking more integrated, data-driven partners.", "New agency relationships often coincide with a fresh look at digital channel mix."], "isMovement": True},
    ]


def main():
    print("=" * 50)
    print("GrabAds Weekly News Generator (NewsAPI Version)")
    print(f"Running at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    if not NEWS_API_KEY:
        print("ERROR: NEWS_API_KEY environment variable not set!")
        print("Add it as a GitHub secret named NEWS_API_KEY")
        exit(1)

    print("\nFetching articles from NewsAPI...")
    all_articles = fetch_all_articles()

    print("\nSelecting top articles...")
    top_articles = select_top_articles(all_articles, max_articles=12)
    print(f"  Selected {len(top_articles)} articles")

    print("\nFormatting articles and generating talking points...")
    formatted = [format_article(a) for a in top_articles]

    if not formatted:
        print("  No articles found, using fallback data")
        formatted = fallback()

    output = {
        "generatedAt":   datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generatedDate": datetime.utcnow().strftime("%-d %b %Y"),
        "articles":      formatted,
    }

    output_path = os.path.join(os.path.dirname(__file__), "news.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"news.json written successfully")
    print(f"Total articles: {len(formatted)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
