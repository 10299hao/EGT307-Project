from api import run_api
from redis_client import get_redis_client, redis_is_ready

if __name__ == "__main__":
    print("Connecting to Redis...")
    client = get_redis_client()
    if not redis_is_ready(client):
        print("CRITICAL ERROR: Could not connect to Redis. Exiting.")
        exit(1)
    print("Connected to Redis. Idle, waiting for a POST to /ingest...")

    run_api()