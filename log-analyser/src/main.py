import redis
import os
import time
import json

# Import your own custom scripts!
from inference import evaluate_trace
from publisher import publish_incident

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

def listen_and_analyze():
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        # Test connection
        client.ping()
        print("Connected to Redis! Listening for Wei Jie's LogEvents...")
    except Exception as e:
        print(f"Waiting for Redis to start... ({e})")
        return

    # This dictionary will hold the live sequences in memory.
    # Format: {'blk_123': ['E5', 'E22', ...], 'blk_456': ['E5', 'E11']}
    block_buffer = {}

    last_id = '$' # '$' means we only want NEW messages that arrive after we start listening

    while True:
        try:
            # 1. Listen to the LogStream
            # Block for 1000ms (1 second) waiting for new logs
            messages = client.xread({'LogStream': last_id}, count=10, block=1000)
            
            if not messages:
                continue

            for stream, entries in messages:
                for message_id, message_data in entries:
                    last_id = message_id # Update the ID so we don't read this message again
                    
                    # 2. Extract the data Wei Jie sent
                    payload = json.loads(message_data.get('payload', '{}'))
                    block_id = payload.get('block_id')
                    event_id = payload.get('event_id')
                    
                    if not block_id or not event_id:
                        continue

                    # 3. Add the event to our memory buffer
                    if block_id not in block_buffer:
                        block_buffer[block_id] = []
                    block_buffer[block_id].append(event_id)
                    
                    # 4. Trigger the AI if the block is "done"
                    # In HDFS, 'E2' or 'E26' often signify the end of a block's lifecycle.
                    # You can adjust this trigger based on your specific system rules!
                    if event_id in ['E2', 'E26'] or len(block_buffer[block_id]) > 25:
                        
                        # Send the finished sequence to your AI
                        event_sequence = block_buffer[block_id]
                        incident_report = evaluate_trace(block_id, event_sequence)
                        
                        # If it's an anomaly, publish it!
                        if incident_report:
                            publish_incident(incident_report)
                            
                        # Clear the block from memory to free up RAM
                        del block_buffer[block_id]

        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(2) # Prevent rapid crash loops

if __name__ == "__main__":
    # Keep restarting the listener if it fails
    while True:
        listen_and_analyze()
        time.sleep(5)