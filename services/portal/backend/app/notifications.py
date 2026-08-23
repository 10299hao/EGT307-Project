#window notification

import asyncio

import httpx

from .config import Settings
from .database import PortalDatabase


def local_notification_payload(incident: dict) -> dict:
    """Convert a stored incident into the local receiver's small JSON contract."""
    confidence = f"{float(incident['anomaly_probability']) * 100:.2f}%"
    category = str(incident["category"]).replace("_", " ").title()
    severity = str(incident["severity"]).upper()
    action = str(incident["recommended_action"]).replace("_", " ").title()
    return {
        "source": "LogSentinel",
        "title": f"{severity} HDFS incident detected",
        "message": f"{category} - {confidence} confidence",
        "incident_id": incident["incident_id"],
        "block_id": incident["block_id"],
        "severity": severity,
        "category": category,
        "confidence": confidence,
        "recommended_action": action,
    }


async def send_local_notification(
    incident: dict,
    database: PortalDatabase,
    config: Settings,
) -> None:
    """Deliver one new incident and record every attempt for auditing."""
    if not config.local_notification_configured:
        return

    payload = local_notification_payload(incident)
    for attempt in range(1, config.notification_max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=config.notification_timeout_seconds) as client:
                response = await client.post(config.local_notification_url, json=payload)
                response.raise_for_status()
            database.record_notification(
                incident["incident_id"], attempt, "delivered", response.status_code
            )
            return
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            database.record_notification(
                incident["incident_id"], attempt, "failed", error=str(exc)[:300]
            )
            if attempt < config.notification_max_attempts:
                # Short exponential backoff: 1 second, then 2 seconds.
                await asyncio.sleep(2 ** (attempt - 1))
