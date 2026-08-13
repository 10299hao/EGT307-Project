# Incident Portal
## What the Portal does

The Portal has five main responsibilities:

1. Receive anomaly results produced by Danish's Log Analyzer.
2. Validate and convert those results into a consistent incident format.
3. Store incidents, action requests, action results and alert attempts in SQLite.
4. Present the information in a responsive dashboard for the operator.
5. Send a recommended dry-run action to Ethan's Automation Executor.

The operator can use the dashboard to:

- see open incidents and their severity;
- check the AI confidence score and detected event evidence;
- search and filter incident history;
- open an incident to view its full details;
- acknowledge an incident after reviewing it;
- check the connection status of the other services; and
- view the status of Executor actions when a result is returned.

## How the complete project works

```text
HDFS demonstration data
        |
        v
Wei Jie's Log Collector
        |  Redis: log-events / data
        v
Portal integration bridge
        |  Redis: LogStream / payload
        v
Danish's Log Analyzer and AI model
        |  Redis: IncidentStream / payload
        v
Minghao's Incident Portal
        |  Redis: ActionStream / command
        v
Ethan's Automation Executor
        |  Redis: action-results / payload (future return path)
        v
Incident Portal updates the action status
```

Redis Streams is the shared communication channel. The services do not need to import one another's Python code while running. They exchange messages through agreed stream names and fields.

The Portal joins an incident and its action result using the same `incident_id`. It stores action results separately so a result can still be handled if it arrives before its incident.

## Data used by the Portal

The Portal does not train Danish's model and does not directly read the raw HDFS training CSV files.

In integrated mode, the data shown in the dashboard comes from Analyzer messages in Redis. Wei Jie's Collector starts the pipeline by replaying `data/demonstration_traces.csv`. Danish's Analyzer processes those events and publishes anomaly predictions to `IncidentStream`.

In standalone development mode, the Portal uses safe seeded demonstration records from `backend/app/demo_data.py`. The dashboard clearly labels these records as demo data. They are not live AI predictions.

## Main technologies

- React and Vite for the dashboard
- FastAPI for the REST API
- SQLite for incident history
- Redis Streams for microservice communication
- Docker Compose for local integration
- Kubernetes YAML for deployment evidence

## Folder guide

```text
services/portal/
|-- backend/
|   |-- app/
|   |   |-- main.py          # FastAPI routes and application startup
|   |   |-- config.py        # environment-variable settings
|   |   |-- consumer.py      # consumes Incident and ActionResult streams
|   |   |-- adapters.py      # converts Analyzer output to Portal format
|   |   |-- schemas.py       # validates incoming messages
|   |   |-- database.py      # SQLite tables and queries
|   |   |-- executor.py      # publishes Executor action requests
|   |   |-- notifications.py # sends optional desktop alerts
|   |   `-- demo_data.py     # creates standalone demonstration records
|   |-- tests/               # backend integration tests
|   `-- requirements.txt     # backend Python dependencies
|-- frontend/
|   |-- src/
|   |   |-- App.jsx          # dashboard pages and interactions
|   |   |-- portal.js        # shared API helpers and display formatting
|   |   |-- styles.css       # dashboard and responsive styling
|   |   |-- signal-map.svg   # decorative dashboard illustration
|   |   `-- main.jsx         # starts the React application
|   `-- package.json         # frontend dependencies and commands
|-- integration/
|   |-- bridge.py            # adapts Collector messages for the Analyzer
|   |-- Dockerfile           # bridge container definition
|   |-- analyzer.Dockerfile  # wrapper for Danish's existing service
|   `-- executor.Dockerfile  # wrapper for Ethan's existing service
|-- tools/local-notifier/    # optional Windows desktop-alert receiver
|-- k8s/                     # Kubernetes manifests
|-- Dockerfile               # builds the Portal frontend and backend
|-- docker-compose.yml       # runs the complete integrated application
|-- .env.example             # example configuration without private values
`-- RUBRIC_EVIDENCE.md       # project requirement and evidence checklist
```

## Option 1: run the complete integrated application

This is the recommended method for the final demonstration. It starts Redis, Collector, integration bridge, Analyzer, Executor and Portal together.

### Requirements

- Docker Desktop is installed and running.
- The team folders `log-collector`, `log-analyser` and `executor` are still present in the main project folder.
- `data/demonstration_traces.csv` is present.

### Start the application

Open PowerShell and run:

```powershell
cd "C:\Users\mingh\OneDrive\Documents\AI APPLICATION 2\services\portal"
docker compose up --build
```

The first build can take several minutes. Wait until the Portal and the other services have started, then open:

- Dashboard: `http://localhost:8000`
- Portal API documentation: `http://localhost:8000/docs`
- Portal readiness check: `http://localhost:8000/api/health/ready`
- Collector health check: `http://localhost:8080/health`

Keep the PowerShell window open while demonstrating the application.

### Run in the background

Use this if you want to close the PowerShell window after startup:

```powershell
docker compose up --build -d
```

View the running services and their output with:

```powershell
docker compose ps
docker compose logs -f
```

### Stop the application

```powershell
docker compose down
```

`docker compose down` stops the containers but keeps the named Redis and Portal database volumes. Do not add `-v` unless you intentionally want to delete the stored Redis and incident data.

### Rebuild after changing code

```powershell
docker compose down
docker compose up --build
```

If the browser still shows an older design, refresh with `Ctrl + F5` after the new container starts.

## Option 2: run only the Portal for development

Use this mode when the other microservices are unavailable. It starts the backend with seeded demo incidents and the frontend development server.

