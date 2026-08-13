import redis
import json

# Connect to Ethan's fresh Redis container
client = redis.Redis(host='localhost', port=6379, decode_responses=True, protocol=2)

# Create a fake incident payload that mimics Minghao's future dashboard
payload = {
    "incident_id": "INC-999-DOOM",
    "action": "isolate_node"
}

# Fire it into the exact stream the Executor is watching
client.xadd('ActionStream', {'command': json.dumps(payload)})

print("🚀 Emergency signal sent to the ActionStream!")