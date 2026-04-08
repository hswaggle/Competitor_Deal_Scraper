"""
scraper.py
Fetches recent acquisition news for each configured acquirer
using Google News RSS — no API key required.
"""
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta


def _parse_rss_date(date_str: str) -> datetime | None:
    """Parse RSS pubDate string into a timezone-aware datetime."""
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def fetch_acquisitions_for(acquirer: str, lookback_days: int) -> list[dict]:
    """
    Query Google News RSS for acquisition news about a single acquirer.
    Returns a list of raw article dicts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    query = f'"{acquirer}" acquisition OR acquires OR acquired software'
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    )

    print(f"  Fetching news for: {acquirer}")

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AcquisitionTracker/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_bytes = response.read()
    except Exception as e:
        print(f"  ✗ Failed to fetch for {acquirer}: {e}")
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  ✗ Failed to parse RSS for {acquirer}: {e}")
        return []

    articles = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_str = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()

        pub_date = _parse_rss_date(pub_date_str) if pub_date_str else None

        # Drop articles outside the lookback window
        if pub_date and pub_date < cutoff:
            continue

        articles.append(
            {
                "acquirer": acquirer,
                "title": title,
                "url": link,
                "source": source,
                "published_date": pub_date.strftime("%Y-%m-%d") if pub_date else "",
                "published_dt": pub_date,  # kept for dedup sorting, stripped later
            }
        )

    print(f"  ✓ {len(articles)} articles found for {acquirer}")
    return articles


def scrape_all(acquirers: list[str], lookback_days: int) -> list[dict]:
    """
    Scrape acquisition news for every acquirer in the list.
    Adds a short sleep between requests to be polite to Google's servers.
    """
    all_articles = []
    for acquirer in acquirers:
        results = fetch_acquisitions_for(acquirer, lookback_days)
        all_articles.extend(results)
        time.sleep(1.5)  # gentle rate limiting
    return all_articles
