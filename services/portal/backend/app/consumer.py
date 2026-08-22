import asyncio
import json
import logging

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from .adapters import normalise_analyzer_incident
from .config import Settings
from .database import PortalDatabase
from .executor import dispatch_action_request
from .notifications import send_local_notification
from .schemas import ActionResultIn, IncidentIn


logger = logging.getLogger(__name__)
#consume Analyzer incidents and Executor results from Redis
class StreamConsumer:
    def __init__(self, database: PortalDatabase, config: Settings):
        self.database = database
        self.config = config
        self.redis = Redis.from_url(config.redis_url, decode_responses=True)
        self.running = False

    async def ensure_groups(self) -> None:
        for stream in (*self.config.incident_streams, self.config.action_result_stream):
            try:
                await self.redis.xgroup_create(stream, self.config.consumer_group, id="0", mkstream=True)
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

    async def run(self) -> None:
        self.running = True
        while self.running:
            try:
                await self.ensure_groups()
                while self.running:
                    messages = await self.redis.xreadgroup(
                        self.config.consumer_group,
                        self.config.consumer_name,
                        {stream: ">" for stream in (*self.config.incident_streams, self.config.action_result_stream)},
                        count=10,
                        block=2000,
                    )
                    for stream, entries in messages:
                        for message_id, fields in entries:
                            await self._handle(stream, message_id, fields)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Portal stream consumer crashed, retrying in 5 seconds")
                await asyncio.sleep(5)
                
    async def _handle(self, stream: str, message_id: str, fields: dict[str, str]) -> None:
        try:
            raw = fields.get("payload") or fields.get("data") or json.dumps(fields)
            payload = json.loads(raw)
            if stream in self.config.incident_streams:
                incident = IncidentIn.model_validate(normalise_analyzer_incident(payload))
                is_new = self.database.upsert_incident(incident)
                stored = self.database.get_incident(incident.incident_id)
                await dispatch_action_request(self.redis, self.database, self.config, stored)
                if is_new:
                    await send_local_notification(stored, self.database, self.config)
            else:
                self.database.upsert_action_result(ActionResultIn.model_validate(payload))
            await self.redis.xack(stream, self.config.consumer_group, message_id)
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
            await self.redis.xadd(
                self.config.dead_letter_stream,
                {"source_stream": stream, "source_id": message_id, "error": str(exc), "payload": json.dumps(fields)},
            )
            await self.redis.xack(stream, self.config.consumer_group, message_id)
        except Exception:
            logger.exception("Portal failed to process Redis message %s", message_id)

    async def close(self) -> None:
        self.running = False
        await self.redis.aclose()

    async def is_ready(self) -> bool:
        try:
            return bool(await asyncio.wait_for(self.redis.ping(), timeout=1))
        except Exception:
            return False
