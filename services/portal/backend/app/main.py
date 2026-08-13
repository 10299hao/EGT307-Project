import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .adapters import normalise_analyzer_incident
from .config import settings
from .consumer import StreamConsumer
from .database import PortalDatabase
from .demo_data import seed
from .executor import dispatch_action_request
from .notifications import send_local_notification
from .schemas import AcknowledgeIn, ActionResultIn, IncidentIn


database = PortalDatabase(settings.database_path)
consumer: StreamConsumer | None = None
consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare storage/Redis on startup and close cleanly on shutdown."""
    global consumer, consumer_task
    if settings.seed_demo_data:
        seed(database)
    if settings.enable_redis:
        consumer = StreamConsumer(database, settings)
        consumer_task = asyncio.create_task(consumer.run())
    yield
    if consumer:
        await consumer.close()
    if consumer_task:
        consumer_task.cancel()


app = FastAPI(
    title="LogSentinel Incident Portal",
    version="1.0.0",
    description="Stores and presents AI-detected HDFS incidents and dry-run actions.",
    lifespan=lifespan,
)


@app.get("/api/health/live")
def liveness() -> dict:
    return {"status": "alive", "service": "incident-portal"}


@app.get("/api/health/ready")
async def readiness() -> dict:
    redis_ready = await consumer.is_ready() if consumer else None
    if settings.enable_redis and not redis_ready:
        raise HTTPException(status_code=503, detail="Redis is not ready")
    return {"status": "ready", "database": "connected", "redis": redis_ready}


@app.get("/api/incidents")
def incidents(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
) -> dict:
    items = database.list_incidents(severity, status, search)
    return {"items": items, "count": len(items)}


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: str) -> dict:
    incident = database.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident["notification_attempts"] = database.notification_history(incident_id)
    return incident


@app.post("/api/incidents/{incident_id}/acknowledge")
def acknowledge(incident_id: str, body: AcknowledgeIn) -> dict:
    if not database.acknowledge(incident_id, body.operator):
        raise HTTPException(status_code=404, detail="Incident not found")
    return database.get_incident(incident_id)


@app.get("/api/stats")
def stats() -> dict:
    return database.stats()


@app.get("/api/service-status")
async def service_status() -> dict:
    redis_ready = await consumer.is_ready() if consumer else False
    collector_state = "not configured"
    if settings.collector_health_url:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(settings.collector_health_url)
                collector_state = "online" if response.is_success else "offline"
        except httpx.HTTPError:
            collector_state = "offline"

    bridge_state = "disabled"
    analyzer_state = "waiting"
    executor_state = "disabled"
    if consumer and redis_ready:
        bridge_state = (
            "online"
            if await consumer.redis.exists(settings.bridge_heartbeat_key)
            else "offline"
        )
        analyzer_messages = await consumer.redis.xlen(settings.incident_stream)
        analyzer_state = "online" if analyzer_messages > 0 else "waiting"
        if settings.enable_executor:
            # Ethan's current service has no health endpoint or heartbeat, so
            # report the request path as configured rather than claiming online.
            executor_state = "configured"

    bridge_aligned = bridge_state == "online"
    return {
        "portal": "online",
        "database": "online",
        "redis": (
            "online"
            if redis_ready
            else ("disabled" if not settings.enable_redis else "offline")
        ),
        "local_notifications": (
            "configured" if settings.local_notification_configured else "not configured"
        ),
        "notification_channel": "windows-local" if settings.local_notification_configured else "none",
        "collector": collector_state,
        "analyzer": analyzer_state,
        "integration_bridge": bridge_state,
        "executor": executor_state,
        "mode": "live streams" if settings.enable_redis else "demo data",
        "data_source": "redis-streams" if settings.enable_redis else "seeded-demo-records",
        "incident_stream": settings.incident_stream,
        "incident_stream_aliases": list(settings.incident_stream_aliases),
        "action_result_stream": settings.action_result_stream,
        "action_request_stream": settings.action_request_stream,
        "action_request_field": settings.action_request_field,
        "executor_contract": "ethan-actionstream-v1",
        "executor_result_support": "awaiting-ethan-publisher",
        "dead_letter_stream": settings.dead_letter_stream,
        "consumer_group": settings.consumer_group,
        "collector_output_stream": settings.collector_output_stream,
        "collector_message_field": settings.collector_message_field,
        "analyzer_input_stream": settings.analyzer_input_stream,
        "analyzer_message_field": settings.analyzer_message_field,
        "analyzer_contract_adapter": "danish-analyzer-v1",
        "upstream_contract_match": bridge_aligned or (
            settings.collector_output_stream == settings.analyzer_input_stream
            and settings.collector_message_field == settings.analyzer_message_field
        ),
    }


@app.post("/api/ingest/incident", status_code=202)
async def ingest_incident(body: dict, tasks: BackgroundTasks) -> dict:
    try:
        incident = IncidentIn.model_validate(normalise_analyzer_incident(body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid Analyzer incident: {exc}") from exc
    is_new = database.upsert_incident(incident)
    stored = database.get_incident(incident.incident_id)
    if consumer and settings.enable_executor:
        await dispatch_action_request(consumer.redis, database, settings, stored)
        stored = database.get_incident(incident.incident_id)
    if is_new:
        tasks.add_task(send_local_notification, stored, database, settings)
    return {"accepted": True, "new": is_new, "incident_id": incident.incident_id}


@app.post("/api/ingest/action-result", status_code=202)
def ingest_action_result(body: ActionResultIn) -> dict:
    is_new = database.upsert_action_result(body)
    return {"accepted": True, "new": is_new, "incident_id": body.incident_id}


static_dir = Path(settings.static_dir)
if static_dir.exists():
    assets = static_dir / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(request: Request, full_path: str):
        target = static_dir / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(static_dir / "index.html")
