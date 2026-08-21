"""
Convert Analyzer's output into the portal standard data format

├── extract event IDs
├── determine incident category
├── convert confidence
├── generate incident ID
└── select recommended action

"""

from hashlib import sha256     #consistent identifier
import re
from typing import Any    


#event id --> incident categories
CATEGORY_RULES = (
    ("network_transfer_failure", {"E4", "E7", "E10", "E12", "E14", "E17"}),
    ("replication_timeout", {"E24", "E25", "E29"}),
    ("storage_block_failure", {"E20", "E21", "E27"}),
    ("metadata_failure", {"E15", "E22", "E26", "E28"}),
)

#each incident cat --> recommended actions
ACTION_BY_CATEGORY = {
    "network_transfer_failure": "restart_datanode",
    "replication_timeout": "check_replication_health",
    "storage_block_failure": "run_block_health_check",
    "metadata_failure": "notify_operator",
    "hdfs_anomaly": "notify_operator",
}

#Checking
def _event_ids(raw_evidence: Any) -> list[str]:
    if isinstance(raw_evidence, list):
        values = raw_evidence
    else:
        values = re.findall(r"\bE\d+\b", str(raw_evidence or ""), flags=re.IGNORECASE)
    return list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))


#event id --> category
def _category(event_ids: list[str]) -> str:
    evidence = set(event_ids)
    for category, matching_events in CATEGORY_RULES:
        if evidence & matching_events:
            return category
    return "hdfs_anomaly"

#analyser % --> 0-1
def _probability(value: Any) -> float:
    confidence = float(value)
    if confidence > 1:
        confidence /= 100
    return confidence

#analyser output --> portal incident formaat
def normalise_analyzer_incident(payload: dict[str, Any]) -> dict[str, Any]:
    if "anomaly_probability" in payload and "incident_id" in payload:
        return payload

    if "confidence_score" not in payload or "block_id" not in payload:
        return payload

    if str(payload.get("status") or "Anomaly").strip().lower() != "anomaly":
        raise ValueError("Analyzer status must be Anomaly before publishing an incident")

    evidence_summary = str(payload.get("evidence") or "").strip()
    event_ids = _event_ids(evidence_summary)
    category = _category(event_ids)
    fingerprint = f"{payload['block_id']}|{evidence_summary}".encode("utf-8")
    incident_id = payload.get("incident_id") or f"INC-{sha256(fingerprint).hexdigest()[:12].upper()}"

    return {
        "schema_version": str(payload.get("schema_version") or "1.0"),
        "incident_id": incident_id,
        "block_id": str(payload["block_id"]),
        "prediction": "anomaly",
        "anomaly_probability": _probability(payload["confidence_score"]),
        "category": payload.get("category") or category,
        "severity": str(payload.get("severity") or "medium").strip().lower(),
        "evidence_event_ids": event_ids,
        "evidence_summary": evidence_summary or None,
        "total_events_analyzed": payload.get("total_events_analyzed"),
        "recommended_action": payload.get("recommended_action") or ACTION_BY_CATEGORY[category],
        "model_version": payload.get("model_version") or "log-analyzer-logistic-regression-v1",
        **({"created_at": payload["created_at"]} if payload.get("created_at") else {}),
    }
