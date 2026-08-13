"""SQLite persistence and queries for incidents, actions and notifications."""

import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any

from .schemas import ActionResultIn, IncidentIn, utc_now


EVENT_DESCRIPTIONS = {
    "E1": "Tried to add a block that already exists",
    "E2": "Block verification succeeded",
    "E3": "Block was served to another node",
    "E4": "Exception occurred while serving a block",
    "E5": "DataNode started receiving a block",
    "E6": "DataNode finished receiving a block",
    "E7": "Write-block operation raised an exception",
    "E8": "Packet responder was interrupted",
    "E9": "Block was received from another node",
    "E10": "Packet responder raised an exception",
    "E11": "Packet responder terminated",
    "E12": "Exception occurred while writing to a mirror",
    "E13": "Empty packet was received for a block",
    "E14": "Receive-block operation raised an exception",
    "E15": "Block and metadata file offsets were changed",
    "E16": "Block was transmitted to another node",
    "E17": "Block transfer failed",
    "E18": "Transfer thread started for a block",
    "E19": "Block was reopened",
    "E20": "Block deletion failed because metadata was missing",
    "E21": "Block file was deleted",
    "E22": "NameNode allocated a block",
    "E23": "Deleted block was added to the invalid set",
    "E24": "Block was removed from needed replications",
    "E25": "NameNode requested block replication",
    "E26": "Stored-block map was updated",
    "E27": "Redundant stored-block request was received",
    "E28": "Stored block did not belong to any file",
    "E29": "Pending block replication timed out",
}


