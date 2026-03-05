from celery.schedules import crontab

beat_schedule = {
    # Hourly scraping - runs at :00 every hour
    "scrape-all-sources": {
        "task": "worker.tasks.scraping.orchestrate_scraping",
        "schedule": crontab(minute=0),
    },
    # Market data - runs at :05, weekdays only
    "fetch-market-data": {
        "task": "worker.tasks.scraping.market_data.fetch_all_market_data",
        "schedule": crontab(minute=5, day_of_week="1-5"),
    },
    # Sentiment catch-up - runs at :15 to process any missed articles
    # (primary sentiment runs chained after scraping at :00)
    "sentiment-catchup": {
        "task": "worker.tasks.sentiment.sentiment_task.process_new_articles_sentiment",
        "schedule": crontab(minute=15),
    },
    # Signal generation - runs at :30 (after sentiment processing)
    "generate-signals": {
        "task": "worker.tasks.signals.signal_generator.generate_all_signals",
        "schedule": crontab(minute=30),
    },
    # Data maintenance - daily at 3 AM (runs all cleanup tasks sequentially)
    "data-maintenance": {
        "task": "worker.tasks.maintenance.run_all_maintenance",
        "schedule": crontab(hour=3, minute=0),
    },
}
