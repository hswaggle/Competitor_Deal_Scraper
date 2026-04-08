"""
main.py
Orchestrates the acquisition tracker pipeline.
Run by GitHub Actions on the configured schedule.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import yaml

# Allow imports from src/ when run as `python src/main.py`
sys.path.insert(0, str(Path(__file__).parent))

from scraper import scrape_all
from enricher import enrich_articles
from deduplicator import filter_new, persist_seen
from formatter import format_report
from send_email import send_email_report

load_dotenv()

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def parse_extra_recipients(raw: str) -> list[str]:
    if not raw:
        return []
    return [r.strip() for r in raw.split(",") if r.strip()]


def main() -> bool:
    print("=" * 60)
    print("ACQUISITION TRACKER — AUTOMATED RUN")
    print("=" * 60)

    # ── Load config ───────────────────────────────────────────────────────
    cfg = load_config()
    acquirers: list[str] = cfg.get("acquirers", [])
    lookback_days: int = cfg.get("lookback_days", 16)
    output_format: str = cfg.get("output_format", "xlsx")
    subject: str = cfg.get("email_subject", "🔎 Software Acquisition Tracker Report")
    extra_recipients = parse_extra_recipients(cfg.get("extra_recipients", ""))

    print(f"\nMonitoring {len(acquirers)} acquirer(s), lookback = {lookback_days} days")

    # ── Step 1: Scrape ────────────────────────────────────────────────────
    print("\n[1/4] Scraping acquisition news...")
    raw_articles = scrape_all(acquirers, lookback_days)
    print(f"✓ {len(raw_articles)} total articles scraped")

    if not raw_articles:
        print("\n⚠ No articles found. Sending a 'nothing new' email and exiting.")
        send_email_report(
            attachment_data=b"",
            attachment_filename="no_deals.txt",
            num_deals=0,
            acquirers=acquirers,
            subject=subject + " (no new deals)",
            extra_recipients=extra_recipients,
        )
        return True

    # ── Step 2: Deduplicate ───────────────────────────────────────────────
    print("\n[2/4] Deduplicating against prior runs...")
    new_articles, updated_seen = filter_new(raw_articles)

    if not new_articles:
        print("✓ No new articles since last run. Nothing to report.")
        return True

    # ── Step 3: Enrich ────────────────────────────────────────────────────
    print("\n[3/4] Enriching articles with Claude...")
    enriched = enrich_articles(new_articles)

    # Strip internal-only fields before formatting
    for a in enriched:
        a.pop("published_dt", None)

    print(f"✓ {len(enriched)} articles after enrichment + filtering")

    # ── Step 4: Format + send ─────────────────────────────────────────────
    print(f"\n[4/4] Building {output_format.upper()} report and sending email...")
    report_data, filename = format_report(enriched, output_format)

    success = send_email_report(
        attachment_data=report_data,
        attachment_filename=filename,
        num_deals=len(enriched),
        acquirers=acquirers,
        subject=subject,
        extra_recipients=extra_recipients,
    )

    if success:
        # Persist dedup state only after a successful send
        persist_seen(updated_seen)
        print("\n" + "=" * 60)
        print("✓ ACQUISITION TRACKER COMPLETED SUCCESSFULLY")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("✗ EMAIL FAILED — seen.json NOT updated (will retry next run)")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
