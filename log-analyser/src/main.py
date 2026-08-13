import redis
import os
import time
import json

from inference import evaluate_trace
from publisher import publish_incident

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

def listen_and_analyze():
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        client.ping()
        print("Connected to Redis! Listening for Wei Jie's log-events...")
    except Exception as e:
        print(f"Waiting for Redis to start... ({e})")
        return

    block_buffer = {}
    last_id = '$'

    while True:
        try:
            # FIXED: Listening to 'log-events' instead of 'LogStream'
            messages = client.xread({'log-events': last_id}, count=10, block=1000)
            
            if not messages:
                continue

            for stream, entries in messages:
                for message_id, message_data in entries:
                    last_id = message_id 
                    
                    # FIXED: Extracting from 'data' instead of 'payload'
                    payload = json.loads(message_data.get('data', '{}'))
                    block_id = payload.get('block_id')
                    event_id = payload.get('event_id')
                    trace_complete = payload.get('trace_complete', False)
                    
                    if not block_id or not event_id:
                        continue

                    if block_id not in block_buffer:
                        block_buffer[block_id] = []
                    block_buffer[block_id].append(event_id)
                    
                    # FIXED: Using the trace_complete flag to trigger the AI
                    if trace_complete in [True, 'true', 'True']:
                        event_sequence = block_buffer[block_id]
                        incident_report = evaluate_trace(block_id, event_sequence)
                        
                        if incident_report:
                            publish_incident(incident_report)
                            
                        del block_buffer[block_id]

        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(2) 

if __name__ == "__main__":
    while True:
        listen_and_analyze()
        time.sleep(5)