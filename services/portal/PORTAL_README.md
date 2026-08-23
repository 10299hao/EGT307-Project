# LogSentinel Incident Portal

This folder contains Minghao's Incident Portal microservice. The Portal is the control and presentation layer of LogSentinel: it receives AI-detected HDFS incidents, validates and stores them, displays them to the operator, records acknowledgements, receives Ethan's dry-run results and can send an optional Windows desktop alert.

The Portal does not train the AI model, read the full HDFS training dataset or execute infrastructure commands. Danish's Analyzer owns prediction, while Ethan's Executor owns safe dry-run action selection and simulation.

## What the Portal does

The Portal has six main responsibilities:

1. Consume anomaly messages published by Danish's Analyzer to Redis `IncidentStream`.
2. Convert Danish's message format into the Portal contract and validate every field.
3. Store incidents, action results, acknowledgements and notification attempts in SQLite.
4. Provide a responsive React dashboard for searching, filtering and reviewing incidents.
5. Consume Ethan's results from `action-results` and join them to incidents using `incident_id`.
6. Send an optional HTTP notification to the Windows popup receiver when a genuinely new incident is stored.

The operator can view incident severity, AI confidence, model version, supporting evidence, dry-run Executor results and service configuration. Incidents can be searched, filtered, inspected and acknowledged.

## Current system workflow

```text
HDFS demonstration_traces.csv
        |
        v
Wei Jie's Log Collector
        |  Redis: log-events / data
        v
Danish's Log Analyzer + AI model
        |  Redis: IncidentStream / payload
        +-----------------------------+
        |                             |
        v                             v
Minghao's Incident Portal       Ethan's Automation Executor
        |                             |
        | SQLite                      | dry-run simulation
        |                             |
        |<---- Redis: action-results / payload
        |
        +--> React dashboard
        +--> Optional Windows popup
```

Redis Streams is the shared communication layer. The services run independently and exchange JSON messages instead of importing one another's source files.

Danish publishes an anomaly to `IncidentStream`. The Portal and Ethan consume the same incident. Ethan publishes the result to `action-results`, and the Portal attaches it to the correct SQLite record using the shared `incident_id`.

The Portal still contains a backward-compatible `ActionStream` publisher from the earlier sequential design. Ethan's current Executor does not consume it; he reads `IncidentStream` directly. The Executor response displayed in the dashboard comes from Ethan's real `action-results` message.

## Live data and demo data

The Kubernetes deployment uses:

```text
ENABLE_REDIS=true
SEED_DEMO_DATA=false
```

The deployed dashboard therefore uses live Redis messages produced by Danish's Analyzer. The Portal does not directly open the training CSV files or saved model.

For standalone Portal development, Redis can be disabled and `SEED_DEMO_DATA=true` can be used. Those records come from `backend/app/demo_data.py` and are not real AI predictions.

## Main technologies

| Area | Technology |
|---|---|
| Backend API | FastAPI and Pydantic |
| Dashboard | React, Vite, GSAP and Phosphor Icons |
| Incident storage | SQLite in WAL mode |
| Messaging | Redis Streams |
| Container | Multi-stage Docker image |
| Orchestration | Kubernetes with Minikube |
| Optional alert | Local FastAPI receiver and native Windows dialog |

## Folder guide

