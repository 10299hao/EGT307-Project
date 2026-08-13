import pandas as pd
import time
import os
import re
import threading

from api import run_api
from validator import validate_row
from redis_client import (
    get_redis_client,
    publish_event,
    publish_dead_letter,
    redis_is_ready,
)

REPLAY_SPEED = float(os.getenv('REPLAY_SPEED', '0.1'))

current_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV_PATH = os.path.join(current_dir, '../../data/demonstration_traces.csv')
DEFAULT_MEANING_PATH = os.path.join(current_dir, '../../data/EVENTID_MEANING.csv')

CSV_PATH = os.getenv('CSV_PATH', DEFAULT_CSV_PATH)
MEANING_PATH = os.getenv('MEANING_PATH', DEFAULT_MEANING_PATH)


def load_event_templates():
    print(f"Loading event translation key from {MEANING_PATH}...")
    try:
        df_meaning = pd.read_csv(MEANING_PATH)
        templates = {}
        for _, row in df_meaning.iterrows():
            pattern = re.escape(row['EventTemplate']).replace(r'\[\*\]', '.*')
            templates[row['EventId']] = re.compile(pattern)
        return templates
    except Exception as e:
        print(f"Error loading EVENTID_MEANING.csv: {e}")
        return {}


def map_event_id(raw_message, event_templates):
    """Translate a raw HDFS message into its E1-E29 template ID."""
    for event_id, regex_pattern in event_templates.items():
        if regex_pattern.search(raw_message):
            return event_id
    return "E1"  # Default fallback if nothing matches


def stream_logs():
    print("Connecting to Redis...")
    client = get_redis_client()
    if not redis_is_ready(client):
        print("CRITICAL ERROR: Could not connect to Redis.")
        return
    print("Connected to Redis!")

    print(f"Loading live log data from {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"Error: Could not find {CSV_PATH}.")
        return

    event_templates = load_event_templates()

    print("Calculating trace completion markers...")
    last_indices = df.drop_duplicates(subset=['block_id'], keep='last').index
    df['trace_complete'] = False
    df.loc[last_indices, 'trace_complete'] = True

    print("Beginning live log stream...")

    for _, row in df.iterrows():
        is_valid, reason = validate_row(row)
        if not is_valid:
            publish_dead_letter(client, row, reason)
            continue

        raw_message = str(row['message'])
        mapped_event_id = map_event_id(raw_message, event_templates)

        event = {
            "block_id": str(row['block_id']),
            "event_id": mapped_event_id,
            "trace_complete": bool(row['trace_complete']),
        }

        sent = publish_event(client, event)
        if sent:
            print(f"Sent: {event['block_id']} | {event['event_id']} | Complete: {event['trace_complete']}")
        else:
            publish_dead_letter(client, row, "Redis publish failed after retries")

        time.sleep(REPLAY_SPEED)


if __name__ == "__main__":
    threading.Thread(target=run_api, daemon=True).start()
    time.sleep(3)
    stream_logs()