### Terminal 1: backend

```powershell
cd "C:\Users\mingh\OneDrive\Documents\AI APPLICATION 2\services\portal\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = "."
$env:ENABLE_REDIS = "false"
$env:SEED_DEMO_DATA = "true"
python -m uvicorn app.main:app --reload --port 8000
```

The environment only needs to be created and installed once. On later runs, activate `.venv` and start Uvicorn again.

### Terminal 2: frontend

```powershell
cd "C:\Users\mingh\OneDrive\Documents\AI APPLICATION 2\services\portal\frontend"
pnpm install
pnpm run dev
```

Open `http://localhost:5173` for the development dashboard. The API remains at `http://localhost:8000/docs`.

If `pnpm` is not recognised, enable it using Node's Corepack:

```powershell
corepack enable
corepack prepare pnpm@11.9.0 --activate
```

Then close and reopen PowerShell before running `pnpm install` again.

## Optional desktop alerts

The Portal can display a persistent Windows popup when a new incident is stored.

First ensure the backend `.venv` and dependencies have been created using the Portal-only instructions above. Then open another PowerShell window:

```powershell
cd "C:\Users\mingh\OneDrive\Documents\AI APPLICATION 2\services\portal"
.\tools\local-notifier\start.ps1
```

For Docker mode, create a private `.env` file beside `docker-compose.yml` and add:

```text
LOCAL_NOTIFICATION_URL=http://host.docker.internal:8090/notify
```

The `.env` file is ignored by Git. Do not commit private settings. The Portal records whether each alert was delivered, retries failed deliveries up to three times, and avoids sending a second alert for a duplicate incident.

## Run the backend tests

```powershell
cd "C:\Users\mingh\OneDrive\Documents\AI APPLICATION 2\services\portal\backend"
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python -m pip install pytest
python -m pytest -q
```

The tests cover:

- storing and acknowledging an incident;
- accepting Danish's current Analyzer message format;
- rejecting invalid incident data;
- duplicate-message protection;
- joining an action result that arrives before its incident;
- reporting the configured stream contracts; and
- publishing the action format expected by Ethan's Executor.

## Important Redis message contracts

| Purpose | Stream | Field |
|---|---|---|
| Collector output | `log-events` | `data` |
| Analyzer input | `LogStream` | `payload` |
| Analyzer incident output | `IncidentStream` | `payload` |
| Portal action request | `ActionStream` | `command` |
| Executor action result | `action-results` | `payload` |
| Invalid Portal message | `portal-dead-letter` | error details |

The integration bridge exists because Wei Jie's Collector and Danish's Analyzer currently use different stream and field names. It changes the message envelope but does not alter either teammate's source code.

The versioned team contracts are also stored at the repository root:

- `contracts/incident.schema.json`
- `contracts/action_result.schema.json`

## Portal API routes

| Route | Purpose |
|---|---|
| `GET /api/health/live` | Confirms that the Portal process is running |
| `GET /api/health/ready` | Checks whether required dependencies are ready |
| `GET /api/service-status` | Shows current integration configuration and status |
| `GET /api/incidents` | Returns incidents with optional filters |
| `GET /api/incidents/{incident_id}` | Returns one incident and its related history |
| `POST /api/incidents/{incident_id}/acknowledge` | Records operator acknowledgement |
| `GET /api/stats` | Returns dashboard summary values |
| `POST /api/ingest/incident` | HTTP route for testing an Analyzer incident |
| `POST /api/ingest/action-result` | HTTP route for testing an Executor result |

## Reliability and code-quality decisions

- Incoming data is validated before it is stored.
- Invalid Redis messages are moved to a dead-letter stream for inspection.
- A Redis message is acknowledged only after it has been stored successfully.
- Database upserts and unique message IDs prevent duplicate incidents.
- Stable incident IDs are generated when the Analyzer does not provide one.
- Configuration is controlled using environment variables instead of hard-coded addresses.
- The frontend reads information only through the Portal API; it does not connect directly to SQLite or Redis.
- Recommended actions remain dry-run requests. The Portal never executes system commands itself.

## Current integration status and limitations

- Wei Jie's Collector can publish demonstration events through Redis.
- The integration bridge translates the Collector envelope for Danish's Analyzer.
- Danish's Analyzer can publish predictions that the Portal converts and stores.
- The Portal can send Ethan's expected `incident_id` and `action` request format.
- Ethan's current Executor simulates the action and prints the outcome in its container output, but it does not yet publish an `ActionResult` to `action-results`. Until that is added, the Portal cannot display a real returned completion result.
- SQLite is suitable for this local prototype and Minikube demonstration, but a production system with multiple Portal replicas should use a shared database such as PostgreSQL.
- Authentication and role-based access are outside the scope of this prototype.

## Simple explanation for a lecturer

The Incident Portal is the control and presentation layer of the project. The AI work stays inside the Analyzer, while the Portal receives only the prediction result. It validates the result, saves it as an incident, and presents the important information to the operator. If a response is recommended, the Portal sends a request to the Executor but does not run the command itself. Redis Streams keeps the microservices separate, while `incident_id` connects the prediction, incident and action history together.

For a code walkthrough, a clear order is:

1. `schemas.py` — the messages the Portal accepts.
2. `consumer.py` and `adapters.py` — how Analyzer messages enter the Portal.
3. `database.py` — how incident and action history is stored.
4. `executor.py` — how action requests are sent safely.
5. `main.py` — the API used by the dashboard.
6. `App.jsx` — how the operator views and manages the incidents.
