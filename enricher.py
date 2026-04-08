"""
enricher.py
Uses the Claude API to extract structured acquisition details
(target company, deal size, sector, summary) from raw article titles.

Requires ANTHROPIC_API_KEY to be set as a GitHub Actions secret / .env var.
If the key is missing, articles pass through unenriched.
"""
import json
import os
import urllib.request
import urllib.error


_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-sonnet-4-20250514"


def _call_claude(prompt: str) -> str | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    payload = json.dumps(
        {
            "model": _MODEL,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()

    req = urllib.request.Request(
        _API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            return body["content"][0]["text"]
    except Exception as e:
        print(f"  ✗ Claude API error: {e}")
        return None


def enrich_articles(articles: list[dict]) -> list[dict]:
    """
    Sends article titles in batches to Claude and asks it to extract:
      - target_company  (the company being acquired)
      - deal_size       (e.g. "$1.2B" or "undisclosed")
      - sector          (e.g. "cybersecurity", "analytics", "AI/ML")
      - is_acquisition  (true/false — filter out non-acquisition news)
      - summary         (one sentence)

    Falls back gracefully if the API key is absent.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("  ℹ ANTHROPIC_API_KEY not set — skipping enrichment.")
        for a in articles:
            a.setdefault("target_company", "")
            a.setdefault("deal_size", "")
            a.setdefault("sector", "")
            a.setdefault("is_acquisition", True)
            a.setdefault("summary", "")
        return articles

    # Process in batches of 10 to keep prompts short
    BATCH = 10
    enriched = []

    for i in range(0, len(articles), BATCH):
        batch = articles[i : i + BATCH]
        numbered = "\n".join(
            f"{j+1}. [{a['acquirer']}] {a['title']}" for j, a in enumerate(batch)
        )

        prompt = f"""You are an M&A analyst assistant. Given these news article titles, extract structured data.

For each article return a JSON array where each element has:
- "index": the 1-based number
- "target_company": name of the company being acquired (empty string if unclear)
- "deal_size": deal value as reported (e.g. "$1.2B", "undisclosed", or "" if unknown)
- "sector": software sector (e.g. "cybersecurity", "analytics", "AI/ML", "cloud infra", "HR tech")
- "is_acquisition": true if this is genuinely about an acquisition/merger, false if it's unrelated news
- "summary": one sentence plain-English summary of the deal

Return ONLY a valid JSON array, no markdown, no explanation.

Articles:
{numbered}
"""

        raw = _call_claude(prompt)
        parsed = []

        if raw:
            try:
                parsed = json.loads(raw.strip())
            except json.JSONDecodeError:
                print(f"  ✗ Could not parse enrichment response for batch {i//BATCH + 1}")

        # Map results back onto articles by index
        result_map = {r["index"]: r for r in parsed if isinstance(r, dict)}

        for j, article in enumerate(batch):
            r = result_map.get(j + 1, {})
            article["target_company"] = r.get("target_company", "")
            article["deal_size"] = r.get("deal_size", "")
            article["sector"] = r.get("sector", "")
            article["is_acquisition"] = r.get("is_acquisition", True)
            article["summary"] = r.get("summary", "")
            enriched.append(article)

    # Filter out articles Claude flagged as non-acquisitions
    before = len(enriched)
    enriched = [a for a in enriched if a.get("is_acquisition", True)]
    dropped = before - len(enriched)
    if dropped:
        print(f"  ✓ Filtered out {dropped} non-acquisition articles after enrichment")

    return enriched
