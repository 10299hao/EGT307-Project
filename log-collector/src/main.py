import redis
import pandas as pd
import time
import json
import os
import re

# 1. Setup Redis Connection
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REPLAY_SPEED = float(os.getenv('REPLAY_SPEED', '0.1')) 

current_dir = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(current_dir, '../../data/demonstration_traces.csv')
MEANING_PATH = os.path.join(current_dir, '../../data/EVENTID_MEANING.csv')

def load_event_templates():
    print(f"Loading event translation key from {MEANING_PATH}...")
    try:
        df_meaning = pd.read_csv(MEANING_PATH)
        templates = {}
        for _, row in df_meaning.iterrows():
            # Convert the [*] in the CSV into a regex wildcard .*
            # This allows Python to ignore the dynamic IP addresses and block IDs
            pattern = re.escape(row['EventTemplate']).replace(r'\[\*\]', '.*')
            templates[row['EventId']] = re.compile(pattern)
        return templates
    except Exception as e:
        print(f"Error loading EVENTID_MEANING.csv: {e}")
        return {}

def stream_logs():
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        client.ping()
        print("Connected to Redis!")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to Redis. {e}")
        return

    print(f"Loading live log data from {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"Error: Could not find {CSV_PATH}.")
        return

    # Load the templates for translation
    event_templates = load_event_templates()

    print("Calculating trace completion markers...")
    last_indices = df.drop_duplicates(subset=['block_id'], keep='last').index
    df['trace_complete'] = False
    df.loc[last_indices, 'trace_complete'] = True

    print("Beginning live log stream...")
    
    for index, row in df.iterrows():
        try:
            raw_message = str(row['message'])
            mapped_event_id = "E1" # Default fallback
            
            # Translate the raw message using the Regex templates
            for event_id, regex_pattern in event_templates.items():
                if regex_pattern.search(raw_message):
                    mapped_event_id = event_id
                    break

            payload = {
                "block_id": str(row['block_id']),
                "event_id": mapped_event_id,
                "trace_complete": bool(row['trace_complete']) 
            }

            client.xadd('log-events', {'data': json.dumps(payload)})
            
            print(f"Sent: {payload['block_id']} | {payload['event_id']} | Complete: {payload['trace_complete']}")
            time.sleep(REPLAY_SPEED)
            
        except Exception as e:
            print(f"Failed to send log: {e}")
            time.sleep(1)

if __name__ == "__main__":
    time.sleep(3)
    stream_logs()