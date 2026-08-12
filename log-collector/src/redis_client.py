import os
import time
import json
import redis


# =========================
# REDIS SETTINGS
# =========================

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))

LOG_STREAM = os.getenv("LOG_STREAM", "log-events")
DEAD_LETTER_STREAM = os.getenv(
    "DEAD_LETTER_STREAM",
    "log-events-dead-letter"
)

MAX_RETRIES = 3
RETRY_DELAY = 1


# =========================
# CONNECT TO REDIS
# =========================

def get_redis_client():

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        protocol = 2
    )

    return client


# =========================
# PUBLISH VALID LOG EVENT
# =========================

def publish_event(client, event):

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            client.xadd(
                LOG_STREAM,
                {
                    "data": json.dumps(event)
                }
            )

            print(
                f"Published event {event['event_id']} "
                f"for {event['block_id']}"
            )

            return True

        except redis.RedisError as error:

            print(
                f"Redis error. Attempt "
                f"{attempt}/{MAX_RETRIES}: {error}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    return False


# =========================
# DEAD LETTER STREAM
# =========================

def publish_dead_letter(client, row, reason):

    dead_letter = {
        "reason": reason,
        "row": json.dumps(
            {key: str(value) for key, value in row.items()}
        )
    }

    try:

        client.xadd(
            DEAD_LETTER_STREAM,
            dead_letter
        )

        print(
            f"Sent bad record to dead-letter stream: {reason}"
        )

        return True

    except redis.RedisError as error:

        print(
            f"Could not send record to dead-letter stream: {error}"
        )

        return False


# =========================
# CHECK REDIS CONNECTION
# =========================

def redis_is_ready(client):

    try:
        return client.ping()

    except redis.RedisError:
        return False