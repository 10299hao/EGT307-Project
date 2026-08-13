"""Receives Portal alert requests and displays a native Windows dialog."""

import ctypes
from threading import Thread

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="LogSentinel Local Notification Receiver")


class IncidentNotification(BaseModel):
    """Small payload sent by the Portal when it stores a new incident."""

    source: str = "LogSentinel"
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=300)
    incident_id: str
    block_id: str
    severity: str
    category: str
    confidence: str
    recommended_action: str

@app.get("/health")
def health() -> dict:
    return {"status": "ready", "receiver": "windows-popup"}


def show_windows_popup(payload: IncidentNotification) -> None:
    details = "\n".join([
        payload.message,
        "",
        f"Incident: {payload.incident_id}",
        f"Block: {payload.block_id}",
        f"Recommended action: {payload.recommended_action}",
        "",
        "Open http://localhost:8000 to review the incident.",
    ])
    # MB_OK | MB_ICONWARNING | MB_TOPMOST keeps the classroom demo visible.
    ctypes.windll.user32.MessageBoxW(
        None,
        details,
        payload.title,
        0x00000000 | 0x00000030 | 0x00040000,
    )


@app.post("/notify")
def notify(payload: IncidentNotification) -> dict:
    # Run the modal dialog on another thread so the HTTP response returns
    # immediately; otherwise the Portal would retry while waiting for a click.
    Thread(target=show_windows_popup, args=(payload,), daemon=True).start()
    print(f"Windows popup displayed for {payload.incident_id}", flush=True)
    return {"delivered": True, "incident_id": payload.incident_id}
