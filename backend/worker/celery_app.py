from celery import Celery
from celery.signals import worker_process_init

from app.config import settings

celery_app = Celery(
    "stock_predictor",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "worker.tasks.scraping.*": {"queue": "scraping"},
        "worker.tasks.sentiment.*": {"queue": "sentiment"},
        "worker.tasks.signals.*": {"queue": "signals"},
        "worker.tasks.maintenance.*": {"queue": "maintenance"},
    },
)


@worker_process_init.connect
def init_worker_logging(**_kwargs):
    """Configure structured JSON logging for each Celery worker process."""
    from app.core.logging_config import setup_logging

    setup_logging(settings.log_level)

celery_app.conf.include = [
    "worker.tasks.scraping.orchestrate",
    "worker.tasks.scraping.market_data",
    "worker.tasks.scraping.yahoo_news",
    "worker.tasks.scraping.finviz",
    "worker.tasks.scraping.reuters_rss",
    "worker.tasks.scraping.sec_edgar",
    "worker.tasks.scraping.marketwatch",
    "worker.tasks.scraping.reddit",
    "worker.tasks.scraping.fred",
    "worker.tasks.sentiment.sentiment_task",
    "worker.tasks.signals.signal_generator",
    "worker.tasks.signals.alert_dispatcher",
    "worker.tasks.maintenance.tasks",
]

# Import beat schedule
from worker.beat_schedule import beat_schedule  # noqa: E402

celery_app.conf.beat_schedule = beat_schedule