```text
services/portal/
|-- backend/
|   |-- app/
|   |   |-- __init__.py       # marks app as a Python package
|   |   |-- main.py           # startup, API routes and frontend serving
|   |   |-- config.py         # environment-variable configuration
|   |   |-- consumer.py       # consumes IncidentStream and action-results
|   |   |-- adapters.py       # converts Danish's message into Portal fields
|   |   |-- schemas.py        # validates message contracts
|   |   |-- database.py       # SQLite schema, queries and updates
|   |   |-- executor.py       # backward-compatible ActionStream publisher
|   |   |-- notifications.py  # sends requests to the local alert receiver
|   |   `-- demo_data.py      # optional standalone records
|   |-- tests/
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |   |-- App.jsx           # dashboard pages and interactions
|   |   |-- portal.js         # API helpers and display formatting
|   |   |-- styles.css        # responsive styling and transitions
|   |   |-- signal-map.svg    # dashboard illustration
|   |   `-- main.jsx          # React entry point
|   |-- package.json
|   |-- pnpm-lock.yaml
|   |-- pnpm-workspace.yaml
|   `-- vite.config.js
|-- tools/local-notifier/
|   |-- app.py                # displays the Windows popup
|   |-- start.ps1             # starts the receiver on port 8090
|   `-- requirements.txt
|-- Dockerfile
|-- .env.example
`-- PORTAL_README.md
```

The full-system Kubernetes manifests are in the repository-root `kubernetes/` folder.

## Run an existing Minikube deployment

From the repository root:

```powershell
minikube status
kubectl get pods
```

Redis and all four microservices should show `1/1 Running`.

Open one PowerShell window for the Portal:

```powershell
kubectl port-forward service/incident-portal 8000:8000
```

Open another PowerShell window for the Collector:

```powershell
kubectl port-forward service/log-collector 8080:8080
```

If port 8080 is already occupied, test whether an existing port-forward is healthy:

```powershell
Invoke-RestMethod "http://localhost:8080/health"
```

Open `http://localhost:8000`. FastAPI documentation is at `http://localhost:8000/docs`.

Submit the demonstration traces from the repository root:

```powershell
curl.exe -X POST "http://localhost:8080/ingest" `
  -F "file=@.\data\demonstration_traces.csv"
```

Wait for processing, refresh the dashboard and open a new incident. It should show Danish's confidence and evidence followed by Ethan's `SIMULATION ONLY` result.

The root [README](../../README.md) contains the complete first-time Minikube and four-image build procedure.

## Rebuild only the Portal

A Portal backend or frontend change does not require rebuilding Collector, Analyzer, Executor or Redis.

```powershell
$portalVersion = Get-Date -Format "yyyy.MM.dd-HHmm"

docker build `
  --build-arg PORTAL_VERSION=$portalVersion `
  -t "logsentinel-portal:$portalVersion" `
  .\services\portal

minikube image load "logsentinel-portal:$portalVersion"

kubectl set image deployment/incident-portal `
  "incident-portal=logsentinel-portal:$portalVersion"

kubectl rollout status deployment/incident-portal
```

Restart the Portal port-forward after the rollout and refresh the browser with `Ctrl + F5`.

Check the deployed image:

```powershell
kubectl get deployment incident-portal `
  -o jsonpath="{.spec.template.spec.containers[0].image}"
```

## Optional Windows desktop alerts

The notification receiver runs on Windows because a Linux container cannot directly display a native dialog on the host desktop.

Create the backend virtual environment once:

```powershell
cd .\services\portal\backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..
```

Start the receiver and keep its window open:

```powershell
.\tools\local-notifier\start.ps1
```

Verify it:

```powershell
Invoke-RestMethod "http://localhost:8090/health"
```

Connect the Kubernetes Portal to the laptop:

```powershell
kubectl set env deployment/incident-portal `
  LOCAL_NOTIFICATION_URL=http://host.minikube.internal:8090/notify

