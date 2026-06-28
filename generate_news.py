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
    {"name": "Marketing Interactive", "url": "https://rss.app/feeds/CQ6qthodCcoFXLjT.xml", "sea_trusted": True},
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
        "This is a good conversation starter for FMCG and e-commerce clients — ask them how they're currently measuring cross-channel performance, then introduce GrabAds' closed-loop attribution across the Grab ecosystem.",
        "For brands still relying on broad demographic targeting, this is an opportunity to show how GrabAds' first-party data from real transactions can sharpen their audience precision — book a discovery call to walk through a use case.",
        "If you're meeting a performance-focused client this week, use this to open a conversation about how GrabAds connects intent signals (food orders, rides, payments) directly to ad outcomes — ask for a brief to build a proposal.",
        "This is a great hook for finance or telco clients investing in digital — position GrabAds as a platform where ads reach high-frequency, high-intent users daily, and offer to share a relevant case study.",
        "For any client asking about cookieless targeting, use this as context to explain GrabAds' first-party data advantage — suggest a follow-up session to map their audience segments to our solutions.",
        "Bring this up with e-commerce or retail clients to show category expertise — then ask what their current cost-per-acquisition looks like and offer a GrabAds benchmark comparison.",
    ],
    "creative": [
        "Use this with F&B and QSR clients who run frequent promotions — ask if their current creatives are localised per market, and offer a GrabAds creative effectiveness review to show what resonates with Grab users.",
        "For FMCG brands running regional campaigns, this is a good prompt to ask: 'How are you adapting global assets for SEA?' — then position GrabAds' in-app formats as a high-attention environment for localised storytelling.",
        "If a client just launched a campaign, use this as an opener: 'Have you seen this trend in award-winning APAC work?' — then offer to share GrabAds creative benchmarks for their category.",
        "For travel or hospitality clients, connect this to seasonal campaigns — ask about their next peak period and propose a GrabAds brand awareness package timed around it.",
        "Use this with agencies to show creative intelligence — ask what briefs they're working on and offer a GrabAds format deep-dive to match their creative goals.",
    ],
    "media": [
        "For media planning clients, use this to challenge their current channel mix — ask what percentage of budget goes to mobile, and show how GrabAds reaches SEA consumers across 8 daily touchpoints in the app.",
        "For telco or streaming clients, this is a timely hook — ask if they're running any connected TV or in-app video activations, and propose a GrabAds video ad trial.",
        "If a client is heavy on traditional media, use this to introduce incremental reach — offer to model what adding GrabAds to their mix could deliver in terms of unique audience reach.",
        "For OOH-heavy brands, position this as a natural bridge to digital — ask if they've considered GrabAds' car-top DOOH formats to extend their outdoor presence into high-dwell moments.",
        "Use this with finance or banking clients running awareness campaigns — ask about their media mix and offer a GrabAds audience overlap analysis to show incrementality.",
    ],
    "retail": [
        "For FMCG or CPG clients, this is a direct conversation opener — ask if they're currently running any retail media activations, then introduce GrabAds' Retail Media Network and offer a tailored demo.",
        "For e-commerce or marketplace brands, use this to show urgency — retail media budgets are moving fast, and brands not building expertise now will lose shelf space to competitors. Offer to run a pilot.",
        "If a client sells through GrabMart or Grab Food, this is a natural lead-in — show how GrabAds can close the loop between their ad spend and actual basket purchases. Ask for a meeting to walk through the data.",
        "For QSR or F&B clients, connect this to GrabFood — ask how they're currently driving app orders, and propose a Sponsored Listing or GrabAds in-feed campaign to boost visibility at the point of hunger.",
        "Use this with any brand selling in SEA to show market momentum — then ask if they have a dedicated retail media budget, or if this is a conversation worth having with their trade team.",
    ],
    "industry": [
        "If this is a brand you're actively prospecting, reach out this week — leadership changes and agency switches are the best time to get a first meeting. Use this news as your reason to connect on LinkedIn.",
        "For brands in transition, position GrabAds as an easy first step — offer a no-commitment audience insights report to show the scale of their target audience on the Grab platform.",
        "Use this as an ice-breaker in your next client meeting — ask how the news affects their plans, then listen for budget signals before introducing how GrabAds fits into their new strategy.",
        "If a competitor just won this account, use it to re-engage dormant prospects in the same category — what worked for one brand in the vertical can work for another.",
        "For any account going through a pitch or review, offer something tangible — a GrabAds media plan, an audience sizing report, or a case study from a comparable brand to get your foot in the door.",
    ],
}

