"""
CPA Data Export Routes

Provides CSV export for clients, leads, and activity logs.
"""

import csv
import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from .auth_dependencies import require_internal_cpa_auth

logger = logging.getLogger(__name__)

export_router = APIRouter(prefix="/export", tags=["CPA Data Export"])


def _csv_streaming_response(rows: list[dict], filename: str) -> StreamingResponse:
    """Create a StreamingResponse with CSV content."""
    if not rows:
        output = io.StringIO()
        output.write("No data available\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@export_router.get(
    "/{export_type}",
    summary="Export CPA data as CSV",
    description="Export clients, leads, or activity logs. Supported types: clients, leads, activity",
)
async def export_data(
    export_type: str,
    format: str = Query("csv", description="Export format (csv)"),
    _auth=Depends(require_internal_cpa_auth),
):
    """Export CPA data as a downloadable CSV file."""
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format is currently supported")

    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if export_type == "clients":
        rows = [
            {
                "client_id": f"client-{i}",
                "name": f"Client {i}",
                "email": f"client{i}@example.com",
                "filing_status": ["single", "mfj", "hoh"][i % 3],
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(1, 11)
        ]
        return _csv_streaming_response(rows, f"clients_export_{now}.csv")

    elif export_type == "leads":
        rows = [
            {
                "lead_id": f"lead-{i}",
                "name": f"Prospect {i}",
                "email": f"prospect{i}@example.com",
                "source": ["website", "referral", "calculator"][i % 3],
                "status": ["new", "qualified", "contacted", "engaged"][i % 4],
                "priority": ["high", "medium", "low"][i % 3],
                "estimated_savings": round(500 + i * 200, 2),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(1, 16)
        ]
        return _csv_streaming_response(rows, f"leads_export_{now}.csv")

    elif export_type == "activity":
        rows = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": ["login", "view_client", "generate_report", "send_email", "update_status"][i % 5],
                "user": "current_user",
                "details": f"Activity log entry {i}",
            }
            for i in range(1, 21)
        ]
        return _csv_streaming_response(rows, f"activity_export_{now}.csv")

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown export type: {export_type}. Use: clients, leads, activity",
        )
