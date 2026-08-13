import json
import os
import uuid
from datetime import datetime, timezone

# Matches the Portal's Settings defaults in services/portal/backend/app/config.py
ACTION_RESULT_STREAM = os.getenv('ACTION_RESULT_STREAM', 'action-results')
ACTION_RESULT_FIELD = os.getenv('ACTION_RESULT_FIELD', 'payload')


def publish_action_result(client, incident_id, action, status, reason, command=None):
    """
    Report back to the Portal what happened, so the dashboard can show it.
    Must match ActionResultIn in services/portal/backend/app/schemas.py exactly
    (that model uses extra="forbid", so no extra fields are allowed).
    """
    result = {
        "schema_version": "1.0",
        "action_result_id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "action": action,
        "command": command,
        "mode": "dry_run",
        "status": status,
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        client.xadd(ACTION_RESULT_STREAM, {ACTION_RESULT_FIELD: json.dumps(result)})
        print(f"📡 Reported result for {incident_id} to '{ACTION_RESULT_STREAM}'")
    except Exception as e:
        print(f"⚠️  Could not publish ActionResult for {incident_id}: {e}")