# ── Vertical and topic-specific talking points
# Triggered when article text matches a keyword — more specific than category templates
TOPIC_TALKING_POINTS = {
    "fmcg":         "Ask this FMCG client how they're currently driving trial and repeat purchase in SEA — then show how GrabAds reaches consumers at the moment they're ordering groceries or daily essentials on GrabMart.",
    "food":         "For F&B and QSR brands, ask about their next promotion window — then propose a GrabFood Sponsored Listing or in-app banner campaign to capture hungry, high-intent users at decision time.",
    "e-commerce":   "Ask this e-commerce client what their current cost-per-click looks like on other platforms — then offer to run a GrabAds benchmark comparison using transaction data from Grab's ecosystem.",
    "finance":      "For finance and banking clients, GrabAds offers access to verified, high-income urban consumers across SEA — ask about their current digital acquisition channels and offer a GrabAds audience sizing report.",
    "travel":       "With travel demand rebounding across SEA, ask this client about their next peak campaign — then propose a GrabAds travel vertical package targeting users actively booking rides to airports and hotels.",
    "telco":        "For telco clients, ask how they're reaching mobile-first consumers beyond their own app — then show how GrabAds in-app placements reach millions of verified users daily across SEA.",
    "tiktok":       "Use TikTok's growth as context — then ask if this client is spreading budget across too many platforms. Position GrabAds as the platform with the deepest purchase-intent data in SEA.",
    "influencer":   "Ask this client how they're measuring influencer ROI beyond reach — then introduce GrabAds performance formats that connect awareness to actual transactions on the Grab platform.",
    "retail media": "Ask if this brand has a dedicated retail media budget yet — if not, this is the moment to get in front of the right stakeholder. Offer to send a GrabAds Retail Media one-pager to start the conversation.",
    "programmatic": "Ask what DSPs this client is currently using and whether they have access to SEA-specific first-party data — then position GrabAds' programmatic offering as the only one built on real transaction behaviour in the region.",
    "first-party":  "Ask this client how they're preparing for the cookieless future — then show how GrabAds' first-party data from 35M+ SEA users gives them targeting precision that third-party data can't match.",
    "connected tv": "Ask if this client is currently running any CTV activations — then propose a GrabAds video campaign targeting premium in-app placements to reach cord-cutters across SEA.",
    "out-of-home":  "For OOH-active clients, ask if they've considered extending their outdoor presence into high-dwell digital moments — then introduce GrabAds' car-top DOOH and in-app formats as a complement.",
    "measurement":  "Ask this client how they're currently proving campaign ROI to their CFO — then offer a GrabAds closed-loop measurement pilot to connect ad impressions directly to sales outcomes.",
    "acquisition":  "Ask what their current customer acquisition cost looks like — then offer a GrabAds performance campaign proposal benchmarked against category averages on the Grab platform.",
    "brand":        "Ask how this client balances brand building vs performance in their current budget split — then show how GrabAds supports both with full-funnel solutions across Grab's super-app.",
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
                url     = extract_article_url(entry, entry.get("link", ""))
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


def select_top_articles(all_articles: list, max_articles: int = 6) -> list:
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


def extract_article_url(entry, fallback_url: str) -> str:
    """For Telegram posts (t.me links), extract the real article URL from the post body."""
    if "t.me/" not in fallback_url:
        return fallback_url
    # Search raw HTML content for an external http(s) link
    raw_html = entry.get("summary", "") or entry.get("description", "") or ""
    matches = re.findall(r'href=["\']?(https?://(?!t\.me)[^\s"\'<>]+)', raw_html)
    return matches[0] if matches else fallback_url


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
    top_articles = select_top_articles(all_articles, max_articles=6)
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
