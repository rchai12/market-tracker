import pytest


@pytest.fixture
def sample_article():
    return {
        "source": "yahoo_finance",
        "source_url": "https://example.com/article/1",
        "title": "ExxonMobil Reports Strong Q4 Earnings",
        "raw_text": "Exxon Mobil Corporation $XOM reported strong fourth quarter earnings...",
        "author": "Test Author",
    }
