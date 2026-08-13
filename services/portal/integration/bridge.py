"""Translate Wei Jie's LogEvents into Danish's current Analyzer input contract."""

import json
import logging
import os
import time

from redis import Redis
from redis.exceptions import ResponseError


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("portal-integration-bridge")


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SOURCE_STREAM = os.getenv("SOURCE_STREAM", "log-events")
SOURCE_FIELD = os.getenv("SOURCE_FIELD", "data")
TARGET_STREAM = os.getenv("TARGET_STREAM", "LogStream")
TARGET_FIELD = os.getenv("TARGET_FIELD", "payload")
DEAD_LETTER_STREAM = os.getenv("BRIDGE_DEAD_LETTER_STREAM", "integration-dead-letter")
CONSUMER_GROUP = os.getenv("BRIDGE_CONSUMER_GROUP", "portal-integration-bridge")
CONSUMER_NAME = os.getenv("BRIDGE_CONSUMER_NAME", "bridge-1")
STARTUP_DELAY = float(os.getenv("STARTUP_DELAY_SECONDS", "8"))
HEARTBEAT_KEY = os.getenv("BRIDGE_HEARTBEAT_KEY", "portal-integration-bridge:heartbeat")


EVENT_RULES = (
    ("E20", ("unexpected error trying to delete block", "blockinfo not found")),
    ("E28", ("addstoredblock request received", "does not belong to any file")),
    ("E27", ("redundant addstoredblock request",)),
    ("E26", ("addstoredblock", "blockmap updated")),
    ("E24", ("removing block", "neededreplications")),
    ("E23", ("invalidset",)),
    ("E22", ("allocateblock:",)),
    ("E29", ("pendingreplicationmonitor timed out",)),
    ("E18", ("starting thread to transfer block",)),
    ("E17", ("failed to transfer",)),
    ("E16", ("transmitted block",)),
    ("E15", ("changing block file offset",)),
    ("E14", ("exception in receiveblock",)),
    ("E13", ("receiving empty packet",)),
    ("E12", ("exception writing block", "mirror")),
    ("E11", ("packetresponder", "terminating")),
    ("E10", ("packetresponder", "exception")),
    ("E8", ("packetresponder", "interrupted")),
    ("E7", ("writeblock", "received exception")),
    ("E4", ("got exception while serving",)),
    ("E3", ("served block",)),
    ("E2", ("verification succeeded",)),
    ("E1", ("adding an already existing block",)),
    ("E21", ("deleting block", "file")),
    ("E19", ("reopen block",)),
    ("E6", ("received block", "src:", "dest:", "of size")),
    ("E9", ("received block", "of size", "from")),
    ("E5", ("receiving block", "src:", "dest:")),
    ("E25", ("block* ask", "to replicate",)),
)


def event_template_id(message: str) -> str | None:
    """Map one raw HDFS message to the E1-E29 vocabulary used by the model."""
    normalised = str(message).strip().lower()
    for event_id, required_parts in EVENT_RULES:
        if all(part in normalised for part in required_parts):
            return event_id
    return None


def translate(payload: dict) -> dict:
    """Preserve Collector fields while replacing its line ID with a model event ID."""
    event_id = event_template_id(payload.get("message", ""))
    if not event_id:
        raise ValueError("HDFS message did not match an E1-E29 model event template")
    return {
        **payload,
        "version": str(payload.get("version") or "1.0"),
        "collector_event_id": payload.get("event_id"),
        "event_id": event_id,
    }


def main() -> None:
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    while True:
        try:
            client.ping()
            break
        except Exception as error:
            logger.warning("Waiting for Redis: %s", error)
            time.sleep(2)

    try:
        client.xgroup_create(SOURCE_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise

    time.sleep(STARTUP_DELAY)
    logger.info(
        "Bridging %s/%s to %s/%s",
        SOURCE_STREAM,
        SOURCE_FIELD,
        TARGET_STREAM,
        TARGET_FIELD,
    )
    while True:
        client.set(HEARTBEAT_KEY, str(time.time()), ex=15)
        messages = client.xreadgroup(
            CONSUMER_GROUP,
            CONSUMER_NAME,
            {SOURCE_STREAM: ">"},
            count=50,
            block=2000,
        )
        for _, entries in messages:
            for message_id, fields in entries:
                try:
                    raw = fields.get(SOURCE_FIELD) or fields.get("data") or fields.get("payload")
                    translated = translate(json.loads(raw or "{}"))
                    client.xadd(TARGET_STREAM, {TARGET_FIELD: json.dumps(translated)})
                    client.xack(SOURCE_STREAM, CONSUMER_GROUP, message_id)
                except Exception as error:
                    client.xadd(DEAD_LETTER_STREAM, {
                        "source_id": message_id,
                        "error": str(error),
                        "payload": json.dumps(fields),
                    })
                    client.xack(SOURCE_STREAM, CONSUMER_GROUP, message_id)


if __name__ == "__main__":
    main()
