"""
GrabAds News Widget -- Weekly News Generator
=============================================
Fetches SEA + global ad industry news from verified RSS feeds.
Run by GitHub Actions every Monday. Outputs news.json for the widget.

Dependencies: feedparser, python-dateutil, requests
"""

import json
import os
import re
import hashlib
import random
import requests
import feedparser
from datetime import datetime, timezone
from dateutil import parser as dateparser

# ── Verified RSS feeds as of May 2026
RSS_FEEDS = [
    # SEA-focused publications (trusted as inherently relevant)
    {"name": "Campaign Asia",         "url": "https://rss.app/feeds/sBwZgWOqOWen0qHY.xml",        "sea_trusted": True},
    {"name": "Marketing Interactive", "url": "https://rss.app/feeds/Jd6qTo2o46Mxxe3D.xml",        "sea_trusted": True},
    {"name": "MARKETECH APAC",        "url": "https://rss.app/feeds/Di8qt6zeF2FMZyPy.xml",        "sea_trusted": True},
    {"name": "Campaign Brief Asia",   "url": "https://campaignbriefasia.com/feed/",                "sea_trusted": True},
    # Global ad industry publications (confirmed working, require SEA keyword match)
    {"name": "Adweek",                "url": "https://www.adweek.com/feed/",                       "sea_trusted": False},
    {"name": "Digiday",               "url": "https://digiday.com/feed/",                          "sea_trusted": False},
    {"name": "AdExchanger",           "url": "https://adexchanger.com/feed/",                      "sea_trusted": False},
    {"name": "Marketing Dive",        "url": "https://www.marketingdive.com/feeds/news/",          "sea_trusted": False},
    {"name": "Social Media Today",    "url": "https://www.socialmediatoday.com/feeds/news/",       "sea_trusted": False},
    {"name": "Mumbrella",             "url": "https://mumbrella.com.au/feed/",                     "sea_trusted": False},
]

# ── SEA/Taiwan keywords for non-trusted sources
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
    "account win", "agency win", "pitch win", "wins account", "wins pitch",
    "appointed", "appoints", "new ceo", "new chief",
    "merger", "acquisition", "acquires", "acquired by",
    "rebranding", "rebrand", "launches", "expands into",
    "partnership", "joint venture",
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
        "ecommerce advertising", "connected tv", "ctv", "streaming ads", "commerce media",
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
        "in-store advertising", "shopper marketing", "ecommerce ads", "retail advertising",
    ],
    "industry": [
        "agency wins", "account win", "new business", "merger", "acquisition",
        "appoints", "new ceo", "new appointment", "brand launch", "rebranding",
        "partnership", "ad spend", "advertising revenue", "market share",
        "industry report", "ad market", "pitch win", "advertising agency",
    ],
}

# ── Rule-based talking point templates per category
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
        "Closed-loop retail media measurement connects ad spend directly to sales — a major shift from traditional media.",
        "As e-commerce grows across SEA, brands that build retail media expertise now will have a lasting advantage.",
        "First-party shopper data from retail platforms is among the most valuable targeting assets available today.",
        "Retail media is the fastest-growing ad channel globally — brands not investing risk ceding ground to competitors.",
    ],
    "industry": [
        "Agency consolidation signals brands are seeking more integrated partners who can connect media, data, and creative.",
        "Account moves often signal a brand is ready to rethink its media strategy — an opportunity to present new solutions.",
        "When brands change agencies, they're typically open to trying new platforms and channels — timing is everything.",
        "Industry shifts like this show how quickly the competitive landscape is evolving — staying close to market news is key.",
        "Leadership changes at brands often accelerate marketing transformation — a great moment to open new conversations.",
    ],
}

TOPIC_TALKING_POINTS = {
    "tiktok":       "TikTok's explosive growth across SEA makes short-form video a must-have in any brand's media mix.",
    "influencer":   "Influencer marketing in SEA is maturing — brands are shifting from reach to engagement and conversion metrics.",
    "retail media": "Retail media is the fastest-growing ad channel globally — brands not investing risk ceding ground to competitors.",
    "programmatic": "Programmatic efficiency is improving rapidly — smarter bidding and better data are reducing wasted impressions.",
    "first-party":  "First-party data is the new currency of digital advertising — brands building their data assets now are ahead.",
    "connected tv": "CTV adoption in SEA is accelerating — premium video inventory is now accessible to performance marketers.",
    "out-of-home":  "Digital OOH in SEA is growing fast — contextual, location-based placements are driving real-world outcomes.",
    "social media": "Social platforms in SEA have among the highest engagement rates globally — critical for brand building.",
    "ai":           "AI is reshaping how ads are created, targeted, and measured — brands embracing it early are seeing efficiency gains.",
    "e-commerce":   "SEA's e-commerce boom is creating new advertising opportunities at the point of purchase intent.",
    "streaming":    "Streaming audiences in SEA are growing rapidly — ad-supported tiers are opening new premium placements.",
    "measurement":  "As attribution models evolve, brands investing in robust measurement frameworks will have clearer proof of impact.",
}


USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (compatible; GrabAds-NewsBot/1.0; +https://grab.com)",
]


def fetch_all_articles() -> list:
    seen_urls    = set()
    all_articles = []

    for i, feed_info in enumerate(RSS_FEEDS):
        source      = feed_info["name"]
        sea_trusted = feed_info["sea_trusted"]
        # Rotate User-Agent per request
        headers = {"User-Agent": USER_AGENTS[i % len(USER_AGENTS)]}
        try:
            response = requests.get(feed_info["url"], headers=headers, timeout=15)
            response.raise_for_status()
            feed     = feedparser.parse(response.content)

            count    = 0
            filtered = 0
            for entry in feed.entries:
                title   = entry.get("title", "").strip()
                url     = entry.get("link", "")
                summary = clean_html(entry.get("summary", entry.get("description", "")))

                if not title or not url or url in seen_urls:
                    continue

                raw_text = (title + " " + summary).lower()
                article  = {
                    "title":       title,
                    "summary":     summary,
                    "url":         url,
                    "source":      source,
                    "published":   parse_date(entry),
                    "raw_text":    raw_text,
                    "sea_trusted": sea_trusted,
                    "image":       "",
                }

                if not is_ads_relevant(article):
                    filtered += 1
                    continue

                seen_urls.add(url)
                all_articles.append(article)
                count += 1

            print(f"    {count} relevant articles from {source} ({filtered} filtered out)")

        except Exception as e:
            print(f"    Failed {source} ({feed_info['url']}): {e}")

    print(f"  Total relevant articles: {len(all_articles)}")
    return all_articles


def is_ads_relevant(article: dict) -> bool:
    return any(kw in article["raw_text"] for kw in ADS_RELEVANCE_KEYWORDS)


def is_sea_relevant(article: dict) -> bool:
    # SEA-trusted sources are always relevant
    if article.get("sea_trusted"):
        return True
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
    text     = article["raw_text"]
    category = article.get("category", "industry")
    points   = []

    for keyword, point in TOPIC_TALKING_POINTS.items():
        if keyword in text and point not in points:
            points.append(point)
        if len(points) >= 2:
            break

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
    sea       = [a for a in all_articles if is_sea_relevant(a)]
    movements = [a for a in all_articles if is_industry_movement(a) and not is_sea_relevant(a)]

    print(f"  SEA/trusted: {len(sea)}")
    print(f"  Global industry movements: {len(movements)}")

    combined = sea[:max_articles]
    if len(combined) < max_articles:
        combined += movements[:(max_articles - len(combined))]

    # Sort by recency
    def sort_key(a):
        d = format_date(a["published"])
        return {"Today": 0, "Yesterday": 1}.get(d, 2)
    combined.sort(key=sort_key)

    return combined[:max_articles]


def format_article(article: dict) -> dict:
    category = classify_category(article)
    article["category"] = category
    summary  = article["summary"]
    if len(summary) > 200:
        summary = summary[:197] + "..."

    seed  = int(hashlib.md5(article.get("url", "").encode()).hexdigest(), 16) % 1000
    image = article.get("image") or f"https://picsum.photos/seed/{seed}/600/280"

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
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fallback() -> list:
    return [
        {"headline": "Programmatic spend surges across SEA markets", "summary": "Digital ad investment continues to climb with new data-driven strategies across Southeast Asia.", "category": "digital", "source": "Campaign Asia", "date": "This week", "url": "", "image": "https://picsum.photos/seed/1/600/280", "talkingPoints": ["Performance marketing in SEA is increasingly driven by first-party data.", "Programmatic efficiency is improving rapidly across the region."], "isMovement": False},
        {"headline": "Retail media networks gain momentum in APAC", "summary": "Retailers across Asia Pacific are launching ad networks to monetise their audiences.", "category": "retail", "source": "MARKETECH APAC", "date": "This week", "url": "", "image": "https://picsum.photos/seed/2/600/280", "talkingPoints": ["Retail media lets brands reach consumers closest to the point of purchase.", "Closed-loop measurement connects ad spend directly to sales."], "isMovement": False},
        {"headline": "Agency account moves signal shifting brand priorities", "summary": "Several major advertisers have consolidated their media buying with new agency partners.", "category": "industry", "source": "Adweek", "date": "This week", "url": "", "image": "https://picsum.photos/seed/3/600/280", "talkingPoints": ["Account moves signal brands are seeking more integrated, data-driven partners.", "New agency relationships often coincide with a fresh look at digital channel mix."], "isMovement": True},
    ]


def main():
    print("=" * 50)
    print("GrabAds Weekly News Generator (RSS Version)")
    print(f"Running at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    print("\nFetching RSS feeds...")
    all_articles = fetch_all_articles()

    print("\nSelecting top articles...")
    top_articles = select_top_articles(all_articles, max_articles=12)
    print(f"  Selected {len(top_articles)} articles")

    print("\nFormatting and generating talking points...")
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

    total = sum(1 for _ in formatted)
    print("\n" + "=" * 50)
    print(f"news.json written successfully — {total} articles")
    print("=" * 50)


if __name__ == "__main__":
    main()
