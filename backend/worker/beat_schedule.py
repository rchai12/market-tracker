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
    # Signal generation - runs at :30 (after sentiment processing)
    "generate-signals": {
        "task": "worker.tasks.signals.signal_generator.generate_all_signals",
        "schedule": crontab(minute=30),
    },
    # Data maintenance - daily at 3 AM
    "data-maintenance": {
        "task": "worker.tasks.maintenance.compress_old_articles",
        "schedule": crontab(hour=3, minute=0),
    },
}