kubectl rollout status deployment/incident-portal
```

Confirm that the Portal pod can reach it:

```powershell
kubectl exec deployment/incident-portal -- python -c "import urllib.request; print(urllib.request.urlopen('http://host.minikube.internal:8090/health').read().decode())"
```

Notifications are sent only for genuinely new incident IDs. Browser refreshes and duplicate incidents do not produce repeated popups.

## SQLite database

The live Kubernetes database is:

```text
/app/data/portal.db
```

It is mounted from the `portal-data` persistent-volume claim, so it is not the same as a local project `data` folder.

```powershell
kubectl exec deployment/incident-portal -- ls -lh /app/data
```

SQLite uses WAL mode, so `portal.db`, `portal.db-wal` and `portal.db-shm` are normal. Do not delete the WAL or SHM files while the Portal is running.

List the database tables:

```powershell
kubectl exec deployment/incident-portal -- python -c "import sqlite3; db=sqlite3.connect('/app/data/portal.db'); print(db.execute('SELECT name FROM sqlite_master WHERE type=?', ('table',)).fetchall())"
```

Show the latest incidents:

```powershell
kubectl exec deployment/incident-portal -- python -c "import sqlite3; db=sqlite3.connect('/app/data/portal.db'); rows=db.execute('SELECT incident_id, block_id, severity, anomaly_probability, recommended_action, acknowledged FROM incidents ORDER BY received_at DESC LIMIT 5').fetchall(); [print(row) for row in rows]"
```

Show Ethan's stored results:

```powershell
kubectl exec deployment/incident-portal -- python -c "import sqlite3; db=sqlite3.connect('/app/data/portal.db'); rows=db.execute('SELECT incident_id, action, command, mode, status FROM action_results ORDER BY received_at DESC LIMIT 5').fetchall(); [print(row) for row in rows]"
```

The dashboard and Excel Power Query can read live records through `GET /api/incidents`. A copied database file is only a snapshot.

## Useful API routes

| Route | Purpose |
|---|---|
| `GET /api/health/live` | Confirms that the Portal process is running |
| `GET /api/health/ready` | Checks Redis readiness |
| `GET /api/service-status` | Returns integration status and stream configuration |
| `GET /api/incidents` | Returns searchable incident records |
| `GET /api/incidents/{incident_id}` | Returns one incident, action result and alert history |
| `POST /api/incidents/{incident_id}/acknowledge` | Records operator acknowledgement |
| `GET /api/stats` | Returns dashboard summary values |
| `POST /api/ingest/incident` | Accepts a test Analyzer incident over HTTP |
| `POST /api/ingest/action-result` | Accepts a test Executor result over HTTP |

## Current Redis contracts

| Flow | Stream | Field |
|---|---|---|
| Collector to Analyzer | `log-events` | `data` |
| Analyzer to Portal and Executor | `IncidentStream` | `payload` |
| Executor to Portal | `action-results` | `payload` |
| Invalid Portal input | `portal-dead-letter` | error details |
| Invalid Executor input | `executor-dead-letter` | `payload` |

The `incident_id` joins the Analyzer prediction, Portal incident and Executor result.

## Run backend tests

```powershell
cd .\services\portal\backend
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."
python -m pip install pytest
python -m pytest -q
```

The tests cover incident storage, acknowledgement, Analyzer adaptation, validation, duplicate protection, action-result joins and service-status responses.

## Reliability and safety

- Pydantic validates incidents and action results before storage.
- Unexpected message fields are rejected.
- Invalid Redis messages are preserved in a dead-letter stream.
- SQLite upserts and unique IDs reduce duplicate records.
- Desktop-alert attempts and failures are recorded for auditing.
- The Portal never executes infrastructure commands.
- Ethan's actions are displayed as `dry_run` and `SIMULATION ONLY`.
- The frontend uses the Portal API instead of connecting directly to Redis or SQLite.
- Kubernetes liveness and readiness probes monitor the Portal.
- A persistent-volume claim preserves SQLite data across pod restarts.

## Current limitations

- Ethan does not expose an HTTP health endpoint or Redis heartbeat, so the Portal reports the integration as configured rather than continuously online.
- Analyzer status is inferred from data in `IncidentStream`, not a dedicated heartbeat.
- The backward-compatible Portal `ActionStream` publisher is unused by Ethan's current direct consumer.
- SQLite is suitable for one Portal replica; multiple production replicas should use a shared database such as PostgreSQL.
- Authentication, role-based access, approval workflows and real remediation are outside this prototype.
- Desktop alerts require the local Windows receiver.
- Historical incidents created before Analyzer evidence was added remain without evidence.

## Short lecturer explanation

The Incident Portal is the operator-facing part of LogSentinel. Danish's Analyzer publishes an anomaly to Redis, the Portal validates and stores it in SQLite, and the React dashboard presents it to the operator. Ethan independently reads the same anomaly, chooses an approved response, performs a dry-run simulation and publishes the result. The Portal joins that result to the incident using `incident_id`, records the history and allows the operator to acknowledge it. An optional Windows receiver displays a popup whenever a genuinely new incident is stored.

For a code walkthrough, use this order:

1. `schemas.py` for accepted message contracts.
2. `adapters.py` for Danish's compatibility conversion.
3. `consumer.py` for Redis incident and result processing.
4. `database.py` for SQLite persistence and joins.
5. `notifications.py` and `tools/local-notifier/app.py` for alerts.
6. `main.py` for application startup, API routes and frontend serving.
7. `App.jsx` for the operator dashboard.
