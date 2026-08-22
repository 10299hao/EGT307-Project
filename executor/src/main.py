import redis
import json
import time
import os
from datetime import datetime, timezone
from results_publisher import publish_action_result

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_SOCKET_TIMEOUT = float(os.getenv('REDIS_SOCKET_TIMEOUT', 10))

PROCESSED_KEY_PREFIX = 'executor:processed:'
PROCESSED_TTL_SECONDS = int(os.getenv('PROCESSED_TTL_SECONDS', 86400))
CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', 70))
METRICS_KEY = os.getenv('METRICS_KEY', 'executor:metrics')
DEAD_LETTER_STREAM = os.getenv(
    'DEAD_LETTER_STREAM',
    'executor-dead-letter',
)

def log_event(level, event, **details):
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "automation-executor",
        "level": level.upper(),
        "event": event,
    }
    log_entry.update(details)
    print(json.dumps(log_entry, default=str), flush=True)

def increment_metric(client, metric_name):
    try:
        client.hincrby(METRICS_KEY, metric_name, 1)
    except redis.exceptions.RedisError as e:
        log_event(
            "ERROR",
            "metric_update_failed",
            metric=metric_name,
            error=str(e),
        )

def publish_dead_letter(client, message_id, reason, raw_payload):
    dead_letter = {
        "schema_version": "1.0",
        "original_message_id": message_id,
        "reason": reason,
        "raw_payload": raw_payload,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        client.xadd(
            DEAD_LETTER_STREAM,
            {"payload": json.dumps(dead_letter, default=str)},
        )
        increment_metric(client, "dead_lettered")
        log_event(
            "WARNING",
            "incident_sent_to_dead_letter",
            message_id=message_id,
            reason=reason,
        )
    except redis.exceptions.RedisError as e:
        log_event(
            "ERROR",
            "dead_letter_publish_failed",
            message_id=message_id,
            error=str(e),
        )

def select_action(payload):
    status = payload.get('status', '').lower()
    severity = payload.get('severity', '').lower()

    if status != 'anomaly':
        return 'no_action'
    try:
        confidence = float(payload.get('confidence_score', 0))
    except (TypeError, ValueError):
        confidence = 0

    if confidence < CONFIDENCE_THRESHOLD:
        return 'monitor_incident'

    if severity in ('critical', 'high'):
        return 'isolate_node'

    elif severity == 'medium':
        return 'notify_operator'

    else:
        return 'monitor_incident'

def validate_incident(payload):
    required_fields = (
        'incident_id',
        'block_id',
        'status',
        'confidence_score',
        'severity',
    )

    missing_fields = [
        field for field in required_fields
        if payload.get(field) in (None, '')
    ]

    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    if not isinstance(payload['incident_id'], str):
        return False, "incident_id must be a string."

    if not isinstance(payload['block_id'], str):
        return False, "block_id must be a string."

    if not isinstance(payload['status'], str):
        return False, "status must be a string."

    if payload['status'].lower() not in ('anomaly', 'normal'):
        return False, "status must be 'anomaly' or 'normal'."

    if not isinstance(payload['severity'], str):
        return False, "severity must be a string."

    if payload['severity'].lower() not in ('critical', 'high', 'medium', 'low'):
        return False, "severity must be Critical, High, Medium, or Low."

    try:
        confidence = float(payload['confidence_score'])
    except (TypeError, ValueError):
        return False, "confidence_score must be numeric."

    if not 0 <= confidence <= 100:
        return False, "confidence_score must be between 0 and 100."

    return True, ""

def was_incident_processed(client, incident_id):
    key = f"{PROCESSED_KEY_PREFIX}{incident_id}"
    return client.exists(key) == 1

def mark_incident_processed(client, incident_id):
    key = f"{PROCESSED_KEY_PREFIX}{incident_id}"
    client.setex(key, PROCESSED_TTL_SECONDS, "1")

def execute_dry_run(action):
    if action == 'isolate_node':
        log_event(
            "INFO",
            "dry_run_action",
            action=action,
            description="Isolating the affected node.",
        )
        time.sleep(2)

    elif action == 'notify_operator':
        log_event(
            "INFO",
            "dry_run_action",
            action=action,
            description="Notifying the system operator.",
        )
        time.sleep(1)

    elif action == 'monitor_incident':
        log_event(
            "INFO",
            "dry_run_action",
            action=action,
            description="Monitoring the incident.",
        )

    else:
        log_event(
            "INFO",
            "dry_run_action",
            action=action,
            description="No action required.",
        )

def listen_for_actions():
    log_event(
        "INFO",
        "redis_connection_attempt",
        host=REDIS_HOST,
        port=REDIS_PORT,
    )
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            protocol=2,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=5,
        )
        client.ping()
        log_event(
            "INFO",
            "executor_online",
            message="Executor is listening for incidents.",
        )
    except Exception as e:
        log_event(
            "CRITICAL",
            "redis_connection_failed",
            error=str(e),
        )
        return

    #'$' tells Redis: "Only give me NEW messages that arrive after I start up"
    last_id = '$'


    while True:
        try:
            # Block for up to 5 seconds waiting for a new message to hit 'IncidentStream'
            messages = client.xread({'IncidentStream': last_id}, count=1, block=5000)

            if messages:
                for stream, entries in messages:
                    for message_id, message_data in entries:
                        log_event(
                            "INFO",
                            "incident_message_received",
                            message_id=message_id,
                        )
                        increment_metric(client, "messages_received")

                        # Parse the incident sent by the Analyzer
                        try:
                            raw_payload = message_data.get('payload', '')
                            payload = json.loads(raw_payload)
                        except (json.JSONDecodeError, TypeError):
                            log_event(
                                "WARNING",
                                "invalid_incident_json",
                                message_id=message_id,
                            )
                            increment_metric(client, "invalid_json")
                            publish_dead_letter(
                                client,
                                message_id,
                                "Invalid JSON.",
                                raw_payload,
                            )
                            last_id = message_id
                            continue

                        if not isinstance(payload, dict):
                            log_event(
                                "WARNING",
                                "invalid_incident_type",
                                message_id=message_id,
                            )
                            increment_metric(client, "invalid_payload_type")
                            publish_dead_letter(
                                client,
                                message_id,
                                "Payload must be a JSON object.",
                                raw_payload,
                            )
                            last_id = message_id
                            continue

                        is_valid, validation_error = validate_incident(payload)

                        if not is_valid:
                            log_event(
                                "WARNING",
                                "incident_validation_failed",
                                message_id=message_id,
                                reason=validation_error,
                            )
                            increment_metric(client, "validation_failed")
                            publish_dead_letter(
                                client,
                                message_id,
                                validation_error,
                                raw_payload,
                            )
                            last_id = message_id
                            continue

                        incident_id = payload['incident_id']

                        log_event(
                            "INFO",
                            "incident_validated",
                            message_id=message_id,
                            incident_id=incident_id,
                            block_id=payload['block_id'],
                            severity=payload['severity'],
                            confidence_score=payload['confidence_score'],
                        )

                        if was_incident_processed(client, incident_id):
                            log_event(
                                "WARNING",
                                "incident_already_processed",
                                message_id=message_id,
                                incident_id=incident_id,
                            )
                            increment_metric(client, "duplicates_skipped")
                            last_id = message_id
                            continue

                        action = select_action(payload)

                        log_event(
                            "INFO",
                            "action_selected",
                            incident_id=incident_id,
                            action=action,
                        )

                        # Simulate the selected response without executing real system commands
                        execute_dry_run(action)
                        log_event(
                            "INFO",
                            "dry_run_completed",
                            incident_id=incident_id,
                            action=action,
                        )
                        
                        if action == 'no_action':
                            result_status = "skipped"
                            result_reason = "Message was not classified as an anomaly."
                            simulated_command = None
                        else:
                            result_status = "completed"
                            result_reason = f"Dry-run '{action}' executed by Automation Executor."
                            simulated_command = f"simulate:{action}"

                        publish_action_result(
                            client,
                            incident_id=incident_id,
                            action=action,
                            status=result_status,
                            reason=result_reason,
                            command=simulated_command,
                        )
                        mark_incident_processed(client, incident_id)
                        increment_metric(client, "incidents_processed")
                        increment_metric(client, f"action_{action}")
                        increment_metric(client, f"result_{result_status}")

                        # Update the ID so we don't process the same alert twice
                        last_id = message_id
                        log_event(
                            "INFO",
                            "waiting_for_incident",
                        )

        except Exception as e:
            log_event(
                "ERROR",
                "stream_processing_error",
                error=str(e),
            )
            time.sleep(2)

if __name__ == "__main__":
    listen_for_actions()