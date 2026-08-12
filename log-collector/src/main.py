import os
import time
import threading
import pandas as pd
from pathlib import Path

from validator import validate_row, create_log_event
from redis_client import (
    get_redis_client,
    publish_event,
    publish_dead_letter,
    redis_is_ready
)
from api import run_api


# =========================
# SETTINGS
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = PROJECT_ROOT / "data" / "demonstration_traces.csv"

REPLAY_SPEED = float(
    os.getenv("REPLAY_SPEED", "0.1")
)


# =========================
# MAIN
# =========================

def main():

    print("Starting Log Collector...")


    # -------------------------
    # Start API
    # -------------------------

    api_thread = threading.Thread(
        target=run_api,
        daemon=True
    )

    api_thread.start()


    # -------------------------
    # Connect Redis
    # -------------------------

    redis_client = get_redis_client()

    if not redis_is_ready(redis_client):
        print("Redis is not available.")
        return

    print("Connected to Redis.")


    # -------------------------
    # Read demonstration CSV
    # -------------------------

    data = pd.read_csv(
        DATA_FILE,
        dtype=str
    )

    # Keep original order
    data["line_id"] = pd.to_numeric(
        data["line_id"]
    )

    data = data.sort_values(
        "line_id"
    ).reset_index(drop=True)


    # -------------------------
    # Find final row of each block
    # -------------------------

    last_rows = (
        data
        .reset_index()
        .groupby("block_id")["index"]
        .max()
        .to_dict()
    )


    # -------------------------
    # Replay logs
    # -------------------------

    for index, row in data.iterrows():

        valid, reason = validate_row(row)


        # Bad row
        if not valid:

            print(
                f"Invalid event: {reason}"
            )

            publish_dead_letter(
                redis_client,
                row,
                reason
            )

            continue


        # Is this the last event
        # belonging to this block?
        block_id = row["block_id"]

        trace_complete = (
            index == last_rows[block_id]
        )


        # Create LogEvent
        event = create_log_event(
            row,
            trace_complete
        )


        # Publish LogEvent
        success = publish_event(
            redis_client,
            event
        )


        if not success:

            publish_dead_letter(
                redis_client,
                row,
                "Redis publishing failed"
            )


        if trace_complete:

            print(
                f"Trace complete: {block_id}"
            )


        # Replay speed
        time.sleep(REPLAY_SPEED)


    print("Log replay completed.")

# Keep the service running after replay finishes
    api_thread.join()

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()