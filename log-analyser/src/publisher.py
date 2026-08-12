import redis
import json
import os

# We use environment variables so this works safely on your laptop AND inside Kubernetes later!
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

def publish_incident(incident_dict):
    """
    Takes the Incident dictionary from the AI and sends it to the Redis IncidentStream.
    """
    try:
        # 1. Connect to Redis
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        
        # 2. Convert the Python dictionary to a JSON string and publish to the new stream
        message = {'payload': json.dumps(incident_dict)}
        client.xadd('IncidentStream', message)
        
        print(f"📡 SUCCESS: Incident for {incident_dict['block_id']} published to Redis IncidentStream!")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to publish incident to Redis. Is Redis running? Error: {e}")

if __name__ == "__main__":
    # Danish can run a quick local test to see if it connects to Redis
    print("\n--- Running Local Publisher Test ---")
    fake_incident = {"block_id": "blk_test_123", "status": "Anomaly"}
    publish_incident(fake_incident)