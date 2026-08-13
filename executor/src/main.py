import redis
import json
import time
import os

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

def listen_for_actions():
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, protocol=2)
        client.ping()
        print("🛡️  Executor is ONLINE. Guarding the system and listening for actions...")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to Redis. {e}")
        return

    # The '$' symbol tells Redis: "Only give me NEW messages that arrive after I start up"
    last_id = '$'  

    while True:
        try:
            # Block for up to 5 seconds waiting for a new message to hit 'ActionStream'
            messages = client.xread({'ActionStream': last_id}, count=1, block=5000)
            
            if messages:
                for stream, entries in messages:
                    for message_id, message_data in entries:
                        print(f"\n[!] RED ALERT RECEIVED [!]")
                        
                        # Parse the command sent by Minghao's portal
                        payload = json.loads(message_data.get('command', '{}'))
                        incident_id = payload.get('incident_id', 'UNKNOWN')
                        action = payload.get('action', 'isolate_node')
                        
                        print(f"⚡ Target Incident: {incident_id}")
                        print(f"⚡ Executing Protocol: '{action}'")
                        
                        # Simulate the time it takes to actually isolate a server node
                        print("Status: Isolating affected server node...")
                        time.sleep(2)
                        print("Status: Rerouting network traffic...")
                        time.sleep(1)
                        print(f"✅ Mitigation Complete! Incident {incident_id} has been neutralized.")
                        
                        # Update the ID so we don't process the same alert twice
                        last_id = message_id
                        print("\n🛡️  Resuming watch...")
                        
        except Exception as e:
            print(f"Error reading from stream: {e}")
            time.sleep(2)

if __name__ == "__main__":
    listen_for_actions()