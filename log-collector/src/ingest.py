import os
import time

import pandas as pd

from event_mapping import load_event_templates, map_event_id
from redis_client import get_redis_client, publish_event, publish_dead_letter, redis_is_ready
from validator import validate_row

STREAM_SPEED = float(os.getenv('REPLAY_SPEED', '0.01'))


def process_upload(csv_path, labels_path=None):
    """
    Process one uploaded batch: merge optional labels, validate every row,
    map event IDs, compute trace-completion for THIS batch, and stream
    valid events to Redis. Returns a summary dict.

    Note: trace_complete is computed per-batch (last occurrence of a
    block_id within THIS upload). If a block's events are deliberately
    split across two separate uploads, the first upload will mark it
    complete based on partial data.
    """
    summary = {
        "rows_received": 0,
        "rows_valid": 0,
        "rows_dead_lettered": 0,
        "blocks_seen": 0,
        "labels_merged": False,
        "error": None,
    }

    client = get_redis_client()
    if not redis_is_ready(client):
        summary["error"] = "Could not connect to Redis"
        return summary

    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as e:
        summary["error"] = f"Could not read uploaded CSV: {e}"
        return summary

    summary["rows_received"] = len(df)

    if labels_path:
        try:
            labels = pd.read_csv(labels_path, dtype=str)
            labels.columns = labels.columns.str.strip()
            labels["BlockId"] = labels["BlockId"].str.strip()
            labels["Label"] = labels["Label"].str.strip()
            labels = labels.drop_duplicates(subset=["BlockId"])
            label_for_merge = labels[["BlockId", "Label"]].rename(columns={"BlockId": "block_id"})
            df = df.merge(label_for_merge, on="block_id", how="left", sort=False)
            summary["labels_merged"] = True
        except Exception as e:
            summary["error"] = f"Could not merge labels file: {e}"

    if "block_id" not in df.columns:
        summary["error"] = "Uploaded CSV has no block_id column"
        return summary

    summary["blocks_seen"] = df["block_id"].nunique()

    last_indices = df.drop_duplicates(subset=["block_id"], keep="last").index
    df["trace_complete"] = False
    df.loc[last_indices, "trace_complete"] = True

    event_templates = load_event_templates()

    for _, row in df.iterrows():
        is_valid, reason = validate_row(row)
        if not is_valid:
            publish_dead_letter(client, row, reason)
            summary["rows_dead_lettered"] += 1
            continue

        raw_message = str(row["message"])
        mapped_event_id = map_event_id(raw_message, event_templates)

        event = {
            "block_id": str(row["block_id"]),
            "event_id": mapped_event_id,
            "trace_complete": bool(row["trace_complete"]),
        }

        sent = publish_event(client, event)
        if sent:
            summary["rows_valid"] += 1
        else:
            publish_dead_letter(client, row, "Redis publish failed after retries")
            summary["rows_dead_lettered"] += 1

        time.sleep(STREAM_SPEED)

    return summary