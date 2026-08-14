import os
import re

import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MEANING_PATH = os.path.join(current_dir, '../../data/EVENTID_MEANING.csv')
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
    return "E1"