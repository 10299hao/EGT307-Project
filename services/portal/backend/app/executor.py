#send action requests to executor

import json

from redis.asyncio import Redis

from .config import Settings
from .database import PortalDatabase


async def dispatch_action_request(
    redis: Redis,
    database: PortalDatabase,
    config: Settings,
    incident: dict,
) -> str | None:
    """Publish Ethan's ActionStream contract once for each incident.

    The Redis message ID is stored in SQLite. That audit field also acts as
    duplicate protection if the Analyzer replays the same incident.
    """
    incident_id = incident["incident_id"]
    if not config.enable_executor or database.action_already_dispatched(incident_id):
        return None

    command = {
        "incident_id": incident_id,
        "action": incident["recommended_action"],
    }
    try:
        message_id = await redis.xadd(
            config.action_request_stream,
            {config.action_request_field: json.dumps(command)},
        )
        database.record_action_dispatch(incident_id, request_id=str(message_id))
        return str(message_id)
    except Exception as exc:
        database.record_action_dispatch(incident_id, error=str(exc)[:300])
        raise