class PortalDatabase:
    """Thread-safe repository used by both FastAPI routes and Redis consumers."""

    def __init__(self, path: str):
        self.path = path
        self._lock = Lock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.initialise()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialise(self) -> None:
        """Create the schema and apply small forward-compatible migrations."""
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    block_id TEXT NOT NULL,
                    anomaly_probability REAL NOT NULL CHECK(anomaly_probability BETWEEN 0 AND 1),
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    evidence_event_ids TEXT NOT NULL,
                    evidence_summary TEXT,
                    total_events_analyzed INTEGER,
                    recommended_action TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    acknowledged_by TEXT,
                    acknowledged_at TEXT,
                    action_request_id TEXT,
                    action_request_sent_at TEXT,
                    action_request_error TEXT,
                    received_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_results (
                    action_result_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL UNIQUE,
                    schema_version TEXT NOT NULL,
                    action TEXT NOT NULL,
                    command TEXT,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    response_code INTEGER,
                    error TEXT,
                    attempted_at TEXT NOT NULL,
                    UNIQUE(incident_id, attempt_number)
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(incidents)")}
            if "evidence_summary" not in columns:
                connection.execute("ALTER TABLE incidents ADD COLUMN evidence_summary TEXT")
            if "total_events_analyzed" not in columns:
                connection.execute("ALTER TABLE incidents ADD COLUMN total_events_analyzed INTEGER")
            if "action_request_id" not in columns:
                connection.execute("ALTER TABLE incidents ADD COLUMN action_request_id TEXT")
            if "action_request_sent_at" not in columns:
                connection.execute("ALTER TABLE incidents ADD COLUMN action_request_sent_at TEXT")
            if "action_request_error" not in columns:
                connection.execute("ALTER TABLE incidents ADD COLUMN action_request_error TEXT")

    def upsert_incident(self, incident: IncidentIn) -> bool:
        """Insert/update an incident and return True only for a new record."""
        payload = incident.model_dump()
        with self._lock, self.connect() as connection:
            existed = connection.execute(
                "SELECT 1 FROM incidents WHERE incident_id = ?", (incident.incident_id,)
            ).fetchone() is not None
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, schema_version, block_id, anomaly_probability, category,
                    severity, evidence_event_ids, evidence_summary, total_events_analyzed,
                    recommended_action, model_version, created_at, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    block_id=excluded.block_id,
                    anomaly_probability=excluded.anomaly_probability,
                    category=excluded.category,
                    severity=excluded.severity,
                    evidence_event_ids=excluded.evidence_event_ids,
                    evidence_summary=excluded.evidence_summary,
                    total_events_analyzed=excluded.total_events_analyzed,
                    recommended_action=excluded.recommended_action,
                    model_version=excluded.model_version
                """,
                (
                    payload["incident_id"], payload["schema_version"], payload["block_id"],
                    payload["anomaly_probability"], payload["category"], payload["severity"],
                    json.dumps(payload["evidence_event_ids"]), payload["evidence_summary"],
                    payload["total_events_analyzed"], payload["recommended_action"],
                    payload["model_version"], payload["created_at"], utc_now(),
                ),
            )
        return not existed

    def upsert_action_result(self, result: ActionResultIn) -> bool:
        """Store one Executor result per incident without creating duplicates."""
        payload = result.model_dump()
        with self._lock, self.connect() as connection:
            existed = connection.execute(
                "SELECT 1 FROM action_results WHERE action_result_id = ? OR incident_id = ?",
                (result.action_result_id, result.incident_id),
            ).fetchone() is not None
            connection.execute(
                """
                INSERT INTO action_results (
                    action_result_id, incident_id, schema_version, action, command,
                    mode, status, reason, created_at, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    action_result_id=excluded.action_result_id,
                    action=excluded.action,
                    command=excluded.command,
                    mode=excluded.mode,
                    status=excluded.status,
                    reason=excluded.reason,
                    created_at=excluded.created_at,
                    received_at=excluded.received_at
                """,
                (
                    payload["action_result_id"], payload["incident_id"], payload["schema_version"],
                    payload["action"], payload["command"], payload["mode"], payload["status"],
                    payload["reason"], payload["created_at"], utc_now(),
                ),
            )
        return not existed

    def record_action_dispatch(
        self,
        incident_id: str,
        request_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Record whether an action request reached Ethan's Redis stream."""
        with self._lock, self.connect() as connection:
            connection.execute(
                """UPDATE incidents
                   SET action_request_id=?, action_request_sent_at=?, action_request_error=?
                   WHERE incident_id=?""",
                (request_id, utc_now() if request_id else None, error, incident_id),
            )

    def action_already_dispatched(self, incident_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT action_request_id FROM incidents WHERE incident_id=?", (incident_id,)
            ).fetchone()
        return bool(row and row["action_request_id"])

    @staticmethod
    def _to_incident(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["acknowledged"] = bool(item["acknowledged"])
        event_ids = json.loads(item.pop("evidence_event_ids"))
        item["evidence_event_ids"] = event_ids
        item["evidence"] = [
            {"event_id": event_id, "description": EVENT_DESCRIPTIONS.get(event_id, "Unknown event template")}
            for event_id in event_ids
        ]
        item.pop("received_at", None)
        item["action_request"] = {
            "status": "sent" if item.get("action_request_id") else (
                "failed" if item.get("action_request_error") else "not_sent"
            ),
            "message_id": item.pop("action_request_id", None),
            "sent_at": item.pop("action_request_sent_at", None),
            "error": item.pop("action_request_error", None),
        }
        action_keys = ["action_result_id", "action", "command", "mode", "action_status", "action_reason", "action_created_at"]
        if item.get("action_result_id"):
            item["action_result"] = {
                "action_result_id": item.pop("action_result_id"),
                "action": item.pop("action"),
                "command": item.pop("command"),
                "mode": item.pop("mode"),
                "status": item.pop("action_status"),
                "reason": item.pop("action_reason"),
                "created_at": item.pop("action_created_at"),
            }
        else:
            for key in action_keys:
                item.pop(key, None)
            item["action_result"] = None
        return item

    def list_incidents(self, severity: str | None = None, status: str | None = None, search: str | None = None) -> list[dict]:
        """Return the dashboard incident list with optional user filters."""
        where, params = [], []
        if severity and severity != "all":
            where.append("i.severity = ?")
            params.append(severity)
        if status == "open":
            where.append("i.acknowledged = 0")
        elif status == "acknowledged":
            where.append("i.acknowledged = 1")
        if search:
            where.append("(i.incident_id LIKE ? OR i.block_id LIKE ? OR i.category LIKE ?)")
            query = f"%{search}%"
            params.extend([query, query, query])
        clause = " WHERE " + " AND ".join(where) if where else ""
        sql = self._select_sql() + clause + " ORDER BY i.created_at DESC LIMIT 200"
        with self.connect() as connection:
            return [self._to_incident(row) for row in connection.execute(sql, params).fetchall()]

    def get_incident(self, incident_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(self._select_sql() + " WHERE i.incident_id = ?", (incident_id,)).fetchone()
        return self._to_incident(row) if row else None

    @staticmethod
    def _select_sql() -> str:
        return """
            SELECT i.*, a.action_result_id, a.action, a.command, a.mode,
                   a.status AS action_status, a.reason AS action_reason,
                   a.created_at AS action_created_at
            FROM incidents i LEFT JOIN action_results a ON a.incident_id = i.incident_id
        """

    def acknowledge(self, incident_id: str, operator: str) -> bool:
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                """UPDATE incidents SET acknowledged=1, acknowledged_by=?, acknowledged_at=?
                   WHERE incident_id=?""",
                (operator, utc_now(), incident_id),
            )
            return cursor.rowcount > 0

    def stats(self) -> dict:
        """Calculate the small set of summary values shown on the Overview page."""
        with self.connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            open_count = connection.execute("SELECT COUNT(*) FROM incidents WHERE acknowledged=0").fetchone()[0]
            critical = connection.execute("SELECT COUNT(*) FROM incidents WHERE severity='critical' AND acknowledged=0").fetchone()[0]
            automated = connection.execute("SELECT COUNT(*) FROM action_results WHERE status='completed'").fetchone()[0]
            confidence = connection.execute("SELECT AVG(anomaly_probability) FROM incidents").fetchone()[0] or 0
            severity_rows = connection.execute("SELECT severity, COUNT(*) count FROM incidents GROUP BY severity").fetchall()
        return {
            "total_incidents": total,
            "open_incidents": open_count,
            "critical_open": critical,
            "completed_actions": automated,
            "average_confidence": round(confidence, 4),
            "by_severity": {row["severity"]: row["count"] for row in severity_rows},
        }

    def record_notification(self, incident_id: str, attempt: int, status: str, response_code: int | None = None, error: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO notification_attempts
                   (incident_id, attempt_number, status, response_code, error, attempted_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (incident_id, attempt, status, response_code, error, utc_now()),
            )

    def notification_history(self, incident_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM notification_attempts WHERE incident_id=? ORDER BY attempt_number", (incident_id,)
            ).fetchall()
        return [dict(row) for row in rows]
