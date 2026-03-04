"""Reddit scraper using PRAW (r/stocks, r/wallstreetbets)."""

import logging
from datetime import datetime, timezone

from worker.tasks.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

SUBREDDITS = ["stocks", "wallstreetbets"]


class RedditScraper(BaseScraper):
    source_name = "reddit_stocks"

    def _get_reddit_client(self):
        """Create PRAW Reddit instance. Returns None if credentials missing."""
        from app.config import settings

        if not settings.reddit_client_id or not settings.reddit_client_secret:
            logger.warning("Reddit API credentials not configured, skipping")
            return None

        import praw

        return praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

    def scrape(self) -> list[dict]:
        reddit = self._get_reddit_client()
        if not reddit:
            return []

        articles = []

        for sub_name in SUBREDDITS:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=25):
                    # Skip stickied/pinned posts
                    if post.stickied:
                        continue

                    articles.append({
                        "title": post.title,
                        "url": f"https://reddit.com{post.permalink}",
                        "body": post.selftext[:5000] if post.selftext else None,
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "subreddit": sub_name,
                        "created_utc": post.created_utc,
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch r/{sub_name}: {e}")

        return articles

    def parse(self, raw_data: list[dict]) -> list[dict]:
        seen_urls = set()
        parsed = []

        for item in raw_data:
            url = item.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Only keep posts with some engagement
            if item.get("score", 0) < 10:
                continue

            created = None
            if item.get("created_utc"):
                created = datetime.fromtimestamp(item["created_utc"], tz=timezone.utc)

            sub = item.get("subreddit", "stocks")
            source_name = f"reddit_{sub}" if sub == "wallstreetbets" else "reddit_stocks"

            parsed.append({
                "source": source_name,
                "source_url": url,
                "title": item["title"],
                "raw_text": item.get("body"),
                "published_at": created or datetime.now(timezone.utc),
                "metadata": {
                    "score": item.get("score"),
                    "num_comments": item.get("num_comments"),
                    "subreddit": sub,
                },
            })

        return parsed
