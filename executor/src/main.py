import redis
import json
import time
import os
from results_publisher import publish_action_result

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

def select_action(payload):
    status = payload.get('status', '').lower()
    severity = payload.get('severity', '').lower()

    if status != 'anomaly':
        return 'no_action'

    try:
        confidence = float(payload.get('confidence_score', 0))
    except (TypeError, ValueError):
        confidence = 0

    if confidence < 70:
        return 'monitor_incident'

    if severity == 'high':
        return 'isolate_node'
    elif severity == 'medium':
        return 'notify_operator'
    else:
        return 'monitor_incident'

def execute_dry_run(action):
    if action == 'isolate_node':
        print("Status: [DRY RUN] Isolating the affected node...")
        time.sleep(2)

    elif action == 'notify_operator':
        print("Status: [DRY RUN] Notifying the system operator...")
        time.sleep(1)

    elif action == 'monitor_incident':
        print("Status: [DRY RUN] Monitoring the incident...")

    else:
        print("Status: No action required.")

def listen_for_actions():
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, protocol=2)
        client.ping()
        print("[ONLINE] Executor is guarding the system and listening for incidents...")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to Redis. {e}")
        return

    #'$' tells Redis: "Only give me NEW messages that arrive after I start up"
    last_id = '$'
    processed_incidents = set()

    while True:
        try:
            # Block for up to 5 seconds waiting for a new message to hit 'IncidentStream'
            messages = client.xread({'IncidentStream': last_id}, count=1, block=5000)

            if messages:
                for stream, entries in messages:
                    for message_id, message_data in entries:
                        print(f"\n[!] RED ALERT RECEIVED [!]")

                        # Parse the incident sent by the Analyzer
                        try:
                            payload = json.loads(message_data.get('payload', '{}'))
                        except (json.JSONDecodeError, TypeError):
                            print("⚠️ Invalid incident JSON. Skipping message.")
                            last_id = message_id
                            continue

                        if not isinstance(payload, dict):
                            print("⚠️ Incident payload must be a JSON object. Skipping message.")
                            last_id = message_id
                            continue

                        print("\n===== INCIDENT PAYLOAD =====")
                        print(json.dumps(payload, indent=4))

                        incident_id = payload.get('incident_id', 'UNKNOWN')
                        if incident_id == 'UNKNOWN':
                            print("⚠️ Incident has no incident_id. Skipping message.")
                            last_id = message_id
                            continue

                        if incident_id in processed_incidents:
                            print(f"⚠️ Incident {incident_id} was already processed. Skipping duplicate.")
                            last_id = message_id
                            continue

                        action = select_action(payload)

                        print(f"[TARGET] Incident: {incident_id}")
                        print(f"[ACTION] Selected protocol: '{action}'")

                        # Simulate the selected response without executing real system commands
                        execute_dry_run(action)
                        print(f"[RESULT] Processing completed for incident {incident_id}.")
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
                        processed_incidents.add(incident_id)

                        # Update the ID so we don't process the same alert twice
                        last_id = message_id
                        print("\n[WATCHING] Waiting for the next incident...")

        except Exception as e:
            print(f"Error reading from stream: {e}")
            time.sleep(2)

if __name__ == "__main__":
    listen_for_actions()