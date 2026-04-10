"""
MarketSentinel — X API Post Fetcher
=====================================
Uses Tweepy v4+ (OAuth 2.0 Bearer Token) to:
  1. Load the watchlist from config.json
  2. Fetch recent tweets for each monitored account
  3. Compute and cache each author's rolling engagement average
  4. Score each tweet using score_engine.py
  5. Write scored posts to ../data/posts.json (read by the dashboard)
  6. Print ALERT for any post exceeding the critical threshold

REQUIREMENTS:
  pip install tweepy requests schedule python-dotenv

USAGE:
  python fetch_posts.py            # runs once then exits
  python fetch_posts.py --loop     # runs every N minutes (set in config)
  python fetch_posts.py --test     # dry-run with mock data (no API calls)
"""

import json
import logging
import os
import sys
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

try:
    import tweepy
except ImportError:
    print("ERROR: tweepy not installed. Run: pip install tweepy")
    sys.exit(1)

from score_engine import ScoreEngine

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("../data/sentinel.log", mode="a"),
    ],
)
logger = logging.getLogger("MarketSentinel")

CONFIG_PATH = Path(__file__).parent / "config.json"
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════
class MarketSentinelFetcher:

    def __init__(self, config: dict, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.settings = config["settings"]
        self.scorer = ScoreEngine(config)
        self.output_path = DATA_DIR / "posts.json"
        self.baselines_path = DATA_DIR / "author_baselines.json"
        self.baselines = self._load_baselines()

        if not dry_run:
            bearer = config["api_keys"]["x_bearer_token"]
            if bearer == "YOUR_X_BEARER_TOKEN_HERE":
                logger.error("X Bearer Token not configured. Edit backend/config.json first.")
                sys.exit(1)
            self.client = tweepy.Client(bearer_token=bearer, wait_on_rate_limit=True)
            logger.info("X API client initialised (bearer token)")
        else:
            self.client = None
            logger.info("DRY RUN MODE — no API calls will be made")

    # ────────────────────────────────────────
    # BASELINE MANAGEMENT
    # ────────────────────────────────────────
    def _load_baselines(self) -> dict:
        if self.baselines_path.exists():
            with open(self.baselines_path) as f:
                return json.load(f)
        return {}

    def _save_baselines(self):
        with open(self.baselines_path, "w") as f:
            json.dump(self.baselines, f, indent=2)

    def _update_baseline(self, author_id: str, metrics: dict):
        """Update rolling average for an author using exponential moving average."""
        if author_id not in self.baselines:
            self.baselines[author_id] = {
                "avg_views":   metrics.get("impression_count", 0),
                "avg_reposts": metrics.get("retweet_count", 0),
                "avg_likes":   metrics.get("like_count", 0),
                "avg_replies": metrics.get("reply_count", 0),
                "sample_count": 1,
            }
        else:
            b = self.baselines[author_id]
            alpha = 0.1  # EMA smoothing factor (lower = more stable baseline)
            b["avg_views"]   = (1 - alpha) * b["avg_views"]   + alpha * metrics.get("impression_count", 0)
            b["avg_reposts"] = (1 - alpha) * b["avg_reposts"] + alpha * metrics.get("retweet_count", 0)
            b["avg_likes"]   = (1 - alpha) * b["avg_likes"]   + alpha * metrics.get("like_count", 0)
            b["avg_replies"] = (1 - alpha) * b["avg_replies"] + alpha * metrics.get("reply_count", 0)
            b["sample_count"] = b.get("sample_count", 0) + 1

    # ────────────────────────────────────────
    # FETCH X POSTS
    # ────────────────────────────────────────
    def fetch_user_tweets(self, author: dict, max_results: int = 10) -> list[dict]:
        """
        Fetch recent tweets for a single X user.
        Returns list of raw tweet dicts.
        """
        handle = author["handle"]
        try:
            # Get user ID from handle if not stored
            user_resp = self.client.get_user(
                username=handle,
                user_fields=["id", "name", "public_metrics"]
            )
            if not user_resp.data:
                logger.warning(f"Could not find user: @{handle}")
                return []

            user = user_resp.data
            user_id = user.id

            # Calculate lookback window
            lookback_hours = self.settings.get("lookback_hours", 24)
            start_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

            # Fetch tweets
            tweets_resp = self.client.get_users_tweets(
                id=user_id,
                max_results=min(max_results, 100),
                start_time=start_time,
                tweet_fields=[
                    "created_at", "text", "public_metrics",
                    "context_annotations", "entities"
                ],
                exclude=["retweets", "replies"],  # only original posts
            )

            if not tweets_resp.data:
                logger.info(f"@{handle}: no new posts in last {lookback_hours}h")
                return []

            tweets = []
            for tweet in tweets_resp.data:
                metrics = tweet.public_metrics or {}
                tweet_dict = {
                    "tweet_id": str(tweet.id),
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "metrics": {
                        "views":   metrics.get("impression_count", 0),
                        "reposts": metrics.get("retweet_count", 0),
                        "likes":   metrics.get("like_count", 0),
                        "replies": metrics.get("reply_count", 0),
                    },
                    "raw_metrics": metrics,
                }
                tweets.append(tweet_dict)
                self._update_baseline(str(user_id), metrics)

            logger.info(f"@{handle}: fetched {len(tweets)} tweets")
            return tweets

        except tweepy.TooManyRequests:
            logger.warning(f"Rate limited fetching @{handle} — skipping this cycle")
            return []
        except tweepy.Unauthorized:
            logger.error("Unauthorized — check your API keys in config.json")
            return []
        except Exception as e:
            logger.error(f"Error fetching @{handle}: {e}")
            return []

    # ────────────────────────────────────────
    # PROCESS AND SCORE
    # ────────────────────────────────────────
    def process_tweets(self, tweets: list[dict], author: dict, author_id: str) -> list[dict]:
        """Score a list of tweets and return those above min_score threshold."""
        min_score = self.settings.get("min_score_to_save", 30)
        processed = []

        for t in tweets:
            baseline = self.baselines.get(author_id, {})
            score_result = self.scorer.score_post(
                text=t["text"],
                author=author,
                post_metrics=t["metrics"],
                author_averages=baseline,
            )

            if score_result["score"] < min_score:
                continue

            # Build the full post record (matching dashboard's expected format)
            post = {
                "tweet_id":     t["tweet_id"],
                "author":       author["name"],
                "authorId":     author["handle"].lower(),
                "role":         author.get("role", ""),
                "platform":     author.get("platform", "x").upper(),
                "handle":       f"@{author['handle']}",
                "created_at":   t["created_at"],
                "text":         t["text"],
                "score":        score_result["score"],
                "scoreClass":   score_result["score_class"],
                "signals":      score_result["signals"],
                "tickers":      score_result["tickers"],
                "direction":    score_result["direction"],
                "metrics": {
                    "views":   {"value": _fmt_number(t["metrics"]["views"]),   "label": "Views",   "vs": _fmt_spike(score_result["engagement_spike"])},
                    "reposts": {"value": _fmt_number(t["metrics"]["reposts"]), "label": "Reposts", "vs": ""},
                    "likes":   {"value": _fmt_number(t["metrics"]["likes"]),   "label": "Likes",   "vs": ""},
                    "replies": {"value": _fmt_number(t["metrics"]["replies"]), "label": "Replies", "vs": ""},
                },
                "impactBreakdown": score_result["breakdown"],
                "dramatic_keywords": score_result["dramatic_keywords"],
                "policy_keywords":   score_result["policy_keywords"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            processed.append(post)

            # Alert for high-impact posts
            alert_threshold = self.settings.get("alert_threshold", 75)
            critical_threshold = self.settings.get("critical_threshold", 85)
            if post["score"] >= alert_threshold:
                severity = "CRITICAL" if post["score"] >= critical_threshold else "HIGH IMPACT"
                tickers_str = ", ".join(post["tickers"]) if post["tickers"] else "no specific ticker"
                logger.warning(
                    f"🚨 [{severity}] @{author['handle']} — Score: {post['score']} "
                    f"| Tickers: {tickers_str} | '{t['text'][:80]}...'"
                )

        return processed

    # ────────────────────────────────────────
    # SAVE OUTPUT
    # ────────────────────────────────────────
    def save_posts(self, posts: list[dict]):
        """Merge new posts with existing data, deduplicate, sort by score."""
        existing = []
        if self.output_path.exists():
            with open(self.output_path) as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []

        # Deduplicate by tweet_id
        existing_ids = {p["tweet_id"] for p in existing if "tweet_id" in p}
        new_posts = [p for p in posts if p.get("tweet_id") not in existing_ids]

        all_posts = new_posts + existing
        # Sort by score descending, keep latest 500
        all_posts.sort(key=lambda x: x["score"], reverse=True)
        all_posts = all_posts[:500]

        with open(self.output_path, "w") as f:
            json.dump(all_posts, f, indent=2)

        logger.info(f"Saved {len(new_posts)} new posts (total: {len(all_posts)})")
        return new_posts

    # ────────────────────────────────────────
    # MAIN RUN CYCLE
    # ────────────────────────────────────────
    def run_cycle(self):
        """Execute one full fetch-score-save cycle across all watchlist accounts."""
        logger.info("═" * 50)
        logger.info("Starting fetch cycle...")
        all_scored_posts = []

        watchlist = self.config["watchlist"]
        all_authors = (
            watchlist.get("hedge_fund_managers", []) +
            watchlist.get("short_sellers", []) +
            watchlist.get("macro_policy", []) +
            watchlist.get("market_commentators", [])
        )

        x_authors = [a for a in all_authors if a.get("platform", "x") == "x"]
        truth_authors = [a for a in all_authors if a.get("platform") == "truth"]

        # Fetch X posts
        for author in x_authors:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would fetch @{author['handle']}")
                continue

            tweets = self.fetch_user_tweets(author)
            if tweets:
                author_id = author.get("x_id", author["handle"])
                scored = self.process_tweets(tweets, author, author_id)
                all_scored_posts.extend(scored)

            # Small delay to be respectful to API rate limits
            time.sleep(0.5)

        # Truth Social (unofficial — placeholder for scraping module)
        if truth_authors:
            logger.info(f"Truth Social accounts ({len(truth_authors)}) — scraping module not yet active. See truth_scraper.py")

        if all_scored_posts or self.dry_run:
            if not self.dry_run:
                new_posts = self.save_posts(all_scored_posts)
                self._save_baselines()
                logger.info(f"Cycle complete. {len(new_posts)} new high-impact posts saved.")
            else:
                logger.info("[DRY RUN] Cycle complete — no data written.")
        else:
            logger.info("No posts exceeded minimum score threshold this cycle.")

        return all_scored_posts


# ────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────
def _fmt_number(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)

def _fmt_spike(mult: float) -> str:
    if mult <= 0: return ""
    if mult >= 2: return f"{mult:.0f}× avg"
    return "~avg"


# ════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MarketSentinel Post Fetcher")
    parser.add_argument("--loop",  action="store_true", help="Run continuously on interval")
    parser.add_argument("--test",  action="store_true", help="Dry run (no API calls)")
    args = parser.parse_args()

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    fetcher = MarketSentinelFetcher(config, dry_run=args.test)

    if args.loop:
        interval_minutes = config["settings"].get("fetch_interval_minutes", 5)
        logger.info(f"Running in loop mode — fetching every {interval_minutes} minutes")
        try:
            while True:
                fetcher.run_cycle()
                logger.info(f"Sleeping {interval_minutes} minutes until next cycle...")
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            logger.info("MarketSentinel stopped by user.")
    else:
        fetcher.run_cycle()
