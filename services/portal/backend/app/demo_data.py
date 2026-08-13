from .database import PortalDatabase
from .schemas import ActionResultIn, IncidentIn


INCIDENTS = [
    {
        "incident_id": "INC-2026-0842", "block_id": "blk_6279226377833208445",
        "anomaly_probability": 0.99994, "category": "network_transfer_failure", "severity": "critical",
        "evidence_event_ids": ["E17", "E29", "E20"], "recommended_action": "restart_datanode",
        "model_version": "hdfs-tfidf-logreg-v1", "created_at": "2026-08-01T09:42:18+08:00",
    },
    {
        "incident_id": "INC-2026-0841", "block_id": "blk_-4720116503510508292",
        "anomaly_probability": 0.9821, "category": "replication_timeout", "severity": "high",
        "evidence_event_ids": ["E12", "E28", "E17"], "recommended_action": "check_replication_health",
        "model_version": "hdfs-tfidf-logreg-v1", "created_at": "2026-08-01T09:31:05+08:00",
    },
    {
        "incident_id": "INC-2026-0839", "block_id": "blk_8807356229781918656",
        "anomaly_probability": 0.9678, "category": "storage_block_failure", "severity": "medium",
        "evidence_event_ids": ["E18", "E20", "E27"], "recommended_action": "run_block_health_check",
        "model_version": "hdfs-tfidf-logreg-v1", "created_at": "2026-08-01T08:56:47+08:00",
    },
    {
        "incident_id": "INC-2026-0837", "block_id": "blk_-1199030689311487523",
        "anomaly_probability": 0.9612, "category": "metadata_failure", "severity": "low",
        "evidence_event_ids": ["E13", "E24"], "recommended_action": "notify_operator",
        "model_version": "hdfs-tfidf-logreg-v1", "created_at": "2026-08-01T08:12:29+08:00",
    },
]


RESULTS = [
    {
        "action_result_id": "ACT-0842", "incident_id": "INC-2026-0842", "action": "restart_datanode",
        "command": "kubectl rollout restart deployment/hdfs-datanode", "status": "completed",
        "reason": "Critical anomaly exceeded the 0.96 confidence threshold.", "created_at": "2026-08-01T09:42:21+08:00",
    },
    {
        "action_result_id": "ACT-0841", "incident_id": "INC-2026-0841", "action": "check_replication_health",
        "command": "hdfs fsck / -blocks -locations", "status": "completed",
        "reason": "High-severity replication issue matched the approved diagnostic action.", "created_at": "2026-08-01T09:31:09+08:00",
    },
    {
        "action_result_id": "ACT-0839", "incident_id": "INC-2026-0839", "action": "run_block_health_check",
        "command": "hdfs fsck / -blockId blk_8807356229781918656", "status": "completed",
        "reason": "Storage anomaly matched the approved health-check policy.", "created_at": "2026-08-01T08:56:51+08:00",
    },
    {
        "action_result_id": "ACT-0837", "incident_id": "INC-2026-0837", "action": "notify_operator",
        "command": None, "status": "skipped", "reason": "Low severity incidents require operator review only.",
        "created_at": "2026-08-01T08:12:34+08:00",
    },
]


def seed(database: PortalDatabase) -> None:
    for payload in INCIDENTS:
        database.upsert_incident(IncidentIn.model_validate(payload))
    for payload in RESULTS:
        database.upsert_action_result(ActionResultIn.model_validate(payload))
