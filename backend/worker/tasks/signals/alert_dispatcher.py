"""Alert dispatcher task.

For a given signal, finds all matching AlertConfig records and sends
notifications via Discord webhook and/or email SMTP. Logs each attempt
in AlertLog.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models.alert import AlertConfig, AlertLog
from app.models.signal import Signal
from app.models.user import User
from worker.celery_app import celery_app
from worker.utils.async_task import run_async

logger = logging.getLogger(__name__)

STRENGTH_ORDER = {"weak": 0, "moderate": 1, "strong": 2}


@celery_app.task(
    name="worker.tasks.signals.alert_dispatcher.dispatch_alerts",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def dispatch_alerts(self, signal_id: int):
    """Dispatch alerts for a signal to all matching user configs."""
    try:
        return run_async(_dispatch_alerts_async(signal_id))
    except Exception as exc:
        logger.error(f"Alert dispatch failed for signal {signal_id}: {exc}")
        raise self.retry(exc=exc)


async def _dispatch_alerts_async(signal_id: int) -> dict:
    """Find matching configs and send alerts."""
    sent = 0
    failed = 0

    async with async_session() as session:
        result = await session.execute(
            select(Signal)
            .options(selectinload(Signal.stock))
            .where(Signal.id == signal_id)
        )
        signal = result.scalar_one_or_none()

        if signal is None:
            logger.error(f"Signal {signal_id} not found")
            return {"sent": 0, "failed": 0, "error": "signal_not_found"}

        configs = await _find_matching_configs(session, signal)

        if not configs:
            logger.info(f"No matching alert configs for signal {signal_id}")
            return {"sent": 0, "failed": 0}

        logger.info(f"Dispatching signal {signal_id} to {len(configs)} alert configs")

        for config in configs:
            user_result = await session.execute(
                select(User).where(User.id == config.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user is None:
                continue

            channels = _get_channels(config.channel)

            for channel in channels:
                success, error_msg = await _send_alert(channel, signal, user)

                log = AlertLog(
                    signal_id=signal.id,
                    user_id=user.id,
                    channel=channel,
                    success=success,
                    error_message=error_msg,
                )
                session.add(log)

                if success:
                    sent += 1
                else:
                    failed += 1

        await session.commit()

    logger.info(f"Alert dispatch complete for signal {signal_id}: {sent} sent, {failed} failed")
    return {"sent": sent, "failed": failed}


async def _find_matching_configs(session, signal: Signal) -> list[AlertConfig]:
    """Find active AlertConfigs that match this signal's stock, strength, and direction."""
    signal_strength_val = STRENGTH_ORDER.get(signal.strength, 0)

    result = await session.execute(
        select(AlertConfig).where(AlertConfig.is_active == True)  # noqa: E712
    )
    all_configs = result.scalars().all()

    matched = []
    for config in all_configs:
        if config.stock_id is not None and config.stock_id != signal.stock_id:
            continue

        min_strength_val = STRENGTH_ORDER.get(config.min_strength, 1)
        if signal_strength_val < min_strength_val:
            continue

        if config.direction_filter:
            if signal.direction not in config.direction_filter:
                continue

        matched.append(config)

    return matched


def _get_channels(channel: str) -> list[str]:
    """Expand 'both' into individual channels."""
    if channel == "both":
        return ["discord", "email"]
    return [channel]


async def _send_alert(
    channel: str, signal: Signal, user: User
) -> tuple[bool, str | None]:
    """Send a single alert via the specified channel."""
    try:
        if channel == "discord":
            return await _send_discord_alert(signal, user)
        elif channel == "email":
            return await _send_email_alert(signal, user)
        else:
            return False, f"Unknown channel: {channel}"
    except Exception as e:
        logger.error(f"Alert send error ({channel}): {e}")
        return False, str(e)


async def _send_discord_alert(signal: Signal, user) -> tuple[bool, str | None]:
    """Send a Discord webhook notification."""
    webhook_url = getattr(user, "discord_webhook_url", None) or settings.discord_webhook_url

    if not webhook_url:
        return False, "No Discord webhook URL configured"

    ticker = signal.stock.ticker if signal.stock else "Unknown"

    color_map = {"bullish": 0x22C55E, "bearish": 0xEF4444, "neutral": 0x6B7280}
    strength_emoji = {"strong": "!!!", "moderate": "!!", "weak": "!"}

    embed = {
        "title": f"{strength_emoji.get(signal.strength, '')} {signal.direction.upper()} Signal: {ticker}",
        "description": signal.reasoning or "No reasoning available.",
        "color": color_map.get(signal.direction, 0x6B7280),
        "fields": [
            {"name": "Composite Score", "value": f"{float(signal.composite_score):.3f}", "inline": True},
            {"name": "Strength", "value": signal.strength.capitalize(), "inline": True},
            {"name": "Articles (24h)", "value": str(signal.article_count), "inline": True},
        ],
        "footer": {"text": "Stock Predictor Signal"},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json={"embeds": [embed]})
        if response.status_code in (200, 204):
            return True, None
        else:
            return False, f"Discord API returned {response.status_code}: {response.text[:200]}"


async def _send_email_alert(signal: Signal, user) -> tuple[bool, str | None]:
    """Send an email alert via SMTP."""
    if not settings.smtp_user or not settings.smtp_password:
        return False, "SMTP not configured"

    if not user.email:
        return False, "User has no email address"

    ticker = signal.stock.ticker if signal.stock else "Unknown"

    subject = f"[Stock Predictor] {signal.strength.capitalize()} {signal.direction} signal: {ticker}"

    body_html = f"""
    <h2>{signal.direction.upper()} Signal for {ticker}</h2>
    <p><strong>Strength:</strong> {signal.strength.capitalize()}</p>
    <p><strong>Composite Score:</strong> {float(signal.composite_score):.3f}</p>
    <p><strong>Articles (24h):</strong> {signal.article_count}</p>
    <p><strong>Reasoning:</strong> {signal.reasoning or 'N/A'}</p>
    <hr>
    <p style="color: #888; font-size: 12px;">Stock Predictor Signal Alert</p>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.alert_from_email or settings.smtp_user
    msg["To"] = user.email
    msg.attach(MIMEText(body_html, "html"))

    try:
        await asyncio.to_thread(_send_smtp, msg)
        return True, None
    except Exception as e:
        return False, f"SMTP error: {str(e)[:200]}"


def _send_smtp(msg: MIMEMultipart):
    """Synchronous SMTP send, called via asyncio.to_thread."""
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
