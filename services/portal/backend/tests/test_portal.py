import asyncio
import importlib
import json
from dataclasses import replace

from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SEED_DEMO_DATA", "false")
    monkeypatch.setenv("ENABLE_REDIS", "false")
    import app.config
    import app.main
    importlib.reload(app.config)
    importlib.reload(app.main)
    return TestClient(app.main.app)


INCIDENT = {
    "incident_id": "INC-TEST-1", "block_id": "blk_test", "anomaly_probability": 0.98,
    "category": "network_transfer_failure", "severity": "high",
    "evidence_event_ids": ["E17", "E29"], "recommended_action": "restart_datanode",
    "model_version": "test-model-1",
}


ACTION = {
    "action_result_id": "ACT-TEST-1", "incident_id": "INC-TEST-1", "action": "restart_datanode",
    "command": "kubectl rollout restart deployment/hdfs-datanode", "status": "completed",
    "reason": "Policy matched during the test.",
}


DANISH_ANALYZER_INCIDENT = {
    "block_id": "blk_danish_test",
    "status": "Anomaly",
    "confidence_score": 97.25,
    "severity": "High",
    "total_events_analyzed": 6,
    "evidence": "E5 E22 E11 E17 E29 E26",
}


def test_incident_can_be_stored_and_acknowledged(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.post("/api/ingest/incident", json=INCIDENT)
        assert response.status_code == 202
        assert response.json()["new"] is True
        detail = client.get("/api/incidents/INC-TEST-1").json()
        assert detail["evidence"][0]["event_id"] == "E17"
        acknowledged = client.post("/api/incidents/INC-TEST-1/acknowledge", json={"operator": "Minghao"})
        assert acknowledged.status_code == 200
        assert acknowledged.json()["acknowledged"] is True


def test_action_result_can_arrive_before_incident(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        assert client.post("/api/ingest/action-result", json=ACTION).status_code == 202
        assert client.post("/api/ingest/incident", json=INCIDENT).status_code == 202
        detail = client.get("/api/incidents/INC-TEST-1").json()
        assert detail["action_result"]["status"] == "completed"


def test_duplicate_messages_are_idempotent(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        assert client.post("/api/ingest/incident", json=INCIDENT).json()["new"] is True
        assert client.post("/api/ingest/incident", json=INCIDENT).json()["new"] is False
        assert client.get("/api/stats").json()["total_incidents"] == 1


def test_invalid_probability_is_rejected(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        invalid = {**INCIDENT, "incident_id": "INC-BAD", "anomaly_probability": 1.4}
        response = client.post("/api/ingest/incident", json=invalid)
        assert response.status_code == 422
        assert client.get("/api/stats").json()["total_incidents"] == 0


def test_danish_analyzer_message_is_adapted_and_stored(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        accepted = client.post("/api/ingest/incident", json=DANISH_ANALYZER_INCIDENT)
        assert accepted.status_code == 202
        incident_id = accepted.json()["incident_id"]
        assert incident_id.startswith("INC-")
        detail = client.get(f"/api/incidents/{incident_id}").json()
        assert detail["anomaly_probability"] == 0.9725
        assert detail["severity"] == "high"
        assert detail["category"] == "network_transfer_failure"
        assert detail["evidence_event_ids"] == ["E5", "E22", "E11", "E17", "E29", "E26"]
        assert detail["evidence_summary"] == DANISH_ANALYZER_INCIDENT["evidence"]
        assert detail["total_events_analyzed"] == 6
        assert detail["model_version"] == "log-analyzer-logistic-regression-v1"

        duplicate = client.post("/api/ingest/incident", json=DANISH_ANALYZER_INCIDENT)
        assert duplicate.json()["new"] is False
        assert duplicate.json()["incident_id"] == incident_id


def test_non_anomaly_analyzer_message_is_rejected(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        normal = {**DANISH_ANALYZER_INCIDENT, "status": "Normal"}
        response = client.post("/api/ingest/incident", json=normal)
        assert response.status_code == 422
        assert client.get("/api/stats").json()["total_incidents"] == 0


def test_service_status_identifies_demo_data_and_stream_contracts(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        status = client.get("/api/service-status")
        assert status.status_code == 200
        assert status.json()["data_source"] == "seeded-demo-records"
        assert status.json()["incident_stream"] == "IncidentStream"
        assert status.json()["incident_stream_aliases"] == ["incidents"]
        assert status.json()["action_result_stream"] == "action-results"
        assert status.json()["action_request_stream"] == "ActionStream"
        assert status.json()["action_request_field"] == "command"
        assert status.json()["collector_output_stream"] == "log-events"
        assert status.json()["analyzer_input_stream"] == "LogStream"
        assert status.json()["upstream_contract_match"] is False


def test_executor_request_matches_ethans_actionstream_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATABASE_PATH", str(tmp_path / "executor-test.db"))
    from app.config import settings
    from app.database import PortalDatabase
    from app.executor import dispatch_action_request
    from app.schemas import IncidentIn

    class FakeRedis:
        def __init__(self):
            self.calls = []

        async def xadd(self, stream, fields):
            self.calls.append((stream, fields))
            return "123-0"

    database = PortalDatabase(str(tmp_path / "executor-test.db"))
    database.upsert_incident(IncidentIn.model_validate(INCIDENT))
    redis = FakeRedis()
    config = replace(settings, enable_executor=True)

    asyncio.run(dispatch_action_request(redis, database, config, database.get_incident("INC-TEST-1")))
    assert redis.calls == [("ActionStream", {"command": json.dumps({
        "incident_id": "INC-TEST-1",
        "action": "restart_datanode",
    })})]
    stored = database.get_incident("INC-TEST-1")
    assert stored["action_request"]["status"] == "sent"
    assert stored["action_request"]["message_id"] == "123-0"

    # Replaying the same incident must not trigger Ethan twice.
    asyncio.run(dispatch_action_request(redis, database, config, stored))
    assert len(redis.calls) == 1


def test_local_notification_contains_incident_details():
    from app.notifications import local_notification_payload

    notification = local_notification_payload(INCIDENT)
    assert notification["source"] == "LogSentinel"
    assert notification["incident_id"] == "INC-TEST-1"
    assert notification["severity"] == "HIGH"
    assert notification["confidence"] == "98.00%"
