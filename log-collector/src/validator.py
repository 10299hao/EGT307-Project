import pandas as pd


def validate_row(row):
    """
    Validate one row from demonstration_traces.csv.

    Returns:
        (True, "") if valid
        (False, reason) if invalid
    """

    required_fields = [
        "line_id",
        "timestamp",
        "level",
        "component",
        "block_id",
        "message"
    ]

    # Check required fields exist
    for field in required_fields:
        if field not in row:
            return False, f"Missing field: {field}"

        value = row[field]

        if pd.isna(value) or str(value).strip() == "":
            return False, f"Empty field: {field}"

    # -------------------------
    # Validate line_id
    # -------------------------

    try:
        int(row["line_id"])
    except (ValueError, TypeError):
        return False, "line_id must be a number"

    # -------------------------
    # Validate timestamp
    # -------------------------

    try:
        pd.to_datetime(row["timestamp"])
    except Exception:
        return False, "Invalid timestamp"

    # -------------------------
    # Validate block ID
    # -------------------------

    block_id = str(row["block_id"]).strip()

    if not block_id.startswith("blk_"):
        return False, "Invalid block_id"

    # -------------------------
    # Validate level
    # -------------------------

    level = str(row["level"]).strip().upper()

    allowed_levels = [
        "INFO",
        "WARN",
        "WARNING",
        "ERROR",
        "DEBUG",
        "FATAL"
    ]

    if level not in allowed_levels:
        return False, f"Invalid log level: {level}"

    return True, ""


def create_log_event(row, trace_complete=False):
    """
    Convert a validated CSV row into a LogEvent.
    """

    event = {
        "version": "1.0",

        # line_id becomes event_id
        "event_id": str(row["line_id"]).strip(),

        "timestamp": str(row["timestamp"]).strip(),

        "block_id": str(row["block_id"]).strip(),

        "component": str(row["component"]).strip(),

        "level": str(row["level"]).strip(),

        "message": str(row["message"]).strip(),

        # Tells the Analyzer whether this is
        # the final event for the block trace
        "trace_complete": trace_complete
    }

    return event