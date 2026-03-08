"""Near-duplicate article detection using fuzzy title matching.

Uses rapidfuzz token_set_ratio to compare article titles.
Financial headlines about the same event tend to share vocabulary
regardless of source, making title similarity effective.
"""

from rapidfuzz.fuzz import token_set_ratio


def find_duplicate_group(
    title: str,
    recent_articles: list[tuple[int, str, int | None]],
    threshold: float = 85.0,
) -> int | None:
    """Find a duplicate group for a new article based on title similarity.

    Args:
        title: Title of the new article.
        recent_articles: List of (article_id, title, existing_group_id) tuples
            from recent articles that share at least one ticker.
        threshold: Minimum token_set_ratio score (0-100) to consider a match.

    Returns:
        duplicate_group_id if a match is found, None otherwise.
        Uses the matched article's existing group_id, or the matched article's
        id as the new group identifier.
    """
    if not title or not recent_articles:
        return None

    best_score = 0.0
    best_match: tuple[int, int | None] | None = None  # (article_id, group_id)

    for article_id, other_title, group_id in recent_articles:
        if not other_title:
            continue
        score = token_set_ratio(title, other_title)
        if score > best_score:
            best_score = score
            best_match = (article_id, group_id)

    if best_score >= threshold and best_match is not None:
        article_id, group_id = best_match
        # Propagate existing group_id, or use the matched article's id as group id
        return group_id if group_id is not None else article_id

    return None
