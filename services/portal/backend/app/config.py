"""Environment-driven configuration for the Incident Portal."""

from dataclasses import dataclass
import os


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


@dataclass(frozen=True)
class Settings:
    database_path: str = os.getenv("PORTAL_DATABASE_PATH", "data/portal.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Danish's Analyzer currently publishes to IncidentStream. The original
    # agreed name (incidents) remains an alias so older test publishers work.
    incident_stream: str = os.getenv("INCIDENT_STREAM", "IncidentStream")
    incident_stream_aliases: tuple[str, ...] = _as_list(
        os.getenv("INCIDENT_STREAM_ALIASES", "incidents")
    )
    action_result_stream: str = os.getenv("ACTION_RESULT_STREAM", "action-results")
    # Ethan's Executor listens here for Portal action requests.
    action_request_stream: str = os.getenv("ACTION_REQUEST_STREAM", "ActionStream")
    action_request_field: str = os.getenv("ACTION_REQUEST_FIELD", "command")
    dead_letter_stream: str = os.getenv("DEAD_LETTER_STREAM", "portal-dead-letter")
    collector_output_stream: str = os.getenv("COLLECTOR_OUTPUT_STREAM", "log-events")
    analyzer_input_stream: str = os.getenv("ANALYZER_INPUT_STREAM", "LogStream")
    collector_message_field: str = os.getenv("COLLECTOR_MESSAGE_FIELD", "data")
    analyzer_message_field: str = os.getenv("ANALYZER_MESSAGE_FIELD", "payload")
    collector_health_url: str | None = os.getenv("COLLECTOR_HEALTH_URL")
    bridge_heartbeat_key: str = os.getenv(
        "BRIDGE_HEARTBEAT_KEY", "portal-integration-bridge:heartbeat"
    )
    consumer_group: str = os.getenv("PORTAL_CONSUMER_GROUP", "incident-portal")
    consumer_name: str = os.getenv("PORTAL_CONSUMER_NAME", "portal-1")
    local_notification_url: str | None = os.getenv("LOCAL_NOTIFICATION_URL")
    notification_timeout_seconds: float = float(os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "4"))
    notification_max_attempts: int = int(os.getenv("NOTIFICATION_MAX_ATTEMPTS", "3"))
    enable_redis: bool = _as_bool(os.getenv("ENABLE_REDIS"), False)
    enable_executor: bool = _as_bool(os.getenv("ENABLE_EXECUTOR"), False)
    seed_demo_data: bool = _as_bool(os.getenv("SEED_DEMO_DATA"), True)
    static_dir: str = os.getenv("PORTAL_STATIC_DIR", "frontend/dist")

    @property
    def local_notification_configured(self) -> bool:
        return bool(self.local_notification_url)

    @property
    def incident_streams(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((self.incident_stream, *self.incident_stream_aliases)))


settings = Settings()
